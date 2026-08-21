"""
音乐状态机 — 管理游戏音乐状态的转换和过渡
===========================================

基于指导第 6.4 节：实现探索→警戒→战斗→胜利等状态的平滑过渡。

核心概念:
- 每个状态对应一组音乐参数（调式、BPM、密度、情绪张力）
- 状态转换触发过渡动画（渐强/渐弱/交叉淡化）
- 支持自定义状态和转换规则
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple
import time


# ============================================================
# 状态定义
# ============================================================

class MusicState(Enum):
    """预置音乐状态"""
    EXPLORE = auto()       # 探索 — 低张力、环境感
    TENSION = auto()       # 紧张 — 警戒、预感危险
    COMBAT_LOW = auto()    # 低烈度战斗 — 小怪
    COMBAT_HIGH = auto()   # 高烈度战斗 — BOSS
    VICTORY = auto()       # 胜利 — 辉煌收尾
    DEFEAT = auto()        # 失败 — 低沉收尾
    TRANSITION = auto()    # 过渡 — 场景切换
    PAUSE = auto()         # 暂停 — 菜单/背包


@dataclass
class StateParams:
    """音乐状态参数"""
    bpm: int = 120                    # 速度 (BPM)
    tension: float = 0.0              # 张力 (0=完全放松, 1=极度紧张)
    density: int = 2                  # 层次密度 (同时播放的层数, 1-8)
    scale_type: str = "minor"         # 调式倾向
    root_note: str = "C"              # 根音
    dynamic_range: float = 6.0        # 动态范围 (dB)
    reverb_mix: float = 0.3           # 混响量
    filter_openness: float = 1.0      # 滤波器开放度 (0=暗, 1=亮)
    low_freq_content: float = 0.5     # 低频含量 (0-1)
    high_freq_content: float = 0.5    # 高频含量 (0-1)
    distortion_amount: float = 0.0    # 失真量
    pulse_weight: float = 0.5         # 脉冲感/节奏强调


# ============================================================
# 预置状态参数表
# ============================================================

DEFAULT_STATE_PARAMS: Dict[MusicState, StateParams] = {
    MusicState.EXPLORE: StateParams(
        bpm=80, tension=0.1, density=2, scale_type="minor",
        dynamic_range=4.0, reverb_mix=0.5, filter_openness=0.7,
        low_freq_content=0.3, high_freq_content=0.3,
        distortion_amount=0.0, pulse_weight=0.3,
    ),
    MusicState.TENSION: StateParams(
        bpm=95, tension=0.4, density=3, scale_type="minor",
        dynamic_range=5.0, reverb_mix=0.4, filter_openness=0.8,
        low_freq_content=0.4, high_freq_content=0.4,
        distortion_amount=0.05, pulse_weight=0.5,
    ),
    MusicState.COMBAT_LOW: StateParams(
        bpm=120, tension=0.6, density=4, scale_type="phrygian",
        dynamic_range=8.0, reverb_mix=0.25, filter_openness=0.9,
        low_freq_content=0.6, high_freq_content=0.5,
        distortion_amount=0.15, pulse_weight=0.7,
    ),
    MusicState.COMBAT_HIGH: StateParams(
        bpm=150, tension=0.9, density=6, scale_type="phrygian",
        dynamic_range=10.0, reverb_mix=0.15, filter_openness=1.0,
        low_freq_content=0.8, high_freq_content=0.7,
        distortion_amount=0.3, pulse_weight=0.9,
    ),
    MusicState.VICTORY: StateParams(
        bpm=100, tension=0.05, density=3, scale_type="major",
        dynamic_range=6.0, reverb_mix=0.45, filter_openness=1.0,
        low_freq_content=0.5, high_freq_content=0.6,
        distortion_amount=0.0, pulse_weight=0.6,
    ),
    MusicState.DEFEAT: StateParams(
        bpm=60, tension=0.8, density=2, scale_type="minor",
        dynamic_range=3.0, reverb_mix=0.5, filter_openness=0.4,
        low_freq_content=0.3, high_freq_content=0.2,
        distortion_amount=0.0, pulse_weight=0.2,
    ),
    MusicState.TRANSITION: StateParams(
        bpm=100, tension=0.3, density=2, scale_type="minor",
        dynamic_range=4.0, reverb_mix=0.6, filter_openness=0.5,
        low_freq_content=0.3, high_freq_content=0.4,
        distortion_amount=0.0, pulse_weight=0.4,
    ),
    MusicState.PAUSE: StateParams(
        bpm=80, tension=0.0, density=1, scale_type="major",
        dynamic_range=2.0, reverb_mix=0.7, filter_openness=0.3,
        low_freq_content=0.1, high_freq_content=0.15,
        distortion_amount=0.0, pulse_weight=0.1,
    ),
}


# ============================================================
# 过渡参数
# ============================================================

@dataclass
class TransitionParams:
    """状态过渡参数"""
    duration: float = 2.0             # 过渡时长 (秒)
    curve: str = "ease_in_out"        # 过渡曲线 (linear / ease_in / ease_out / ease_in_out)
    crossfade: bool = True            # 是否交叉淡化
    crossfade_duration: float = 0.5   # 交叉淡化持续时间 (秒)
    hold_previous: bool = False       # 过渡期间保持前状态


# ============================================================
# 状态机核心
# ============================================================

class MusicStateMachine:
    """
    游戏音乐状态机

    用例:
        sm = MusicStateMachine()
        sm.start(MusicState.EXPLORE)       # 初始状态
        sm.transition_to(MusicState.COMBAT_LOW)  # 敌人生成 → 战斗音乐
        current = sm.tick(dt)              # 每帧调用，返回当前参数

    特性:
        - 平滑参数插值过渡
        - 回调钩子 (on_enter / on_exit / on_update)
        - 过渡锁定 (transition 期间不响应新请求)
    """

    def __init__(self):
        # 状态参数表
        self._state_params: Dict[MusicState, StateParams] = dict(DEFAULT_STATE_PARAMS)

        # 当前状态
        self._current_state: Optional[MusicState] = None
        self._previous_state: Optional[MusicState] = None

        # 过渡控制
        self._transition: Optional[TransitionParams] = None
        self._transition_elapsed: float = 0.0
        self._is_transitioning: bool = False
        self._transition_target: Optional[MusicState] = None

        # 过渡锁 — 过渡期间是否锁定
        self._transition_lock: bool = False

        # 当前插值后的活跃参数
        self._active_params: Optional[StateParams] = None

        # 回调: (state, params) -> None
        self._on_enter: Dict[MusicState, List[Callable]] = {}
        self._on_exit: Dict[MusicState, List[Callable]] = {}
        self._on_update: List[Callable] = []

    # ── 配置 ──

    def set_state_params(self, state: MusicState, params: StateParams):
        """自定义状态参数"""
        self._state_params[state] = params

    def set_transition_defaults(self, params: TransitionParams):
        """设置默认过渡参数"""
        self._transition = params

    def set_transition_lock(self, locked: bool):
        """设置过渡锁 — True 则过渡期间忽略新的 transition_to 请求"""
        self._transition_lock = locked

    # ── 钩子 ──

    def on(self, event: str, state: MusicState, callback: Callable):
        """注册状态钩子: 'enter' / 'exit'"""
        if event == "enter":
            self._on_enter.setdefault(state, []).append(callback)
        elif event == "exit":
            self._on_exit.setdefault(state, []).append(callback)

    def on_update(self, callback: Callable):
        """注册每帧更新回调: (elapsed, params) -> None"""
        self._on_update.append(callback)

    # ── 状态操作 ──

    def start(self, state: MusicState, params: Optional[TransitionParams] = None):
        """立即进入指定状态（无过渡）"""
        self._current_state = state
        self._active_params = self._clone_params(self._state_params.get(state))
        self._is_transitioning = False
        self._fire_callbacks("enter", state)

    def transition_to(
        self,
        state: MusicState,
        params: Optional[TransitionParams] = None,
    ) -> bool:
        """
        请求过渡到目标状态。
        如果处于过渡锁状态，返回 False 并忽略请求。
        """
        if state == self._current_state and not self._is_transitioning:
            return True  # 已在目标状态

        if self._transition_lock and self._is_transitioning:
            return False  # 锁定期内拒绝新转换

        # 触发 exit
        if self._current_state is not None:
            self._fire_callbacks("exit", self._current_state)

        tr = params or self._transition or TransitionParams()
        self._previous_state = self._current_state
        self._transition_target = state
        self._transition_elapsed = 0.0
        self._is_transitioning = True
        self._current_transition = tr

        return True

    def tick(self, dt: float) -> Optional[StateParams]:
        """
        每帧更新。dt 为帧间隔（秒）。
        返回当前活跃的音乐参数（可传递给合成引擎）。
        """
        if self._active_params is None:
            return None

        if self._is_transitioning and self._transition_target is not None:
            tr = self._current_transition or TransitionParams()
            self._transition_elapsed += dt
            progress = min(self._transition_elapsed / tr.duration, 1.0)

            # 应用过渡曲线
            progress = self._apply_curve(progress, tr.curve)

            # 插值参数
            src = self._state_params.get(self._current_state)
            dst = self._state_params.get(self._transition_target)
            if src is not None and dst is not None:
                self._active_params = self._interpolate_params(src, dst, progress)

            # 过渡完成
            if self._transition_elapsed >= tr.duration:
                self._current_state = self._transition_target
                self._is_transitioning = False
                self._transition_target = None
                self._transition_elapsed = 0.0
                self._fire_callbacks("enter", self._current_state)

        # 触发 update 回调
        for cb in self._on_update:
            cb(self._transition_elapsed, self._active_params)

        return self._clone_params(self._active_params)

    # ── 查询 ──

    @property
    def current_state(self) -> Optional[MusicState]:
        return self._current_state

    @property
    def is_transitioning(self) -> bool:
        return self._is_transitioning

    @property
    def transition_progress(self) -> float:
        """过渡进度 0-1，仅过渡期间有效"""
        if not self._is_transitioning:
            return 0.0
        tr = self._current_transition or TransitionParams()
        return min(self._transition_elapsed / tr.duration, 1.0)

    @property
    def active_params(self) -> Optional[StateParams]:
        return self._clone_params(self._active_params) if self._active_params else None

    # ── 内部 ──

    def _clone_params(self, p: Optional[StateParams]) -> Optional[StateParams]:
        if p is None:
            return None
        return StateParams(
            bpm=p.bpm, tension=p.tension, density=p.density,
            scale_type=p.scale_type, root_note=p.root_note,
            dynamic_range=p.dynamic_range, reverb_mix=p.reverb_mix,
            filter_openness=p.filter_openness,
            low_freq_content=p.low_freq_content,
            high_freq_content=p.high_freq_content,
            distortion_amount=p.distortion_amount,
            pulse_weight=p.pulse_weight,
        )

    @staticmethod
    def _apply_curve(t: float, curve: str) -> float:
        """应用缓动曲线到 [0,1] 区间"""
        if curve == "linear":
            return t
        elif curve == "ease_in":
            return t * t
        elif curve == "ease_out":
            return 1 - (1 - t) ** 2
        elif curve == "ease_in_out":
            return 3 * t * t - 2 * t * t * t
        else:
            return t

    @staticmethod
    def _interpolate_params(a: StateParams, b: StateParams, t: float) -> StateParams:
        """参数线性插值"""
        return StateParams(
            bpm=int(a.bpm + (b.bpm - a.bpm) * t),
            tension=a.tension + (b.tension - a.tension) * t,
            density=int(a.density + (b.density - a.density) * t),
            scale_type=b.scale_type if t > 0.5 else a.scale_type,
            root_note=b.root_note if t > 0.5 else a.root_note,
            dynamic_range=a.dynamic_range + (b.dynamic_range - a.dynamic_range) * t,
            reverb_mix=a.reverb_mix + (b.reverb_mix - a.reverb_mix) * t,
            filter_openness=a.filter_openness + (b.filter_openness - a.filter_openness) * t,
            low_freq_content=a.low_freq_content + (b.low_freq_content - a.low_freq_content) * t,
            high_freq_content=a.high_freq_content + (b.high_freq_content - a.high_freq_content) * t,
            distortion_amount=a.distortion_amount + (b.distortion_amount - a.distortion_amount) * t,
            pulse_weight=a.pulse_weight + (b.pulse_weight - a.pulse_weight) * t,
        )

    def _fire_callbacks(self, event: str, state: MusicState):
        pool = (self._on_enter if event == "enter" else self._on_exit).get(state, [])
        params = self._state_params.get(state)
        for cb in pool:
            try:
                cb(state, params)
            except Exception:
                pass
