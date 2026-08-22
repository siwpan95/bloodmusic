# -*- coding: utf-8 -*-
"""
test_new_engines.py —— SPECTRUM 新并入引擎冒烟测试
====================================================

覆盖 core/additive.py（加法合成）、core/modal.py（模态合成）、
core/hybrid.py（混合合成）、sfx/material.py（材质撞击 SFX）：
每引擎合成一段音频，断言长度正确、数值有限、能量非零（非静音）。
（对应 D 盘评估报告中「新引擎零测试覆盖」的补强项）
"""

from __future__ import annotations

import numpy as np
import pytest

from bloodmusic.core.additive import additive_synth
from bloodmusic.core.modal import modal_synth
from bloodmusic.core.hybrid import hybrid_synth, HYBRID_PRESETS
from bloodmusic.sfx.material import (
    synthesize_material_impact,
    render_all_materials,
    MATERIAL_PRESETS,
)

SR = 44100
T_1S = np.linspace(0.0, 1.0, SR, dtype=np.float64)


def _assert_audio(audio: np.ndarray, expected_len: int) -> None:
    assert len(audio) == expected_len, f"长度不符: {len(audio)} != {expected_len}"
    assert np.all(np.isfinite(audio)), "存在非有限值 (NaN/Inf)"
    peak = float(np.max(np.abs(audio)))
    assert peak > 1e-4, f"输出近乎静音: peak={peak:.2e}"


# ═══════════════════════ 加法合成 ═══════════════════════

def test_additive_synth_non_silent():
    audio = additive_synth(freq=440.0, t=T_1S, volume=0.8)
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


def test_additive_synth_custom_partials():
    """自定义分音配置（engine_params）也应产出有效音频。"""
    audio = additive_synth(
        freq=220.0, t=T_1S, volume=0.6,
        engine_params={"partials": [(1.0, 1.0), (2.0, 0.5), (3.0, 0.3)]},
    )
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


# ═══════════════════════ 模态合成 ═══════════════════════

def test_modal_synth_non_silent():
    audio = modal_synth(freq=330.0, t=T_1S, volume=0.8)
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


def test_modal_synth_custom_modes():
    audio = modal_synth(
        freq=330.0, t=T_1S, volume=0.6,
        engine_params={"modes": [(1.0, 0.5, 2.0), (2.7, 0.2, 8.0)]},
    )
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


# ═══════════════════════ 混合合成 ═══════════════════════

@pytest.mark.parametrize("preset", ["bell_metal", "glass_strike", "hybrid_pad"])
def test_hybrid_synth_presets_non_silent(preset):
    assert preset in HYBRID_PRESETS, f"预设缺失: {preset}"
    audio = hybrid_synth(freq=440.0, t=T_1S, volume=0.7,
                         engine_params={"preset": preset})
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


def test_hybrid_synth_default_non_silent():
    audio = hybrid_synth(freq=440.0, t=T_1S)
    _assert_audio(np.asarray(audio, dtype=np.float64), SR)


# ═══════════════════════ 材质撞击 SFX ═══════════════════════

@pytest.mark.parametrize("material", ["wood", "metal", "glass", "stone"])
def test_material_impact_non_silent(material):
    if material not in MATERIAL_PRESETS:
        pytest.skip(f"材质未注册: {material}")
    audio = synthesize_material_impact(material=material, velocity=0.9, duration=0.4)
    _assert_audio(np.asarray(audio, dtype=np.float64), int(0.4 * SR))
    # 归一化输出不应削波
    assert float(np.max(np.abs(audio))) <= 0.96


def test_render_all_materials():
    all_materials = render_all_materials(duration=0.3, velocity=0.8)
    assert all_materials, "render_all_materials 返回空字典"
    for name, audio in all_materials.items():
        _assert_audio(np.asarray(audio, dtype=np.float64), int(0.3 * SR))


# ═══════════════════════ 引擎注册一致性 ═══════════════════════

def test_new_engines_registered_in_synth_engine():
    """四个新引擎必须已注册进 SynthEngine 枚举（SPECTRUM 乐器池依赖它）。"""
    from bloodmusic.music.instrument_pool import SynthEngine
    values = {e.value for e in SynthEngine}
    for name in ("additive", "modal", "hybrid", "material"):
        assert name in values, f"SynthEngine 缺少 {name}"
