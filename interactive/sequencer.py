"""
横向排序器 — 按游戏场景拼接音乐片段
=======================================

基于指导第 6.3 节：按照游戏进程横向编排音乐片段，
实现 A→B→C 段落的序列拼接和过渡。

核心概念:
- 片段 (Segment): 一段预定义的音频块，带循环属性和过渡标记
- 序列 (Sequence): 片段的有序列表
- 分支规则: 根据游戏参数选择下一个片段
- 过渡: 片段间的交叉淡化
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple
import numpy as np


class SegmentCategory(Enum):
    """片段类别"""
    INTRO = "intro"         # 开场
    LOOP_A = "loop_a"       # 循环A段
    LOOP_B = "loop_b"       # 循环B段
    BRIDGE = "bridge"       # 桥段
    CLIMAX = "climax"       # 高潮
    OUTRO = "outro"         # 尾奏
    STINGER = "stinger"     # 短标记音 (胜利/失败提示)


@dataclass
class MusicSegment:
    """单个音乐片段"""
    name: str
    category: SegmentCategory = SegmentCategory.LOOP_A

    # 音频数据 — 在引擎层渲染后填充
    audio: Optional[np.ndarray] = None

    # 片段时长 (秒)
    duration: float = 8.0

    # 循环属性
    loop: bool = True           # 是否循环
    loop_count: int = 0         # 循环次数 (0=无限)
    loop_start: float = 0.0     # 循环起始点 (秒)

    # 过渡标记
    exit_point: float = 7.0     # 可于此时间点后退出 (秒)
    entry_point: float = 0.0    # 下一段从此处切入 (秒)

    # 元数据
    bpm: int = 120
    key: str = "C minor"
    tags: List[str] = field(default_factory=list)

    # 渲染回调 — 延迟渲染
    _render_fn: Optional[Callable[[], np.ndarray]] = None

    def render(self) -> np.ndarray:
        """渲染/获取音频数据"""
        if self.audio is not None:
            return self.audio
        if self._render_fn is not None:
            self.audio = self._render_fn()
            return self.audio
        raise ValueError(f"Segment '{self.name}' has no audio data and no render function")


@dataclass
class BranchRule:
    """分支规则 — 根据游戏参数选择下一片段"""
    condition: Callable[[dict], bool]          # (game_state) -> bool
    target: str                                # 目标片段名
    priority: int = 0                          # 优先级 (越高越优先)
    cooldown: float = 0.0                      # 冷却时间 (秒), 0=无冷却


class HorizontalSequencer:
    """
    横向排序器

    用法:
        seq = HorizontalSequencer()
        seq.add_segment(MusicSegment(name="intro", ...))
        seq.add_segment(MusicSegment(name="combat_a", ...))
        seq.add_branch_rule(
            BranchRule(lambda gs: gs['enemy_count'] > 3, "combat_a")
        )

        # 每帧
        seq.update(game_state, dt)
        audio = seq.process_frame()
    """

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 512):
        self.sr = sample_rate
        self.buffer_size = buffer_size

        self._segments: Dict[str, MusicSegment] = {}
        self._branch_rules: Dict[str, List[BranchRule]] = {}
        self._sequence: List[str] = []       # 当前播放序列
        self._seq_index: int = 0
        self._playhead: int = 0             # 当前片段的采样位置

        # 运行时状态
        self._current_segment_name: Optional[str] = None
        self._is_transitioning: bool = False
        self._transition_buf: Optional[np.ndarray] = None
        self._transition_pos: int = 0
        self._transition_duration: int = 0   # 过渡采样数

        # 冷却追踪
        self._cooldowns: Dict[str, float] = {}

        # 回调
        self._on_segment_change: List[Callable] = []

    # ── 配置 ──

    def add_segment(self, segment: MusicSegment):
        """添加一个片段"""
        self._segments[segment.name] = segment

    def add_branch_rule(self, rule: BranchRule, from_segment: Optional[str] = None):
        """
        添加分支规则。
        from_segment=None 表示全局规则（适用于任意片段）。
        """
        key = from_segment or "__global__"
        self._branch_rules.setdefault(key, []).append(rule)
        self._branch_rules[key].sort(key=lambda r: -r.priority)

    def set_sequence(self, segment_names: List[str]):
        """设置固定播放序列"""
        self._sequence = segment_names
        self._seq_index = 0

    def on_segment_change(self, callback: Callable):
        """注册片段切换回调"""
        self._on_segment_change.append(callback)

    def start(self, segment_name: str):
        """立即开始播放指定片段"""
        self._current_segment_name = segment_name
        self._playhead = 0
        self._is_transitioning = False

    # ── 每帧更新 ──

    def update(self, game_state: dict, dt: float):
        """
        根据游戏状态选择下一片段。
        如果当前片段到达 exit_point 或自然结束，评估分支规则。
        """
        current = self._segments.get(self._current_segment_name or "")
        if current is None:
            return

        segment_pos_sec = self._playhead / self.sr

        # 更新冷却
        for rule_name in list(self._cooldowns.keys()):
            self._cooldowns[rule_name] -= dt
            if self._cooldowns[rule_name] <= 0:
                del self._cooldowns[rule_name]

        # 检查是否需要切换
        should_switch = (
            segment_pos_sec >= current.exit_point
            and (not current.loop or current.loop_count == 0)
        )

        if should_switch:
            next_seg = self._evaluate_branches(self._current_segment_name, game_state)
            if next_seg:
                self._start_transition(next_seg)
            elif current.loop:
                # 循环回退
                self._playhead = int(current.loop_start * self.sr)

        # 更新过渡
        if self._is_transitioning:
            self._transition_pos += int(dt * self.sr)
            if self._transition_pos >= self._transition_duration:
                self._finish_transition()

    def process_frame(self) -> np.ndarray:
        """
        处理一帧音频输出。
        正常播放时循环/前进当前片段。
        过渡期间进行交叉淡化。
        """
        current = self._segments.get(self._current_segment_name or "")
        if current is None:
            return np.zeros(self.buffer_size, dtype=np.float32)

        current.audio = current.render()
        sr = self.sr
        audio_len = len(current.audio)

        # 过渡期间：交叉淡化
        if self._is_transitioning and self._transition_buf is not None:
            t_buf = self._transition_buf
            t_len = len(t_buf)
            t_pos = self._transition_pos
            d_total = self._transition_duration

            # 从当前片段读取
            out_current = np.zeros(self.buffer_size, dtype=np.float32)
            for i in range(self.buffer_size):
                pos = (self._playhead + i) % audio_len if current.loop else min(self._playhead + i, audio_len - 1)
                out_current[i] = current.audio[pos]

            # 从过渡目标读取
            out_target = np.zeros(self.buffer_size, dtype=np.float32)
            t_start = max(0, t_pos)
            for i in range(self.buffer_size):
                target_pos = t_start + i
                if target_pos < t_len:
                    out_target[i] = t_buf[target_pos]

            # 交叉淡化权重
            fade_progress = np.clip(
                np.linspace(t_pos / d_total, (t_pos + self.buffer_size) / d_total, self.buffer_size),
                0, 1
            )
            result = out_current * (1 - fade_progress) + out_target * fade_progress

            self._playhead += self.buffer_size
            if current.loop:
                self._playhead %= audio_len

            return np.clip(result, -1.0, 1.0)

        # 正常播放
        result = np.zeros(self.buffer_size, dtype=np.float32)
        for i in range(self.buffer_size):
            if current.loop:
                idx = (self._playhead + i) % audio_len
            else:
                idx = min(self._playhead + i, audio_len - 1)
            result[i] = current.audio[idx]

        self._playhead += self.buffer_size
        if current.loop and audio_len > 0:
            self._playhead %= audio_len

        return np.clip(result, -1.0, 1.0)

    # ── 内部 ──

    def _evaluate_branches(self, from_segment: Optional[str], game_state: dict) -> Optional[str]:
        """评估分支规则，返回目标片段名"""
        rules = self._branch_rules.get(from_segment or "", []) + \
                self._branch_rules.get("__global__", [])
        rules.sort(key=lambda r: -r.priority)

        for rule in rules:
            if rule.cooldown > 0:
                if rule.target in self._cooldowns:
                    continue
            try:
                if rule.condition(game_state):
                    if rule.cooldown > 0:
                        self._cooldowns[rule.target] = rule.cooldown
                    return rule.target
            except Exception:
                continue
        return None

    def _start_transition(self, target_name: str):
        """开始过渡到目标片段"""
        target = self._segments.get(target_name)
        if target is None:
            return

        old_name = self._current_segment_name
        self._target_segment_name = target_name
        self._transition_buf = target.render()
        self._transition_pos = 0
        self._transition_duration = min(
            int(2.0 * self.sr),   # max 2 sec transition
            len(self._transition_buf),
        )
        self._is_transitioning = True

        for cb in self._on_segment_change:
            try:
                cb(old_name, target_name)
            except Exception:
                pass

    def _finish_transition(self):
        """完成过渡"""
        self._current_segment_name = self._target_segment_name
        self._playhead = 0
        self._is_transitioning = False
        self._transition_buf = None
        self._transition_pos = 0
        self._target_segment_name = None
