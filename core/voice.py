"""
合成核心 —— SynthVoice 参数定义 + 合成引擎
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .constants import SR
from .oscillator import oscillator, OscType
from .envelope import make_envelope, EnvShape, ADSRParams


class LFOTarget(Enum):
    """LFO 调制目标"""
    AMPLITUDE = "amplitude"
    FILTER_CUTOFF = "filter_cutoff"
    PITCH = "pitch"


@dataclass
class LFOParams:
    """LFO 调制参数"""
    rate: float = 0.0          # LFO 频率 (Hz)
    depth: float = 0.0         # 调制深度
    target: LFOTarget = LFOTarget.AMPLITUDE  # 调制目标


@dataclass
class SynthVoice:
    """单音合成参数"""
    freq: float = 440.0
    osc_type: OscType = OscType.SINE
    duration: float = 0.15               # 秒
    volume: float = 1.0
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional["EffectChain"] = None  # 延迟导入
    pitch_mod: float = 0.0               # 音高变化量 (半音)
    vibrato_rate: float = 0.0            # 颤音频率 (Hz)
    vibrato_depth: float = 0.0           # 颤音深度 (半音)
    detune: float = 0.0                  # Unison 不协和度
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    """泛音列表: [(倍频, 相对振幅), ...]"""
    lfo: Optional[LFOParams] = None      # LFO 调制参数


def synthesize_voice(voice: SynthVoice) -> np.ndarray:
    """合成单个 SynthVoice 为 float32 波形。

    Args:
        voice: SynthVoice 参数
    Returns:
        float32 波形数组，范围约 [-1, 1]
    """
    n_samples = max(int(voice.duration * SR), 1)
    t = np.linspace(0, voice.duration, n_samples, dtype=np.float64)

    # 基础频率 + 音高偏移
    base_freq = voice.freq * (2 ** (voice.pitch_mod / 12))

    # 颤音调制
    if voice.vibrato_depth > 0 and voice.vibrato_rate > 0:
        vib_env = make_envelope(n_samples, EnvShape.PAD)[:n_samples]
        vib = 1.0 + (voice.vibrato_depth / 12) * np.sin(
            2 * np.pi * voice.vibrato_rate * t) * vib_env
        mod_freq = base_freq * vib
    else:
        mod_freq = np.full(n_samples, base_freq)

    # 主振荡器
    main_sig = oscillator(t, mod_freq, voice.osc_type)

    # 泛音叠加
    for harmonic_mult, harmonic_amp in voice.harmonics:
        h_sig = oscillator(t, mod_freq * harmonic_mult, voice.osc_type)
        main_sig += h_sig * harmonic_amp

    # Unison detune
    if abs(voice.detune) > 0.001:
        detune_sig = oscillator(
            t, mod_freq * (2 ** (voice.detune / 12)), voice.osc_type
        ) * 0.6
        main_sig += detune_sig

    # LFO 调制
    if voice.lfo is not None and voice.lfo.depth > 0:
        lfo_sig = np.sin(2 * np.pi * voice.lfo.rate * t)
        if voice.lfo.target == LFOTarget.AMPLITUDE:
            mod_env = (1.0 + lfo_sig * voice.lfo.depth).clip(0.0)
            main_sig = main_sig * mod_env
        elif voice.lfo.target == LFOTarget.PITCH:
            pitch_mod_factor = 1.0 + lfo_sig * voice.lfo.depth * 0.01
            main_sig = oscillator(t, mod_freq * pitch_mod_factor, voice.osc_type)
        elif voice.lfo.target == LFOTarget.FILTER_CUTOFF:
            pass  # 滤波器调制在效果链中处理

    # 包络
    env = make_envelope(n_samples, voice.env_shape, voice.adsr)
    sig = main_sig * env * voice.volume

    # 效果链
    if voice.effect_chain is not None:
        from bloodmusic.effects.chain import process_effects
        sig = process_effects(sig, voice.effect_chain)

    # 安全限幅
    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak * 0.98

    return sig.astype(np.float32)
