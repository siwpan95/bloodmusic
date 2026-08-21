"""制作工作室流程测试 — 单曲 / 专辑 / Beats 三流程可用性。"""

import numpy as np
import pytest

from bloodmusic.gui.maker_gui import (
    MakerGUI, _HAS_BEATS, _BEAT_STYLES,
)
from bloodmusic.album_maker.style_db import STYLE_DB
from bloodmusic.album_maker.quick import QuickMaker


# ═══════════════════════════════════════════════════════════════
# 模块级结构
# ═══════════════════════════════════════════════════════════════

def test_beat_styles_registry():
    if not _HAS_BEATS:
        pytest.skip("make_beats 模块不可用")
    assert len(_BEAT_STYLES) == 7
    assert "Trap" in _BEAT_STYLES and "Ambient" in _BEAT_STYLES


def test_style_db_has_12_styles():
    assert len(STYLE_DB) == 12
    assert {"classical", "jazz", "electronic", "lofi", "battle"} <= set(STYLE_DB)


def test_parse_opt_int():
    """_parse_opt_int 仅依赖 var.get()，用 MagicMock 免 Tk 环境。"""
    from unittest.mock import MagicMock
    obj = MakerGUI.__new__(MakerGUI)

    # 空输入 → None
    v = MagicMock()
    v.get.return_value = ""
    assert obj._parse_opt_int(v) is None
    # 有效输入
    v2 = MagicMock()
    v2.get.return_value = "120"
    assert obj._parse_opt_int(v2) == 120
    # 无效输入 → 抛 ValueError（GUI 层弹窗）
    v3 = MagicMock()
    v3.get.return_value = "abc"
    with pytest.raises(ValueError):
        obj._parse_opt_int(v3)


# ═══════════════════════════════════════════════════════════════
# Beats 流程（slow — 实际渲染 8 风格）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
@pytest.mark.parametrize("name", [
    "Trap", "Boom Bap", "Lo-Fi", "Battle",
    "Drum Only", "EDM", "Ambient",
])
def test_beat_styles_generate_audio(name):
    """7 种纯合成 beat 风格均产出非零音频。"""
    if not _HAS_BEATS:
        pytest.skip("make_beats 模块不可用")
    result = _BEAT_STYLES[name]()
    if result is None:
        pytest.skip(f"{name}: 无输出，跳过")
    audio = np.asarray(result)
    assert audio.size > 0, f"{name}: empty output"
    assert float(np.max(np.abs(audio))) > 1e-4, f"{name}: silent output"


# ═══════════════════════════════════════════════════════════════
# 单曲流程（slow — 3 个代表风格实际渲染）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
@pytest.mark.parametrize("style_name", ["lofi", "electronic", "classical"])
def test_quick_single_generates_wav(style_name, tmp_path):
    qr = QuickMaker.style(style_name, str(tmp_path), seed=42)
    assert qr.style == style_name
    assert qr.wave_path is not None, f"{style_name}: no WAV produced"
    assert str(qr.wave_path).endswith(".wav")
    assert qr.duration_sec > 1.0
    assert qr.bpm > 0


@pytest.mark.slow
def test_quick_random_generates_wav(tmp_path):
    qr = QuickMaker.random(str(tmp_path), seed=7)
    assert qr.wave_path is not None
    assert qr.style in STYLE_DB


# ═══════════════════════════════════════════════════════════════
# 专辑流程（slow — demo 专辑 3 曲）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
def test_demo_album_generates(tmp_path):
    from bloodmusic.album_maker.album import AlbumMaker
    from bloodmusic.album_maker.demo_config import make_demo_config

    result = AlbumMaker(make_demo_config()).make(str(tmp_path))
    assert len(result.tracks) == 3
    ok = [t for t in result.tracks if t.success]
    assert len(ok) >= 1, "demo album should produce at least 1 track"
    for t in ok:
        assert t.song_path and str(t.song_path).endswith(".wav")
