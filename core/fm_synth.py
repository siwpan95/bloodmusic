"""FM 合成 —— FMSynthVoice 参数定义 + 合成引擎"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Tuple

from .constants import SR
from .oscillator import oscillator, OscType
from .envelope import make_envelope, EnvShape, ADSRParams
from .voice import LFOParams


@dataclass
class FMSynthVoice:
    """FM 合成参数（双算子：carrier + modulator）"""
    carrier_freq: float = 440.0
    carrier_type: OscType = OscType.SINE
    modulator_freq_ratio: float = 1.0      # modulator_freq = carrier_freq * ratio
    modulator_type: OscType = OscType.SINE
    fm_depth: float = 100.0                 # FM 调制深度 (Hz)
    duration: float = 0.3
    volume: float = 1.0
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional["EffectChain"] = None
    lfo: Optional[LFOParams] = None


def synthesize_fm_voice(voice: FMSynthVoice) -> np.ndarray:
    """合成 FM 声音为 float32 波形。

    Args:
        voice: FMSynthVoice 参数
    Returns:
        float32 波形数组
    """
    n_samples = max(int(voice.duration * SR), 1)
    t = np.linspace(0, voice.duration, n_samples, dtype=np.float64)

    # 调制器
    mod_freq = voice.carrier_freq * voice.modulator_freq_ratio
    modulator_sig = oscillator(t, mod_freq, voice.modulator_type)

    # FM: carrier_freq + fm_depth * modulator
    modulated_freq = voice.carrier_freq + voice.fm_depth * modulator_sig

    # 载波（注意：对噪声类型不适用FM，降级为普通振荡器）
    if voice.carrier_type in (OscType.NOISE_WHITE, OscType.NOISE_PINK, OscType.NOISE_BROWN):
        carrier_sig = oscillator(t, voice.carrier_freq, voice.carrier_type)
    else:
        carrier_sig = oscillator(t, modulated_freq, voice.carrier_type)

    # LFO 调制
    if voice.lfo is not None and voice.lfo.depth > 0:
        lfo_sig = np.sin(2 * np.pi * voice.lfo.rate * t)
        if voice.lfo.target.value == "amplitude":
            carrier_sig = carrier_sig * (1.0 + lfo_sig * voice.lfo.depth).clip(0.0)
        elif voice.lfo.target.value == "pitch":
            pitch_mod_factor = 1.0 + lfo_sig * voice.lfo.depth * 0.01
            carrier_sig = oscillator(t, modulated_freq * pitch_mod_factor, voice.carrier_type)

    # 包络
    env = make_envelope(n_samples, voice.env_shape, voice.adsr)
    sig = carrier_sig * env * voice.volume

    # 效果链
    if voice.effect_chain is not None:
        from bloodmusic.effects.chain import process_effects
        sig = process_effects(sig, voice.effect_chain)

    # 安全限幅
    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak * 0.98

    return sig.astype(np.float32)
