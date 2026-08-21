"""滤波器 —— 低通 / 高通 / 带通 / 陷波（scipy.signal 二阶巴特沃斯）

支持 Q/Resonance 参数的谐振滤波器变体:
  - apply_lowpass / apply_highpass: 标准 Butterworth (Q≈0.707)
  - apply_resonant_lpf / apply_resonant_hpf: 带 Q 谐振控制的低通/高通
"""

import numpy as np
from scipy.signal import butter, sosfilt
from ..core.constants import SR as _SR


def apply_lowpass(sig: np.ndarray, cutoff_hz: float, sr: int = _SR) -> np.ndarray:
    """二阶巴特沃斯低通滤波器 (无谐振, Q≈0.707)。

    Args:
        sig: 输入信号
        cutoff_hz: 截止频率 (Hz)
        sr: 采样率
    """
    if cutoff_hz is None or cutoff_hz <= 0:
        return sig
    nyq = sr / 2.0
    if cutoff_hz >= nyq:
        return sig
    sos = butter(2, cutoff_hz / nyq, btype='low', output='sos')
    return sosfilt(sos, sig)


def apply_highpass(sig: np.ndarray, cutoff_hz: float, sr: int = _SR) -> np.ndarray:
    """二阶巴特沃斯高通滤波器 (无谐振, Q≈0.707)。

    Args:
        sig: 输入信号
        cutoff_hz: 截止频率 (Hz)
        sr: 采样率
    """
    if cutoff_hz is None or cutoff_hz <= 0:
        return sig
    nyq = sr / 2.0
    if cutoff_hz >= nyq:
        return sig
    sos = butter(2, cutoff_hz / nyq, btype='high', output='sos')
    return sosfilt(sos, sig)


def apply_resonant_lpf(
    sig: np.ndarray,
    cutoff_hz: float,
    q: float = 0.707,
    sr: int = _SR,
) -> np.ndarray:
    """2-pole 谐振低通滤波器 (基于 RBJ Audio EQ Cookbook)。

    比标准 Butterworth 更灵活，支持 resonance 参数：
      - Q = 0.707: 等同于 Butterworth (最平坦)
      - Q = 1.0:  临界阻尼，12dB/oct 转折点略凸
      - Q = 2.0:  明显谐振峰，类似 Moog ladder 质感
      - Q = 5.0+: 强烈谐振，产生哨声般的共鸣

    Args:
        sig: 输入信号 (mono float64)
        cutoff_hz: 截止频率 (Hz)
        q: 谐振品质因数 Q (0.5 ~ 20+)
        sr: 采样率

    Returns:
        滤波后的信号
    """
    if cutoff_hz is None or cutoff_hz <= 0:
        return sig
    nyq = sr / 2.0
    if cutoff_hz >= nyq:
        return sig

    w0 = 2.0 * np.pi * cutoff_hz / sr
    cos_w0 = np.cos(w0)
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))

    b0 = (1.0 - cos_w0) / 2.0
    b1 = 1.0 - cos_w0
    b2 = (1.0 - cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    # 使用 sosfilt 实现
    sos = np.array([[
        b0 / a0, b1 / a0, b2 / a0,
        1.0, a1 / a0, a2 / a0,
    ]])
    result = sosfilt(sos, sig)
    return np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)


def apply_resonant_hpf(
    sig: np.ndarray,
    cutoff_hz: float,
    q: float = 0.707,
    sr: int = _SR,
) -> np.ndarray:
    """2-pole 谐振高通滤波器 (基于 RBJ Audio EQ Cookbook)。

    Args:
        sig: 输入信号 (mono float64)
        cutoff_hz: 截止频率 (Hz)
        q: 谐振品质因数 Q (0.5 ~ 20+)
        sr: 采样率

    Returns:
        滤波后的信号
    """
    if cutoff_hz is None or cutoff_hz <= 0:
        return sig
    nyq = sr / 2.0
    if cutoff_hz >= nyq:
        return sig

    w0 = 2.0 * np.pi * cutoff_hz / sr
    cos_w0 = np.cos(w0)
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))

    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    sos = np.array([[
        b0 / a0, b1 / a0, b2 / a0,
        1.0, a1 / a0, a2 / a0,
    ]])
    result = sosfilt(sos, sig)
    return np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)


def apply_bandpass(sig: np.ndarray, center_hz: float, q: float = 1.0, sr: int = _SR) -> np.ndarray:
    """二阶巴特沃斯带通滤波器。

    Args:
        sig: 输入信号
        center_hz: 中心频率 (Hz)
        q: 品质因数 (Q值)，越高越窄
        sr: 采样率
    """
    if center_hz is None or center_hz <= 0:
        return sig
    nyq = sr / 2.0
    bandwidth = center_hz / max(q, 0.1)
    low = max(center_hz - bandwidth / 2, 1.0)
    high = min(center_hz + bandwidth / 2, nyq - 1)
    if low >= high:
        return sig
    sos = butter(2, [low / nyq, high / nyq], btype='band', output='sos')
    return sosfilt(sos, sig)


def apply_notch(sig: np.ndarray, freq_hz: float, q: float = 1.0, sr: int = _SR) -> np.ndarray:
    """二阶巴特沃斯陷波滤波器。

    Args:
        sig: 输入信号
        freq_hz: 陷波频率 (Hz)
        q: 品质因数 (Q值)
        sr: 采样率
    """
    if freq_hz is None or freq_hz <= 0:
        return sig
    nyq = sr / 2.0
    if freq_hz >= nyq:
        return sig
    bandwidth = freq_hz / max(q, 0.1)
    low = max(freq_hz - bandwidth / 2, 0.1)
    high = min(freq_hz + bandwidth / 2, nyq - 1)
    if low >= high:
        return sig
    sos = butter(2, [low / nyq, high / nyq], btype='bandstop', output='sos')
    return sosfilt(sos, sig)
