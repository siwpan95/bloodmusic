"""
包络模块 —— ADSR 参数化 + 五种经典包络形状

形状:
  PERCUSSIVE  打击乐 — 快速起音 + 指数衰减
  PAD         铺底   — 慢起慢落，适合氛围
  PLUCK       拨弦   — 极速起音 + 快速衰减
  SWELL       渐强   — 慢起 + 持续 + 快速释放
  REVERSE     反转   — 渐强 + 骤停（反向播放感）
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EnvShape(Enum):
    PERCUSSIVE = "percussive"
    PAD = "pad"
    PLUCK = "pluck"
    SWELL = "swell"
    REVERSE = "reverse"


@dataclass
class ADSRParams:
    """ADSR 参数。所有时间单位为秒。"""
    attack: float = 0.01
    decay: float = 0.1
    sustain: float = 0.7
    release: float = 0.3


def make_envelope(
    length: int,
    shape: EnvShape = EnvShape.PERCUSSIVE,
    adsr: Optional[ADSRParams] = None,
) -> np.ndarray:
    """生成包络数组。

    Args:
        length: 样本数
        shape: 包络形状
        adsr: 自定义 ADSR（仅 shape=PERCUSSIVE 时生效）
    Returns:
        float64 包络数组，范围 [0, 1]
    """
    t = np.linspace(0, 1, length)

    if shape == EnvShape.PERCUSSIVE:
        if adsr is not None:
            a_len = int(length * adsr.attack)
            d_len = int(length * (adsr.attack + adsr.decay))
            env = np.ones(length)
            env[a_len:] = np.linspace(1, adsr.sustain, d_len - a_len)
            env[:a_len] = np.linspace(0, 1, a_len)
            env[d_len:] = adsr.sustain * np.linspace(1, 0, length - d_len)
            return env

        # 默认打击乐：快速起音 + 指数衰减
        attack_samples = int(length * 0.02)
        env = np.exp(-t * 15)
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        return env

    elif shape == EnvShape.PAD:
        attack_samples = int(length * 0.3)
        release_start = int(length * 0.8)
        env = np.ones(length)
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        env[release_start:] = np.linspace(1, 0, length - release_start)
        return env

    elif shape == EnvShape.PLUCK:
        attack_samples = int(length * 0.01)
        env = np.exp(-t * 25) * 0.9
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        return env

    elif shape == EnvShape.SWELL:
        crescendo_end = int(length * 0.7)
        release_start = int(length * 0.9)
        env = np.ones(length)
        env[:crescendo_end] = np.linspace(0.05, 0.95, crescendo_end)
        env[crescendo_end:release_start] = 0.95
        env[release_start:] = np.linspace(0.95, 0, length - release_start)
        return env

    elif shape == EnvShape.REVERSE:
        reverse_sustain = int(length * 0.7)
        env = np.ones(length)
        env[:reverse_sustain] = np.linspace(0.05, 1.0, reverse_sustain)
        env[reverse_sustain:] = 0  # 骤停
        return env

    else:
        return np.ones(length)
