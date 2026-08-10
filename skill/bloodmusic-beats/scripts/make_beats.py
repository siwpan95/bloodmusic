"""
BloodMusic Beat 制作器 v2 — 全引擎驱动
=========================================
使用: SongArrangement + EffectChain + Automation + BassSynth + Harmony

用法: python make_beats.py
输出: ./output_beats/ 目录下 7 种风格 WAV 文件
"""

import os, numpy as np
from datetime import datetime
from scipy.io import wavfile

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape
from bloodmusic.music import (
    MusicPattern, DrumPattern, MultiTrackPattern, render_multi_track,
    SongArrangement, Section, Transition, render_song,
    AutomationLane, apply_filter_sweep, apply_volume_automation,
    build_up_lowpass, fade_in_out, drop_filter_resonance,
    BassSynth, render_bass_pattern,
    generate_parallel_harmony, render_harmony_tracks,
)
from bloodmusic.music.presets import STYLE_KITS
from bloodmusic.effects.chain import EffectChain, process_effects
from bloodmusic.effects.filters import apply_resonant_lpf

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output_beats")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ═══════════════════════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════════════════════

def save_wav(audio: np.ndarray, filename: str):
    audio = audio.astype(np.float64)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95
    base, ext = os.path.splitext(filename)
    path = os.path.join(OUTPUT_DIR, f"{base}_{TIMESTAMP}{ext}")
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))
    print(f"  [OK] {os.path.basename(path)}")


def _is_stereo(audio: np.ndarray) -> bool:
    return audio.ndim == 2 and audio.shape[1] == 2


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """立体声 → 单声道（用于需要 mono 的处理）"""
    if _is_stereo(audio):
        return audio.mean(axis=1)
    return audio


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    """单声道 → 立体声"""
    if not _is_stereo(audio):
        return np.column_stack([audio, audio])
    return audio


def _mix_bass(main_audio: np.ndarray, bass_audio: np.ndarray, vol: float = 0.85) -> np.ndarray:
    """将预渲染的 Bass 音频混入主音频（兼容单声道/立体声）"""
    m = min(len(main_audio), len(bass_audio))
    if _is_stereo(main_audio):
        bass_stereo = np.column_stack([bass_audio[:m], bass_audio[:m]]) * vol
        main_audio[:m] += bass_stereo
    else:
        main_audio[:m] += bass_audio[:m] * vol
    return main_audio


def _fade_edges(audio: np.ndarray, fade_in: float = 1.0, fade_out: float = 2.0) -> np.ndarray:
    """对音频首尾做简单的淡入淡出（兼容单声道/立体声）"""
    n = audio.shape[0]
    fi = min(int(fade_in * SR), n // 2)
    fo = min(int(fade_out * SR), n // 2)
    if _is_stereo(audio):
        fade = np.ones(n)
        if fi > 0: fade[:fi] = np.linspace(0, 1, fi)
        if fo > 0: fade[-fo:] = np.linspace(1, 0, fo)
        audio[:, 0] *= fade; audio[:, 1] *= fade
    else:
        if fi > 0: audio[:fi] *= np.linspace(0, 1, fi)
        if fo > 0: audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 1: Trap Beat — SongArrangement + EffectChain + Sub Bass
# ═══════════════════════════════════════════════════════════════════════

def make_trap_beat():
    print("\n[STYLE 1] Trap Beat (编曲+效果链+Sub Bass)")
    kit = STYLE_KITS["trap"]
    bpm = kit["bpm"]

    song = SongArrangement(name="trap_beat", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    lead = kit["melody"][0](bpm)
    pad = kit["pad"](bpm)

    # 编曲结构: intro → verse → hook → verse → hook → bridge → hook → outro
    song.add_section("intro",  4, [pad], None)
    song.add_section("verse",  8, [pad], drum)
    song.add_section("hook",   8, [lead, pad], drum)
    song.add_section("verse",  8, [pad], drum)
    song.add_section("hook",   8, [lead, pad], drum)
    song.add_section("bridge", 4, [pad], drum)
    song.add_section("hook",   8, [lead, pad], drum)
    song.add_section("outro",  4, [lead])

    audio = render_song(song)
    audio = _to_mono(audio)  # 后续处理在 mono 域
    total_dur = len(audio) / SR

    # Sub Bass
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.9)

    # 淡入淡出
    audio = _fade_edges(audio, 1.0, 3.0)

    save_wav(audio, "trap_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 2: Boom Bap — SongArrangement + Sub Bass + Subtle Master
# ═══════════════════════════════════════════════════════════════════════

def make_boom_bap_beat():
    print("\n[STYLE 2] Boom Bap (编曲+效果链+Sub Bass)")
    kit = STYLE_KITS["boom_bap"]
    bpm = kit["bpm"]

    song = SongArrangement(name="boom_bap", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    melody = kit["melody"][0](bpm)

    song.add_section("intro",  4, [], drum)
    song.add_section("verse",  8, [melody], drum)
    song.add_section("hook",   8, [melody], drum)
    song.add_section("verse",  8, [melody], drum)
    song.add_section("hook",   8, [melody], drum)
    song.add_section("outro",  4, [melody])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur = len(audio) / SR

    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.88)

    audio = _fade_edges(audio, 0.8, 2.5)

    save_wav(audio, "boom_bap_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 3: Lo-Fi Beat — SongArrangement + Harmony + EffectChain
# ═══════════════════════════════════════════════════════════════════════

def make_lofi_beat():
    print("\n[STYLE 3] Lo-Fi Beat (编曲+和声+效果链)")
    kit = STYLE_KITS["lofi"]
    bpm = kit["bpm"]

    song = SongArrangement(name="lofi_beat", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    melody = kit["melody"][0](bpm)

    # 和声: 三度平行和声增加 Lo-Fi 温暖层次感
    chord_notes = []
    if melody.chords:
        for ch in melody.chords:
            chord_notes.extend(ch)
    else:
        chord_notes = [n for n in melody.notes if n]
    harmony_voices = generate_parallel_harmony(chord_notes[:16], intervals=[3, 5])
    # 从 HarmonyVoice 提取音符
    harmony_notes_all = []
    if harmony_voices:
        for v in harmony_voices:
            harmony_notes_all.extend(v.notes if v.notes else [])

    harmony = MusicPattern(
        name="lofi_harmony", bpm=bpm, loop=True,
        notes=[n for n in harmony_notes_all[:16]] + [None] * max(0, 16 - len(harmony_notes_all)),
        durations=[1.0] * 16,
        osc_type=OscType.SINE, volume=0.08, env_shape=EnvShape.PAD,
        harmonics=[(2.0, 0.15)], vibrato_rate=3.0, vibrato_depth=0.1,
        reverb_mix=0.5, reverb_decay=2.0, stereo_width=0.9, lp_filter_hz=2500,
    )

    song.add_section("intro",  4, [melody], None)
    song.add_section("verse",  8, [melody, harmony], drum)
    song.add_section("chorus", 8, [melody, harmony], drum)
    song.add_section("verse",  8, [melody, harmony], drum)
    song.add_section("outro",  4, [melody])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur = len(audio) / SR

    # Bass
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.7)

    # Lo-Fi 特色: 温和低通滤波模拟磁带质感
    audio = apply_resonant_lpf(audio, 4000, q=0.5)
    audio = _fade_edges(audio, 1.5, 4.0)

    save_wav(audio, "lofi_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 4: Battle Beat — SongArrangement + FM Bass + Filter Sweep
# ═══════════════════════════════════════════════════════════════════════

def make_battle_beat():
    print("\n[STYLE 4] Battle Beat (编曲+FM Bass+滤波器扫频)")
    kit = STYLE_KITS["battle"]
    bpm = kit["bpm"]

    song = SongArrangement(name="battle_beat", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    melody = kit["melody"][0](bpm)

    song.add_section("intro",  4, [], drum)
    song.add_section("verse",  8, [melody], drum)
    song.add_section("climax", 8, [melody], drum)
    song.add_section("verse",  8, [melody], drum)
    song.add_section("climax", 8, [melody], drum)
    song.add_section("outro",  4, [melody])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur = len(audio) / SR

    # FM Bass — 金属质感战斗低音
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.85)

    # 战斗专属: 滤波器扫频（intro 段落渐开）
    sweep_lane = AutomationLane("cutoff", [
        (0.0, 300), (4.0, 20000), (total_dur, 20000),
    ], interpolate="smooth")
    audio = apply_filter_sweep(audio, sweep_lane, filter_type="lowpass", q=1.5)

    audio = _fade_edges(audio, 0.5, 1.5)

    save_wav(audio, "battle_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 5: Drum Only — SongArrangement + Clean Master (纯鼓)
# ═══════════════════════════════════════════════════════════════════════

def make_drum_only_beat():
    print("\n[STYLE 5] 纯鼓 Beat (编曲+母带压缩)")
    kit = STYLE_KITS["drum_only"]
    bpm = kit["bpm"]

    song = SongArrangement(name="drum_only", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)

    # A/B 段交替
    song.add_section("a_section", 8, [], drum)
    song.add_section("b_section", 8, [], drum)
    song.add_section("a_section", 8, [], drum)
    song.add_section("b_section", 8, [], drum)
    song.add_section("a_section", 8, [], drum)
    song.add_section("outro",     4, [], drum)

    audio = render_song(song)
    audio = _to_mono(audio)
    audio = _fade_edges(audio, 0.5, 3.0)

    save_wav(audio, "drum_only_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 6: EDM Beat — SongArrangement + Acid Bass + Filter Drop
# ═══════════════════════════════════════════════════════════════════════

def make_edm_beat():
    print("\n[STYLE 6] EDM Beat (编曲+Acid Bass+Drop)")
    kit = STYLE_KITS["edm"]
    bpm = kit["bpm"]

    song = SongArrangement(name="edm_beat", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    lead = kit["melody"][0](bpm)
    chords = kit["melody"][1](bpm)

    # EDM 结构: intro → build → drop → break → build → drop → outro
    song.add_section("intro",     8, [chords], None)
    song.add_section("build_up",  4, [chords], drum)
    song.add_section("drop",     16, [lead, chords], drum)
    song.add_section("break",     8, [chords], None)
    song.add_section("build_up",  4, [chords], drum)
    song.add_section("drop",     16, [lead, chords], drum)
    song.add_section("outro",     8, [lead])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur = len(audio) / SR

    # Acid Bass
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.8)

    # EDM 专属: Drop 时滤波器全开效果
    drop_lane = drop_filter_resonance(total_dur)
    audio = apply_filter_sweep(audio, drop_lane, filter_type="lowpass", q=3.0)

    audio = _fade_edges(audio, 1.0, 4.0)

    save_wav(audio, "edm_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 7: Ambient Beat — SongArrangement + Pluck Bass + 氛围效果链
# ═══════════════════════════════════════════════════════════════════════

def make_ambient_beat():
    print("\n[STYLE 7] 氛围 Beat (编曲+Pluck Bass+混响链)")
    kit = STYLE_KITS["ambient"]
    bpm = kit["bpm"]

    song = SongArrangement(name="ambient_beat", bpm=bpm, master_chain=kit["master"])
    drum = kit["drum"](bpm)
    melody = kit["melody"][0](bpm)

    # 氛围结构: intro → body → climax → resolution → outro
    song.add_section("intro",      8, [melody], None)
    song.add_section("body",      16, [melody], drum)
    song.add_section("climax",     8, [melody], drum)
    song.add_section("resolution", 8, [melody])
    song.add_section("outro",      8, [melody])

    audio = render_song(song)
    audio = _to_mono(audio)
    total_dur = len(audio) / SR

    # Pluck Bass — 柔和低频点缀
    bass_pat = kit["bass"](bpm)
    bass_synth = BassSynth.preset(kit["bass_type"])
    b_audio = render_bass_pattern(bass_pat, bass_synth, total_dur)
    audio = _mix_bass(audio, b_audio, 0.6)

    # 氛围专属: 慢速低通扫频 + 长淡入淡出
    sweep_lane = AutomationLane("cutoff", [
        (0.0, 2000), (total_dur * 0.3, 8000),
        (total_dur * 0.7, 8000), (total_dur, 2000),
    ], interpolate="smooth")
    audio = apply_filter_sweep(audio, sweep_lane, filter_type="lowpass", q=0.707)

    audio = _fade_edges(audio, 3.0, 5.0)

    save_wav(audio, "ambient_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  BloodMusic Beat 制作器 v2 — 全引擎驱动")
    print("  SongArrangement + EffectChain + Automation + BassSynth + Harmony")
    print("=" * 60)

    try:
        make_trap_beat()
        make_boom_bap_beat()
        make_lofi_beat()
        make_battle_beat()
        make_drum_only_beat()
        make_edm_beat()
        make_ambient_beat()

        print(f"\n{'=' * 60}")
        print(f"  全部完成！输出目录: {OUTPUT_DIR}")
        print(f"{'=' * 60}")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
