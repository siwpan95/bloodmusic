"""调制效果 —— Chorus (向量化优化版)"""

import numpy as np


def apply_chorus(
    sig: np.ndarray,
    mix: float = 0.5,
    rate: float = 0.5,
    depth: float = 0.002,
    n_voices: int = 3,
    sr: int = 44100,
) -> np.ndarray:
    """Chorus 效果 — 延迟线 + LFO 调制 (向量化优化)。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 (0~1)
        rate: LFO 速率 (Hz)
        depth: 调制深度 (秒)
        n_voices: 合唱声部数
        sr: 采样率
    Returns:
        chorus 效果处理后的信号
    """
    if mix <= 0.001:
        return sig

    n = len(sig)
    wet = np.zeros(n)

    for v in range(n_voices):
        base_delay = int((0.005 + v * 0.003) * sr)
        phase_offset = v * 2 * np.pi / n_voices

        t = np.arange(n) / sr
        lfo = np.sin(2 * np.pi * rate * t + phase_offset)
        delay_samples = (base_delay + lfo * depth * sr).astype(int)
        delay_samples = np.clip(delay_samples, 0, base_delay * 3)

        # 向量化延迟线: 构建索引数组批量读取
        indices = np.arange(n) - delay_samples
        valid = indices >= 0
        wet[valid] += sig[indices[valid]]

    wet_peak = np.max(np.abs(wet))
    if wet_peak > 0:
        wet = wet / wet_peak

    result = sig * (1 - mix) + wet * mix
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95
    return result
