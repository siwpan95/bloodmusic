"""音乐模式预设库"""

from typing import Dict, Callable, List, Optional

from ..core.oscillator import OscType
from ..core.envelope import EnvShape
from .pattern import MusicPattern, DrumPattern, DrumSoundParams
from ..effects.chain import EffectChain
from ..effects.dynamics import CompressorParams
from ..effects.eq import ParametricEQParams


# ═══════ 菜单主题 ═══════
MENU_MUSIC = MusicPattern(
    name="menu_theme",
    notes=["C4", "Eb_4", "G4", "C5",
           "Bb4", "G4", "Eb_4", "C4",
           "Ab4", "C5", "Bb4", "G4",
           "Eb_4", "C4", None, "G4"],
    durations=[1.0, 0.5, 0.5, 1.0,
               0.5, 0.5, 1.0, 0.5,
               1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 1.0],
    bpm=85, loop=True,
    osc_type=OscType.TRIANGLE, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=4.5, vibrato_depth=1.5,
    reverb_mix=0.2, stereo_width=0.4, lp_filter_hz=4000,
)

# ═══════ 低强度战斗 ═══════
BATTLE_LOW_MUSIC = MusicPattern(
    name="battle_low",
    notes=["C3", None, "G3", None, "Eb3", None, "Bb3", None,
           "C3", None, "G3", "Eb3", None, "C3", None, None],
    durations=[0.75, 0.25, 0.75, 0.25, 0.75, 0.25, 0.75, 0.25,
               0.5, 0.25, 0.5, 0.5, 0.5, 1.0, 0.5, 0.5],
    bpm=110, loop=True,
    osc_type=OscType.SAW, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(0.5, 0.15), (2.0, 0.1)],
    vibrato_rate=3, vibrato_depth=1,
    reverb_mix=0.15, stereo_width=0.3, lp_filter_hz=3000,
)

# ═══════ 高强度战斗 ═══════
BATTLE_HIGH_MUSIC = MusicPattern(
    name="battle_high",
    notes=["C3", "Eb3", "G3", "C4", "G3", "Eb3", "C3", "G2",
           "C3", "Eb3", "G3", "Bb3", "Ab3", "G3", "Eb3", "C3"],
    durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5, 0.75, 0.25, 0.5, 1.0],
    bpm=130, loop=True,
    osc_type=OscType.SAW, volume=0.17, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5, 0.2), (2.0, 0.15), (3.0, 0.05)],
    reverb_mix=0.12, stereo_width=0.5, lp_filter_hz=4500,
)

# ═══════ 事件/胜利 ═══════
EVENT_MUSIC = MusicPattern(
    name="event_theme",
    notes=["C5", None, "E5", "G5", "C5", "B4", "C5", None,
           "G5", "E5", "C5", "B4", "C5", None, None, None],
    durations=[0.75, 0.25, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 1.0, 0.5],
    bpm=95, loop=True,
    osc_type=OscType.TRIANGLE, volume=0.18, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.25), (3.0, 0.1), (4.0, 0.03)],
    vibrato_rate=5, vibrato_depth=2,
    reverb_mix=0.25, stereo_width=0.5, lp_filter_hz=5000,
)

# ═══════ 商人 ═══════
MERCHANT_MUSIC = MusicPattern(
    name="merchant_theme",
    notes=["C4", "Eb4", "G4", "Eb4", "C4", "Bb3", "C4", None,
           "Eb4", "G4", "Bb4", "G4", "Eb4", "C4", None, None],
    durations=[0.66, 0.34, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 1.0, 0.5],
    bpm=100, loop=True,
    osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.15), (3.0, 0.05), (5.0, 0.02)],
    vibrato_rate=5.5, vibrato_depth=1.5,
    reverb_mix=0.18, stereo_width=0.35,
)

# ═══════ 篝火/休息 ═══════
CAMPFIRE_MUSIC = MusicPattern(
    name="campfire_theme",
    notes=["G4", None, "E4", None, "C4", None, "E4", "G4",
           "A4", None, "E4", "C4", None, "D4", None, None],
    durations=[1.0, 0.5, 1.0, 0.5, 1.0, 0.5, 0.5, 0.5,
               1.0, 0.5, 0.5, 0.5, 1.0, 1.5, 0.5, 0.5],
    bpm=72, loop=True,
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.12), (3.0, 0.05)],
    vibrato_rate=3.5, vibrato_depth=1,
    reverb_mix=0.3, reverb_decay=1.2, stereo_width=0.5, lp_filter_hz=3500,
)

# ═══════ Boss 战斗 ═══════
BOSS_FIGHT_MUSIC = MusicPattern(
    name="boss_fight",
    notes=["C3", "C3", "Eb3", "C3", "G2", "G2", "Bb2", "G2",
           "Ab2", "Ab2", "B2", "Ab2", "G2", "G2", "F2", "G2"],
    durations=[0.5, 0.25, 0.5, 0.25, 0.5, 0.25, 0.5, 0.25,
               0.5, 0.25, 0.5, 0.25, 0.75, 0.25, 0.5, 1.0],
    bpm=140, loop=True,
    osc_type=OscType.SAW, volume=0.18, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5, 0.25), (2.0, 0.15), (3.0, 0.08)],
    reverb_mix=0.1, stereo_width=0.5, lp_filter_hz=5000,
)

# ═══════ 地下城 ═══════
DUNGEON_MUSIC = MusicPattern(
    name="dungeon",
    notes=["C3", None, "Eb3", None, "Ab3", None, "G3", None,
           "F3", None, "Eb3", None, "D3", "C3", None, None],
    durations=[0.75, 0.25, 0.75, 0.25, 0.75, 0.25, 1.0, 0.5,
               0.75, 0.25, 0.75, 0.25, 0.5, 1.0, 0.5, 0.5],
    bpm=80, loop=True,
    osc_type=OscType.TRIANGLE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.15), (3.0, 0.06)],
    vibrato_rate=3.0, vibrato_depth=1.5,
    reverb_mix=0.35, reverb_decay=1.2, stereo_width=0.6, lp_filter_hz=2500,
)

# ═══════ 酒馆 ═══════
TAVERN_MUSIC = MusicPattern(
    name="tavern",
    notes=["G4", "A4", "B4", "D5", "B4", "A4", "G4", None,
           "E4", "G4", "A4", "G4", "E4", "D4", None, None],
    durations=[0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 0.5, 0.5],
    bpm=108, loop=True,
    osc_type=OscType.SINE, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=4.0, vibrato_depth=1.2,
    reverb_mix=0.2, stereo_width=0.3, lp_filter_hz=4500,
)

# ═══════ 森林 ═══════
FOREST_MUSIC = MusicPattern(
    name="forest",
    notes=["C5", None, "E5", None, "G5", "E5", "C5", None,
           "A4", None, "C5", None, "E5", "D5", "C5", None],
    durations=[1.0, 0.5, 1.0, 0.5, 0.5, 0.5, 1.5, 0.5,
               1.0, 0.5, 1.0, 0.5, 0.5, 0.5, 1.5, 0.5],
    bpm=68, loop=True,
    osc_type=OscType.TRIANGLE, volume=0.12, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.12), (3.0, 0.05), (5.0, 0.02)],
    vibrato_rate=3.5, vibrato_depth=2.0,
    reverb_mix=0.3, reverb_decay=1.0, stereo_width=0.6, lp_filter_hz=3500,
)

# ═══════ 解谜 ═══════
PUZZLE_MUSIC = MusicPattern(
    name="puzzle",
    notes=["E4", "G4", "B4", "E5", "D5", "B4", "G4", "E4",
           "F4", "A4", "C5", "F5", "E5", "C5", "A4", "F4"],
    durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
               0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    bpm=90, loop=True,
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.15)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.25, stereo_width=0.4, lp_filter_hz=5000,
)

# ═══════ 标题画面 ═══════
TITLE_SCREEN_MUSIC = MusicPattern(
    name="title_screen",
    notes=["C4", "E4", "G4", "C5", "B4", "G4", "E4", "C4",
           "F4", "A4", "C5", "F5", "E5", "C5", "A4", "F4"],
    durations=[0.75, 0.25, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5,
               0.75, 0.25, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5],
    bpm=92, loop=True,
    osc_type=OscType.TRIANGLE, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.2), (3.0, 0.1), (4.0, 0.04)],
    vibrato_rate=4.0, vibrato_depth=1.5,
    reverb_mix=0.22, stereo_width=0.45, lp_filter_hz=4500,
)

# ═══════ Game Over ═══════
GAME_OVER_MUSIC = MusicPattern(
    name="game_over",
    notes=["C4", "B3", "Bb3", "A3", "Ab3", "G3", "Gb3", "F3",
           "E3", None, "C3", None, None, None, None, None],
    durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
               2.0, 0.5, 2.0, 0.5, 1.0, 1.0, 1.0, 1.0],
    bpm=72, loop=False,
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.REVERSE,
    harmonics=[(0.5, 0.2), (2.0, 0.1)],
    reverb_mix=0.35, reverb_decay=1.5, stereo_width=0.5, lp_filter_hz=2000,
)

# ═══════ 制作组字幕 ═══════
CREDITS_MUSIC = MusicPattern(
    name="credits",
    notes=["C4", "E4", "G4", "C5", "A4", "G4", "E4", "F4",
           "A4", "C5", "F5", "E5", "D5", "C5", "G4", "C4"],
    durations=[0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5,
               0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5, 1.0],
    bpm=96, loop=True,
    osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=4.5, vibrato_depth=1.8,
    reverb_mix=0.2, reverb_decay=0.8, stereo_width=0.5, lp_filter_hz=4000,
)

# ═══════ 平台跳跃 ═══════
PLATFORMER_MUSIC = MusicPattern(
    name="platformer",
    notes=["C4", "E4", "G4", "C5", "G4", "E4", "C4", "D4",
           "F4", "A4", "D5", "A4", "F4", "D4", "G4", "C5"],
    durations=[0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.25,
               0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.25, 0.5],
    bpm=135, loop=True,
    osc_type=OscType.SQUARE, volume=0.14, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(2.0, 0.1)],
    reverb_mix=0.12, stereo_width=0.4, lp_filter_hz=6000,
)

# ═══════ 汇总 ═══════
ALL_MUSIC_PATTERNS: Dict[str, MusicPattern] = {
    "menu": MENU_MUSIC,
    "battle_low": BATTLE_LOW_MUSIC,
    "battle_high": BATTLE_HIGH_MUSIC,
    "event": EVENT_MUSIC,
    "merchant": MERCHANT_MUSIC,
    "campfire": CAMPFIRE_MUSIC,
    "boss_fight": BOSS_FIGHT_MUSIC,
    "dungeon": DUNGEON_MUSIC,
    "tavern": TAVERN_MUSIC,
    "forest": FOREST_MUSIC,
    "puzzle": PUZZLE_MUSIC,
    "title_screen": TITLE_SCREEN_MUSIC,
    "game_over": GAME_OVER_MUSIC,
    "credits": CREDITS_MUSIC,
    "platformer": PLATFORMER_MUSIC,
}

# ═══════════════════════════════════════════════════════════════════════
# 鼓工厂 — bpm → DrumPattern
# ═══════════════════════════════════════════════════════════════════════

_T = True; _F = False

def _mk_drum(name: str, bpm: int,
             kick_t: List[bool], snare_t: List[bool], hh_t: List[bool],
             kick_s: DrumSoundParams = None, snare_s: DrumSoundParams = None,
             hh_s: DrumSoundParams = None) -> DrumPattern:
    return DrumPattern(name=name, steps=16, bpm=bpm, tracks={
        "kick": kick_t, "snare": snare_t, "hihat": hh_t,
    }, sounds={
        "kick":  kick_s or DrumSoundParams(osc_type=OscType.SINE, pitch_hz=55, decay=0.22, volume=0.8),
        "snare": snare_s or DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=180, decay=0.15, hp_hz=250, volume=0.65),
        "hihat": hh_s   or DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=8000, decay=0.06, hp_hz=1500, volume=0.35),
    })

# ── 7 种风格的鼓工厂 ──

TRAP_DRUMS = lambda bpm: _mk_drum("trap", bpm,
    [_T,_F,_F,_F, _T,_F,_F,_F, _T,_F,_F,_F, _T,_F,_F,_F],
    [_F,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F],
    [_T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=50,decay=0.25,volume=0.88),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=200,decay=0.12,hp_hz=300,volume=0.72),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=9000,decay=0.04,hp_hz=2000,volume=0.38))

BOOM_BAP_DRUMS = lambda bpm: _mk_drum("boom_bap", bpm,
    [_T,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F, _T,_F,_T,_F],
    [_F,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_T,_F],
    [_T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=60,decay=0.18,volume=0.82),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=170,decay=0.13,hp_hz=200,volume=0.7),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=7500,decay=0.05,hp_hz=1200,volume=0.32))

LOFI_DRUMS = lambda bpm: _mk_drum("lofi", bpm,
    [_T,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F],
    [_F,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F],
    [_T,_F,_F,_T, _F,_F,_T,_F, _T,_F,_F,_F, _T,_F,_T,_F],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=55,decay=0.22,volume=0.7),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=180,decay=0.15,hp_hz=250,volume=0.4),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=6000,decay=0.06,hp_hz=1500,volume=0.25))

EDM_DRUMS = lambda bpm: _mk_drum("edm", bpm,
    [_T,_F,_F,_F, _T,_F,_F,_F, _T,_F,_F,_F, _T,_F,_F,_F],
    [_F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F],
    [_T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F, _T,_F,_T,_F],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=55,decay=0.2,volume=0.85),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=200,decay=0.15,hp_hz=250,volume=0.65),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=8000,decay=0.04,hp_hz=2000,volume=0.4))

BATTLE_DRUMS = lambda bpm: _mk_drum("battle", bpm,
    [_T,_F,_F,_T, _T,_F,_F,_F, _T,_F,_T,_F, _T,_F,_F,_T],
    [_F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_T,_F, _T,_F,_F,_F],
    [_T,_T,_T,_T, _T,_T,_T,_T, _T,_T,_T,_T, _T,_T,_T,_T],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=48,decay=0.18,volume=0.88),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=210,decay=0.1,hp_hz=350,volume=0.75),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=10000,decay=0.03,hp_hz=2500,volume=0.45))

AMBIENT_DRUMS = lambda bpm: _mk_drum("ambient", bpm,
    [_T,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_F,_F],
    [_F,_F,_F,_F, _F,_F,_F,_F, _F,_F,_F,_F, _T,_F,_F,_F],
    [_F,_F,_F,_F, _F,_F,_F,_F, _F,_F,_F,_F, _F,_F,_F,_F],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=45,decay=0.35,volume=0.75),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=150,decay=0.2,hp_hz=200,volume=0.4))

DRUM_ONLY = lambda bpm: _mk_drum("drum_only", bpm,
    [_T,_F,_F,_F, _T,_F,_F,_T, _T,_F,_F,_F, _T,_F,_T,_T],
    [_F,_F,_F,_F, _T,_F,_F,_F, _F,_F,_T,_F, _T,_F,_T,_F],
    [_T,_F,_T,_T, _T,_F,_T,_F, _T,_T,_T,_F, _T,_F,_T,_T],
    DrumSoundParams(osc_type=OscType.SINE,pitch_hz=55,decay=0.22,volume=0.85),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=190,decay=0.14,hp_hz=250,volume=0.7),
    DrumSoundParams(osc_type=OscType.NOISE_WHITE,pitch_hz=8000,decay=0.05,hp_hz=1500,volume=0.38))

DRUM_PRESETS: Dict[str, Callable[[int], DrumPattern]] = {
    "trap": TRAP_DRUMS, "boom_bap": BOOM_BAP_DRUMS, "lofi": LOFI_DRUMS,
    "edm": EDM_DRUMS, "battle": BATTLE_DRUMS, "ambient": AMBIENT_DRUMS,
    "drum_only": DRUM_ONLY,
}

# ═══════════════════════════════════════════════════════════════════════
# 效果链预设 — 7 种风格 + 母带
# ═══════════════════════════════════════════════════════════════════════

LOFI_CHAIN = EffectChain(
    lp_filter_hz=8000, reverb_mix=0.35, reverb_decay=1.8,
    reverb_delay_ms=50, stereo_width=0.6,
    eq=ParametricEQParams(low_freq=200,low_gain_db=2,low_q=0.7,
                          mid_freq=800,mid_gain_db=-3,mid_q=1.5,
                          high_freq=8000,high_gain_db=-4,high_q=0.5),
    compressor=CompressorParams(threshold_db=-18,ratio=3,attack_ms=15,release_ms=150,makeup_db=4),
    chorus_mix=0.15,chorus_rate=0.4,chorus_depth=0.003,
)

TRAP_CHAIN = EffectChain(
    lp_filter_hz=15000, reverb_mix=0.2, reverb_decay=1.2,
    stereo_width=0.4,
    eq=ParametricEQParams(low_freq=60,low_gain_db=4,low_q=0.5,
                          mid_freq=500,mid_gain_db=-2,mid_q=1.0,
                          high_freq=10000,high_gain_db=-2,high_q=0.7),
    compressor=CompressorParams(threshold_db=-14,ratio=5,attack_ms=5,release_ms=80,makeup_db=5),
    delay_mix=0.12,delay_time=0.25,delay_feedback=0.3,
)

AMBIENT_CHAIN = EffectChain(
    lp_filter_hz=6000, reverb_mix=0.45, reverb_decay=2.0,
    reverb_delay_ms=60, reverb_schroeder=True, stereo_width=0.8,
    eq=ParametricEQParams(low_freq=150,low_gain_db=1,low_q=0.6,
                          mid_freq=2000,mid_gain_db=-1,mid_q=0.8,
                          high_freq=10000,high_gain_db=-3,high_q=0.4),
    chorus_mix=0.2,chorus_rate=0.3,chorus_depth=0.004,
    delay_mix=0.2,delay_time=0.5,delay_feedback=0.5,
)

EDM_CHAIN = EffectChain(
    lp_filter_hz=18000, hp_filter_hz=30,
    reverb_mix=0.18, reverb_decay=0.8, stereo_width=0.5,
    eq=ParametricEQParams(low_freq=80,low_gain_db=3,low_q=0.7,
                          mid_freq=300,mid_gain_db=-3,mid_q=2.0,
                          high_freq=12000,high_gain_db=2,high_q=0.6),
    compressor=CompressorParams(threshold_db=-12,ratio=4,attack_ms=3,release_ms=60,makeup_db=4),
)

BATTLE_CHAIN = EffectChain(
    lp_filter_hz=16000, hp_filter_hz=40,
    reverb_mix=0.15, reverb_decay=0.6, stereo_width=0.4,
    eq=ParametricEQParams(low_freq=100,low_gain_db=2,low_q=0.8,
                          mid_freq=1500,mid_gain_db=-2,mid_q=1.2,
                          high_freq=12000,high_gain_db=1,high_q=0.5),
    compressor=CompressorParams(threshold_db=-10,ratio=6,attack_ms=2,release_ms=40,makeup_db=6),
)

CLEAN_MASTER = EffectChain(
    compressor=CompressorParams(threshold_db=-20,ratio=2.5,attack_ms=10,release_ms=200,makeup_db=3),
    eq=ParametricEQParams(low_freq=120,low_gain_db=1,low_q=0.7,
                          high_freq=10000,high_gain_db=-1,high_q=0.5),
    stereo_width=0.3,
)

SUBTLE_MASTER = EffectChain(
    compressor=CompressorParams(threshold_db=-24,ratio=2,attack_ms=20,release_ms=300,makeup_db=2),
    reverb_mix=0.08, reverb_decay=1.0, stereo_width=0.25,
    eq=ParametricEQParams(low_freq=100,low_gain_db=0.5,low_q=0.6,
                          high_freq=12000,high_gain_db=-0.5,high_q=0.4),
)

EFFECT_PRESETS: Dict[str, EffectChain] = {
    "lofi": LOFI_CHAIN, "trap": TRAP_CHAIN, "ambient": AMBIENT_CHAIN,
    "edm": EDM_CHAIN, "battle": BATTLE_CHAIN,
    "clean_master": CLEAN_MASTER, "subtle_master": SUBTLE_MASTER,
}

# ═══════════════════════════════════════════════════════════════════════
# 旋律模板 — bpm → MusicPattern (各风格专属)
# ═══════════════════════════════════════════════════════════════════════

TRAP_MELODY = lambda bpm: MusicPattern(
    name="trap_lead", bpm=bpm, loop=True,
    notes=["C4","Eb4","G4","C5","Bb4","G4","Eb4","C4",
           "Ab4","C5","Bb4","G4","Eb4","C4","G4",None],
    durations=[1.0,0.5,0.5,1.0,0.5,0.5,1.0,0.5,
               1.0,0.5,0.5,0.5,1.0,0.5,1.0,0.5],
    osc_type=OscType.TRIANGLE, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(2.0,0.2),(3.0,0.08)],
    vibrato_rate=4.5, vibrato_depth=1.5,
    reverb_mix=0.2, stereo_width=0.4, lp_filter_hz=4000,
)

TRAP_PAD = lambda bpm: MusicPattern(
    name="trap_pad", bpm=bpm, loop=True,
    chords=[["C4","Eb4","G4"],["Ab3","C4","Eb4"],
            ["F3","Ab3","C4"],["G3","B3","D4"]],
    notes=[None]*8, durations=[2.0]*8,
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PAD,
    harmonics=[(1.0,1.0),(2.0,0.15)],
    reverb_mix=0.35, stereo_width=0.7, lp_filter_hz=3000,
)

LOFI_MELODY = lambda bpm: MusicPattern(
    name="lofi_lead", bpm=bpm, loop=True,
    chords=[["A4","C5","E5","G5"],["D4","F5","A5","C6"],
            ["G4","B5","D6","F6"],["C4","E5","G5","B5"]],
    notes=[None]*8, durations=[2.0]*8,
    osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0,1.0),(2.0,0.3),(3.0,0.1)],
    vibrato_rate=3.5, vibrato_depth=0.15,
    reverb_mix=0.4, reverb_decay=2.0, stereo_width=0.7, lp_filter_hz=3500,
)

BOOM_BAP_MELODY = lambda bpm: MusicPattern(
    name="bap_sample", bpm=bpm, loop=True,
    chords=[["E4","G4","B4"],["A3","C4","E4"],
            ["D4","F4","A4"],["G3","B3","D4"]],
    notes=[None,"B4",None,"D5","E5",None,"B4",None],
    durations=[1.0,0.5,0.5,1.0,0.5,0.5,1.0,0.5],
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(2.0,0.2),(3.0,0.1),(5.0,0.03)],
    vibrato_rate=4.0, vibrato_depth=1.0,
    reverb_mix=0.25, lp_filter_hz=5000,
)

EDM_LEAD = lambda bpm: MusicPattern(
    name="edm_synth", bpm=bpm, loop=True,
    notes=["C4","E4","G4","C5","G4","E4","C4","D4",
           "F4","A4","D5","A4","F4","D4","G4","C5"],
    durations=[0.25]*16,
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(2.0,0.1)],
    reverb_mix=0.12, stereo_width=0.5, lp_filter_hz=8000,
)

EDM_CHORDS = lambda bpm: MusicPattern(
    name="edm_pad", bpm=bpm, loop=True,
    chords=[["C3","E4","G4","C5"],["G2","B3","D4","G4"],
            ["A2","C4","E4","A4"],["F2","A3","C4","F4"]],
    notes=[None]*4, durations=[4.0]*4,
    osc_type=OscType.SAW, volume=0.1, env_shape=EnvShape.SWELL,
    harmonics=[(1.0,1.0),(2.0,0.2)],
    reverb_mix=0.3, stereo_width=0.8, lp_filter_hz=6000,
)

BATTLE_MELODY = lambda bpm: MusicPattern(
    name="battle_lead", bpm=bpm, loop=True,
    notes=["C3","Eb3","G3","C4","G3","Eb3","C3","G2",
           "C3","Eb3","G3","Bb3","Ab3","G3","Eb3","C3"],
    durations=[0.5,0.5,0.5,0.5,0.5,0.5,1.0,0.5,
               0.5,0.5,0.5,0.5,0.75,0.25,0.5,1.0],
    osc_type=OscType.SAW, volume=0.17, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5,0.2),(2.0,0.15),(3.0,0.05)],
    reverb_mix=0.12, stereo_width=0.5, lp_filter_hz=4500,
)

AMBIENT_MELODY = lambda bpm: MusicPattern(
    name="ambient_drone", bpm=bpm, loop=True,
    notes=["C4",None,"Eb4",None,"G4","Eb4","C4",None,
           "A3",None,"C4",None,"Eb4","D4","C4",None],
    durations=[1.0,0.5,1.0,0.5,0.5,0.5,1.5,0.5,
               1.0,0.5,1.0,0.5,0.5,0.5,1.5,0.5],
    osc_type=OscType.TRIANGLE, volume=0.1, env_shape=EnvShape.PAD,
    harmonics=[(2.0,0.1),(3.0,0.04),(5.0,0.01)],
    vibrato_rate=3.0, vibrato_depth=2.0,
    reverb_mix=0.45, reverb_decay=2.0, stereo_width=0.8, lp_filter_hz=2500,
)

MELODY_PRESETS: Dict[str, Callable[[int], MusicPattern]] = {
    "trap": TRAP_MELODY, "trap_pad": TRAP_PAD,
    "lofi": LOFI_MELODY, "boom_bap": BOOM_BAP_MELODY,
    "edm_lead": EDM_LEAD, "edm_chords": EDM_CHORDS,
    "battle": BATTLE_MELODY, "ambient": AMBIENT_MELODY,
}

# ═══════════════════════════════════════════════════════════════════════
# Bass 线模板 — bpm → MusicPattern (供 BassSynth 渲染)
# ═══════════════════════════════════════════════════════════════════════

TRAP_BASS = lambda bpm: MusicPattern(
    name="trap_808", bpm=bpm, loop=True,
    notes=["C1","C1","G1","G1","A1","A1","F1","F1",
           "C1","C1","Eb1","Eb1","F1","F1","G1","G1"],
    durations=[0.5]*16,
    osc_type=OscType.SINE, volume=0.8, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5,0.3)],
)

BOOM_BAP_BASS = lambda bpm: MusicPattern(
    name="bap_bass", bpm=bpm, loop=True,
    notes=["E1","E1","G1","A1","B1","A1","G1","E1",
           "E1","G1","A1","B1","C2","B1","A1","G1"],
    durations=[0.5]*16,
    osc_type=OscType.SINE, volume=0.75, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(2.0,0.15)],
)

LOFI_BASS = lambda bpm: MusicPattern(
    name="lofi_bass", bpm=bpm, loop=True,
    notes=["A1","C2","E2","G2","D2","F2","A2","C2",
           "G1","B1","D2","F2","C2","E2","G2","B1"],
    durations=[0.5]*16,
    osc_type=OscType.SINE, volume=0.65, env_shape=EnvShape.PAD,
    harmonics=[(2.0,0.12)],
)

EDM_BASS = lambda bpm: MusicPattern(
    name="edm_bass", bpm=bpm, loop=True,
    notes=["C1","C1","C1","C1","G1","G1","G1","G1",
           "A1","A1","A1","A1","F1","F1","F1","F1"],
    durations=[0.25]*16,
    osc_type=OscType.SAW, volume=0.75, env_shape=EnvShape.PERCUSSIVE,
    lp_filter_hz=2000,
)

BATTLE_BASS = lambda bpm: MusicPattern(
    name="battle_bass", bpm=bpm, loop=True,
    notes=["C1","C1","C1","C1","G1","G1","G1","G1",
           "A1","A1","A1","A1","F1","F1","G1","G1"],
    durations=[0.25]*16,
    osc_type=OscType.SAW, volume=0.78, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5,0.25)],
)

AMBIENT_BASS = lambda bpm: MusicPattern(
    name="ambient_bass", bpm=bpm, loop=True,
    notes=["C1",None,None,None,"Eb1",None,None,None,
           "F1",None,None,None,"G1",None,None,None],
    durations=[1.0,0.5,0.5,0.5]*4,
    osc_type=OscType.SINE, volume=0.55, env_shape=EnvShape.PAD,
    harmonics=[(2.0,0.1)],
)

BASS_PRESETS: Dict[str, Callable[[int], MusicPattern]] = {
    "trap": TRAP_BASS, "boom_bap": BOOM_BAP_BASS, "lofi": LOFI_BASS,
    "edm": EDM_BASS, "battle": BATTLE_BASS, "ambient": AMBIENT_BASS,
}

# ═══════════════════════════════════════════════════════════════════════
# 风格套件 — 一键获取某风格的全部组件
# ═══════════════════════════════════════════════════════════════════════

STYLE_KITS: Dict[str, Dict] = {
    "trap": {
        "bpm": 140, "drum": TRAP_DRUMS,
        "melody": [TRAP_MELODY], "pad": TRAP_PAD,
        "bass": TRAP_BASS, "bass_type": "sub",
        "effect": TRAP_CHAIN, "master": CLEAN_MASTER,
        "arrangement": "hip-hop",
    },
    "boom_bap": {
        "bpm": 92, "drum": BOOM_BAP_DRUMS,
        "melody": [BOOM_BAP_MELODY],
        "bass": BOOM_BAP_BASS, "bass_type": "sub",
        "effect": CLEAN_MASTER, "master": SUBTLE_MASTER,
        "arrangement": "hip-hop",
    },
    "lofi": {
        "bpm": 78, "drum": LOFI_DRUMS,
        "melody": [LOFI_MELODY],
        "bass": LOFI_BASS, "bass_type": "sub",
        "effect": LOFI_CHAIN, "master": SUBTLE_MASTER,
        "arrangement": "lo-fi",
    },
    "edm": {
        "bpm": 128, "drum": EDM_DRUMS,
        "melody": [EDM_LEAD, EDM_CHORDS],
        "bass": EDM_BASS, "bass_type": "acid",
        "effect": EDM_CHAIN, "master": CLEAN_MASTER,
        "arrangement": "electronic",
    },
    "battle": {
        "bpm": 145, "drum": BATTLE_DRUMS,
        "melody": [BATTLE_MELODY],
        "bass": BATTLE_BASS, "bass_type": "fm",
        "effect": BATTLE_CHAIN, "master": CLEAN_MASTER,
        "arrangement": "electronic",
    },
    "ambient": {
        "bpm": 70, "drum": AMBIENT_DRUMS,
        "melody": [AMBIENT_MELODY],
        "bass": AMBIENT_BASS, "bass_type": "pluck",
        "effect": AMBIENT_CHAIN, "master": SUBTLE_MASTER,
        "arrangement": "ambient",
    },
    "drum_only": {
        "bpm": 95, "drum": DRUM_ONLY,
        "melody": [], "bass": None, "bass_type": None,
        "effect": CLEAN_MASTER, "master": CLEAN_MASTER,
        "arrangement": "hip-hop",
    },
}
