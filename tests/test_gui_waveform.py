"""GUI 波形可视化测试 — 含 matplotlib 缺失降级与有 matplotlib 渲染。"""

import numpy as np
import pytest

from bloodmusic.gui.workstation import (
    GameAudioWorkstationGUI, _HAS_MPL,
)
from bloodmusic.sfx.presets import GAME_FX_PRESETS


def _bare_instance():
    """不启动 Tk 的裸实例（绕过 __init__）。"""
    obj = GameAudioWorkstationGUI.__new__(GameAudioWorkstationGUI)
    obj._canvas = None
    obj._fig = None
    obj._ax = None
    return obj


def test_module_imports_and_flag():
    assert isinstance(_HAS_MPL, bool)


def test_update_waveform_safe_without_canvas():
    """无 canvas（headless / 无 matplotlib）时安全返回，不抛异常。"""
    obj = _bare_instance()
    obj._update_waveform(np.zeros(4410), title="x")  # 不应抛异常
    obj._update_waveform(np.zeros(0), title="empty")  # 空音频也不应抛
    obj._update_waveform(np.random.RandomState(0).randn(2205), title="noise")


def test_update_waveform_handles_stereo():
    obj = _bare_instance()
    stereo = np.random.RandomState(1).randn(4410, 2)
    obj._update_waveform(stereo, title="stereo")  # 应降为 mono 处理，不抛


def test_game_fx_category_available_for_gui():
    """T6 的 GAME_FX_PRESETS 已在 GUI 分类中使用（8 类可被列出）。"""
    assert set(GAME_FX_PRESETS) >= {
        "pickup_coin", "laser_shoot", "explosion", "power_up",
        "hit_hurt", "jump", "blip_select", "random_pick",
    }


@pytest.mark.skipif(not _HAS_MPL, reason="matplotlib 未安装")
def test_waveform_render_with_matplotlib():
    """有 matplotlib 时用 Agg 后端渲染波形（无需显示器）。"""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    obj = _bare_instance()
    obj._fig = Figure(figsize=(3, 2), dpi=80)
    obj._ax = obj._fig.add_subplot(111)
    # canvas 为 None → 走 draw_idle 前返回? 不, 有 canvas 才 draw。
    # 模拟无 Tk canvas：仅验证绘图调用不抛异常。
    obj._canvas = None
    obj._update_waveform(np.sin(np.linspace(0, 40, 4410)), title="sine")
    lines = obj._ax.get_lines()
    assert len(lines) >= 2, "waveform + envelope 两条线应已绘制"
    assert obj._ax.get_title() == "sine"
