"""workstation 子包验收测试 —— 移植自 station/audio_studio/core 的引擎层四件套。

覆盖:
  - nodes      : 节点图拓扑排序 / 无环检测 / process_block 实际产出
  - ring_buffer: SPSC 读写往返 / 可读可写计数 / 溢出计数
  - commands   : 线程安全 CommandBus + 具体命令 execute/undo
  - dsp_utils  : 纯函数 DSP 工具（增益换算 / 混音 / 波形生成）

运行::

    cd <仓库根>
    python -m pytest tests/test_workstation.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

from bloodmusic.workstation import (
    AudioGraph,
    SourceNode,
    VolumeNode,
    SummingNode,
    RingBuffer,
    CommandBus,
    LockFreeCommandQueue,
    AddTrackCommand,
    SetTrackVolumeCommand,
    CompoundCommand,
    mix_buffers,
    db_to_linear,
    linear_to_db,
    pan_law,
    sine_wave,
    normalize,
)
from bloodmusic.workstation import __all__ as _EXPORTS


# ----------------------------------------------------------------------------
# 1. 包导出完整性
# ----------------------------------------------------------------------------
def test_exports_nonempty():
    assert isinstance(_EXPORTS, list)
    assert len(_EXPORTS) >= 30
    # 关键符号必须全部对外可见
    for sym in ("AudioGraph", "CommandBus", "RingBuffer", "mix_buffers", "db_to_linear"):
        assert sym in _EXPORTS


# ----------------------------------------------------------------------------
# 2. nodes：拓扑排序 / 无环 / 实际处理
# ----------------------------------------------------------------------------
def _build_graph():
    g = AudioGraph(samplerate=44100)
    src = SourceNode("src")
    src.set_audio_data(np.full(64, 0.8, dtype=np.float32))
    vol = VolumeNode("vol")
    vol.set_volume(0.5)
    master = SummingNode("master")  # 输出端口 output_0（2 通道）
    # 把单声道源汇入 master 的两个输入通道
    master.add_input("in_src")
    g.add_node(src).add_node(vol).add_node(master)
    g.connect("src", "output_0", "vol", "input_0")
    g.connect("vol", "output_0", "master", "in_src")
    return g, src, vol, master


def test_topological_order_respects_edges():
    g, *_ = _build_graph()
    order = g.get_processing_order()
    assert order.index("src") < order.index("vol") < order.index("master")


def test_cycle_detection_raises():
    g = AudioGraph()
    # 必须用带输入/输出端口的节点（SourceNode 仅输出）
    a = VolumeNode("a")
    b = VolumeNode("b")
    g.add_node(a).add_node(b)
    g.connect("a", "output_0", "b", "input_0")
    g.connect("b", "output_0", "a", "input_0")
    is_dag, cycle = g.check_acyclic()
    assert is_dag is False
    assert len(cycle) >= 1  # 检测到环（含至少一个节点）
    with pytest.raises(RuntimeError):
        g.get_processing_order()


def test_process_block_produces_output():
    g, src, vol, master = _build_graph()
    g.process_block(64)
    out = g.get_master_output("output_0")
    assert out is not None
    assert out.shape == (64, 2)
    # VolumeNode 在块内做 1.0 -> 0.5 的平滑渐变（ramap）：
    #   i=0  : 增益 1.0 => 源 0.8 * 1.0 = 0.8 => 汇入双声道各 0.5 => 0.4
    #   i=63 : 增益 0.5 => 源 0.8 * 0.5 = 0.4 => 0.2
    assert abs(float(out[0, 0]) - 0.4) < 1e-4
    assert abs(float(out[-1, 0]) - 0.2) < 1e-4
    # 双声道一致（单声道源广播）
    assert abs(float(out[0, 1]) - float(out[0, 0])) < 1e-6


# ----------------------------------------------------------------------------
# 3. ring_buffer：SPSC 读写往返
# ----------------------------------------------------------------------------
def test_ring_buffer_roundtrip():
    rb = RingBuffer(capacity=1024, channels=2)
    assert rb.capacity >= 1024
    assert rb.channels == 2
    assert rb.is_empty

    written = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
    n = rb.write(written, 4)
    assert n == 4
    assert rb.readable == 4
    assert not rb.is_empty

    out = [[0.0] * 4, [0.0] * 4]
    m = rb.read(out, 4)
    assert m == 4
    # 环形缓冲内部用 float32 存储，转回 list 有精度损失，用 allclose
    assert np.allclose(out[0], [0.1, 0.2, 0.3, 0.4])
    assert np.allclose(out[1], [0.5, 0.6, 0.7, 0.8])
    assert rb.is_empty


def test_ring_buffer_overrun_underrun_counters():
    rb = RingBuffer(capacity=8, channels=1)
    # 写满 8 个（capacity 会向上对齐到 2 的幂 => 至少 8）
    big = [[1.0] * rb.capacity]
    rb.write(big, rb.capacity)
    assert rb.is_full
    # 再写 => 溢出计数 +1
    rb.write([[9.0] * 4], 4)
    assert rb.overrun_count == 1
    # 读空 => 下溢
    out = [[0.0] * rb.capacity]
    rb.read(out, rb.capacity)
    assert rb.is_empty
    rb.read([[0.0] * 4], 4)
    assert rb.underrun_count == 1


# ----------------------------------------------------------------------------
# 4. commands：CommandBus + 具体命令
# ----------------------------------------------------------------------------
class _FakeTrack:
    def __init__(self):
        self.volume = 1.0
        self.pan = 0.0
        self.solo = False
        self.mute = False
        self._effects = {}

    def add_effect(self, node, pos=-1):
        self._effects[id(node)] = node

    def remove_effect(self, effect_id):
        return self._effects.pop(effect_id, None)

    def get_effect(self, effect_id):
        return self._effects.get(effect_id)


class _FakeEngine:
    def __init__(self):
        self.tracks = {}
        self.playhead = 0.0

    def add_track(self, track_id, name, track_type):
        self.tracks[track_id] = _FakeTrack()
        return True

    def remove_track(self, track_id):
        return self.tracks.pop(track_id, None) is not None

    def get_track(self, track_id):
        return self.tracks.get(track_id)

    def restore_track(self, saved_state):
        return True

    def create_effect_node(self, effect_type, effect_id):
        return object()

    def set_playhead(self, position):
        self.playhead = position


def test_command_bus_drain_pending():
    bus = CommandBus()
    eng = _FakeEngine()
    assert bus.post(AddTrackCommand("t1", "Track1"))
    assert bus.post(AddTrackCommand("t2", "Track2"))
    pending = bus.drain_pending()
    assert len(pending) == 2
    # 队列已清空
    assert bus.drain_pending() == []


def test_command_bus_execute_pending():
    bus = CommandBus()
    eng = _FakeEngine()
    assert bus.post(AddTrackCommand("t1", "Track1"))
    executed = bus.execute_pending(eng)
    assert executed == 1
    assert "t1" in eng.tracks


def test_command_undo_volume():
    bus = CommandBus()
    eng = _FakeEngine()
    eng.add_track("t1", "Track1", "audio")
    cmd = SetTrackVolumeCommand("t1", 0.3)
    bus.post(cmd)
    bus.execute_pending(eng)  # 记录 _old_volume = 1.0，写入 0.3
    assert eng.tracks["t1"].volume == 0.3
    assert bus.undo_last(eng) is True
    assert eng.tracks["t1"].volume == 1.0  # 回到旧值


def test_compound_command_rollback_on_failure():
    eng = _FakeEngine()
    ok = AddTrackCommand("t1", "Track1")
    fail = SetTrackVolumeCommand("nonexistent", 0.5)  # get_track 返回 None => 失败
    comp = CompoundCommand([ok, fail], name="atomic")
    assert comp.execute(eng) is False
    assert "t1" not in eng.tracks  # 已回滚


def test_lockfree_queue_basic():
    q = LockFreeCommandQueue(maxlen=4)
    assert q.post(AddTrackCommand("a"))
    assert q.post(AddTrackCommand("b"))
    drained = q.drain_all()
    assert len(drained) == 2
    assert q.drain_all() == []


# ----------------------------------------------------------------------------
# 5. dsp_utils：纯函数
# ----------------------------------------------------------------------------
def test_db_linear_roundtrip():
    assert abs(db_to_linear(0.0) - 1.0) < 1e-9
    assert abs(db_to_linear(6.0206) - 2.0) < 1e-3
    # 往返
    lin = db_to_linear(-6.0)
    assert abs(linear_to_db(lin) - (-6.0)) < 1e-9


def test_mix_buffers_sums_clamped():
    out = [[0.0] * 4, [0.0] * 4]
    buffers = [
        [[0.4, 0.4, 0.4, 0.4]],  # 单声道轨需广播到 2 通道时只填 ch0
        [[0.3, 0.3, 0.3, 0.3]],
    ]
    mix_buffers(buffers, out, 4)
    # ch0 = 0.4 + 0.3 = 0.7；ch1 无对应通道 => 0
    assert abs(out[0][0] - 0.7) < 1e-9
    assert out[1][0] == 0.0


def test_pan_law_center_equals_unity():
    left, right = pan_law(0.0, law=-3.0)
    assert abs(left - 1.0) < 1e-9
    assert abs(right - 1.0) < 1e-9


def test_sine_wave_and_normalize():
    sr = 44100
    w = sine_wave(440.0, sr, 0.01, amplitude=0.5)
    assert len(w) == int(sr * 0.01)
    # 归一化到 0.95 峰值
    buf = [[0.1, 0.2, 0.3, 0.4]]
    gain = normalize(buf, 4, target_peak=0.95)
    assert abs(max(buf[0]) - 0.95) < 1e-9
    assert abs(gain - (0.95 / 0.4)) < 1e-9
