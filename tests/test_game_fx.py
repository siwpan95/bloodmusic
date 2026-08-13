"""GAME_FX_PRESETS 测试 — sfxr 经典 8 类游戏通用预设。"""

import numpy as np
import pytest

from bloodmusic.core import synthesize_voice
from bloodmusic.sfx.presets import GAME_FX_PRESETS
from bloodmusic.sfx.mutate import ALL_PRESETS


#: sfxr 经典 8 类名称
SFRX_CLASSICS = [
    "pickup_coin", "laser_shoot", "explosion", "power_up",
    "hit_hurt", "jump", "blip_select", "random_pick",
]


def test_all_8_classes_present():
    assert set(SFRX_CLASSICS) <= set(GAME_FX_PRESETS)


def test_each_preset_synthesizes_nonzero_audio():
    for name in SFRX_CLASSICS:
        voice = GAME_FX_PRESETS[name]
        audio = synthesize_voice(voice)
        assert audio.size > 0, f"{name}: empty audio"
        assert float(np.max(np.abs(audio))) > 1e-3, f"{name}: near-silent audio"


def test_no_clipping():
    for name in SFRX_CLASSICS:
        audio = synthesize_voice(GAME_FX_PRESETS[name])
        peak = float(np.max(np.abs(audio)))
        assert peak <= 1.0 + 1e-6, f"{name}: clipping at {peak}"


def test_distinct_timbres():
    """8 类之间音频应互不相同。"""
    audios = [synthesize_voice(GAME_FX_PRESETS[n]) for n in SFRX_CLASSICS]
    max_len = max(len(a) for a in audios)
    padded = [np.pad(a, (0, max_len - len(a))) for a in audios]
    for i in range(len(padded)):
        for j in range(i + 1, len(padded)):
            assert not np.array_equal(padded[i], padded[j]), (
                f"{SFRX_CLASSICS[i]} and {SFRX_CLASSICS[j]} identical"
            )


def test_registered_in_all_presets():
    for name in SFRX_CLASSICS:
        assert name in ALL_PRESETS, f"{name} not in ALL_PRESETS"


def test_serialize_roundtrip():
    """8 类预设可经序列化往返且参数完全一致（与 T4 集成）。

    注意: 噪声类预设 (explosion 的 NOISE_BROWN) 合成结果本身随机，
    因此按参数级相等验证，而非音频位一致。
    """
    from bloodmusic.sfx.serialize import voice_to_compact, voice_from_compact
    for name in SFRX_CLASSICS:
        voice = GAME_FX_PRESETS[name]
        restored = voice_from_compact(voice_to_compact(voice))
        assert restored == voice, f"{name}: params differ after roundtrip"
