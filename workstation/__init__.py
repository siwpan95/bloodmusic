"""音频工作站引擎层（移植自 station/audio_studio/core）。

本包收录 station 中 bloodmusic 此前缺失的四件套，使其可作为独立、低耦合的
音频引擎基础设施复用：

- ``nodes``     : 音频节点图（Kahn 拓扑排序 / DFS 无环检测 / 多通道总线）
- ``commands``  : 命令模式系统（线程安全 CommandBus / undo / 宏录制回放）
- ``ring_buffer``: 无锁 SPSC 环形缓冲（实时音频流传输）
- ``dsp_utils`` : 纯函数 DSP 工具（混音 / 增益 / 声像 / 波形生成）

来源：gitee.com/siwpan/station，MIT，siwpan。
整合进 bloodmusic（2026-10-20）时，移除了对 station domain 的 Clip 命令、
GUI/MVVM 与 VST 桥桩（bloodmusic 已有对应或更强的实现），仅保留引擎层。
"""

from .nodes import (
    AudioPort,
    AudioNode,
    AudioConnection,
    AudioGraph,
    SourceNode,
    VolumeNode,
    BusNode,
    SummingNode,
    LimiterNode,
    EffectNodeWrapper,
    BUILTIN_NODE_TYPES,
)
from .commands import (
    AudioEngineProtocol,
    Command,
    CommandBus,
    LockFreeCommandQueue,
    AddTrackCommand,
    RemoveTrackCommand,
    SetTrackVolumeCommand,
    SetTrackPanCommand,
    SoloTrackCommand,
    MuteTrackCommand,
    AddEffectCommand,
    RemoveEffectCommand,
    SetEffectParameterCommand,
    SetPlayheadCommand,
    SetTempoCommand,
    SetLoopRegionCommand,
    CompoundCommand,
    CommandDispatcher,
)
from .ring_buffer import RingBuffer, RingBufferPool
from .dsp_utils import (
    mix_buffers,
    apply_gain_ramp,
    db_to_linear,
    linear_to_db,
    pan_law,
    resample_mono,
    sine_wave,
    saw_wave,
    square_wave,
    triangle_wave,
    normalize,
)

__all__ = [
    "AudioPort",
    "AudioNode",
    "AudioConnection",
    "AudioGraph",
    "SourceNode",
    "VolumeNode",
    "BusNode",
    "SummingNode",
    "LimiterNode",
    "EffectNodeWrapper",
    "BUILTIN_NODE_TYPES",
    "AudioEngineProtocol",
    "Command",
    "CommandBus",
    "LockFreeCommandQueue",
    "AddTrackCommand",
    "RemoveTrackCommand",
    "SetTrackVolumeCommand",
    "SetTrackPanCommand",
    "SoloTrackCommand",
    "MuteTrackCommand",
    "AddEffectCommand",
    "RemoveEffectCommand",
    "SetEffectParameterCommand",
    "SetPlayheadCommand",
    "SetTempoCommand",
    "SetLoopRegionCommand",
    "CompoundCommand",
    "CommandDispatcher",
    "RingBuffer",
    "RingBufferPool",
    "mix_buffers",
    "apply_gain_ramp",
    "db_to_linear",
    "linear_to_db",
    "pan_law",
    "resample_mono",
    "sine_wave",
    "saw_wave",
    "square_wave",
    "triangle_wave",
    "normalize",
]
