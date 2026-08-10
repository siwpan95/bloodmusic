"""
振荡器模块 —— 多波形振荡器 + 统一接口

波形类型:
  SAW         锯齿波 — 丰富谐波，金属感/弦乐
  SQUARE      方波   — 8-bit 复古 / 芯片音乐
  SINE        正弦波 — 纯净，UI 提示音
  TRIANGLE    三角波 — 柔和泛音，木管质感
  NOISE_WHITE 白噪声 — 全频段，冲击声/爆炸
  NOISE_PINK  粉红噪声 — 自然环境音/雨声
  NOISE_BROWN 棕噪声 — 低频主导，雷声/震动
"""

import numpy as np
from enum import Enum


class OscType(Enum):
    SAW = "saw"
    SQUARE = "square"
    SINE = "sine"
    TRIANGLE = "triangle"
    NOISE_WHITE = "noise_white"
    NOISE_PINK = "noise_pink"
    NOISE_BROWN = "noise_brown"


# ═══════ 单波形生成函数 ═══════

def osc_saw(t: np.ndarray, freq: float) -> np.ndarray:
    """锯齿波"""
    return 2.0 * ((t * freq) % 1.0) - 1.0


def osc_square(t: np.ndarray, freq: float, duty: float = 0.5) -> np.ndarray:
    """方波，duty 控制占空比 (0.0~1.0)"""
    return np.where(((t * freq) % 1.0) < duty, 1.0, -1.0)


def osc_sine(t: np.ndarray, freq: float) -> np.ndarray:
    """正弦波"""
    return np.sin(2.0 * np.pi * t * freq)


def osc_triangle(t: np.ndarray, freq: float) -> np.ndarray:
    """三角波"""
    phase = (t * freq) % 1.0
    return 4.0 * np.abs(phase - 0.5) - 1.0


def osc_noise_white(n: int, rng: np.random.Generator | None = None) -> np.ndarray:
    """白噪声"""
    if rng is None:
        rng = np.random.default_rng()
    return 2.0 * rng.random(n) - 1.0


def _pink_noise_vectorized(n: int) -> np.ndarray:
    """向量化 Voss-McCarthy 粉红噪声生成。

    使用 NumPy 矩阵运算替代 Python for 循环，大幅提升长音频性能。

    Args:
        n: 样本数

    Returns:
        粉红噪声数组
    """
    num_octaves = 12
    # 预生成所有八度的白噪声
    white = np.random.randn(num_octaves, n)
    # 构建状态矩阵：每行每列是前一个状态的指数衰减
    states = np.zeros((num_octaves, n))
    decay = 0.998
    for i in range(1, n):
        states[:, i] = decay * states[:, i - 1] + white[:, i]
    # 每列取均值 + 轻微白噪声
    out = states.mean(axis=0) + white[0] * 0.05
    return out * 3.0


def _pink_noise_kernel(n: int) -> np.ndarray:
    """Voss-McCarthy pink noise 核 (fallback for short audio)."""
    if n > 10000:
        return _pink_noise_vectorized(n)
    # 短音频仍用原始实现（启动开销更小）
    out = np.zeros(n)
    states = np.zeros(12)
    for i in range(n):
        inc = np.random.randn()
        idx = i & (len(states) - 1)
        states[idx] = 0.998 * states[idx] + inc
        out[i] = states.mean() + inc * 0.05
    return out * 3.0


def osc_noise_pink(n: int) -> np.ndarray:
    """粉红噪声"""
    return _pink_noise_kernel(n)


def osc_noise_brown(n: int) -> np.ndarray:
    """棕噪声（随机游走）"""
    out = np.cumsum(2.0 * np.random.random(n) - 1.0)
    return out / (np.max(np.abs(out)) + 1e-8)


# ═══════ 统一接口 ═══════

_OSC_MAP = {
    OscType.SAW:         osc_saw,
    OscType.SQUARE:      osc_square,
    OscType.SINE:        osc_sine,
    OscType.TRIANGLE:    osc_triangle,
}


def oscillator(
    t: np.ndarray,
    freq: float,
    osc_type: OscType = OscType.SAW,
    duty: float = 0.5,
) -> np.ndarray:
    """统一振荡器接口。

    Args:
        t: 时间数组 (秒)
        freq: 基频 (Hz)
        osc_type: 波形类型
        duty: 方波占空比
    Returns:
        归一化 [-1, 1] 波形数组
    """
    if osc_type == OscType.NOISE_WHITE:
        return osc_noise_white(len(t))
    if osc_type == OscType.NOISE_PINK:
        return osc_noise_pink(len(t))
    if osc_type == OscType.NOISE_BROWN:
        return osc_noise_brown(len(t))

    fn = _OSC_MAP.get(osc_type, osc_saw)
    if osc_type == OscType.SQUARE:
        return fn(t, freq, duty)
    return fn(t, freq)
