"""失真效果 —— 软削波 / Bit Crush"""

import numpy as np


def apply_distortion(sig: np.ndarray, amount: float = 0.5) -> np.ndarray:
    """软削波失真。amount 控制失真强度 (0.0~1.0)。

    使用 tanh 非线性，amount 越大失真越强。
    """
    if amount <= 0:
        return sig
    drive = 1.0 + amount * 9.0
    return np.tanh(sig * drive)


def apply_bit_crush(sig: np.ndarray, depth: int = 8) -> np.ndarray:
    """Bit crush — 模拟低比特深度。

    Args:
        depth: 比特深度 (2~16)，越小失真越大
    """
    if depth <= 0:
        return sig
    levels = 2 ** max(1, depth)
    return np.round(sig * levels) / levels
