"""
Flanger / Phaser / Delay 调制效果器
====================================

PRD P2-3: 实现 Flanger 和 Phaser 两种经典调制效果。

Flanger:
    通过 LFO 调制短延迟（<15ms）+ 反馈产生梳状滤波扫频效果。
    经典的"喷气机"音效，广泛用于吉他/电子音乐。

Phaser:
    通过多个全通滤波器产生 notch 频率的扫频效果。
    比 Flanger 更温和，产生"旋转"感。

Delay:
    回声/延迟效果器，支持 ping-pong 立体声延迟和反馈。

使用方式:
    >>> from bloodmusic.effects.flanger import apply_flanger, apply_phaser, apply_delay
    >>> wet = apply_flanger(sig, mix=0.7, rate=0.5, depth=0.003)
"""

import numpy as np
from scipy import signal
from ..core.constants import SR as _SR


# ══════════════════════════════════════════════════════════════
# Flanger
# ══════════════════════════════════════════════════════════════

def apply_flanger(
    sig: np.ndarray,
    mix: float = 0.7,
    rate: float = 0.5,
    depth: float = 0.003,  # 3ms 调制深度
    feedback: float = 0.0,
    base_delay: float = 0.005,  # 5ms 基础延迟
    sr: int = _SR,
) -> np.ndarray:
    """Flanger 效果 — LFO 调制延迟线 + 可选反馈。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 0~1
        rate: LFO 速率 (Hz)，典型值 0.1~5
        depth: 调制深度 (秒)，典型值 0.001~0.010
        feedback: 反馈量 0~0.95 (0=无反馈)
        base_delay: 基础延迟 (秒)
        sr: 采样率

    Returns:
        Flanger 处理后的信号

    原理:
        y[n] = x[n] + mix * x[n - (base + depth * sin(2π * rate * n/sr))]
    """
    if mix <= 0.001:
        return sig

    n = len(sig)
    t = np.arange(n) / sr

    # LFO 调制信号
    lfo = np.sin(2.0 * np.pi * rate * t)

    # 变化的延迟量 (采样)
    max_delay_samples = int((base_delay + depth * 2.0) * sr) + 1
    delay_samples = (base_delay + depth * lfo) * sr
    delay_samples = np.clip(delay_samples, 0, max_delay_samples - 1)

    # 逐采样延迟线 (使用整数延迟近似)
    wet = _variable_delay_line(sig, delay_samples)

    # 反馈
    if feedback > 0.001:
        wet_fb = np.zeros_like(sig)
        buffer = np.zeros(max_delay_samples)
        buf_pos = 0
        for i in range(n):
            d = int(delay_samples[i])
            read_pos = (buf_pos - d) % max_delay_samples
            delayed = buffer[read_pos]
            wet_fb[i] = delayed
            # 写入: 输入 + 反馈 * 延迟
            input_val = sig[i] + feedback * delayed
            buffer[buf_pos] = input_val
            buf_pos = (buf_pos + 1) % max_delay_samples
        wet = wet_fb

    # 混合
    result = sig * (1.0 - mix) + wet * mix

    # 安全限幅
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95

    return result


def _variable_delay_line(
    sig: np.ndarray,
    delay_samples: np.ndarray,
) -> np.ndarray:
    """可变延迟线 — 线性插值。

    Args:
        sig: 输入信号
        delay_samples: 每个采样的延迟量（浮点数，支持亚采样精度）

    Returns:
        延迟后的信号
    """
    n = len(sig)
    max_delay = int(np.ceil(np.max(delay_samples))) + 1
    buffer = np.zeros(max_delay + n)
    buffer[max_delay:max_delay + n] = sig

    wet = np.zeros(n)
    for i in range(n):
        d = delay_samples[i]
        d_int = int(d)
        d_frac = d - d_int
        pos = max_delay + i - d_int
        if 0 <= pos < len(buffer) - 1:
            wet[i] = buffer[pos] * (1.0 - d_frac) + buffer[pos + 1] * d_frac

    return wet


# ══════════════════════════════════════════════════════════════
# Phaser
# ══════════════════════════════════════════════════════════════

def apply_phaser(
    sig: np.ndarray,
    mix: float = 0.5,
    rate: float = 0.5,
    depth: float = 0.7,
    n_stages: int = 6,
    feedback: float = 0.0,
    sr: int = _SR,
) -> np.ndarray:
    """Phaser 效果 — 多级全通滤波器 + LFO 扫频。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 0~1
        rate: LFO 速率 (Hz)
        depth: 调制深度 0~1 (0=无调制, 1=最宽范围)
        n_stages: 全通滤波器级数，典型值 2~12
        feedback: 反馈量 0~0.9
        sr: 采样率

    Returns:
        Phaser 处理后的信号

    原理:
        每级全通滤波器引入频率相关的相位偏移。LFO 调制中心频率，
        多级串联产生移动的 notch (陷波) 效果。
    """
    if mix <= 0.001:
        return sig

    n = len(sig)
    t = np.arange(n) / sr

    # LFO: 在 min_freq ~ max_freq 之间扫频
    min_freq = 200.0
    max_freq = 4000.0
    center = np.sqrt(min_freq * max_freq)

    lfo = 0.5 + 0.5 * np.sin(2.0 * np.pi * rate * t)
    lfo = lfo * depth + (1.0 - depth) * 0.5  # depth 控制调制范围
    freq = min_freq + lfo * (max_freq - min_freq)

    # 逐级处理（实时调制频率）
    wet = sig.copy()
    feedback_buf = np.zeros(1)  # 上一采样反馈值

    for stage in range(n_stages):
        # 每级的中心频率略有偏移
        detune = 1.0 + stage * 0.05
        stage_freq = freq * detune

        # 构建逐采样全通滤波器
        stage_out = np.zeros(n)

        # 全通滤波器状态
        x1, x2 = 0.0, 0.0  # 输入历史
        y1, y2 = 0.0, 0.0  # 输出历史

        for i in range(n):
            # 根据当前 LFO 频率计算全通系数
            f0 = stage_freq[i]
            w0 = 2.0 * np.pi * f0 / sr
            # 双二阶全通系数
            bw = w0 / 10.0  # Q factor
            alpha = np.sin(w0) * np.sinh(np.log(2.0) / 2.0 * bw / w0 * (1.0 if w0 > 0 else 1.0))
            if np.abs(w0) < 1e-8:
                cos_w0 = 1.0
            else:
                cos_w0 = np.cos(w0)

            b0 = 1.0 - alpha
            b1 = -2.0 * cos_w0
            b2 = 1.0 + alpha
            a0 = 1.0 + alpha
            a1 = -2.0 * cos_w0
            a2 = 1.0 - alpha

            # 归一化
            b0, b1, b2 = b0 / a0, b1 / a0, b2 / a0
            a1, a2 = a1 / a0, a2 / a0

            x_in = wet[i] + feedback * feedback_buf[0]

            # 双二阶滤波
            y = b0 * x_in + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2

            x2, x1 = x1, x_in
            y2, y1 = y1, y

            stage_out[i] = y
            feedback_buf[0] = y

        wet = stage_out

    # 混合
    result = sig * (1.0 - mix) + wet * mix

    # 安全限幅
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95

    return result


# ══════════════════════════════════════════════════════════════
# Delay
# ══════════════════════════════════════════════════════════════

def apply_delay(
    sig: np.ndarray,
    mix: float = 0.4,
    delay_time: float = 0.3,  # 延迟时间 (秒)
    feedback: float = 0.3,    # 反馈 0~0.95
    sr: int = _SR,
) -> np.ndarray:
    """单声道延迟效果。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 0~1
        delay_time: 延迟时间 (秒)
        feedback: 反馈量 0~0.95
        sr: 采样率

    Returns:
        延迟处理后的信号
    """
    if mix <= 0.001 or delay_time <= 0:
        return sig

    n = len(sig)
    delay_samples = int(delay_time * sr)
    if delay_samples <= 0:
        return sig

    tail_samples = max(delay_samples * 8, n // 2)
    result = np.zeros(n + tail_samples)  # 留出尾部空间
    result[:n] = sig

    for i in range(n):
        if i + delay_samples < len(result):
            result[i + delay_samples] += sig[i] * feedback

    # 衰减尾部
    fade_len = min(tail_samples, len(result) - n)
    if fade_len > 0:
        fade = np.linspace(1.0, 0.0, fade_len)
        result[n:n + fade_len] *= fade

    # 混合: 从 result 中提取 wet 部分 (与原始信号等长)
    wet = np.zeros(n)
    avail = min(n, len(result) - n)
    if avail > 0:
        wet[:avail] = result[n:n + avail]
    output = sig * (1.0 - mix) + wet[:n] * mix

    # 安全限幅
    peak = np.max(np.abs(output))
    if peak > 1.0:
        output = output / peak * 0.95

    return output


def apply_pingpong_delay(
    sig: np.ndarray,
    mix: float = 0.4,
    delay_time: float = 0.3,
    feedback: float = 0.35,
    stereo_spread: float = 0.7,
    sr: int = _SR,
) -> np.ndarray:
    """乒乓立体声延迟 — 左声道延迟到右声道，反之亦然。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 0~1
        delay_time: 延迟时间 (秒)
        feedback: 反馈量 0~0.95
        stereo_spread: 立体声扩散 0~1
        sr: 采样率

    Returns:
        立体声信号 (2, n_samples) float64
    """
    if mix <= 0.001 or delay_time <= 0:
        return np.stack([sig, sig])

    n = len(sig)
    delay_samples = int(delay_time * sr)
    if delay_samples <= 0:
        return np.stack([sig, sig])

    # 左声道 = 原信号在左 + 延迟信号在右 (交替)
    left = np.zeros(n + delay_samples * 8)
    right = np.zeros(n + delay_samples * 8)
    left[:n] = sig
    right[:n] = sig * stereo_spread

    for i in range(n):
        if i + delay_samples < len(left):
            right[i + delay_samples] += sig[i] * feedback
        if i + delay_samples * 2 < len(left):
            left[i + delay_samples * 2] += sig[i] * feedback * 0.5

    # 截取并混合
    dry_left = sig * (1.0 - mix)
    dry_right = sig * (1.0 - mix) * stereo_spread
    wet_left = left[n:n + n] * mix if len(left) > n else np.zeros(n)
    wet_right = right[n:n + n] * mix if len(right) > n else np.zeros(n)

    result = np.stack([
        dry_left + wet_left,
        dry_right + wet_right,
    ])

    # 限幅
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95

    return result


def apply_multitap_delay(
    sig: np.ndarray,
    mix: float = 0.5,
    tap_times: list = None,   # 例如 [0.2, 0.5, 0.8] 秒
    tap_gains: list = None,   # 例如 [0.6, 0.4, 0.2]
    sr: int = _SR,
) -> np.ndarray:
    """多拍延迟 — 多个不同时间的回声拍子。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比
        tap_times: 各拍延迟时间 (秒)
        tap_gains: 各拍增益 (0~1)
        sr: 采样率

    Returns:
        延迟处理后的信号
    """
    if tap_times is None:
        tap_times = [0.15, 0.3, 0.45]
    if tap_gains is None:
        tap_gains = [0.5, 0.35, 0.2]

    if mix <= 0.001:
        return sig

    n = len(sig)
    max_delay = int(max(tap_times) * sr)
    result = np.zeros(n + max_delay, dtype=np.float64)
    result[:n] = sig.copy()

    wet = np.zeros(n, dtype=np.float64)

    for delay_sec, gain in zip(tap_times, tap_gains):
        delay_samp = int(delay_sec * sr)
        if delay_samp <= 0:
            continue
        # 湿信号 = 延迟 + 衰减的干信号
        for i in range(n):
            if i + delay_samp < len(result):
                result[i + delay_samp] += sig[i] * gain

    # 从 result 中提取湿信号
    for i in range(n):
        # 所有超过原始长度的都是湿信号
        pass  # 留空,保持架构

    output = sig * (1.0 - mix) + result[n:n + n] * mix if len(result) > n else sig

    peak = np.max(np.abs(output))
    if peak > 1.0:
        output = output / peak * 0.95

    return output
