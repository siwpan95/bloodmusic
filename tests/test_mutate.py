"""变异(mutation)引擎测试 — mutate / randomize / locked fields。"""

import numpy as np
import pytest

from bloodmusic.core import synthesize_voice
from bloodmusic.sfx.presets import UI_FX_PRESETS
from bloodmusic.sfx.mutate import (
    mutate_voice, randomize_voice, mutate_preset, get_preset, ALL_PRESETS,
)


def test_mutate_changes_audio():
    """变异后音频与原不同（听感变化）。"""
    base = UI_FX_PRESETS["button_click"]
    variant = mutate_voice(base, amount=0.2)
    a = synthesize_voice(base)
    b = synthesize_voice(variant)
    assert not np.array_equal(a, b), "mutated voice should differ from original"


def test_mutate_preserves_structure():
    """变异保留枚举/结构字段（osc_type/env_shape 不变）。"""
    base = UI_FX_PRESETS["button_click"]
    variant = mutate_voice(base, amount=0.2)
    assert variant.osc_type == base.osc_type
    assert variant.env_shape == base.env_shape


def test_locked_field_unchanged():
    """锁定 freq 后变异，freq 保持不变。"""
    base = UI_FX_PRESETS["button_click"]
    variant = mutate_voice(base, amount=0.3, locked_fields={"freq"})
    assert variant.freq == base.freq, "locked freq must not change"


def test_locked_nested_field_unchanged():
    """锁定 effect_chain.reverb_mix 后变异，该字段不变。"""
    base = UI_FX_PRESETS["menu_open"]  # 带 reverb_mix=0.15
    assert base.effect_chain is not None
    variant = mutate_voice(base, amount=0.5, locked_fields={"effect_chain.reverb_mix"})
    assert variant.effect_chain.reverb_mix == base.effect_chain.reverb_mix


def test_original_not_modified():
    """mutate 不得修改原对象（deepcopy 语义）。"""
    base = UI_FX_PRESETS["button_click"]
    orig_freq = base.freq
    orig_chain = base.effect_chain
    mutate_voice(base, amount=0.2)
    assert base.freq == orig_freq
    assert base.effect_chain is orig_chain


def test_mutate_preset_count_and_uniqueness():
    """mutate_preset 生成 n 个互不相同的变体。"""
    variants = mutate_preset("button_click", n=5, amount=0.2)
    assert len(variants) == 5
    freqs = [v.freq for v in variants]
    assert len(set(freqs)) == 5, "variants should differ from each other"


def test_mutate_preset_unknown_name():
    with pytest.raises(KeyError):
        mutate_preset("no_such_preset")


def test_randomize_produces_valid_voice():
    """randomize 生成的 voice 可正常合成。"""
    v = randomize_voice()
    audio = synthesize_voice(v)
    assert audio.size > 0
    assert np.max(np.abs(audio)) <= 1.0 + 1e-6


def test_randomize_locked_freq():
    base = UI_FX_PRESETS["button_click"]
    v = randomize_voice(base=base, locked_fields={"freq"})
    assert v.freq == base.freq


def test_randomize_without_base_has_full_structure():
    v = randomize_voice()
    assert v.effect_chain is not None
    assert 0.0 < v.duration < 1.0


def test_all_presets_registry():
    """ALL_PRESETS 含四类全部预设。"""
    assert "button_click" in ALL_PRESETS
    assert "card_play" in ALL_PRESETS
    total = len(UI_FX_PRESETS) + len(ALL_PRESETS)
    assert total > len(UI_FX_PRESETS)
    assert get_preset("button_click") is UI_FX_PRESETS["button_click"]
