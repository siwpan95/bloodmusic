"""动态效果 —— 压缩器 / 限幅器"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CompressorParams:
    """压缩器参数"""
    threshold_db: float = -12.0     # 阈值 (dB)
    ratio: float = 4.0              # 压缩比
    attack_ms: float = 10.0         # 起音时间 (ms)
    release_ms: float = 100.0       # 释放时间 (ms)
    makeup_db: float = 0.0          # 补偿增益 (dB)


def apply_compressor(sig: np.ndarray, params: CompressorParams, sr: int = 44100) -> np.ndarray:
    """动态范围压缩器。

    Args:
        sig: 输入信号 (mono float64)
        params: 压缩器参数
        sr: 采样率
    Returns:
        压缩后的信号
    """
    if params.threshold_db >= 0:
        return sig

    attack_coeff = 1.0 - np.exp(-1.0 / (params.attack_ms * 0.001 * sr))
    release_coeff = 1.0 - np.exp(-1.0 / (params.release_ms * 0.001 * sr))

    threshold_lin = 10 ** (params.threshold_db / 20.0)
    makeup_gain = 10 ** (params.makeup_db / 20.0)

    envelope = np.zeros_like(sig)
    env = 0.0
    for i in range(len(sig)):
        abs_val = abs(sig[i])
        if abs_val > env:
            env += attack_coeff * (abs_val - env)
        else:
            env += release_coeff * (abs_val - env)
        envelope[i] = env

    # 计算增益衰减
    gain = np.ones_like(sig)
    mask = envelope > threshold_lin
    if np.any(mask):
        over_db = 20 * np.log10(envelope[mask] / threshold_lin)
        gain_db = over_db * (1.0 / params.ratio - 1.0)
        gain[mask] = 10 ** (gain_db / 20.0)

    return sig * gain * makeup_gain


def apply_limiter(sig: np.ndarray, threshold_db: float = -1.0, sr: int = 44100) -> np.ndarray:
    """峰值限幅器。

    Args:
        sig: 输入信号
        threshold_db: 限幅阈值 (dB)
        sr: 采样率
    Returns:
        限幅后的信号
    """
    threshold_lin = 10 ** (threshold_db / 20.0)
    return np.clip(sig, -threshold_lin, threshold_lin)


# ═══════════════════════════════════════════════════════════════════════
# 多段压缩器 (P2)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MultibandCompressorParams:
    """多段压缩器参数"""
    bands: int = 3                             # 频段数 (2-5)
    crossover_freqs: List[float] = field(      # 分频点 (Hz)
        default_factory=lambda: [250.0, 2000.0]
    )
    thresholds_db: Optional[List[float]] = None    # 每段阈值 (dB)
    ratios: Optional[List[float]] = None           # 每段压缩比
    attacks_ms: Optional[List[float]] = None       # 每段起音 (ms)
    releases_ms: Optional[List[float]] = None      # 每段释放 (ms)
    makeup_dbs: Optional[List[float]] = None       # 每段补偿增益 (dB)


def apply_multiband_compressor(
    sig: np.ndarray,
    params: MultibandCompressorParams = None,
    sr: int = 44100,
) -> np.ndarray:
    """多段动态压缩 — 对不同频段独立压缩后合并。

    对低频保持更多能量，中频做适度压缩，高频克制控制。

    Args:
        sig: 输入信号 (float64 mono)
        params: 多段压缩参数
        sr: 采样率

    Returns:
        压缩后的信号
    """
    if params is None:
        params = MultibandCompressorParams()

    n_bands = min(params.bands, len(params.crossover_freqs) + 1)
    if n_bands <= 1:
        return apply_compressor(sig, CompressorParams(), sr)

    # 默认参数
    n = n_bands
    thresh = params.thresholds_db or [-18.0, -15.0, -12.0][:n]
    ratios = params.ratios or [3.0, 2.5, 2.0][:n]
    attacks = params.attacks_ms or [15.0, 10.0, 5.0][:n]
    releases = params.releases_ms or [150.0, 100.0, 80.0][:n]
    makeups = params.makeup_dbs or [2.0, 1.0, 0.0][:n]
    xovers = params.crossover_freqs[:n_bands - 1]

    # 分频 (使用简单 Butterworth 滤波器)
    from scipy.signal import butter, sosfilt

    result = np.zeros_like(sig)
    remaining = sig.copy()

    for b in range(n_bands - 1):
        fc = xovers[b]

        # 低通提取当前频段
        sos = butter(4, fc / (sr / 2), btype='lowpass', output='sos')
        band = sosfilt(sos, remaining)

        # 残差 = 原信号 - 低通 = 剩余高频
        remaining = remaining - band

        # 对该频段压缩
        cp = CompressorParams(
            threshold_db=thresh[b] if b < len(thresh) else -18,
            ratio=ratios[b] if b < len(ratios) else 4,
            attack_ms=attacks[b] if b < len(attacks) else 10,
            release_ms=releases[b] if b < len(releases) else 100,
            makeup_db=makeups[b] if b < len(makeups) else 0,
        )
        band = apply_compressor(band, cp, sr)
        result += band

    # 最后一个频段 (最高频)
    cp_last = CompressorParams(
        threshold_db=thresh[-1] if n_bands - 1 < len(thresh) else -12,
        ratio=ratios[-1] if n_bands - 1 < len(ratios) else 2,
        attack_ms=attacks[-1] if n_bands - 1 < len(attacks) else 5,
        release_ms=releases[-1] if n_bands - 1 < len(releases) else 80,
        makeup_db=makeups[-1] if n_bands - 1 < len(makeups) else 0,
    )
    result += apply_compressor(remaining, cp_last, sr)

    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95

    return result
