"""mix_voices 测试 — N 路 SynthVoice 加权叠加（仿 bfxr Mixer）。"""

import numpy as np
import pytest

from bloodmusic.core.voice import SynthVoice
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape
from bloodmusic.core import synthesize_voice
from bloodmusic.sfx.layered import mix_voices


def _tone(freq=440.0, duration=0.2, volume=0.5):
    return SynthVoice(
        freq=freq, osc_type=OscType.SINE, duration=duration,
        volume=volume, env_shape=EnvShape.PERCUSSIVE,
    )


def test_basic_mix_length():
    v1 = _tone(440.0, 0.2)
    v2 = _tone(880.0, 0.35)
    mix = mix_voices([v1, v2])
    assert len(mix) == int(0.35 * 44100)


def test_mix_no_clipping():
    """输出归一化后无削波（峰值 ≤ 1.0）。"""
    voices = [_tone(f, 0.3, 0.9) for f in (220, 440, 880, 1760)]
    mix = mix_voices(voices)
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6


def test_weights_affect_output():
    v1 = _tone(440.0, 0.2, 0.8)
    v2 = _tone(880.0, 0.2, 0.8)
    a = mix_voices([v1, v2], weights=[1.0, 0.0], normalize=False)
    b = mix_voices([v1, v2], weights=[0.0, 1.0], normalize=False)
    assert not np.array_equal(a, b), "weights should change mix output"


def test_equal_weights_equals_mean():
    """等权混合 = 各路之和（normalize=False 时）。"""
    v1 = _tone(440.0, 0.2)
    v2 = _tone(880.0, 0.2)
    mix = mix_voices([v1, v2], weights=[1.0, 1.0], normalize=False)
    s1 = synthesize_voice(v1).astype(np.float64)
    s2 = synthesize_voice(v2).astype(np.float64)
    expected = s1 + s2
    assert np.allclose(mix, expected, atol=1e-6)


def test_normalize_peak_target():
    """归一化到 -1dBFS：峰值 ≈ 10^(-1/20) ≈ 0.8913。"""
    mix = mix_voices([_tone(440.0, 0.2, 0.3)])
    peak = float(np.max(np.abs(mix)))
    assert abs(peak - (10 ** (-1.0 / 20))) < 0.01


def test_empty_voices_raises():
    with pytest.raises(ValueError):
        mix_voices([])


def test_weight_length_mismatch_raises():
    with pytest.raises(ValueError):
        mix_voices([_tone()], weights=[1.0, 2.0])


def test_non_voice_raises():
    with pytest.raises(TypeError):
        mix_voices(["not-a-voice"])


def test_single_voice_passthrough():
    v = _tone(660.0, 0.25)
    mix = mix_voices([v], normalize=False)
    assert np.allclose(mix, synthesize_voice(v), atol=1e-6)


def test_five_way_mix_bfxr_style():
    """5 路叠加（bfxr Mixer 上限）应正常输出。"""
    voices = [_tone(f, 0.3) for f in (330, 440, 550, 660, 880)]
    mix = mix_voices(voices, weights=[0.6, 0.8, 0.4, 0.7, 0.5])
    assert mix.size > 0
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6
