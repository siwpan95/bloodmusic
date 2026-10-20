"""
命令模式系统 (Command Pattern)
基于 txt.txt 架构要求: 2.2 命令模式分离 UI 和引擎

所有用户操作封装为命令对象，通过线程安全队列发给引擎线程。
GUI 线程只负责创建命令并提交，音频线程在回调前取出命令并安全执行。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np
import queue
import threading
import time


# ============================================================
#  AudioEngine 接口协议
# ============================================================
@runtime_checkable
class AudioEngineProtocol(Protocol):
    """音频引擎接口协议。任何实现了此接口的对象都可作为 Command 的 engine 参数。"""

    session: Any

    def add_track(self, track_id: str, name: str, track_type: str) -> bool: ...
    def remove_track(self, track_id: str) -> bool: ...
    def get_track(self, track_id: str) -> Optional[Any]: ...
    def restore_track(self, saved_state: dict) -> bool: ...
    def create_effect_node(self, effect_type: str, effect_id: str) -> Optional[Any]: ...
    def set_playhead(self, position: float) -> None: ...


# ============================================================
#  Command 基类
# ============================================================
class Command(ABC):
    """命令基类。

    设计要点:
      - execute(engine) 由音频引擎线程调用
      - 命令对象是不可变的，创建后不能修改
      - 支持 undo (可选)
    """

    def __init__(self, command_id: str = ""):
        self.command_id = command_id or f"cmd_{id(self):x}"
        self.timestamp = time.time()

    @abstractmethod
    def execute(self, engine: AudioEngineProtocol) -> bool:
        raise NotImplementedError

    def undo(self, engine: AudioEngineProtocol) -> bool:
        return False

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.command_id}>"


# ============================================================
#  CommandBus - 线程安全命令队列
# ============================================================
class CommandBus:
    """命令总线: GUI 线程和音频引擎线程的线程安全桥梁。

    - 使用 queue.Queue 实现线程安全
    - 音频引擎在 process_block() 前调用 drain_pending() 取出所有待处理命令
    """

    def __init__(self, maxsize: int = 1024):
        self._queue: queue.Queue[Command] = queue.Queue(maxsize=maxsize)
        self._pending_undos: List[Command] = []
        self._lock = threading.Lock()

    def post(self, command: Command) -> bool:
        try:
            self._queue.put_nowait(command)
            return True
        except queue.Full:
            print(f"[CommandBus] 队列已满，丢弃命令 {command}")
            return False

    def drain_pending(self) -> List[Command]:
        commands = []
        while True:
            try:
                commands.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return commands

    def execute_pending(self, engine: AudioEngineProtocol) -> int:
        commands = self.drain_pending()
        success_count = 0
        for cmd in commands:
            try:
                ok = cmd.execute(engine)
                if ok:
                    success_count += 1
                    with self._lock:
                        self._pending_undos.append(cmd)
                else:
                    print(f"[CommandBus] 命令执行失败: {cmd}")
            except Exception as e:
                print(f"[CommandBus] 命令执行异常: {cmd} -> {e}")
        return success_count

    def undo_last(self, engine: AudioEngineProtocol) -> bool:
        with self._lock:
            if not self._pending_undos:
                return False
            cmd = self._pending_undos.pop()
            return cmd.undo(engine)

    def clear(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._pending_undos.clear()


# ============================================================
#  LockFreeCommandQueue
# ============================================================
class LockFreeCommandQueue:
    """低延迟命令队列 (deque + Lock)。"""

    def __init__(self, maxlen: int = 1024):
        self._deque: deque[Command] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def post(self, command: Command) -> bool:
        with self._lock:
            if len(self._deque) >= self._deque.maxlen:
                return False
            self._deque.append(command)
            return True

    def drain_all(self) -> List[Command]:
        with self._lock:
            result = list(self._deque)
            self._deque.clear()
            return result


# ============================================================
#  具体命令实现 (15 个)
# ============================================================

# ---- 轨道命令 ----

class AddTrackCommand(Command):
    def __init__(self, track_id: str, name: str = "", track_type: str = "audio"):
        super().__init__()
        self.track_id = track_id
        self.name = name or track_id
        self.track_type = track_type

    def execute(self, engine: AudioEngineProtocol) -> bool:
        return engine.add_track(self.track_id, self.name, self.track_type)

    def undo(self, engine: AudioEngineProtocol) -> bool:
        return engine.remove_track(self.track_id)


class RemoveTrackCommand(Command):
    def __init__(self, track_id: str):
        super().__init__()
        self.track_id = track_id
        self._saved_state: Optional[Dict] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track:
            self._saved_state = track.to_dict() if hasattr(track, "to_dict") else None
        return engine.remove_track(self.track_id)

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._saved_state:
            return engine.restore_track(self._saved_state)
        return False


class SetTrackVolumeCommand(Command):
    def __init__(self, track_id: str, new_volume: float):
        super().__init__()
        self.track_id = track_id
        self.new_volume = new_volume
        self._old_volume: Optional[float] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        self._old_volume = track.volume
        track.volume = self.new_volume
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_volume is not None:
            track = engine.get_track(self.track_id)
            if track:
                track.volume = self._old_volume
                return True
        return False


class SetTrackPanCommand(Command):
    def __init__(self, track_id: str, new_pan: float):
        super().__init__()
        self.track_id = track_id
        self.new_pan = float(np.clip(new_pan, -1.0, 1.0))
        self._old_pan: Optional[float] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        self._old_pan = track.pan
        track.pan = self.new_pan
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_pan is not None:
            track = engine.get_track(self.track_id)
            if track:
                track.pan = self._old_pan
                return True
        return False


class SoloTrackCommand(Command):
    def __init__(self, track_id: str, solo: bool = True):
        super().__init__()
        self.track_id = track_id
        self.solo = solo
        self._old_solo: Optional[bool] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        self._old_solo = track.solo
        track.solo = self.solo
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_solo is not None:
            track = engine.get_track(self.track_id)
            if track:
                track.solo = self._old_solo
                return True
        return False


class MuteTrackCommand(Command):
    def __init__(self, track_id: str, mute: bool = True):
        super().__init__()
        self.track_id = track_id
        self.mute = mute
        self._old_mute: Optional[bool] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        self._old_mute = track.mute
        track.mute = self.mute
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_mute is not None:
            track = engine.get_track(self.track_id)
            if track:
                track.mute = self._old_mute
                return True
        return False


# ---- Clip 命令（已移除：依赖 station domain.AudioClip，bloodmusic 无对应模型）----

# ---- 效果器命令 ----

class AddEffectCommand(Command):
    def __init__(self, track_id: str, effect_id: str, effect_type: str, position: int = -1):
        super().__init__()
        self.track_id = track_id
        self.effect_id = effect_id
        self.effect_type = effect_type
        self.position = position

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        effect_node = engine.create_effect_node(self.effect_type, self.effect_id)
        if effect_node is None:
            return False
        track.add_effect(effect_node, self.position)
        return True


class RemoveEffectCommand(Command):
    def __init__(self, track_id: str, effect_id: str):
        super().__init__()
        self.track_id = track_id
        self.effect_id = effect_id

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        return track.remove_effect(self.effect_id) is not None


class SetEffectParameterCommand(Command):
    def __init__(self, track_id: str, effect_id: str, param_name: str, param_value: Any):
        super().__init__()
        self.track_id = track_id
        self.effect_id = effect_id
        self.param_name = param_name
        self.param_value = param_value
        self._old_value: Optional[Any] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        track = engine.get_track(self.track_id)
        if track is None:
            return False
        effect = track.get_effect(self.effect_id)
        if effect is None:
            return False
        self._old_value = getattr(effect, self.param_name, None)
        setattr(effect, self.param_name, self.param_value)
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_value is not None:
            track = engine.get_track(self.track_id)
            if track:
                effect = track.get_effect(self.effect_id)
                if effect:
                    setattr(effect, self.param_name, self._old_value)
                    return True
        return False


# ---- 播放控制命令 ----

class SetPlayheadCommand(Command):
    def __init__(self, position: float):
        super().__init__()
        self.position = position

    def execute(self, engine: AudioEngineProtocol) -> bool:
        engine.set_playhead(self.position)
        return True


class SetTempoCommand(Command):
    def __init__(self, bpm: float):
        super().__init__()
        self.bpm = bpm
        self._old_bpm: Optional[float] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        self._old_bpm = engine.session.tempo_map.current_bpm()
        engine.session.tempo_map.set_bpm(self.bpm)
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_bpm is not None:
            engine.session.tempo_map.set_bpm(self._old_bpm)
            return True
        return False


class SetLoopRegionCommand(Command):
    def __init__(self, start: float, end: float):
        super().__init__()
        self.start = start
        self.end = end
        self._old_region: Optional[tuple] = None

    def execute(self, engine: AudioEngineProtocol) -> bool:
        self._old_region = engine.session.loop_region
        engine.session.loop_region = (self.start, self.end)
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        if self._old_region:
            engine.session.loop_region = self._old_region
            return True
        return False


# ---- 事务命令 ----

class CompoundCommand(Command):
    """组合命令: 多个命令打包为原子操作。"""

    def __init__(self, commands: List[Command], name: str = "Compound"):
        super().__init__()
        self.commands = commands
        self.name = name
        self._executed: List[Command] = []

    def execute(self, engine: AudioEngineProtocol) -> bool:
        self._executed.clear()
        for cmd in self.commands:
            ok = cmd.execute(engine)
            if not ok:
                for executed_cmd in reversed(self._executed):
                    executed_cmd.undo(engine)
                self._executed.clear()
                return False
            self._executed.append(cmd)
        return True

    def undo(self, engine: AudioEngineProtocol) -> bool:
        success = True
        for cmd in reversed(self._executed):
            if not cmd.undo(engine):
                success = False
        self._executed.clear()
        return success

    def __repr__(self):
        return f"<CompoundCommand '{self.name}' ({len(self.commands)} cmds)>"


# ============================================================
#  CommandDispatcher
# ============================================================
class CommandDispatcher:
    """命令分发器: 支持接收、执行、宏录制/回放。"""

    def __init__(self, command_bus: CommandBus):
        self._bus = command_bus
        self._macros: Dict[str, List[Command]] = {}
        self._recording: Optional[str] = None
        self._recorded_cmds: List[Command] = []

    def post(self, command: Command) -> bool:
        if self._recording:
            self._recorded_cmds.append(command)
        return self._bus.post(command)

    def post_and_wait(self, command: Command, timeout: float = 1.0) -> bool:
        """提交命令并等待被取出 (简化实现，返回提交状态)"""
        return self._bus.post(command)

    def start_macro(self, macro_name: str):
        self._recording = macro_name
        self._recorded_cmds = []

    def stop_macro(self):
        if self._recording:
            self._macros[self._recording] = self._recorded_cmds.copy()
            self._recording = None
            self._recorded_cmds.clear()

    def play_macro(self, macro_name: str) -> int:
        if macro_name not in self._macros:
            return 0
        count = 0
        for cmd in self._macros[macro_name]:
            if self._bus.post(cmd):
                count += 1
        return count
