"""
动态自动化曲线 —— 参数随时间变化的自动化轨道
==============================================

类似 DAW 中的 Automation Lane，支持随时间变化的参数控制：
 - 滤波器截止频率扫频 (filter sweep)
 - 音量渐变 (fade in/out, automation)
 - 声像移动 (auto-pan)
 - 任意自定义参数曲线

核心数据结构:
 - AutomationPoint: 时间+值的控制点
 - AutomationLane: 一条参数自动化线 (多个点之间插值)
 - AutomationTrack: 多条自动化线的集合

应用到音频:
 - apply_filter_sweep: 实时变化的低通/高通滤波 (支持 Q/Resonance)
 - apply_volume_automation: 音量包络自动化
 - apply_pan_automation: 声像自动化

用法:
    >>> from bloodmusic.music.automation import AutomationLane, apply_filter_sweep
    >>> lane = AutomationLane("cutoff", [(0.0, 20000), (4.0, 500), (8.0, 20000)])
    >>> result = apply_filter_sweep(audio, lane, filter_type="lowpass", q=2.0)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Literal
from ..core.constants import SR as _SR


# ═══════════════════════════════════════════════════════════════════════
# Automation 数据结构
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AutomationPoint:
    """自动化控制点: (时间, 值)"""
    time_sec: float      # 时间 (秒)
    value: float         # 参数值


@dataclass
class AutomationLane:
    """单条自动化曲线 — 多个控制点之间平滑插值。

    Args:
        name: 参数名 (如 "cutoff", "volume", "pan", "delay_mix")
        points: [(time_sec, value), ...] 按时间升序排列
        interpolate: 插值方式 ("linear" | "smooth" | "step")
    """
    name: str
    points: List[Tuple[float, float]]
    interpolate: str = "linear"  # "linear" | "smooth" | "step"

    def __post_init__(self):
        self._sorted = sorted(self.points, key=lambda p: p[0])

    @property
    def sorted_points(self) -> List[Tuple[float, float]]:
        return self._sorted

    @property
    def duration(self) -> float:
        """拐点最大时间 (秒)"""
        return self._sorted[-1][0] if self._sorted else 0.0

    def at_time(self, t: float) -> float:
        """在时间 t 处的插值参数值"""
        pts = self._sorted
        if not pts:
            return 0.0
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]

        # 找到包围区间
        for i in range(len(pts) - 1):
            t0, v0 = pts[i]
            t1, v1 = pts[i + 1]
            if t0 <= t <= t1:
                if self.interpolate == "step":
                    return v0
                elif self.interpolate == "smooth":
                    alpha = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    # smoothstep (Hermite)
                    smooth = alpha * alpha * (3 - 2 * alpha)
                    return v0 + (v1 - v0) * smooth
                else:  # linear
                    alpha = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    return v0 + (v1 - v0) * alpha

        return pts[-1][1]  # fallback

    def to_array(self, sr: int, total_sec: float) -> np.ndarray:
        """将整条自动化线渲染为逐采样的数组。

        Args:
            sr: 采样率
            total_sec: 总时长 (秒)

        Returns:
            (n_samples,) float64 自动化值数组
        """
        n = int(total_sec * sr)
        t = np.linspace(0, total_sec, n)
        return np.array([self.at_time(ti) for ti in t], dtype=np.float64)

    @staticmethod
    def constant(name: str = "constant", value: float = 1.0) -> "AutomationLane":
        """创建恒值自动化"""
        return AutomationLane(name, [(0.0, value), (float('inf'), value)])

    @staticmethod
    def linear_ramp(
        name: str, start_val: float, end_val: float,
        start_time: float = 0.0, end_time: float = 4.0,
    ) -> "AutomationLane":
        """创建线性渐变自动化"""
        return AutomationLane(name, [(start_time, start_val), (end_time, end_val)])

    @staticmethod
    def sweep(
        name: str, from_val: float, to_val: float, to_val2: float,
        time1: float, time2: float, time3: float,
    ) -> "AutomationLane":
        """创建三段扫频: from → to → to2"""
        return AutomationLane(name, [
            (0.0, from_val), (time1, to_val), (time2, to_val2), (time3, from_val),
        ])


@dataclass
class AutomationTrack:
    """多条自动化线的集合 — 一个段落或整首歌的所有自动化参数。

    Args:
        lanes: 自动化线列表
    """
    lanes: List[AutomationLane] = field(default_factory=list)

    def add(self, lane: AutomationLane):
        self.lanes.append(lane)
        return self

    def get(self, name: str) -> Optional[AutomationLane]:
        for lane in self.lanes:
            if lane.name == name:
                return lane
        return None


# ═══════════════════════════════════════════════════════════════════════
# 带 Q/Resonance 的谐振低通/高通滤波器
# ═══════════════════════════════════════════════════════════════════════

def _resonant_lpf_biquad_coeffs(cutoff_hz: float, q: float, sr: int):
    """计算 2-pole 谐振低通双二阶滤波器系数 (基于 RBJ Audio EQ Cookbook)。

    Args:
        cutoff_hz: 截止频率 (Hz)
        q: 谐振 Q 值 (0.5 ~ 20+). Q=0.707 = Butterworth (无谐振),
            Q > 0.707 产生谐振峰值
        sr: 采样率

    Returns:
        (b0, b1, b2, a1, a2) 滤波器系数
    """
    w0 = 2.0 * np.pi * cutoff_hz / sr
    cos_w0 = np.cos(w0)
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))

    b0 = (1.0 - cos_w0) / 2.0
    b1 = 1.0 - cos_w0
    b2 = (1.0 - cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def _resonant_hpf_biquad_coeffs(cutoff_hz: float, q: float, sr: int):
    """计算 2-pole 谐振高通双二阶滤波器系数。

    Args:
        cutoff_hz: 截止频率 (Hz)
        q: 谐振 Q 值
        sr: 采样率

    Returns:
        (b0, b1, b2, a1, a2) 滤波器系数
    """
    w0 = 2.0 * np.pi * cutoff_hz / sr
    cos_w0 = np.cos(w0)
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))

    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


# ═══════════════════════════════════════════════════════════════════════
# 实时变化的滤波器扫频
# ═══════════════════════════════════════════════════════════════════════

def apply_filter_sweep(
    sig: np.ndarray,
    cutoff_lane: AutomationLane,
    filter_type: Literal["lowpass", "highpass"] = "lowpass",
    q: float = 0.707,      # 0.707 = Butterworth, 2.0+ = resonant
    q_lane: Optional[AutomationLane] = None,  # 可选动态 Q 值
    sr: int = _SR,
) -> np.ndarray:
    """对音频应用实时变化的滤波器扫频效果。

    与固定截止频率的 apply_lowpass 不同，此函数使用双二阶滤波器
    逐采样更新系数，支持随时间变化的截止频率和 Q 值 (谐振)。

    Args:
        sig: 输入信号 (mono float64)
        cutoff_lane: 截止频率自动化曲线 (Hz 随时间 t 变化)
        filter_type: "lowpass" 或 "highpass"
        q: 固定 Q 值 (q_lane 为 None 时使用)
        q_lane: 可选 Q 值自动化曲线
        sr: 采样率

    Returns:
        滤波后的信号

    典型用法:
        # 4 小节 lowpass sweep: 20kHz → 500Hz → 20kHz
        >>> lane = AutomationLane("cutoff", [(0, 20000), (2, 500), (4, 20000)])
        >>> result = apply_filter_sweep(audio, lane, q=2.0)  # 带谐振的扫频
    """
    n = len(sig)
    result = np.zeros(n, dtype=np.float64)

    # 滤波器状态
    x1, x2 = 0.0, 0.0
    y1, y2 = 0.0, 0.0

    coeff_fn = _resonant_lpf_biquad_coeffs if filter_type == "lowpass" else _resonant_hpf_biquad_coeffs

    for i in range(n):
        t = i / sr
        cutoff = cutoff_lane.at_time(t)
        current_q = q_lane.at_time(t) if q_lane is not None else q

        if cutoff <= 0:
            result[i] = 0.0 if filter_type == "lowpass" else sig[i]
            continue

        b0, b1, b2, a1, a2 = coeff_fn(cutoff, current_q, sr)
        x = sig[i]

        # Direct Form I
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

        x2, x1 = x1, x
        y2, y1 = y1, y
        result[i] = y

    result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)
    return result


# ═══════════════════════════════════════════════════════════════════════
# 音量自动化
# ═══════════════════════════════════════════════════════════════════════

def apply_volume_automation(
    sig: np.ndarray,
    volume_lane: AutomationLane,
    sr: int = _SR,
) -> np.ndarray:
    """对音频应用音量自动化曲线。

    Args:
        sig: 输入信号
        volume_lane: 音量自动化曲线 (0~1 或 dB)
        sr: 采样率

    Returns:
        自动化处理后的信号
    """
    n = len(sig)
    total_sec = n / sr
    vol_array = volume_lane.to_array(sr, total_sec)
    min_len = min(len(sig), len(vol_array))
    return sig[:min_len] * vol_array[:min_len]


# ═══════════════════════════════════════════════════════════════════════
# 声像自动化
# ═══════════════════════════════════════════════════════════════════════

def apply_pan_automation(
    sig: np.ndarray,
    pan_lane: AutomationLane,
    sr: int = _SR,
) -> np.ndarray:
    """对音频应用声像自动化 (auto-pan)。

    Args:
        sig: 输入 mono 信号
        pan_lane: 声像自动化曲线 (-1=左, 0=中, 1=右)
        sr: 采样率

    Returns:
        立体声信号 (2, n_samples)
    """
    n = len(sig)
    total_sec = n / sr

    t = np.linspace(0, total_sec, n)
    pan_vals = np.array([pan_lane.at_time(ti) for ti in t], dtype=np.float64)
    pan_vals = np.clip(pan_vals, -1.0, 1.0)

    # -3dB center pan law
    left_gain = np.cos((pan_vals + 1.0) * np.pi / 4.0)
    right_gain = np.sin((pan_vals + 1.0) * np.pi / 4.0)

    return np.stack([sig * left_gain, sig * right_gain])


# ═══════════════════════════════════════════════════════════════════════
# 常用自动化预设
# ═══════════════════════════════════════════════════════════════════════

def build_up_lowpass(duration_sec: float, q: float = 2.0) -> AutomationLane:
    """经典的 Build-up 闷声扫频：高→低→恢复。

    Args:
        duration_sec: 段落时长 (秒)
        q: 谐振 Q 值

    Returns:
        cutoff 自动化曲线
    """
    t1 = duration_sec * 0.15
    t2 = duration_sec * 0.85
    return AutomationLane("cutoff", [
        (0.0, 20000),
        (t1, 500),
        (t2, 500),
        (duration_sec * 0.95, 20000),
        (duration_sec, 20000),
    ])


def fade_in_out(duration_sec: float, fade_in: float = 0.5, fade_out: float = 0.5) -> AutomationLane:
    """通用淡入淡出曲线。

    Args:
        duration_sec: 总时长
        fade_in: 淡入时间 (秒)
        fade_out: 淡出时间 (秒)

    Returns:
        音量自动化曲线
    """
    return AutomationLane("volume", [
        (0.0, 0.0),
        (fade_in, 1.0),
        (duration_sec - fade_out, 1.0),
        (duration_sec, 0.0),
    ])


def auto_pan_sine(duration_sec: float, rate: float = 0.25, depth: float = 0.8) -> AutomationLane:
    """正弦 Auto-Pan 自动化曲线。

    Args:
        duration_sec: 总时长
        rate: 摆动速率 (Hz)
        depth: 摆动深度 (0~1)

    Returns:
        声像自动化
    """
    points = []
    step = 0.1
    t = 0.0
    while t <= duration_sec:
        points.append((t, np.sin(2 * np.pi * rate * t) * depth))
        t += step
    points.append((duration_sec, np.sin(2 * np.pi * rate * duration_sec) * depth))
    return AutomationLane("pan", points, interpolate="smooth")


def drop_filter_resonance(duration_sec: float) -> AutomationLane:
    """Drop 段落的截止频率打开效果 — 从低到高快速展开。

    适合 EDM/Electronic 的 Drop 段落。
    """
    return AutomationLane("cutoff", [
        (0.0, 300),
        (duration_sec * 0.3, 20000),
        (duration_sec, 20000),
    ], interpolate="smooth")


# ═══════════════════════════════════════════════════════════════════════
# TempoLane — BPM 自动化 (P1)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TempoLane:
    """BPM 速度自动化曲线。

    支持在整个歌曲时间线上定义光滑的 BPM 变化（rubato、渐快、渐慢）。

    Args:
        points: [(time_sec, bpm), ...] 按时间升序排列的控制点
        interpolate: "linear" | "smooth" | "step"
    """
    points: List[Tuple[float, float]]
    interpolate: str = "smooth"

    def __post_init__(self):
        self._sorted = sorted(self.points, key=lambda p: p[0])

    @staticmethod
    def constant(bpm: float) -> "TempoLane":
        """恒定速度"""
        return TempoLane([(0.0, bpm), (float('inf'), bpm)])

    @staticmethod
    def accelerando(start_bpm: float, end_bpm: float,
                    start_time: float, end_time: float) -> "TempoLane":
        """渐快"""
        return TempoLane([
            (0.0, start_bpm),
            (start_time, start_bpm),
            (end_time, end_bpm),
            (float('inf'), end_bpm),
        ], interpolate="smooth")

    @staticmethod
    def ritardando(start_bpm: float, end_bpm: float,
                   start_time: float, end_time: float) -> "TempoLane":
        """渐慢"""
        return TempoLane([
            (0.0, start_bpm),
            (start_time, start_bpm),
            (end_time, end_bpm),
            (float('inf'), end_bpm),
        ], interpolate="smooth")

    def bpm_at(self, time_sec: float) -> float:
        """在给定时间点的 BPM 值"""
        pts = self._sorted
        if not pts:
            return 120.0
        if time_sec <= pts[0][0]:
            return pts[0][1]
        if time_sec >= pts[-1][0]:
            return pts[-1][1]

        for i in range(len(pts) - 1):
            t0, v0 = pts[i]
            t1, v1 = pts[i + 1]
            if t0 <= time_sec <= t1:
                if self.interpolate == "step":
                    return v0
                if t1 == t0:
                    return v0
                alpha = (time_sec - t0) / (t1 - t0)
                if self.interpolate == "smooth":
                    # smoothstep
                    alpha = alpha * alpha * (3 - 2 * alpha)
                return v0 + (v1 - v0) * alpha

        return pts[-1][1]

    def time_to_beats(self, time_sec: float,
                      sr: int = _SR,
                      resolution: float = 0.01) -> float:
        """将绝对时间(秒)转换为累计拍数。

        通过对 BPM 曲线进行数值积分实现。

        Args:
            time_sec: 目标时间 (秒)
            sr: 用于积分精度的"采样率" (Hz)
            resolution: 积分步长 (秒)

        Returns:
            累计拍数
        """
        total_beats = 0.0
        t = 0.0
        while t < time_sec:
            dt = min(resolution, time_sec - t)
            bpm_here = self.bpm_at(t + dt / 2)
            total_beats += bpm_here * dt / 60.0
            t += dt
        return total_beats

    def beats_to_time(self, target_beats: float,
                      sr: int = _SR,
                      resolution: float = 0.01) -> float:
        """将累计拍数反算为绝对时间(秒)。

        Args:
            target_beats: 目标拍数
            resolution: 积分步长 (秒)

        Returns:
            对应的时间 (秒)
        """
        total_beats = 0.0
        t = 0.0
        max_time = self._sorted[-1][0] if self._sorted else 300.0
        if max_time == float('inf'):
            max_time = 600.0

        while total_beats < target_beats and t < max_time:
            dt = min(resolution, max_time - t)
            bpm_here = self.bpm_at(t + dt / 2)
            total_beats += bpm_here * dt / 60.0
            t += dt

        return t
