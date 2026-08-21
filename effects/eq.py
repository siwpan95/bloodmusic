"""参量均衡器 —— 三段参量 EQ"""

import numpy as np
from dataclasses import dataclass
from scipy.signal import sosfilt


@dataclass
class ParametricEQParams:
    """三段参量 EQ 参数"""
    low_freq: float = 200.0
    low_gain_db: float = 0.0
    low_q: float = 1.0
    mid_freq: float = 1000.0
    mid_gain_db: float = 0.0
    mid_q: float = 1.0
    high_freq: float = 4000.0
    high_gain_db: float = 0.0
    high_q: float = 1.0


def _apply_peaking_eq(sig: np.ndarray, freq: float, gain_db: float, q: float, sr: int) -> np.ndarray:
    """单段参量 EQ（peaking filter）。

    Args:
        sig: 输入信号
        freq: 中心频率 (Hz)
        gain_db: 增益 (dB)
        q: 品质因数
        sr: 采样率
    Returns:
        均衡后的信号
    """
    if abs(gain_db) < 0.1:
        return sig

    # 使用 second-order sections 实现 peaking filter
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2 * q)

    b0 = 1 + alpha * A
    b1 = -2 * np.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha / A

    sos = np.array([[b0/a0, b1/a0, b2/a0, 1.0, a1/a0, a2/a0]])
    return sosfilt(sos, sig)


def apply_parametric_eq(sig: np.ndarray, params: ParametricEQParams, sr: int = 44100) -> np.ndarray:
    """三段参量均衡器。

    Args:
        sig: 输入信号 (mono float64)
        params: EQ 参数
        sr: 采样率
    Returns:
        均衡后的信号
    """
    result = sig.copy()
    result = _apply_peaking_eq(result, params.low_freq, params.low_gain_db, params.low_q, sr)
    result = _apply_peaking_eq(result, params.mid_freq, params.mid_gain_db, params.mid_q, sr)
    result = _apply_peaking_eq(result, params.high_freq, params.high_gain_db, params.high_q, sr)
    return result
