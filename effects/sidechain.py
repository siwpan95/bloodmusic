"""
侧链压缩 / Sidechain Ducking 效果
=================================

实现电子音乐最核心的制作技巧之一：当触发信号（如底鼓）出现时，
自动降低目标信号（如贝斯/合成器）的音量，产生"呼吸/泵动"效果。

技术原理:
    1. 从触发信号提取包络 (全波整流 + RMS/峰值检测)
    2. 计算增益衰减曲线 (attack/release)
    3. 将衰减曲线应用到目标信号

使用方式:
    >>> from bloodmusic.effects.sidechain import sidechain_duck
    >>> bass_ducked = sidechain_duck(bass_sig, kick_sig, attack_ms=10, release_ms=150)

参考:
    - "Seeing Sound: Generative Techno and DSP in Pure NumPy" (msuiche.com)
    - 经典 909 泵动效果: attack 10-30ms, ratio 4:1, release 100-200ms
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional

from ..core.constants import SR as _SR


@dataclass
class SidechainParams:
    """侧链压缩参数"""
    threshold_db: float = -20.0    # 阈值 (dB)
    ratio: float = 4.0             # 压缩比 (1:1 ~ inf:1)
    attack_ms: float = 10.0        # 启动时间 (ms)
    release_ms: float = 150.0      # 释放时间 (ms)
    knee_db: float = 3.0           # 软拐点宽度 (dB)
    makeup_gain_db: float = 0.0    # 补偿增益 (dB)
    floor: float = 0.25            # 最小增益 (0~1，即最小衰减到的比例)


def sidechain_duck(
    target_sig: np.ndarray,
    trigger_sig: np.ndarray,
    params: Optional[SidechainParams] = None,
    sr: int = _SR,
) -> np.ndarray:
    """侧链压缩：当 trigger 信号超过阈值时压缩 target 信号。

    这是标准侧链压缩器的简化实现。使用包络跟随 + 增益衰减曲线。

    Args:
        target_sig: 目标信号 (被压缩/duck 的信号)
        trigger_sig: 触发信号 (通常是底鼓轨道)
        params: 侧链参数，None 使用默认值
        sr: 采样率

    Returns:
        处理后的目标信号

    Example:
        >>> params = SidechainParams(threshold_db=-18, ratio=4, attack_ms=5, release_ms=120)
        >>> bass_ducked = sidechain_duck(bass_sig, kick_sig, params)
    """
    if params is None:
        params = SidechainParams()

    # 确保长度一致
    n = min(len(target_sig), len(trigger_sig))
    target = target_sig[:n].copy()
    trigger = trigger_sig[:n]

    # 1. 计算触发信号的包络 (全波整流 + 指数平滑)
    trigger_env = np.abs(trigger)
    # 简单的 RMS 包络: 快速启动 + 指数衰减
    attack_coeff = np.exp(-1.0 / (params.attack_ms / 1000.0 * sr))
    release_coeff = np.exp(-1.0 / (params.release_ms / 1000.0 * sr))

    env = np.zeros(n)
    env[0] = trigger_env[0]
    for i in range(1, n):
        if trigger_env[i] > env[i - 1]:
            # 启动: 跟随信号
            coeff = attack_coeff
        else:
            # 释放: 指数衰减
            coeff = release_coeff
        env[i] = coeff * env[i - 1] + (1.0 - coeff) * trigger_env[i]

    # 2. 计算增益衰减 (dB 域)
    # 将包络转为 dB
    eps = 1e-10
    env_db = 20.0 * np.log10(env + eps)

    # 超过阈值的部分
    over_threshold = env_db - params.threshold_db

    # 应用软拐点
    if params.knee_db > 0:
        knee_half = params.knee_db / 2.0
        # 软拐点区域
        soft_knee_mask = np.abs(over_threshold) <= knee_half
        gain_reduction_db = np.where(
            soft_knee_mask,
            (over_threshold + knee_half) ** 2 / (2.0 * params.knee_db) * (1.0 - 1.0 / params.ratio),
            np.maximum(0, over_threshold) * (1.0 - 1.0 / params.ratio),
        )
    else:
        # 硬拐点
        gain_reduction_db = np.maximum(0, over_threshold) * (1.0 - 1.0 / params.ratio)

    # 3. 转换为线性增益
    gain_linear = 10.0 ** (-gain_reduction_db / 20.0)  # 增益衰减 → 乘数
    gain_linear = np.clip(gain_linear, params.floor, 1.0)

    # 补偿增益
    if params.makeup_gain_db != 0:
        makeup_linear = 10.0 ** (params.makeup_gain_db / 20.0)
        gain_linear *= makeup_linear

    # 4. 应用增益
    result = target * gain_linear

    return result


def sidechain_envelope_method(
    target_sig: np.ndarray,
    kick_positions: list,  # 底鼓 hit 位置 (采样索引)
    floor: float = 0.4,
    attack_ms: float = 5.0,
    release_ms: float = 220.0,
    sr: int = _SR,
) -> np.ndarray:
    """基于包络形状的侧链 ducking (更简单、更音乐化)。

    与上面的 full sidechain 压缩不同，这个方法直接在底鼓位置叠加
    预设的 attack-release 包络曲线。更适合电子音乐制作。

    Args:
        target_sig: 目标信号
        kick_positions: 底鼓触发位置列表 (采样索引)
        floor: 最小增益 (0~1, 0.4 ≈ -8dB)
        attack_ms: 启动时间 (ms)
        release_ms: 释放时间 (ms)
        sr: 采样率

    Returns:
        处理后的信号

    典型参数:
        - Dark Techno:  attack=1-5ms,   release=200-300ms
        - House/Melodic: attack=10-30ms, release=100-200ms

    Reference:
        msuiche.com "Seeing Sound: Generative Techno and DSP in Pure NumPy"
    """
    n = len(target_sig)
    target = target_sig.copy()

    # 构建包络冲激响应
    attack_n = int(attack_ms / 1000.0 * sr)
    release_n = int(release_ms / 1000.0 * sr)

    shape = np.ones(attack_n + release_n)
    # 线性 attack
    shape[:attack_n] = np.linspace(1.0, floor, attack_n)
    # 指数 release
    rel_t = np.linspace(0, 5, release_n)
    shape[attack_n:] = 1.0 - (1.0 - floor) * np.exp(-rel_t)

    # 在所有 kick 位置叠加包络
    env = np.ones(n)
    for pos in kick_positions:
        if pos < 0 or pos >= n:
            continue
        end = min(pos + len(shape), n)
        seg_len = end - pos
        env[pos:end] = np.minimum(env[pos:end], shape[:seg_len])

    return target * env


def detect_transients(
    sig: np.ndarray,
    threshold: float = 0.3,
    min_gap_ms: float = 50.0,
    sr: int = _SR,
) -> list:
    """检测信号中的瞬态位置 (用于自动识别底鼓等触发信号)。

    Args:
        sig: 输入信号
        threshold: 检测阈值 (归一化幅度)
        min_gap_ms: 两次检测之间的最小间隔 (ms)
        sr: 采样率

    Returns:
        瞬态位置列表 (采样索引)
    """
    min_gap = int(min_gap_ms / 1000.0 * sr)
    envelope = np.abs(sig)

    # 滑动窗口检测峰值
    window = int(0.005 * sr)  # 5ms 窗口
    positions = []
    last_pos = -min_gap

    for i in range(window, len(sig) - window):
        if i - last_pos < min_gap:
            continue
        if envelope[i] > threshold:
            # 检查是否是局部峰值
            if envelope[i] >= np.max(envelope[i - window:i + window]):
                positions.append(i)
                last_pos = i

    return positions


# ══════════════════════════════════════════════════════════════
# Drum Bus Glue Compression
# ══════════════════════════════════════════════════════════════

def drum_bus_compressor(
    drum_mix: np.ndarray,
    threshold_db: float = -12.0,
    ratio: float = 4.0,
    attack_ms: float = 3.0,
    release_ms: float = 80.0,
    makeup_gain_db: float = 3.0,
    sr: int = _SR,
) -> np.ndarray:
    """鼓组总线压缩 — 将所有鼓粘合在一起。

    类似 SSL G-Bus Compressor 的效果。对鼓组整体应用温和压缩，
    增加凝聚力和冲击力。

    Args:
        drum_mix: 鼓组混合信号
        threshold_db: 阈值 (dB)
        ratio: 压缩比
        attack_ms: 启动 (ms), 鼓组通常 1-10ms
        release_ms: 释放 (ms), 鼓组通常 50-150ms
        makeup_gain_db: 补偿增益 (dB)
        sr: 采样率

    Returns:
        压缩后的鼓组信号
    """
    params = SidechainParams(
        threshold_db=threshold_db,
        ratio=ratio,
        attack_ms=attack_ms,
        release_ms=release_ms,
        knee_db=2.0,
        makeup_gain_db=makeup_gain_db,
        floor=0.1,
    )
    # 自侧链：信号自身触发压缩
    return sidechain_duck(drum_mix, drum_mix, params, sr)
