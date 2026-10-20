"""
音频节点图系统 (Audio Node Graph)
基于 txt.txt 架构要求: 2.1 音频处理图

AudioNode 基类 + AudioGraph 拓扑排序/无环检查/多通道总线
"""

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np


# ============================================================
#  端口定义
# ============================================================
@dataclass
class AudioPort:
    """音频端口定义"""
    node_id: str
    port_name: str
    is_input: bool
    channel_count: int = 1

    def full_name(self) -> str:
        return f"{self.node_id}:{self.port_name}"

    def __hash__(self):
        return hash(self.full_name())

    def __eq__(self, other):
        return isinstance(other, AudioPort) and self.full_name() == other.full_name()


# ============================================================
#  AudioNode 基类
# ============================================================
class AudioNode(ABC):
    """音频节点基类。

    process(inputs, outputs, nframes):
      inputs:  List[np.ndarray]  每个输入端口的缓冲区
      outputs: List[np.ndarray]  每个输出端口的缓冲区 (预分配)
      nframes: 当前块采样帧数
    """

    def __init__(self, node_id: str, name: str = ""):
        self.node_id = node_id
        self.name = name or node_id
        self.input_ports: List[AudioPort] = []
        self.output_ports: List[AudioPort] = []
        self.enabled: bool = True
        self._sr: int = 44100

    def add_input_port(self, port_name: str, channel_count: int = 1) -> "AudioNode":
        self.input_ports.append(
            AudioPort(self.node_id, port_name, is_input=True, channel_count=channel_count)
        )
        return self

    def add_output_port(self, port_name: str, channel_count: int = 1) -> "AudioNode":
        self.output_ports.append(
            AudioPort(self.node_id, port_name, is_input=False, channel_count=channel_count)
        )
        return self

    def get_input_port(self, idx: int = 0) -> Optional[AudioPort]:
        return self.input_ports[idx] if idx < len(self.input_ports) else None

    def get_output_port(self, idx: int = 0) -> Optional[AudioPort]:
        return self.output_ports[idx] if idx < len(self.output_ports) else None

    def set_samplerate(self, sr: int):
        self._sr = sr

    @abstractmethod
    def process(self, inputs: List[np.ndarray], outputs: List[np.ndarray], nframes: int):
        raise NotImplementedError

    def reset(self):
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} id='{self.node_id}' name='{self.name}'>"


# ============================================================
#  Connection 连接定义
# ============================================================
@dataclass
class AudioConnection:
    """节点间音频连接"""
    src_node: AudioNode
    src_port_name: str
    dst_node: AudioNode
    dst_port_name: str

    def __hash__(self):
        return hash((self.src_node.node_id, self.src_port_name,
                     self.dst_node.node_id, self.dst_port_name))

    def __eq__(self, other):
        return isinstance(other, AudioConnection) and (
            self.src_node.node_id == other.src_node.node_id and
            self.src_port_name == other.src_port_name and
            self.dst_node.node_id == other.dst_node.node_id and
            self.dst_port_name == other.dst_port_name
        )


# ============================================================
#  AudioGraph 音频处理图
# ============================================================
class AudioGraph:
    """音频处理图：节点管理、连接、拓扑排序、无环检查、多通道总线。

    关键特性 (来自 txt.txt):
      - 图的拓扑排序 (Kahn 算法)
      - 无环检查 (DFS, DAG)
      - 多通道总线支持
      - process_block() 按拓扑序依次处理
    """

    def __init__(self, samplerate: int = 44100):
        self.sr = samplerate
        self.nodes: Dict[str, AudioNode] = {}
        self.connections: List[AudioConnection] = []
        self._topo_order: Optional[List[str]] = None
        self._topo_dirty: bool = True
        self._port_data: Dict[str, np.ndarray] = {}  # 端口数据缓存

    # ---- 节点管理 ----
    def add_node(self, node: AudioNode) -> "AudioGraph":
        if node.node_id in self.nodes:
            raise ValueError(f"节点 ID '{node.node_id}' 已存在!")
        node.set_samplerate(self.sr)
        self.nodes[node.node_id] = node
        self._mark_dirty()
        return self

    def remove_node(self, node_id: str) -> "AudioGraph":
        if node_id in self.nodes:
            del self.nodes[node_id]
            self.connections = [
                c for c in self.connections
                if c.src_node.node_id != node_id and c.dst_node.node_id != node_id
            ]
            self._mark_dirty()
        return self

    def get_node(self, node_id: str) -> Optional[AudioNode]:
        return self.nodes.get(node_id)

    # ---- 连接管理 ----
    def connect(self, src_node_id: str, src_port_name: str,
                dst_node_id: str, dst_port_name: str) -> "AudioGraph":
        src = self.nodes.get(src_node_id)
        dst = self.nodes.get(dst_node_id)
        if src is None:
            raise ValueError(f"源节点 '{src_node_id}' 不存在!")
        if dst is None:
            raise ValueError(f"目标节点 '{dst_node_id}' 不存在!")
        src_port = next((p for p in src.output_ports if p.port_name == src_port_name), None)
        dst_port = next((p for p in dst.input_ports if p.port_name == dst_port_name), None)
        if src_port is None:
            raise ValueError(f"源节点 '{src_node_id}' 无输出端口 '{src_port_name}'")
        if dst_port is None:
            raise ValueError(f"目标节点 '{dst_node_id}' 无输入端口 '{dst_port_name}'")

        conn = AudioConnection(src, src_port_name, dst, dst_port_name)
        if conn not in self.connections:
            self.connections.append(conn)
            self._mark_dirty()
        return self

    def disconnect(self, src_node_id: str, src_port_name: str,
                   dst_node_id: str, dst_port_name: str) -> "AudioGraph":
        self.connections = [
            c for c in self.connections
            if not (c.src_node.node_id == src_node_id and c.src_port_name == src_port_name
                    and c.dst_node.node_id == dst_node_id and c.dst_port_name == dst_port_name)
        ]
        self._mark_dirty()
        return self

    def _mark_dirty(self):
        self._topo_dirty = True
        self._topo_order = None

    # ---- 无环检查 (Cycle Detection) ----
    def check_acyclic(self) -> Tuple[bool, List[str]]:
        """检查图是否为 DAG。返回 (is_dag, cycle_nodes)"""
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for conn in self.connections:
            adj[conn.src_node.node_id].append(conn.dst_node.node_id)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {nid: WHITE for nid in self.nodes}
        path: List[str] = []

        def dfs(node_id: str) -> Tuple[bool, List[str]]:
            color[node_id] = GRAY
            path.append(node_id)
            for nxt in adj.get(node_id, []):
                if color[nxt] == GRAY:
                    cycle_start = path.index(nxt)
                    path.pop()
                    return False, path[cycle_start:]
                if color[nxt] == WHITE:
                    ok, cycle = dfs(nxt)
                    if not ok:
                        path.pop() if path and path[-1] == node_id else None
                        return False, cycle
            path.pop()
            color[node_id] = BLACK
            return True, []

        for nid in self.nodes:
            if color[nid] == WHITE:
                ok, cycle = dfs(nid)
                if not ok:
                    return False, cycle
        return True, []

    # ---- 拓扑排序 ----
    def _rebuild_topo_order(self) -> List[str]:
        """Kahn 算法拓扑排序"""
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in self.nodes}

        for conn in self.connections:
            src_id = conn.src_node.node_id
            dst_id = conn.dst_node.node_id
            adj[src_id].append(dst_id)
            in_degree[dst_id] = in_degree.get(dst_id, 0) + 1

        queue = deque([nid for nid in self.nodes if in_degree[nid] == 0])
        order = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for nxt in adj[nid]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        return order

    def get_processing_order(self) -> List[str]:
        if self._topo_dirty or self._topo_order is None:
            is_dag, cycle = self.check_acyclic()
            if not is_dag:
                raise RuntimeError(
                    f"音频处理图存在环路! 涉及节点: {cycle}\n请移除环路后再处理。"
                )
            self._topo_order = self._rebuild_topo_order()
            self._topo_dirty = False
        return self._topo_order

    # ---- 多通道总线 ----
    def create_multichannel_bus(self, bus_id: str, num_channels: int = 2,
                                name: str = "") -> "BusNode":
        bus = BusNode(bus_id, num_channels, name or bus_id)
        self.add_node(bus)
        return bus

    # ---- 核心: process_block ----
    def process_block(self, nframes: int):
        """按拓扑序依次处理所有节点。"""
        order = self.get_processing_order()
        port_data: Dict[str, np.ndarray] = {}

        for nid in order:
            node = self.nodes[nid]
            if not node.enabled:
                for port in node.output_ports:
                    ch = port.channel_count
                    port_data[port.full_name()] = np.zeros(
                        nframes if ch == 1 else (nframes, ch), dtype=np.float32
                    )
                continue

            # 收集输入
            input_buffers: List[np.ndarray] = []
            for inp_port in node.input_ports:
                key = inp_port.full_name()
                src_data = None
                for conn in self.connections:
                    if (conn.dst_node.node_id == nid
                            and conn.dst_port_name == inp_port.port_name):
                        src_key = f"{conn.src_node.node_id}:{conn.src_port_name}"
                        src_data = port_data.get(src_key)
                        break
                if src_data is not None:
                    input_buffers.append(src_data)
                else:
                    ch = inp_port.channel_count
                    input_buffers.append(
                        np.zeros(nframes if ch == 1 else (nframes, ch), dtype=np.float32)
                    )

            # 准备输出
            output_buffers: List[np.ndarray] = []
            for out_port in node.output_ports:
                ch = out_port.channel_count
                output_buffers.append(
                    np.zeros(nframes if ch == 1 else (nframes, ch), dtype=np.float32)
                )

            # 处理
            node.process(input_buffers, output_buffers, nframes)

            # 存储输出
            for i, out_port in enumerate(node.output_ports):
                port_data[out_port.full_name()] = output_buffers[i]

        self._port_data = port_data

    def get_master_output(self, port_name: str = "output_0") -> Optional[np.ndarray]:
        """获取主输出节点的数据。"""
        for node_id, node in self.nodes.items():
            if node_id.startswith("master"):
                key = f"{node_id}:{port_name}"
                return self._port_data.get(key)
        # fallback: 查找最后一个节点的输出
        order = self.get_processing_order()
        if order:
            last = order[-1]
            for port in self.nodes[last].output_ports:
                key = f"{last}:{port.port_name}"
                if key in self._port_data:
                    return self._port_data[key]
        return None

    def print_graph(self):
        """打印图结构 (调试用)"""
        print(f"AudioGraph ({len(self.nodes)} nodes, {len(self.connections)} connections)")
        for nid, node in self.nodes.items():
            ins = ", ".join([p.port_name for p in node.input_ports]) or "(none)"
            outs = ", ".join([p.port_name for p in node.output_ports]) or "(none)"
            print(f"  [{nid}] {node.name}  IN: {ins}  OUT: {outs}")
        if self.connections:
            for conn in self.connections:
                print(f"  {conn.src_node.node_id}:{conn.src_port_name} "
                      f"-> {conn.dst_node.node_id}:{conn.dst_port_name}")


# ============================================================
#  内置节点类型
# ============================================================

class SourceNode(AudioNode):
    """音源节点：从内部缓冲区读取数据。"""

    def __init__(self, node_id: str, name: str = "Source"):
        super().__init__(node_id, name)
        self.add_output_port("output_0", channel_count=1)
        self._audio_data: Optional[np.ndarray] = None
        self._read_pos: int = 0

    def set_audio_data(self, data: np.ndarray):
        self._audio_data = data.astype(np.float32)
        self._read_pos = 0

    def process(self, inputs, outputs, nframes):
        out = outputs[0]
        if self._audio_data is not None and self._read_pos < len(self._audio_data):
            available = min(nframes, len(self._audio_data) - self._read_pos)
            out[:available] = self._audio_data[self._read_pos:self._read_pos + available]
            if available < nframes:
                out[available:] = 0.0
            self._read_pos += available
        else:
            out[:] = 0.0


class VolumeNode(AudioNode):
    """音量节点：矢量化平滑增益。"""

    def __init__(self, node_id: str, name: str = "Volume"):
        super().__init__(node_id, name)
        self.add_input_port("input_0", channel_count=1)
        self.add_output_port("output_0", channel_count=1)
        self.volume: float = 1.0
        self._current: float = 1.0

    def process(self, inputs, outputs, nframes):
        inp = inputs[0]
        out = outputs[0]
        if abs(self.volume - self._current) > 0.001:
            ramp = np.linspace(self._current, self.volume, nframes, dtype=np.float32)
            out[:] = inp * ramp
            self._current = self.volume
        else:
            out[:] = inp * self.volume

    def set_volume(self, vol: float):
        self.volume = float(np.clip(vol, 0.0, 2.0))


class BusNode(AudioNode):
    """多通道总线节点。"""

    def __init__(self, node_id: str, num_channels: int = 2, name: str = "Bus"):
        super().__init__(node_id, name)
        self.num_channels = num_channels
        self.add_input_port("input_0", channel_count=num_channels)
        self.add_output_port("output_0", channel_count=num_channels)
        self.gain: float = 1.0

    def process(self, inputs, outputs, nframes):
        inp = inputs[0]
        out = outputs[0]
        if inp.ndim == 1:
            out[:] = inp * self.gain
        else:
            out[:, :] = inp * self.gain


class SummingNode(AudioNode):
    """混音节点：多输入相加。"""

    def __init__(self, node_id: str = "master_sum", name: str = "Summing"):
        super().__init__(node_id, name)
        self.add_output_port("output_0", channel_count=2)
        self._num_inputs: int = 0

    def add_input(self, port_name: str = None) -> str:
        idx = self._num_inputs
        port_name = port_name or f"input_{idx}"
        self.add_input_port(port_name, channel_count=2)
        self._num_inputs += 1
        return port_name

    def process(self, inputs, outputs, nframes):
        out = outputs[0]
        out[:, :] = 0.0
        for inp in inputs:
            if inp.ndim == 1:
                out[:, 0] += inp * 0.5
                out[:, 1] += inp * 0.5
            else:
                out[:, :] += inp


class LimiterNode(AudioNode):
    """软限幅器：矢量化处理。"""

    def __init__(self, node_id: str = "limiter", name: str = "Limiter"):
        super().__init__(node_id, name)
        self.add_input_port("input_0", channel_count=2)
        self.add_output_port("output_0", channel_count=2)
        self.threshold: float = 0.98
        self._last_gain: float = 1.0

    def process(self, inputs, outputs, nframes):
        inp = inputs[0]
        out = outputs[0]
        if inp.ndim == 1:
            peak = np.abs(inp) + 1e-8
            gain = np.minimum(1.0, self.threshold / peak)
            # 平滑
            smoothed = np.full(nframes, self._last_gain, dtype=np.float32)
            smoothed = smoothed * 0.9 + gain * 0.1
            out[:] = inp * smoothed
            self._last_gain = float(smoothed[-1])
        else:
            peak = np.max(np.abs(inp), axis=1) + 1e-8
            gain = np.minimum(1.0, self.threshold / peak)
            smoothed = np.full(nframes, self._last_gain, dtype=np.float32)
            smoothed = smoothed * 0.9 + gain * 0.1
            out[:, :] = inp * smoothed[:, np.newaxis]
            self._last_gain = float(smoothed[-1])


class EffectNodeWrapper(AudioNode):
    """效果器包装节点：将函数包装为 AudioNode。"""

    def __init__(self, node_id: str, effect_fn: Callable, name: str = "Effect"):
        super().__init__(node_id, name)
        self.add_input_port("input_0", channel_count=1)
        self.add_output_port("output_0", channel_count=1)
        self.effect_fn = effect_fn
        self.params: Dict[str, Any] = {}

    def process(self, inputs, outputs, nframes):
        inp = inputs[0]
        out = outputs[0]
        try:
            result = self.effect_fn(inp, **self.params)
            out[:] = result[:nframes]
        except Exception as e:
            print(f"[EffectNodeWrapper] error: {e}")
            out[:] = inp


# ============================================================
#  可用节点类型注册表
# ============================================================
BUILTIN_NODE_TYPES: Dict[str, type] = {
    "SourceNode": SourceNode,
    "VolumeNode": VolumeNode,
    "BusNode": BusNode,
    "SummingNode": SummingNode,
    "LimiterNode": LimiterNode,
    "EffectNodeWrapper": EffectNodeWrapper,
}
