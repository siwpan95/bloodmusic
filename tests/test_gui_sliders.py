"""GUI 实时参数滑块测试 — headless 验证滑块逻辑（不启动 Tk）。"""

import copy
import numpy as np
import pytest

from bloodmusic.gui.workstation import GameAudioWorkstationGUI
from bloodmusic.sfx.presets import UI_FX_PRESETS
from bloodmusic.core import synthesize_voice


class _FakePlayer:
    def __init__(self):
        self.played = []
        self.stopped = False

    def play(self, audio):
        self.played.append(np.asarray(audio))

    def stop(self):
        self.stopped = True


class _FakeStatus:
    def config(self, text=""):
        pass


def _bare_instance():
    """不启动 Tk 的裸实例，带假播放器与真实合成状态。"""
    obj = GameAudioWorkstationGUI.__new__(GameAudioWorkstationGUI)
    obj._canvas = None
    obj._fig = None
    obj._ax = None
    obj._sliders = {}
    obj._param_syncing = False
    obj._live_voice = None
    obj._live_name = ""
    obj._last_live_play = 0.0
    obj.player = _FakePlayer()
    obj._status = _FakeStatus()
    return obj


def test_param_specs_cover_6_controls():
    params = [p[0] for p in GameAudioWorkstationGUI._PARAM_SPECS]
    assert params == ["freq", "duration", "volume",
                      "pitch_mod", "distortion", "reverb_mix"]


def test_slider_change_without_live_voice_is_safe():
    obj = _bare_instance()
    obj._on_slider_change("freq", "880.0")  # 无 live voice → 安全返回
    assert obj.player.played == []


def test_sync_sliders_without_live_voice_is_safe():
    obj = _bare_instance()
    obj._sync_sliders_to_voice()  # 不应抛异常


def test_slider_change_updates_top_level_field():
    obj = _bare_instance()
    obj._live_voice = copy.deepcopy(UI_FX_PRESETS["button_click"])
    obj._live_name = "button_click"
    obj._on_slider_change("freq", "1320.0")
    assert obj._live_voice.freq == 1320.0
    # 触发播放（首次无节流限制）
    assert len(obj.player.played) >= 1


def test_slider_change_creates_effect_chain():
    """distortion 参数在 effect_chain 为 None 时自动创建。"""
    from bloodmusic.core.voice import SynthVoice
    obj = _bare_instance()
    obj._live_voice = SynthVoice(freq=440.0, duration=0.2)
    obj._live_name = "test"
    obj._on_slider_change("distortion", "0.5")
    assert obj._live_voice.effect_chain is not None
    assert obj._live_voice.effect_chain.distortion == 0.5


def test_slider_throttle_200ms():
    """200ms 内连续拖动只播放一次（节流），但参数即时更新。"""
    import time as _time
    obj = _bare_instance()
    obj._live_voice = copy.deepcopy(UI_FX_PRESETS["button_click"])
    obj._live_name = "button_click"
    obj._last_live_play = _time.time()  # 视为刚播过
    obj._on_slider_change("freq", "900.0")
    obj._on_slider_change("freq", "1000.0")
    assert obj._live_voice.freq == 1000.0, "参数应即时更新"
    assert len(obj.player.played) == 0, "节流期内不应播放"


def test_apply_live_voice_plays_and_updates_waveform():
    obj = _bare_instance()
    obj._live_voice = copy.deepcopy(UI_FX_PRESETS["button_click"])
    obj._live_name = "button_click"
    obj._apply_live_voice()
    assert len(obj.player.played) == 1
    audio = obj.player.played[0]
    assert audio.size > 0


def test_selection_does_not_mutate_preset():
    """滑块调节基于 deepcopy，不得污染预设库。"""
    obj = _bare_instance()
    orig = copy.deepcopy(UI_FX_PRESETS["button_click"])
    obj._live_voice = copy.deepcopy(UI_FX_PRESETS["button_click"])
    obj._on_slider_change("freq", "2000.0")
    assert UI_FX_PRESETS["button_click"].freq == orig.freq, "预设不得被修改"
