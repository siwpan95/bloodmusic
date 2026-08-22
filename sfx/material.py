"""Material-aware 程序化音效系统
=================================

把"撞击 / 脚步 / 着落"等游戏音效建模为**材质参数**而非采样：
同一套合成逻辑，由 material 参数（共振频率、衰减、明亮度、碎屑量、
音高下沉）驱动出 concrete / wood / metal / gravel / glass / stone /
ice / ceramic / water / sand 等截然不同的撞击质感。

这正是 Wwise·FMOD 文献里"Material-aware SFX"的程序化落地——
footstep 的 surface（concrete/wood/metal/gravel）共振频率不同，
不应每件材质一个采样，而应一个合成器 + 材质参数集。

用法:
    >>> from bloodmusic.sfx.material import synthesize_material_impact
    >>> wood_step = synthesize_material_impact("wood", velocity=0.8, duration=0.25)
    >>> metal_hit = synthesize_material_impact("metal", velocity=1.0, duration=0.6)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Any

from ..core.constants import SR
from ..effects.filters import (
    apply_highpass, apply_lowpass, apply_bandpass,
)


@dataclass
class MaterialImpactParams:
    """单一材质的撞击参数。

    Attributes:
        base_freq: 主体音调基频 (Hz)，给撞击一个"音高"。
        tone_decay: 音调主体衰减时间 (秒)。
        noise_decay: 噪声瞬态衰减时间 (秒)。
        brightness: 明亮度 0~1，映射高通截止 (高频越多越亮)。
        resonances: 共振峰频率列表 (Hz)，并行带通着色出材质"音色指纹"。
        debris: 碎屑颗粒量 0~1 (短促 granular 噪声)。
        pitch_drop: 撞击瞬间音高下沉比例 0~1。
        lowpass: 整体低通截止 (Hz)，限制高频毛刺。
        tone_level: 音调分量音量。
        noise_level: 噪声瞬态分量音量。
        body_level: 共振体分量音量。
    """
    base_freq: float = 400.0
    tone_decay: float = 0.12
    noise_decay: float = 0.05
    brightness: float = 0.5
    resonances: List[float] = field(default_factory=list)
    debris: float = 0.3
    pitch_drop: float = 0.4
    lowpass: float = 9000.0
    tone_level: float = 0.6
    noise_level: float = 0.7
    body_level: float = 0.5


# 各材质的物理/听感特征（音频工程师经验值）
MATERIAL_PRESETS: Dict[str, MaterialImpactParams] = {
    "wood": MaterialImpactParams(
        base_freq=320.0, tone_decay=0.10, noise_decay=0.04,
        brightness=0.45, resonances=[320, 640, 1100], debris=0.25,
        pitch_drop=0.5, lowpass=6000.0, tone_level=0.7, noise_level=0.6, body_level=0.5,
    ),
    "concrete": MaterialImpactParams(
        base_freq=180.0, tone_decay=0.05, noise_decay=0.06,
        brightness=0.7, resonances=[500, 1500, 3000], debris=0.5,
        pitch_drop=0.3, lowpass=11000.0, tone_level=0.4, noise_level=0.9, body_level=0.4,
    ),
    "metal": MaterialImpactParams(
        base_freq=900.0, tone_decay=0.45, noise_decay=0.04,
        brightness=0.9, resonances=[900, 1900, 3100, 5200, 7400], debris=0.15,
        pitch_drop=0.2, lowpass=14000.0, tone_level=0.7, noise_level=0.4, body_level=0.9,
    ),
    "gravel": MaterialImpactParams(
        base_freq=120.0, tone_decay=0.03, noise_decay=0.10,
        brightness=0.4, resonances=[400, 900], debris=0.85,
        pitch_drop=0.1, lowpass=5000.0, tone_level=0.2, noise_level=1.0, body_level=0.3,
    ),
    "glass": MaterialImpactParams(
        base_freq=2600.0, tone_decay=0.22, noise_decay=0.03,
        brightness=0.95, resonances=[2600, 4200, 6800, 9500], debris=0.2,
        pitch_drop=0.15, lowpass=16000.0, tone_level=0.7, noise_level=0.35, body_level=0.85,
    ),
    "stone": MaterialImpactParams(
        base_freq=220.0, tone_decay=0.08, noise_decay=0.07,
        brightness=0.4, resonances=[280, 700, 1400], debris=0.45,
        pitch_drop=0.25, lowpass=7000.0, tone_level=0.4, noise_level=0.85, body_level=0.45,
    ),
    "ice": MaterialImpactParams(
        base_freq=1800.0, tone_decay=0.14, noise_decay=0.05,
        brightness=0.92, resonances=[1800, 3400, 5600], debris=0.55,
        pitch_drop=0.2, lowpass=15000.0, tone_level=0.5, noise_level=0.6, body_level=0.6,
    ),
    "ceramic": MaterialImpactParams(
        base_freq=1200.0, tone_decay=0.18, noise_decay=0.03,
        brightness=0.8, resonances=[1200, 2300, 3700], debris=0.2,
        pitch_drop=0.18, lowpass=13000.0, tone_level=0.7, noise_level=0.4, body_level=0.8,
    ),
    "water": MaterialImpactParams(
        base_freq=160.0, tone_decay=0.06, noise_decay=0.12,
        brightness=0.55, resonances=[300, 800], debris=0.7,
        pitch_drop=0.1, lowpass=4000.0, tone_level=0.3, noise_level=0.95, body_level=0.3,
    ),
    "sand": MaterialImpactParams(
        base_freq=90.0, tone_decay=0.02, noise_decay=0.05,
        brightness=0.3, resonances=[200, 500], debris=0.6,
        pitch_drop=0.05, lowpass=3000.0, tone_level=0.1, noise_level=0.95, body_level=0.2,
    ),
}


def _impact_tone(p: MaterialImpactParams, t: np.ndarray, sr: int) -> np.ndarray:
    """音调主体：基频正弦 + 撞击瞬间指数音高下沉 + 振幅衰减。"""
    f_start = p.base_freq * (1.0 + p.pitch_drop)
    f_end = p.base_freq
    freq = f_end + (f_start - f_end) * np.exp(-t / max(p.tone_decay * 0.4, 1e-3))
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    tone = np.sin(phase)
    amp_env = np.exp(-t / max(p.tone_decay, 1e-3))
    return tone * amp_env * p.tone_level


def _noise_burst(p: MaterialImpactParams, n: int, sr: int) -> np.ndarray:
    """噪声瞬态：白噪声 + 快速衰减 + 明亮度高通。"""
    noise = np.random.uniform(-1, 1, n)
    amp_env = np.exp(-np.arange(n) / max(int(p.noise_decay * sr), 1))
    noise = noise * amp_env * p.noise_level
    hp = 500.0 + p.brightness * 6000.0
    return apply_highpass(noise, hp)


def _resonant_body(p: MaterialImpactParams, n: int, sr: int) -> np.ndarray:
    """共振体：白噪声经并行带通（材质共振峰）着色，模拟物体"音色指纹"。"""
    if not p.resonances:
        return np.zeros(n)
    noise = np.random.uniform(-1, 1, n)
    body = np.zeros(n)
    for f in p.resonances:
        q = 6.0 + p.brightness * 10.0
        band = apply_bandpass(noise, f, q=q)
        body += band
    # 共振体比瞬态更长（物体余响）
    decay = np.exp(-np.arange(n) / max(int(p.tone_decay * 1.5 * sr), 1))
    body = body * decay * p.body_level
    return body


def _debris(p: MaterialImpactParams, n: int, sr: int) -> np.ndarray:
    """碎屑：短促随机颗粒（granular 噪声），量由 debris 参数控制。"""
    if p.debris <= 0:
        return np.zeros(n)
    out = np.zeros(n)
    n_grains = int(p.debris * 40)
    grain_len = max(20, int(0.004 * sr))
    for _ in range(n_grains):
        pos = np.random.randint(0, max(1, n - grain_len))
        grain = np.random.uniform(-1, 1, grain_len)
        g_env = np.exp(-np.arange(grain_len) / max(int(0.0015 * sr), 1))
        out[pos:pos + grain_len] += grain * g_env
    # 碎屑偏高频
    out = apply_highpass(out, 1500.0 + p.brightness * 4000.0)
    return out * 0.4


def synthesize_material_impact(
    material: str = "wood",
    velocity: float = 1.0,
    duration: float = 0.4,
    sr: int = SR,
) -> np.ndarray:
    """合成材质感知撞击音效。

    Args:
        material: 材质名（见 MATERIAL_PRESETS.keys()）。
        velocity: 敲击力度 0~1，影响音量与音高。
        duration: 总时长 (秒)。
        sr: 采样率。

    Returns:
        音频数组 (float64, 归一化 -1~1)。
    """
    p = MATERIAL_PRESETS.get(material, MATERIAL_PRESETS["wood"])
    # velocity 调制：力度越大音量越大、音高略升
    p = MaterialImpactParams(
        **{**p.__dict__, "base_freq": p.base_freq * (1.0 + 0.15 * velocity)},
    )
    p.tone_level *= (0.5 + 0.5 * velocity)
    p.noise_level *= (0.5 + 0.5 * velocity)

    n = int(duration * sr)
    if n < 1:
        n = 1
    t = np.linspace(0, duration, n, dtype=np.float64)

    sig = (
        _impact_tone(p, t, sr)
        + _noise_burst(p, n, sr)
        + _resonant_body(p, n, sr)
        + _debris(p, n, sr)
    )

    sig = apply_lowpass(sig, p.lowpass)

    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak * 0.95
    return sig.astype(np.float64)


# 便捷：一次渲染所有材质（用于试听 / 验证）
def render_all_materials(duration: float = 0.4, velocity: float = 1.0) -> Dict[str, np.ndarray]:
    """渲染所有材质撞击，返回 {材质名: 音频}。"""
    return {
        name: synthesize_material_impact(name, velocity=velocity, duration=duration)
        for name in MATERIAL_PRESETS
    }
