#!/usr/bin/env python3
"""
.. deprecated:: 2026-08-12
    此文件已被 album_maker/ 子包替代。
    请使用 album_maker 的快速单曲模式:

        python -m bloodmusic.album_maker.cli quick       # 随机风格单曲
        python -m bloodmusic.album_maker.cli style jazz  # 指定风格
        python -m bloodmusic.album_maker.cli jam         # 即兴模式

    旧版专辑生成请使用:
        python -m bloodmusic.album_maker.cli make --demo

BloodMusic 纯音乐专辑生成器 — 《血音幻境》 BloodSound Fantasia
================================================================
使用 BloodMusic 全引擎能力，生成 10 首不同风格的纯音乐曲目。
涵盖：古典/钢琴、新世纪、氛围、爵士、电子、影视史诗、
      Lo-Fi、冥想、民谣、史诗终章。


引擎: SongArrangement + EffectChain + Automation + BassSynth
     + Harmony + FM/KS 合成 + 多波形振荡器

用法: python album_generator.py
输出: ./album_output/ 目录下 10 首 WAV 曲目
"""

import os, sys, numpy as np
from datetime import datetime
from scipy.io import wavfile

# Ensure bloodmusic is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape
from bloodmusic.music import (
    MusicPattern, DrumPattern, DrumSoundParams, render_pattern_to_array,
    render_drum_pattern,
    SongArrangement, Section, render_song, TrackChannel,
    AutomationLane, apply_filter_sweep, apply_volume_automation,
    BassSynth, render_bass_pattern,
    generate_parallel_harmony, generate_diatonic_harmony,
    Arpeggiator, ArpMode, generate_arpeggio,
    Scale, SCALE_INTERVALS,
)
from bloodmusic.music.presets import STYLE_KITS, EFFECT_PRESETS
from bloodmusic.effects.chain import EffectChain, process_effects
from bloodmusic.effects.filters import apply_resonant_lpf
from bloodmusic.effects.dynamics import CompressorParams
from bloodmusic.effects.eq import ParametricEQParams

# ── Config ──────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "album_output")
ALBUM_NAME = "血音幻境"
ALBUM_ARTIST = "BloodMusic Engine"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRACKLIST = [
    ("01_晨曦序曲", "Dawn Overture", "古典/钢琴"),
    ("02_星海迷途", "Lost in Cosmos", "新世纪"),
    ("03_深海絮语", "Deep Sea Whispers", "氛围音乐"),
    ("04_午夜爵士", "Midnight Jazz", "爵士"),
    ("05_霓虹脉冲", "Neon Pulse", "电子/EDM"),
    ("06_英雄远征", "Hero's Journey", "影视史诗"),
    ("07_旧日时光", "Nostalgia", "Lo-Fi 低保真"),
    ("08_空山鸟语", "Birds in Empty Mountains", "冥想/自然"),
    ("09_田园小调", "Pastoral Tune", "民谣/世界音乐"),
    ("10_终章·重生", "Finale: Rebirth", "史诗终章"),
]


# ═════════════════════════════════════════════════════════════
# 工具函数
# ═════════════════════════════════════════════════════════════

def _to_mono(audio: np.ndarray) -> np.ndarray:
    """立体声 → 单声道"""
    if audio.ndim == 2 and audio.shape[1] == 2:
        return audio.mean(axis=1)
    return audio


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    """单声道 → 立体声"""
    if audio.ndim != 2 or audio.shape[1] != 2:
        return np.column_stack([audio, audio])
    return audio


def _mix_audio(main: np.ndarray, add: np.ndarray, vol: float = 0.8) -> np.ndarray:
    """将 add 音频混入 main (兼容单声道/立体声)"""
    m = min(len(main), len(add))
    add = add[:m]
    if main.ndim == 2 and main.shape[1] == 2:
        if add.ndim == 1:
            add = np.column_stack([add, add])
        main[:m] += add * vol
    else:
        if add.ndim == 2:
            add = add.mean(axis=1)
        main[:m] += add * vol
    return main


def _fade_edges(audio: np.ndarray, fade_in: float = 1.0, fade_out: float = 2.0) -> np.ndarray:
    """淡入淡出 (兼容单声道/立体声)"""
    n = audio.shape[0] if audio.ndim == 1 else audio.shape[0]
    fi = min(int(fade_in * SR), n // 2)
    fo = min(int(fade_out * SR), n // 2)
    is_stereo = audio.ndim == 2 and audio.shape[1] == 2
    fade = np.ones(n)
    if fi > 0:
        fade[:fi] = np.linspace(0, 1, fi)
    if fo > 0:
        fade[-fo:] = np.linspace(1, 0, fo)
    if is_stereo:
        audio[:, 0] *= fade
        audio[:, 1] *= fade
    else:
        audio *= fade
    return audio


def _normalize(audio: np.ndarray, peak: float = 0.95) -> np.ndarray:
    """峰值归一化"""
    audio = audio.astype(np.float64)
    p = np.max(np.abs(audio))
    if p > 0:
        audio = audio / p * peak
    return audio


def save_wav(audio: np.ndarray, filename: str):
    """保存 WAV 文件"""
    audio = _normalize(audio)
    path = os.path.join(OUTPUT_DIR, filename)
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))
    size_mb = os.path.getsize(path) / 1024 / 1024
    dur = len(audio) / SR
    print(f"  [OK] {filename}  ({dur:.0f}s, {size_mb:.1f}MB)")
    return path


# ═════════════════════════════════════════════════════════════
# 辅助: 快速创建 DrumPattern
# ═════════════════════════════════════════════════════════════

_T = True
_F = False


def _mk_drum(name, bpm, kick_t, snare_t, hh_t, kick_s=None, snare_s=None, hh_s=None):
    """快速构建鼓 Pattern"""
    return DrumPattern(name=name, steps=16, bpm=bpm, tracks={
        "kick": kick_t, "snare": snare_t, "hihat": hh_t,
    }, sounds={
        "kick": kick_s or DrumSoundParams(osc_type=OscType.SINE, pitch_hz=55, decay=0.22, volume=0.8),
        "snare": snare_s or DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=180, decay=0.15, hp_hz=250, volume=0.65),
        "hihat": hh_s or DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=8000, decay=0.06, hp_hz=1500, volume=0.35),
    })


# ═════════════════════════════════════════════════════════════
# 曲目 1: 晨曦序曲 — 古典/钢琴风格
# ═════════════════════════════════════════════════════════════

def track_01_dawn_overture():
    """古典钢琴风格：琶音 + 旋律，无鼓，温暖混响"""
    print("\n" + "=" * 50)
    print("  [Track 01] 晨曦序曲 — 古典/钢琴")
    print("=" * 50)

    bpm = 72
    total_dur = 120.0  # 2 分钟

    # 左手指音 (低音部)
    arp_notes = ["C3", "E3", "G3", "E3", "C3", "E3", "G3", "E3",
                 "A2", "C3", "E4", "C3", "A2", "C3", "E4", "C3",
                 "F2", "A2", "C4", "A2", "F2", "A2", "C4", "A2",
                 "G2", "B2", "D4", "B2", "G2", "B2", "D4", "B2"]
    arp_durs = [0.5] * 32

    left_hand = MusicPattern(
        name="piano_left", bpm=bpm, loop=True,
        notes=arp_notes, durations=arp_durs,
        osc_type=OscType.SINE, volume=0.18, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.25), (3.0, 0.12), (4.0, 0.05)],
        vibrato_rate=2.5, vibrato_depth=0.8,
        reverb_mix=0.3, reverb_decay=1.5, stereo_width=0.45, lp_filter_hz=3000,
    )

    # 右手旋律 (温暖三角波模拟钢琴)
    melody_notes = ["E4", "G4", "C5", None, "D5", "C5", "A4", None,
                    "G4", "E4", "C4", None, "E4", "D4", "C4", None,
                    "A4", "C5", "E5", "D5", "C5", "A4", "G4", "E4",
                    "F4", "A4", "C5", None, "G4", "E4", "C4", None]
    melody_durs = [0.75, 0.25, 1.0, 0.5, 0.5, 0.5, 1.0, 0.5,
                   0.75, 0.25, 1.0, 0.5, 0.75, 0.25, 1.0, 0.5,
                   0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 0.75, 0.25,
                   0.75, 0.25, 1.0, 0.5, 0.75, 0.25, 1.0, 0.5]

    right_hand = MusicPattern(
        name="piano_right", bpm=bpm, loop=True,
        notes=melody_notes, durations=melody_durs,
        osc_type=OscType.TRIANGLE, volume=0.22, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.2), (3.0, 0.08), (5.0, 0.02)],
        vibrato_rate=4.0, vibrato_depth=1.2,
        reverb_mix=0.3, reverb_decay=1.8, stereo_width=0.5, lp_filter_hz=4500,
    )

    # 和声层 (柔和弦乐垫底)
    chord_pad = MusicPattern(
        name="strings_pad", bpm=bpm, loop=True,
        chords=[["C3", "E4", "G4", "C5"], ["A2", "C4", "E4", "A4"],
                ["F2", "A3", "C4", "F4"], ["G2", "B3", "D4", "G4"]],
        notes=[None] * 8, durations=[4.0] * 8,
        osc_type=OscType.SINE, volume=0.08, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.15)],
        reverb_mix=0.4, reverb_decay=2.0, stereo_width=0.7, lp_filter_hz=2500,
    )

    # 编曲
    song = SongArrangement(name="dawn_overture", bpm=bpm)
    song.add_section("intro", 4, [left_hand, chord_pad])
    song.add_section("theme_a", 8, [left_hand, right_hand, chord_pad])
    song.add_section("theme_b", 8, [left_hand, right_hand, chord_pad])
    song.add_section("theme_a", 8, [left_hand, right_hand, chord_pad])
    song.add_section("bridge", 4, [left_hand, chord_pad])
    song.add_section("climax", 8, [left_hand, right_hand, chord_pad])
    song.add_section("outro", 4, [left_hand, chord_pad])

    audio = render_song(song)
    audio = _to_mono(audio)
    audio = _fade_edges(audio, 2.0, 5.0)
    save_wav(audio, "01_晨曦序曲_Dawn_Overture.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 2: 星海迷途 — 新世纪/太空风格
# ═════════════════════════════════════════════════════════════

def track_02_lost_in_cosmos():
    """新世纪：FM 合成钟声 + 环境铺底 + 扫频滤波"""
    print("\n" + "=" * 50)
    print("  [Track 02] 星海迷途 — 新世纪")
    print("=" * 50)

    bpm = 85
    total_dur = 140.0  # 2:20

    # FM 合成铃音旋律 (用高谐波模拟金属质感)
    fm_melody = MusicPattern(
        name="cosmos_bell", bpm=bpm, loop=True,
        notes=["E5", None, "G5", None, "B5", "A5", "G5", "E5",
               "D5", None, "F5", None, "A5", "G5", "F5", "D5",
               "C5", None, "E5", None, "G5", "F5", "E5", "C5",
               "A4", None, "C5", None, "E5", "D5", "C5", None],
        durations=[0.75, 0.25, 0.75, 0.25, 0.5, 0.5, 1.0, 0.5,
                   0.75, 0.25, 0.75, 0.25, 0.5, 0.5, 1.0, 0.5,
                   0.75, 0.25, 0.75, 0.25, 0.5, 0.5, 1.0, 0.5,
                   0.75, 0.25, 0.75, 0.25, 0.5, 0.5, 1.0, 0.5],
        osc_type=OscType.SINE, volume=0.16, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (3.0, 0.4), (5.0, 0.2), (7.0, 0.1), (9.0, 0.05)],
        vibrato_rate=5.5, vibrato_depth=2.0,
        reverb_mix=0.5, reverb_decay=2.5, stereo_width=0.8, lp_filter_hz=5000,
    )

    # 太空铺底 (长和弦)
    space_pad = MusicPattern(
        name="space_drone", bpm=bpm, loop=True,
        chords=[["E3", "G3", "B3", "D4"], ["D3", "F3", "A3", "C4"],
                ["C3", "E3", "G3", "B3"], ["A2", "C3", "E3", "G3"]],
        notes=[None] * 8, durations=[4.0] * 8,
        osc_type=OscType.TRIANGLE, volume=0.07, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.12), (4.0, 0.05)],
        reverb_mix=0.5, reverb_decay=3.0, stereo_width=0.9, lp_filter_hz=2000,
    )

    # 轻柔鼓点 (稀疏)
    drum = _mk_drum("cosmos_drums", bpm,
        [_T, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _F, _F],
        [_F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F],
        [_F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=45, decay=0.4, volume=0.6),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=150, decay=0.25, hp_hz=200, volume=0.3))

    song = SongArrangement(name="lost_in_cosmos", bpm=bpm,
                           master_chain=EFFECT_PRESETS["ambient"])
    song.add_section("intro", 8, [space_pad])
    song.add_section("body", 16, [fm_melody, space_pad], drum)
    song.add_section("climax", 8, [fm_melody, space_pad], drum)
    song.add_section("resolution", 16, [fm_melody, space_pad])
    song.add_section("outro", 8, [space_pad])

    audio = render_song(song)
    audio = _to_mono(audio)

    # 星空扫频效果
    total_dur_actual = len(audio) / SR
    sweep = AutomationLane("cutoff", [
        (0.0, 1500), (total_dur_actual * 0.3, 8000),
        (total_dur_actual * 0.6, 8000), (total_dur_actual, 1500),
    ], interpolate="smooth")
    audio = apply_filter_sweep(audio, sweep, filter_type="lowpass", q=1.0)

    audio = _fade_edges(audio, 3.0, 6.0)
    save_wav(audio, "02_星海迷途_Lost_in_Cosmos.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 3: 深海絮语 — 氛围音乐
# ═════════════════════════════════════════════════════════════

def track_03_deep_sea_whispers():
    """氛围音乐：极简旋律、深海垫底、长混响"""
    print("\n" + "=" * 50)
    print("  [Track 03] 深海絮语 — 氛围音乐")
    print("=" * 50)

    bpm = 60
    total_dur = 160.0  # 2:40

    # 深海低音垫底
    deep_drone = MusicPattern(
        name="ocean_deep", bpm=bpm, loop=True,
        notes=["C2", None, None, None, "G2", None, None, None,
               "F2", None, None, None, "C2", None, None, None],
        durations=[4.0] * 4 + [4.0] * 4 + [4.0] * 4 + [4.0] * 4,
        osc_type=OscType.SINE, volume=0.2, env_shape=EnvShape.SWELL,
        harmonics=[(0.5, 0.5), (1.0, 1.0), (2.0, 0.15)],
        reverb_mix=0.6, reverb_decay=4.0, stereo_width=0.9, lp_filter_hz=800,
    )

    # 中层漂浮旋律
    float_melody = MusicPattern(
        name="floating_mid", bpm=bpm, loop=True,
        notes=["C4", None, None, None, "Eb4", None, None, None,
               "G4", None, "Eb4", None, "C4", None, None, None,
               "F4", None, None, None, "Ab4", None, None, None,
               "C5", None, "Ab4", None, "F4", None, None, None],
        durations=[0.75, 0.25, 0.5, 0.5] * 4 + [0.75, 0.25, 0.5, 0.5] * 4,
        osc_type=OscType.TRIANGLE, volume=0.1, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.1), (4.0, 0.03)],
        vibrato_rate=2.0, vibrato_depth=2.5,
        reverb_mix=0.55, reverb_decay=3.5, stereo_width=0.85, lp_filter_hz=2500,
    )

    # 高频闪烁
    sparkle = MusicPattern(
        name="sparkle", bpm=bpm, loop=True,
        notes=["C6", None, None, None, None, "G5", None, None,
               "E6", None, None, None, None, "C6", None, None],
        durations=[0.25, 0.5, 0.5, 0.5] * 2 + [0.25, 0.5, 0.5, 0.5] * 2,
        osc_type=OscType.SINE, volume=0.06, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(3.0, 0.3), (5.0, 0.15)],
        reverb_mix=0.6, reverb_decay=5.0, stereo_width=0.95, lp_filter_hz=6000,
    )

    song = SongArrangement(name="deep_sea", bpm=bpm,
                           master_chain=EFFECT_PRESETS["ambient"])
    song.add_section("layer_a", 16, [deep_drone])
    song.add_section("layer_b", 16, [deep_drone, float_melody])
    song.add_section("layer_c", 16, [deep_drone, float_melody, sparkle])
    song.add_section("layer_b2", 8, [deep_drone, float_melody])
    song.add_section("layer_a2", 8, [deep_drone])

    audio = render_song(song)
    audio = _to_mono(audio)
    audio = _fade_edges(audio, 5.0, 8.0)
    save_wav(audio, "03_深海絮语_Deep_Sea_Whispers.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 4: 午夜爵士 — 爵士/蓝调风格
# ═════════════════════════════════════════════════════════════

def track_04_midnight_jazz():
    """爵士：三连音摇摆感、蓝调音阶、温暖 EQ、行走 Bass"""
    print("\n" + "=" * 50)
    print("  [Track 04] 午夜爵士 — 爵士")
    print("=" * 50)

    bpm = 90
    total_dur = 120.0  # 2:00

    # 爵士旋律 (蓝调音阶 + 摇摆节奏)
    jazz_lead = MusicPattern(
        name="jazz_lead", bpm=bpm, loop=True,
        notes=["Eb4", "F4", "Gb4", "G4", "Bb4", "G4", "F4", "Eb4",
               "C4", "Eb4", "F4", "Gb4", "F4", "Eb4", "C4", None,
               "Eb4", "F4", "G4", "Bb4", "C5", "Bb4", "G4", "F4",
               "Eb4", "C4", "Eb4", "F4", "Eb4", "C4", "Bb3", None],
        durations=[0.66, 0.34, 0.5, 0.5, 0.66, 0.34, 0.5, 0.5,
                   0.66, 0.34, 0.5, 0.5, 0.66, 0.34, 1.0, 0.5,
                   0.66, 0.34, 0.5, 0.5, 0.66, 0.34, 0.5, 0.5,
                   0.66, 0.34, 0.5, 0.5, 0.66, 0.34, 1.0, 0.5],
        osc_type=OscType.TRIANGLE, volume=0.18, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.2), (3.0, 0.08)],
        vibrato_rate=5.0, vibrato_depth=1.5,
        reverb_mix=0.15, reverb_decay=0.8, stereo_width=0.35, lp_filter_hz=4000,
    )

    # 爵士和弦 (七和弦)
    jazz_chords = MusicPattern(
        name="jazz_chords", bpm=bpm, loop=True,
        chords=[["Eb3", "G3", "Bb3", "D4"], ["Ab3", "C4", "Eb4", "G4"],
                ["Bb2", "D3", "F3", "Ab3"], ["Eb3", "G3", "Bb3", "D4"]],
        notes=[None] * 4, durations=[4.0] * 4,
        osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.15), (3.0, 0.05)],
        reverb_mix=0.2, stereo_width=0.4, lp_filter_hz=3500,
    )

    # 轻爵士鼓 (刷子感)
    jazz_drum = _mk_drum("jazz_drums", bpm,
        [_T, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _T, _F],
        [_F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F],
        [_T, _F, _T, _T, _T, _F, _T, _T, _T, _F, _T, _F, _T, _T, _T, _F],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=60, decay=0.15, volume=0.7),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=160, decay=0.12, hp_hz=200, volume=0.4),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=6000, decay=0.05, hp_hz=1500, volume=0.22))

    song = SongArrangement(name="midnight_jazz", bpm=bpm,
                           master_chain=EffectChain(
                               lp_filter_hz=12000,
                               reverb_mix=0.15, reverb_decay=1.0, stereo_width=0.4,
                               eq=ParametricEQParams(low_freq=100, low_gain_db=2, low_q=0.6,
                                                     mid_freq=800, mid_gain_db=-3, mid_q=1.2,
                                                     high_freq=10000, high_gain_db=-2, high_q=0.5),
                               compressor=CompressorParams(threshold_db=-18, ratio=2.5,
                                                          attack_ms=10, release_ms=150, makeup_db=2),
                           ))
    song.add_section("head", 8, [jazz_lead, jazz_chords], jazz_drum)
    song.add_section("solo", 8, [jazz_lead, jazz_chords], jazz_drum)
    song.add_section("head", 8, [jazz_lead, jazz_chords], jazz_drum)
    song.add_section("bridge", 4, [jazz_chords], jazz_drum)
    song.add_section("head", 8, [jazz_lead, jazz_chords], jazz_drum)
    song.add_section("outro", 4, [jazz_lead])

    audio = render_song(song)
    audio = _to_mono(audio)

    # Jazz Bass (Sub 风格 walking bass)
    bass_pat = MusicPattern(
        name="jazz_bass", bpm=bpm, loop=True,
        notes=["Eb1", "G1", "Bb1", "D2", "Ab1", "C2", "Eb2", "G2",
               "Bb1", "D2", "F2", "Ab2", "Eb1", "G1", "Bb1", "C2"],
        durations=[0.5] * 16,
        osc_type=OscType.SINE, volume=0.7, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.15)],
    )
    bass_synth = BassSynth.preset("sub")
    b_audio = render_bass_pattern(bass_pat, bass_synth, len(audio) / SR)
    audio = _mix_audio(audio, b_audio, 0.7)
    audio = _fade_edges(audio, 1.0, 3.0)
    save_wav(audio, "04_午夜爵士_Midnight_Jazz.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 5: 霓虹脉冲 — 电子/EDM
# ═════════════════════════════════════════════════════════════

def track_05_neon_pulse():
    """电子/EDM：方波 Lead + Acid Bass + Drop + 滤波器扫频"""
    print("\n" + "=" * 50)
    print("  [Track 05] 霓虹脉冲 — 电子/EDM")
    print("=" * 50)

    bpm = 128
    kit = STYLE_KITS["edm"]
    total_dur = 140.0  # 2:20

    # EDM Lead (方波, 能量感)
    edm_lead = MusicPattern(
        name="neon_lead", bpm=bpm, loop=True,
        notes=["C4", "E4", "G4", "C5", "G4", "E4", "C4", "D4",
               "F4", "A4", "D5", "A4", "F4", "D4", "G4", "C5"],
        durations=[0.25] * 16,
        osc_type=OscType.SQUARE, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.1), (3.0, 0.05)],
        reverb_mix=0.1, stereo_width=0.5, lp_filter_hz=8000,
    )

    # EDM 和弦 Pad
    edm_pad = MusicPattern(
        name="neon_pad", bpm=bpm, loop=True,
        chords=[["C3", "E4", "G4", "C5"], ["G2", "B3", "D4", "G4"],
                ["A2", "C4", "E4", "A4"], ["F2", "A3", "C4", "F4"]],
        notes=[None] * 4, durations=[4.0] * 4,
        osc_type=OscType.SAW, volume=0.1, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.2)],
        reverb_mix=0.3, stereo_width=0.8, lp_filter_hz=6000,
    )

    # EDM 鼓
    edm_drum = kit["drum"](bpm)

    song = SongArrangement(name="neon_pulse", bpm=bpm,
                           master_chain=kit["master"])
    song.add_section("intro", 8, [edm_pad])
    song.add_section("build", 4, [edm_pad], edm_drum)
    song.add_section("drop", 16, [edm_lead, edm_pad], edm_drum)
    song.add_section("break", 8, [edm_pad])
    song.add_section("build", 4, [edm_pad], edm_drum)
    song.add_section("drop", 16, [edm_lead, edm_pad], edm_drum)
    song.add_section("outro", 8, [edm_lead])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur_actual = len(audio) / SR

    # Acid Bass
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur_actual)
    audio = _mix_audio(audio, b_audio, 0.85)

    # Drop 效果: 滤波器渐开
    from bloodmusic.music.automation import drop_filter_resonance
    drop_lane = drop_filter_resonance(total_dur_actual)
    audio = apply_filter_sweep(audio, drop_lane, filter_type="lowpass", q=3.0)

    audio = _fade_edges(audio, 1.0, 3.0)
    save_wav(audio, "05_霓虹脉冲_Neon_Pulse.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 6: 英雄远征 — 影视史诗
# ═════════════════════════════════════════════════════════════

def track_06_heros_journey():
    """影视史诗：FM Bass + 和声层 + 战斗鼓 + 渐强结构"""
    print("\n" + "=" * 50)
    print("  [Track 06] 英雄远征 — 影视史诗")
    print("=" * 50)

    bpm = 100
    total_dur = 140.0  # 2:20

    # 主题旋律 (小调, 英雄感)
    hero_melody = MusicPattern(
        name="hero_theme", bpm=bpm, loop=True,
        notes=["C3", "Eb3", "G3", "C4", "G3", "Eb3", "C3", "G2",
               "Ab2", "C3", "Eb3", "Ab3", "G3", "Eb3", "C3", "G3"],
        durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
                   0.5, 0.5, 0.5, 0.5, 0.75, 0.25, 0.5, 1.0],
        osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
        harmonics=[(0.5, 0.2), (2.0, 0.15), (3.0, 0.08)],
        vibrato_rate=3.0, vibrato_depth=1.5,
        reverb_mix=0.15, stereo_width=0.5, lp_filter_hz=5000,
    )

    # 和声 (五度 + 三度, 史诗感)
    hero_harmony = MusicPattern(
        name="hero_harmony", bpm=bpm, loop=True,
        notes=["G3", "Bb3", "D4", "G4", "D4", "Bb3", "G3", "D3",
               "Eb3", "G3", "Bb3", "Eb4", "D4", "Bb3", "G3", "D4"],
        durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
                   0.5, 0.5, 0.5, 0.5, 0.75, 0.25, 0.5, 1.0],
        osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.2), (3.0, 0.1)],
        reverb_mix=0.2, stereo_width=0.4, lp_filter_hz=4000,
    )

    # 弦乐垫底
    epic_pad = MusicPattern(
        name="epic_strings", bpm=bpm, loop=True,
        chords=[["C2", "C3", "Eb3", "G3"], ["Ab2", "Ab3", "C4", "Eb4"],
                ["F2", "F3", "Ab3", "C4"], ["G2", "G3", "B3", "D4"]],
        notes=[None] * 4, durations=[4.0] * 4,
        osc_type=OscType.SAW, volume=0.08, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.15)],
        reverb_mix=0.3, stereo_width=0.7, lp_filter_hz=3000,
    )

    # 战斗鼓
    battle_drum = _mk_drum("epic_drums", bpm,
        [_T, _F, _F, _T, _T, _F, _F, _F, _T, _F, _T, _F, _T, _F, _F, _T],
        [_F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _T, _F, _T, _F, _F, _F],
        [_T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=48, decay=0.18, volume=0.88),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=210, decay=0.1, hp_hz=350, volume=0.75),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=10000, decay=0.03, hp_hz=2500, volume=0.45))

    song = SongArrangement(name="heros_journey", bpm=bpm,
                           master_chain=EFFECT_PRESETS["battle"])
    song.add_section("intro", 4, [epic_pad])
    song.add_section("theme", 8, [hero_melody, epic_pad], battle_drum)
    song.add_section("conflict", 8, [hero_melody, hero_harmony, epic_pad], battle_drum)
    song.add_section("climax", 8, [hero_melody, hero_harmony, epic_pad], battle_drum)
    song.add_section("resolution", 4, [hero_melody, epic_pad])
    song.add_section("finale", 8, [hero_melody, hero_harmony, epic_pad], battle_drum)
    song.add_section("outro", 4, [epic_pad])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur_actual = len(audio) / SR

    # FM Bass
    fm_bass_pat = MusicPattern(
        name="epic_fm_bass", bpm=bpm, loop=True,
        notes=["C1", "C1", "G1", "G1", "Ab1", "Ab1", "F1", "F1",
               "C1", "C1", "G1", "G1", "Ab1", "Ab1", "G1", "G1"],
        durations=[0.25] * 16,
        osc_type=OscType.SAW, volume=0.78, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(0.5, 0.25)],
    )
    fm_bass = BassSynth.preset("fm")
    b_audio = render_bass_pattern(fm_bass_pat, fm_bass, total_dur_actual)
    audio = _mix_audio(audio, b_audio, 0.85)

    # 渐强扫频
    sweep = AutomationLane("cutoff", [
        (0.0, 400), (total_dur_actual * 0.2, 20000),
        (total_dur_actual, 20000),
    ], interpolate="smooth")
    audio = apply_filter_sweep(audio, sweep, filter_type="lowpass", q=1.5)

    audio = _fade_edges(audio, 1.0, 2.5)
    save_wav(audio, "06_英雄远征_Heros_Journey.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 7: 旧日时光 — Lo-Fi 低保真
# ═════════════════════════════════════════════════════════════

def track_07_nostalgia():
    """Lo-Fi：温暖七和弦、低保真滤波、柔和鼓点、Sub Bass"""
    print("\n" + "=" * 50)
    print("  [Track 07] 旧日时光 — Lo-Fi")
    print("=" * 50)

    bpm = 78
    total_dur = 120.0  # 2:00

    # Lo-Fi 爵士和弦 (七和弦, 温暖)
    lofi_chords = MusicPattern(
        name="lofi_chords", bpm=bpm, loop=True,
        chords=[["A3", "C4", "E4", "G4"], ["D4", "F4", "A4", "C5"],
                ["G3", "B3", "D4", "F4"], ["C4", "E4", "G4", "B4"],
                ["F3", "A3", "C4", "E4"], ["E3", "G3", "B3", "D4"],
                ["A3", "C4", "E4", "G4"], ["D4", "F4", "A4", "C5"]],
        notes=[None] * 8, durations=[2.0] * 8,
        osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.25), (3.0, 0.1)],
        vibrato_rate=3.0, vibrato_depth=0.12,
        reverb_mix=0.35, reverb_decay=1.8, stereo_width=0.65, lp_filter_hz=3000,
    )

    # Lo-Fi 旋律
    lofi_melody = MusicPattern(
        name="lofi_lead", bpm=bpm, loop=True,
        notes=["E5", None, "G5", "A5", "B5", "A5", "G5", "E5",
               "D5", None, "F5", "G5", "A5", "G5", "F5", "D5",
               "C5", None, "E5", "D5", "C5", "B4", "A4", "C5",
               "E5", None, "D5", "C5", "B4", "A4", "G4", None],
        durations=[0.5, 0.25, 0.5, 0.5, 0.75, 0.25, 0.5, 0.5,
                   0.5, 0.25, 0.5, 0.5, 0.75, 0.25, 0.5, 0.5,
                   0.5, 0.25, 0.5, 0.5, 0.75, 0.25, 0.5, 0.5,
                   0.5, 0.25, 0.5, 0.5, 0.75, 0.25, 1.0, 0.5],
        osc_type=OscType.TRIANGLE, volume=0.14, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.18), (3.0, 0.08)],
        vibrato_rate=4.0, vibrato_depth=1.0,
        reverb_mix=0.3, reverb_decay=1.5, stereo_width=0.5, lp_filter_hz=3500,
    )

    # Lo-Fi 鼓 (稀疏, 温暖)
    lofi_drum = _mk_drum("lofi_drums", bpm,
        [_T, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _F, _F],
        [_F, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _F, _F],
        [_T, _F, _F, _T, _F, _F, _T, _F, _T, _F, _F, _F, _T, _F, _T, _F],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=55, decay=0.22, volume=0.7),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=180, decay=0.15, hp_hz=250, volume=0.4),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=6000, decay=0.06, hp_hz=1500, volume=0.25))

    song = SongArrangement(name="nostalgia", bpm=bpm,
                           master_chain=EFFECT_PRESETS["lofi"])
    song.add_section("intro", 4, [lofi_chords])
    song.add_section("verse", 8, [lofi_melody, lofi_chords], lofi_drum)
    song.add_section("chorus", 8, [lofi_melody, lofi_chords], lofi_drum)
    song.add_section("verse", 8, [lofi_melody, lofi_chords], lofi_drum)
    song.add_section("outro", 4, [lofi_chords])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur_actual = len(audio) / SR

    # Sub Bass (柔和低频)
    lofi_bass_pat = MusicPattern(
        name="lofi_bass", bpm=bpm, loop=True,
        notes=["A1", "C2", "E2", "G2", "D2", "F2", "A2", "C2",
               "G1", "B1", "D2", "F2", "C2", "E2", "G2", "B1"],
        durations=[0.5] * 16,
        osc_type=OscType.SINE, volume=0.65, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.12)],
    )
    sub_bass = BassSynth.preset("sub")
    b_audio = render_bass_pattern(lofi_bass_pat, sub_bass, total_dur_actual)
    audio = _mix_audio(audio, b_audio, 0.6)

    # Lo-Fi 特色: 低保真低通滤波
    audio = apply_resonant_lpf(audio, 4000, q=0.5)
    audio = _fade_edges(audio, 1.5, 4.0)
    save_wav(audio, "07_旧日时光_Nostalgia.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 8: 空山鸟语 — 冥想/自然风格
# ═════════════════════════════════════════════════════════════

def track_08_birds_in_mountains():
    """冥想/自然：五声音阶、Karplus-Strong 弹拨音、极简、空灵"""
    print("\n" + "=" * 50)
    print("  [Track 08] 空山鸟语 — 冥想/自然")
    print("=" * 50)

    bpm = 55
    total_dur = 160.0  # 2:40

    # 五声音阶垫底 (C D E G A)
    penta_pad = MusicPattern(
        name="mountain_drone", bpm=bpm, loop=True,
        notes=["C3", None, None, None, "G3", None, None, None,
               "C3", None, "E3", None, "G3", None, None, None,
               "D3", None, None, None, "A3", None, None, None,
               "E3", None, "G3", None, "C4", None, None, None],
        durations=[1.0, 0.5, 0.5, 0.5] * 4 + [1.0, 0.5, 0.5, 0.5] * 4,
        osc_type=OscType.SINE, volume=0.09, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.08), (4.0, 0.03)],
        reverb_mix=0.6, reverb_decay=4.0, stereo_width=0.9, lp_filter_hz=1500,
    )

    # 鸟鸣般的高音闪烁 (五声音阶)
    bird_notes = ["C5", None, "E5", None, "G5", "E5", "C5", None,
                  "D5", None, "E5", "G5", "A5", "G5", "E5", "D5",
                  "C5", None, None, "D5", "E5", None, "C5", None,
                  "A4", "C5", "E5", None, "G5", "E5", "D5", None]
    bird_durs = [0.25, 0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5,
                 0.25, 0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.5,
                 0.5, 0.25, 0.25, 0.25, 0.5, 0.25, 0.5, 0.5,
                 0.25, 0.25, 0.25, 0.25, 0.5, 0.25, 0.5, 0.5]

    bird_song = MusicPattern(
        name="bird_song", bpm=bpm, loop=True,
        notes=bird_notes, durations=bird_durs,
        osc_type=OscType.SINE, volume=0.1, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(2.0, 0.3), (3.0, 0.15), (5.0, 0.08)],
        vibrato_rate=6.0, vibrato_depth=3.0,
        reverb_mix=0.7, reverb_decay=5.0, stereo_width=0.95, lp_filter_hz=6000,
    )

    # 低频共鸣 (16 个 notes 配 16 个 durations)
    deep_resonance = MusicPattern(
        name="mountain_deep", bpm=bpm, loop=True,
        notes=["C2", None, None, None, None, None, None, None,
               "G1", None, None, None, None, None, None, None],
        durations=[8.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
                   8.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.SWELL,
        harmonics=[(0.5, 0.5), (1.0, 1.0)],
        reverb_mix=0.5, reverb_decay=5.0, stereo_width=0.8, lp_filter_hz=400,
    )

    song = SongArrangement(name="birds_mountains", bpm=bpm,
                           master_chain=EFFECT_PRESETS["ambient"])
    song.add_section("dawn", 16, [penta_pad, deep_resonance])
    song.add_section("morning", 8, [penta_pad, bird_song, deep_resonance])
    song.add_section("noon", 8, [penta_pad, bird_song, deep_resonance])
    song.add_section("afternoon", 8, [penta_pad, deep_resonance])
    song.add_section("dusk", 8, [penta_pad, bird_song, deep_resonance])
    song.add_section("night", 8, [penta_pad, deep_resonance])

    audio = render_song(song)
    audio = _to_mono(audio)
    audio = _fade_edges(audio, 5.0, 8.0)
    save_wav(audio, "08_空山鸟语_Birds_in_Mountains.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 9: 田园小调 — 民谣/世界音乐
# ═════════════════════════════════════════════════════════════

def track_09_pastoral_tune():
    """民谣/世界音乐：五声音阶、Pluck 拨弦声、轻快节奏、自然音色"""
    print("\n" + "=" * 50)
    print("  [Track 09] 田园小调 — 民谣/世界音乐")
    print("=" * 50)

    bpm = 80
    total_dur = 120.0  # 2:00

    # 民谣主旋律 (五声音阶, 轻快)
    folk_melody = MusicPattern(
        name="folk_theme", bpm=bpm, loop=True,
        notes=["C4", "D4", "E4", "G4", "A4", "G4", "E4", "D4",
               "C4", "D4", "E4", "C4", "D4", "E4", "G4", "A4",
               "G4", "E4", "D4", "C4", "D4", "E4", "G4", None,
               "A4", "G4", "E4", "C4", "D4", "E4", "C4", None],
        durations=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5,
                   0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5,
                   0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5,
                   0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 0.5],
        osc_type=OscType.TRIANGLE, volume=0.18, env_shape=EnvShape.PLUCK,
        harmonics=[(1.0, 1.0), (2.0, 0.2), (4.0, 0.08)],
        vibrato_rate=3.5, vibrato_depth=1.0,
        reverb_mix=0.2, reverb_decay=1.0, stereo_width=0.4, lp_filter_hz=4500,
    )

    # 和声 (三度平行)
    folk_harmony = MusicPattern(
        name="folk_harmony", bpm=bpm, loop=True,
        notes=["E4", "F4", "G4", "B4", "C5", "B4", "G4", "F4",
               "E4", "F4", "G4", "E4", "F4", "G4", "B4", "C5",
               "B4", "G4", "F4", "E4", "F4", "G4", "B4", None,
               "C5", "B4", "G4", "E4", "F4", "G4", "E4", None],
        durations=[0.5] * 32,
        osc_type=OscType.SINE, volume=0.1, env_shape=EnvShape.PLUCK,
        harmonics=[(2.0, 0.15), (3.0, 0.05)],
        reverb_mix=0.25, stereo_width=0.3, lp_filter_hz=3500,
    )

    # 轻打击 (手鼓感)
    folk_drum = _mk_drum("folk_perc", bpm,
        [_T, _F, _F, _F, _T, _F, _F, _F, _T, _F, _F, _F, _T, _F, _F, _F],
        [_F, _F, _F, _F, _F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _F, _F],
        [_F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F, _F],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=60, decay=0.18, volume=0.65),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=160, decay=0.1, hp_hz=200, volume=0.35))

    # 田园 Pad (长和弦衬托)
    pastoral_pad = MusicPattern(
        name="pastoral_pad", bpm=bpm, loop=True,
        chords=[["C3", "E4", "G4"], ["D3", "F4", "A4"],
                ["E3", "G4", "B4"], ["C3", "E4", "G4"]],
        notes=[None] * 4, durations=[4.0] * 4,
        osc_type=OscType.SINE, volume=0.08, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.12)],
        reverb_mix=0.3, stereo_width=0.5, lp_filter_hz=3000,
    )

    song = SongArrangement(name="pastoral_tune", bpm=bpm,
                           master_chain=EffectChain(
                               lp_filter_hz=12000,
                               reverb_mix=0.18, reverb_decay=1.2, stereo_width=0.4,
                               eq=ParametricEQParams(low_freq=150, low_gain_db=1, low_q=0.6,
                                                     high_freq=10000, high_gain_db=-1, high_q=0.5),
                               compressor=CompressorParams(threshold_db=-20, ratio=2,
                                                          attack_ms=15, release_ms=200, makeup_db=2),
                           ))
    song.add_section("intro", 4, [pastoral_pad])
    song.add_section("verse", 8, [folk_melody, folk_harmony, pastoral_pad], folk_drum)
    song.add_section("chorus", 8, [folk_melody, folk_harmony, pastoral_pad], folk_drum)
    song.add_section("verse", 8, [folk_melody, folk_harmony, pastoral_pad], folk_drum)
    song.add_section("outro", 4, [folk_melody, pastoral_pad])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur_actual = len(audio) / SR

    # Pluck Bass
    pluck_bass_pat = MusicPattern(
        name="folk_bass", bpm=bpm, loop=True,
        notes=["C2", "C2", "G1", "G1", "A1", "E1", "F1", "G1",
               "C2", "C2", "G1", "G1", "A1", "E1", "F1", "C2"],
        durations=[0.5] * 16,
        osc_type=OscType.SINE, volume=0.6, env_shape=EnvShape.PLUCK,
        harmonics=[(2.0, 0.12)],
    )
    pluck_bass = BassSynth.preset("pluck")
    b_audio = render_bass_pattern(pluck_bass_pat, pluck_bass, total_dur_actual)
    audio = _mix_audio(audio, b_audio, 0.6)

    audio = _fade_edges(audio, 1.0, 3.0)
    save_wav(audio, "09_田园小调_Pastoral_Tune.wav")


# ═════════════════════════════════════════════════════════════
# 曲目 10: 终章·重生 — 史诗终章
# ═════════════════════════════════════════════════════════════

def track_10_finale_rebirth():
    """史诗终章：全引擎编曲、多段结构、和声层叠、渐强收尾"""
    print("\n" + "=" * 50)
    print("  [Track 10] 终章·重生 — 史诗终章")
    print("=" * 50)

    bpm = 110
    total_dur = 160.0  # 2:40

    # 宏大主题旋律
    finale_lead = MusicPattern(
        name="finale_lead", bpm=bpm, loop=True,
        notes=["C4", "E4", "G4", "C5", "B4", "G4", "E4", "C4",
               "A4", "C5", "E5", "D5", "C5", "A4", "G4", "E4",
               "F4", "A4", "C5", "F5", "E5", "C5", "A4", "G4",
               "C4", "E4", "G4", "C5", "G4", "E4", "C4", "C5"],
        durations=[0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5,
                   0.5, 0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 0.5,
                   0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0, 0.5,
                   0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 0.5, 1.0],
        osc_type=OscType.TRIANGLE, volume=0.17, env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.22), (3.0, 0.1), (4.0, 0.04)],
        vibrato_rate=4.5, vibrato_depth=1.8,
        reverb_mix=0.22, reverb_decay=1.2, stereo_width=0.5, lp_filter_hz=5000,
    )

    # 第二旋律层 (丰富和声)
    finale_harmony2 = MusicPattern(
        name="finale_h2", bpm=bpm, loop=True,
        notes=["E4", "G4", "B4", "E5", "D5", "B4", "G4", "E4",
               "C5", "E5", "A5", "G5", "E5", "C5", "B4", "G4",
               "A4", "C5", "F5", "A5", "G5", "F5", "C5", "B4",
               "E4", "G4", "B4", "E5", "B4", "G4", "E4", "E5"],
        durations=[0.5] * 32,
        osc_type=OscType.SINE, volume=0.11, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.18), (3.0, 0.08)],
        reverb_mix=0.25, stereo_width=0.3, lp_filter_hz=4500,
    )

    # 史诗垫底
    finale_pad = MusicPattern(
        name="finale_pad", bpm=bpm, loop=True,
        chords=[["C2", "G3", "C4", "E4"], ["A2", "E3", "A3", "C4"],
                ["F2", "C3", "F3", "A3"], ["G2", "D3", "G3", "B3"],
                ["C2", "G3", "C4", "E4"], ["A2", "E3", "A3", "C4"],
                ["F2", "C3", "F3", "A3"], ["G2", "D3", "G3", "C4"]],
        notes=[None] * 8, durations=[2.0] * 8,
        osc_type=OscType.SAW, volume=0.08, env_shape=EnvShape.SWELL,
        harmonics=[(1.0, 1.0), (2.0, 0.12)],
        reverb_mix=0.35, stereo_width=0.8, lp_filter_hz=3000,
    )

    # 史诗鼓
    epic_drum = _mk_drum("finale_drums", bpm,
        [_T, _F, _F, _T, _T, _F, _F, _F, _T, _F, _T, _F, _T, _F, _F, _T],
        [_F, _F, _F, _F, _T, _F, _F, _F, _F, _F, _T, _F, _T, _F, _F, _F],
        [_T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T, _T],
        DrumSoundParams(osc_type=OscType.SINE, pitch_hz=50, decay=0.18, volume=0.9),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=210, decay=0.1, hp_hz=350, volume=0.75),
        DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=10000, decay=0.03, hp_hz=2500, volume=0.45))

    song = SongArrangement(name="finale_rebirth", bpm=bpm,
                           master_chain=EFFECT_PRESETS["battle"])
    # 逐渐加强的结构
    song.add_section("intro", 4, [finale_pad])
    song.add_section("build_a", 8, [finale_lead, finale_pad])
    song.add_section("theme", 8, [finale_lead, finale_harmony2, finale_pad], epic_drum)
    song.add_section("conflict", 8, [finale_lead, finale_harmony2, finale_pad], epic_drum)
    song.add_section("climax", 8, [finale_lead, finale_harmony2, finale_pad], epic_drum)
    song.add_section("resolution", 8, [finale_lead, finale_harmony2, finale_pad], epic_drum)
    song.add_section("finale", 8, [finale_lead, finale_harmony2, finale_pad], epic_drum)
    song.add_section("outro", 4, [finale_lead, finale_pad])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur_actual = len(audio) / SR

    # FM Bass 强劲低频
    finale_bass_pat = MusicPattern(
        name="finale_bass", bpm=bpm, loop=True,
        notes=["C1", "C1", "G1", "G1", "A1", "A1", "F1", "F1",
               "C1", "C1", "G1", "G1", "A1", "A1", "G1", "C2"],
        durations=[0.25] * 16,
        osc_type=OscType.SAW, volume=0.8, env_shape=EnvShape.PERCUSSIVE,
        harmonics=[(0.5, 0.3)],
    )
    fm_bass = BassSynth.preset("fm")
    b_audio = render_bass_pattern(finale_bass_pat, fm_bass, total_dur_actual)
    audio = _mix_audio(audio, b_audio, 0.9)

    # 终章扫频: 从暗到明
    sweep = AutomationLane("cutoff", [
        (0.0, 300), (total_dur_actual * 0.15, 5000),
        (total_dur_actual * 0.5, 20000),
        (total_dur_actual * 0.8, 20000),
        (total_dur_actual * 0.9, 8000),
        (total_dur_actual, 2000),
    ], interpolate="smooth")
    audio = apply_filter_sweep(audio, sweep, filter_type="lowpass", q=2.0)

    # 渐强音量
    vol_lane = AutomationLane("volume", [
        (0.0, 0.3), (total_dur_actual * 0.1, 0.8),
        (total_dur_actual * 0.15, 1.0),
        (total_dur_actual * 0.85, 1.0),
        (total_dur_actual, 0.0),
    ], interpolate="smooth")
    audio = apply_volume_automation(audio, vol_lane)

    audio = _fade_edges(audio, 0.5, 5.0)
    save_wav(audio, "10_终章·重生_Finale_Rebirth.wav")


# ═════════════════════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print(f"  BloodMusic 纯音乐专辑生成器")
    print(f"  《{ALBUM_NAME}》 — BloodSound Fantasia")
    print(f"  制作引擎: BloodMusic v2.0.0")
    print(f"  输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    tracks = [
        ("01", "晨曦序曲", track_01_dawn_overture),
        ("02", "星海迷途", track_02_lost_in_cosmos),
        ("03", "深海絮语", track_03_deep_sea_whispers),
        ("04", "午夜爵士", track_04_midnight_jazz),
        ("05", "霓虹脉冲", track_05_neon_pulse),
        ("06", "英雄远征", track_06_heros_journey),
        ("07", "旧日时光", track_07_nostalgia),
        ("08", "空山鸟语", track_08_birds_in_mountains),
        ("09", "田园小调", track_09_pastoral_tune),
        ("10", "终章·重生", track_10_finale_rebirth),
    ]

    generated_files = []
    for num, name, func in tracks:
        try:
            func()
        except Exception as e:
            print(f"\n  [ERROR] Track {num} {name}: {e}")
            import traceback
            traceback.print_exc()

    # 生成专辑信息文件
    info_path = os.path.join(OUTPUT_DIR, "ALBUM_INFO.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(f"专辑名称: {ALBUM_NAME}\n")
        f.write(f"英文名称: BloodSound Fantasia\n")
        f.write(f"制作引擎: BloodMusic v2.0.0 (程序化音频合成)\n")
        f.write(f"制作时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"采样率: {SR} Hz / 16-bit WAV\n")
        f.write("\n" + "=" * 50 + "\n")
        f.write("曲目列表:\n\n")
        for i, (cn, en, style) in enumerate(TRACKLIST, 1):
            f.write(f"  {cn} — {en}\n")
            f.write(f"      风格: {style}\n\n")
        f.write("=" * 50 + "\n")
        f.write("\n本专辑由 BloodMusic 程序化音频合成引擎全自动生成。\n")
        f.write("所有音轨均为纯合成音频，不使用任何外部采样。\n")
        f.write("涵盖风格: 古典/钢琴、新世纪、氛围、爵士、电子、影视史诗、\n")
        f.write("          Lo-Fi、冥想、民谣、史诗终章。\n")

    print(f"\n{'=' * 60}")
    print(f"  专辑制作完成！")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  共 10 首曲目，覆盖 10 种纯音乐风格")
    print(f"  * P1 Motif | P2 Automation | P3 Riser FX | P5 Mix")
    print(f"  专辑信息文件: ALBUM_INFO.txt")
    print(f"{'=' * 60}")


# ═══════════════════════════════════════════════════════════════════
# Pool-based 专辑生成 (v3.0 InstrumentPool 集成)
# ═══════════════════════════════════════════════════════════════════

import logging
from typing import Dict, Tuple, Optional

# ── 常量 ──

POOL_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "album_output_pool")

ALBUM_STYLE_POOLS: Dict[str, Tuple[str, str]] = {
    "01_晨曦序曲":      ("album_dawn_overture.yaml",    "exploration"),
    "02_星海迷途":      ("album_lost_in_cosmos.yaml",   "ambient"),
    "03_深海絮语":      ("album_deep_sea.yaml",         "ambient"),
    "04_午夜爵士":      ("album_midnight_jazz.yaml",    "town"),
    "05_霓虹脉冲":      ("album_neon_pulse.yaml",       "battle"),
    "06_英雄远征":      ("album_heros_journey.yaml",    "battle"),
    "07_旧日时光":      ("album_nostalgia.yaml",        "town"),
    "08_空山鸟语":      ("album_birds_mountains.yaml",  "ambient"),
    "09_田园小调":      ("album_pastoral_tune.yaml",    "exploration"),
    "10_终章·重生":     ("album_finale_rebirth.yaml",    "battle"),
}

FULLPOWER_ALBUM: Dict[str, Tuple[str, str]] = {
    "01_古典歌剧":        ("fullpower_classical_opera.yaml",      "classical"),
    "02_爵士之夜":        ("fullpower_jazz_night.yaml",           "jazz"),
    "03_电子仓库":        ("fullpower_electronic_warehouse.yaml",  "electronic"),
    "04_影视史诗":        ("fullpower_cinematic_odyssey.yaml",    "cinematic"),
    "05_低保真梦境":      ("fullpower_lofi_dreams.yaml",          "lofi"),
    "06_禅意冥想":        ("fullpower_meditation_zen.yaml",       "meditation"),
    "07_民谣之旅":        ("fullpower_folk_voyage.yaml",          "folk"),
    "08_战斗锻造":        ("fullpower_battle_forge.yaml",         "battle"),
    "09_荒野探索":        ("fullpower_exploration_wilds.yaml",    "exploration"),
    "10_城镇市集":        ("fullpower_town_market.yaml",          "town"),
    "11_地城深渊":        ("fullpower_dungeon_depths.yaml",       "dungeon"),
    "12_虚空之境":        ("fullpower_ambient_void.yaml",         "ambient"),
}

FULLPOWER_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "album_output_fullpower")


# ── Pool 模式辅助函数 ──

def save_wav_pool(audio: np.ndarray, filename: str, output_dir: str) -> str:
    """Save WAV to a custom output directory.

    Similar to save_wav() but accepts output_dir parameter.
    Audio is normalized before saving.
    """
    audio = _normalize(audio)
    path = os.path.join(output_dir, filename)
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))
    size_mb = os.path.getsize(path) / 1024 / 1024
    dur = len(audio) / SR
    print(f"  [OK] {filename}  ({dur:.0f}s, {size_mb:.1f}MB)")
    return path


# ── Pool 模式主函数 ──

def generate_album_with_pool(
    pool_dir: str = "",
    output_dir: str = POOL_OUTPUT_DIR,
    duration_sec: float = 120.0,
    seed: Optional[int] = None,
) -> list:
    """Generate a 10-track multi-style album using InstrumentPool + PoolRenderer.

    Iterates over ALBUM_STYLE_POOLS, for each track:
      1. InstrumentPool.from_yaml(pool_dir / yaml_file)
      2. StylePreset.get_style(style_name).apply_to(pool)
      3. PoolRenderer(pool, duration_sec, style_name).render()
      4. _to_mono → _fade_edges → _normalize → save_wav_pool

    Single-track failures are caught, logged, and skipped without crashing.

    Args:
        pool_dir: Directory containing pool YAML configuration files.
        output_dir: Output directory for generated WAV files.
        duration_sec: Target duration per track in seconds.
        seed: Random seed for reproducibility (None = not set).

    Returns:
        List of generated WAV file paths.
    """
    if not pool_dir:
        pool_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music", "pool_presets")

    # Lazy import pool modules — only loaded when --pool is triggered
    from bloodmusic.music.instrument_pool import InstrumentPool
    from bloodmusic.music.pool_renderer import PoolRenderer
    from bloodmusic.music.pool_styles import get_style

    os.makedirs(output_dir, exist_ok=True)
    generated = []

    for track_name, (yaml_file, style_name) in ALBUM_STYLE_POOLS.items():
        yaml_path = os.path.join(pool_dir, yaml_file)
        print(f"\n{'='*50}")
        print(f"  [Pool] {track_name} — style={style_name}")
        print(f"  YAML: {yaml_path}")
        print(f"{'='*50}")

        try:
            # 1. Load pool from YAML
            pool = InstrumentPool.from_yaml(yaml_path)

            # 2. Apply StylePreset overrides
            try:
                style = get_style(style_name)
                pool = style.apply_to(pool)
            except KeyError:
                print(f"  [WARN] Unknown style '{style_name}', using YAML raw config")

            # 3. Set seed if provided
            if seed is not None:
                pool.config.seed = seed

            # 4. Render via PoolRenderer
            renderer = PoolRenderer(pool, duration_sec=duration_sec, style_name=style_name)
            final_audio, stems = renderer.render()

            # 5. Post-processing: mono → fade → normalize
            audio = _to_mono(final_audio.astype(np.float64))
            audio = _fade_edges(audio, 1.0, 3.0)
            audio = _normalize(audio)

            # 6. Save to pool output directory
            filename = f"{track_name}_{style_name}.wav"
            wav_path = save_wav_pool(audio, filename, output_dir)
            generated.append(wav_path)

        except Exception as e:
            print(f"\n  [ERROR] {track_name}: {e}")
            import traceback
            traceback.print_exc()
            print(f"  [INFO] Skipping {track_name}, continuing to next track...")
            continue

    return generated


# ── CLI ──


def _generate_fullpower_album(
    pool_dir: str = "",
    output_dir: str = "",
    duration_sec: float = 120.0,
    seed: Optional[int] = None,
) -> list:
    """Generate a 12-track fullpower album using all 6 real synth engines.

    Iterates over FULLPOWER_ALBUM, for each track:
      1. InstrumentPool.from_yaml(pool_dir / yaml_file)
      2. PoolRenderer(pool, duration_sec, style_name).render()
      3. _to_mono → _fade_edges → _normalize → save_wav_pool

    Single-track failures are caught, logged, and skipped without crashing.

    Args:
        pool_dir: Directory containing pool YAML configuration files.
        output_dir: Output directory for generated WAV files.
        duration_sec: Target duration per track in seconds.
        seed: Random seed for reproducibility.

    Returns:
        List of generated WAV file paths.
    """
    from bloodmusic.music.instrument_pool import InstrumentPool
    from bloodmusic.music.pool_renderer import PoolRenderer

    if not pool_dir:
        pool_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music", "pool_presets")
    if not output_dir:
        output_dir = FULLPOWER_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    generated = []

    for track_name, (yaml_file, style_name) in FULLPOWER_ALBUM.items():
        yaml_path = os.path.join(pool_dir, yaml_file)
        print(f"\n{'='*50}")
        print(f"  [Fullpower] {track_name} — style={style_name}")
        print(f"  YAML: {yaml_path}")
        print(f"{'='*50}")

        try:
            # 1. Load pool from YAML
            pool = InstrumentPool.from_yaml(yaml_path)

            # 2. Set seed if provided
            if seed is not None:
                pool.config.seed = seed

            # 3. Render via PoolRenderer
            renderer = PoolRenderer(
                pool, duration_sec=duration_sec, style_name=style_name,
            )
            final_audio, stems = renderer.render()

            # 4. Post-processing
            audio = _to_mono(final_audio.astype(np.float64))
            audio = _fade_edges(audio, 1.0, 3.0)
            audio = _normalize(audio)

            # 5. Save
            filename = f"{track_name}_{style_name}.wav"
            wav_path = save_wav_pool(audio, filename, output_dir)
            generated.append(wav_path)

        except Exception as e:
            print(f"\n  [ERROR] {track_name}: {e}")
            import traceback
            traceback.print_exc()
            print(f"  [INFO] Skipping {track_name}, continuing to next track...")
            continue

    return generated


# ── CLI ──

def cli_main() -> None:
    """argparse CLI entry point.

    Usage:
        python album_generator.py                  # legacy mode (10 hand-crafted tracks)
        python album_generator.py --pool           # pool mode (10 auto-generated tracks)
        python album_generator.py --fullpower      # fullpower mode (12 all-engine tracks)
        python album_generator.py --pool --duration 180 --seed 42
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="BloodMusic 纯音乐专辑生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python album_generator.py                  # Legacy mode (10 hand-crafted tracks)
  python album_generator.py --pool           # Pool mode (10 auto-generated tracks)
  python album_generator.py --fullpower      # Fullpower mode (12 all-engine tracks)
  python album_generator.py --pool --duration 180 --seed 42
        """,
    )
    parser.add_argument("--pool", action="store_true",
                        help="Use InstrumentPool mode (default: legacy mode)")
    parser.add_argument("--fullpower", action="store_true",
                        help="Use Fullpower 12-track all-engine album mode")
    parser.add_argument("--duration", type=float, default=120.0,
                        help="Duration per track in seconds (default: 120)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory (pool mode default: album_output_pool)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility")
    parser.add_argument("--pool-dir", type=str, default="",
                        help="Pool YAML directory (default: music/pool_presets under script dir)")

    args = parser.parse_args()

    if args.fullpower:
        # ── Fullpower mode ──
        output_dir = args.output or FULLPOWER_OUTPUT_DIR
        print("=" * 60)
        print(f"  BloodMusic 全性能压榨专辑生成器 (Fullpower Mode)")
        print(f"  引擎: 6种真实合成引擎 (FM, FM_ADVANCED, WAVETABLE,")
        print(f"        KARPLUS_STRONG, WAVEGUIDE, GRANULAR)")
        print(f"  输出目录: {output_dir}")
        print(f"  时长: {args.duration}s/track × 12 首")
        print("=" * 60)

        paths = _generate_fullpower_album(
            pool_dir=args.pool_dir,
            output_dir=output_dir,
            duration_sec=args.duration,
            seed=args.seed,
        )

        print(f"\n{'='*60}")
        print(f"  全性能压榨专辑制作完成！")
        print(f"  输出目录: {output_dir}")
        print(f"  成功: {len(paths)}/12 首")
        print(f"{'='*60}")
    elif args.pool:
        # ── Pool mode ──
        output_dir = args.output or POOL_OUTPUT_DIR
        print("=" * 60)
        print(f"  BloodMusic 纯音乐专辑生成器 (Pool Mode)")
        print(f"  引擎: InstrumentPool + PoolRenderer")
        print(f"  输出目录: {output_dir}")
        print(f"  时长: {args.duration}s/track")
        print("=" * 60)

        paths = generate_album_with_pool(
            pool_dir=args.pool_dir,
            output_dir=output_dir,
            duration_sec=args.duration,
            seed=args.seed,
        )

        print(f"\n{'='*60}")
        print(f"  Pool 模式专辑制作完成！")
        print(f"  输出目录: {output_dir}")
        print(f"  成功: {len(paths)}/10 首")
        print(f"{'='*60}")
    else:
        # ── Legacy mode (original behavior, zero change) ──
        main()


if __name__ == "__main__":
    cli_main()
