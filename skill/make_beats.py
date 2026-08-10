"""
BloodMusic Beat 制作脚本 — 生成多种风格的节拍和音乐

用法: python make_beats.py
输出: ./output_beats/ 目录下包含多种风格的 WAV 文件
"""

import os
from datetime import datetime
import numpy as np
from scipy.io import wavfile

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape
from bloodmusic.music import (
    MusicPattern, DrumSoundParams, DrumPattern,
    MultiTrackPattern, render_multi_track,
)
from bloodmusic.music.presets import (
    BOSS_FIGHT_MUSIC, DUNGEON_MUSIC, PLATFORMER_MUSIC,
)
from bloodmusic.sfx.drum_synth import (
    synthesize_808_kick, synthesize_808_snare, synthesize_808_hihat,
    Kick808Params, Snare808Params, Hihat808Params,
)
from bloodmusic.music.euclidean import get_euclidean_tracks

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output_beats")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════

def save_wav(audio: np.ndarray, filename: str):
    """归一化并保存 WAV 文件（自动附加时间戳避免覆盖旧文件）"""
    audio = audio.astype(np.float64)
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.95
    base, ext = os.path.splitext(filename)
    stamped = f"{base}_{TIMESTAMP}{ext}"
    path = os.path.join(OUTPUT_DIR, stamped)
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))
    print(f"  [OK] 已生成: {stamped}")


def manual_808_beat(bpm: int, bars: int, kick_hits: list, snare_hits: list,
                    hihat_subdiv: int = 2) -> np.ndarray:
    """手动编排 808 鼓组的节拍循环

    Args:
        bpm: 速度
        bars: 小节数
        kick_hits: 底鼓位置（以节拍为单位, 0-based, 每拍 1.0）
        snare_hits: 军鼓位置
        hihat_subdiv: 踩镲细分（2=八分音符, 4=十六分音符）
    """
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur  # 4/4 拍
    result = np.zeros(int(total_dur * SR))

    # 合成 808 鼓声
    kick = synthesize_808_kick(Kick808Params(
        freq_start=150, freq_end=45, duration=0.35,
        freq_decay=0.06, amp_decay=0.25, click_level=0.3,
        distortion=0.15, volume=0.85,
    ))
    snare = synthesize_808_snare(Snare808Params(
        tone_freq=180, tone_decay=0.1, noise_decay=0.15,
        duration=0.25, volume=0.75,
    ))
    hihat = synthesize_808_hihat(Hihat808Params(
        osc_freq=8000, decay=0.06, duration=0.1, volume=0.45,
    ))

    def place_hit(audio_hit, position_beats):
        pos = int(position_beats * beat_dur * SR)
        end = min(pos + len(audio_hit), len(result))
        result[pos:end] += audio_hit[:end - pos]

    # 放置底鼓
    for pos in kick_hits:
        place_hit(kick, pos)

    # 放置军鼓
    for pos in snare_hits:
        place_hit(snare, pos)

    # 放置踩镲
    for i in range(int(total_dur / (beat_dur / hihat_subdiv))):
        place_hit(hihat, i / hihat_subdiv)

    return np.clip(result / max(np.max(np.abs(result)), 1e-8), -1, 1)


# ═══════════════════════════════════════════════════════════════════════
# 风格 1: Trap Beat — 暗黑 808 + 滚奏踩镲
# ═══════════════════════════════════════════════════════════════════════

def make_trap_beat():
    print("\n[STYLE 1] Trap Beat (暗黑 808)")

    bpm = 140
    bars = 120  # ~3.4 分钟

    # 底鼓: 每拍一下 + 后半拍加花
    kick = []
    for bar in range(bars):
        base = bar * 4.0
        kick.extend([base, base + 1, base + 2, base + 3])
        # 每四个小节加花
        if bar % 4 == 3:
            kick.extend([base + 2.5, base + 3.5])

    # 军鼓: 第 3 拍 + 滚奏
    snare = []
    for bar in range(bars):
        base = bar * 4.0
        snare.append(base + 2)
        if bar % 2 == 0:
            snare.extend([base + 1.5, base + 2.5])
        # 每四个小节军鼓滚奏
        if bar % 4 == 3:
            for s in [base + 0.25, base + 0.5, base + 0.75,
                      base + 2.25, base + 2.5, base + 2.75]:
                snare.append(s)

    # 踩镲: 三连音滚奏 (hihat_subdiv=3 模拟三连音感)
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur
    result = np.zeros(int(total_dur * SR))

    kick_audio = synthesize_808_kick(Kick808Params(
        freq_start=150, freq_end=40, duration=0.4,
        freq_decay=0.05, amp_decay=0.2, click_level=0.35,
        distortion=0.2, volume=0.88,
    ))
    snare_audio = synthesize_808_snare(Snare808Params(
        tone_freq=200, tone_decay=0.08, noise_decay=0.12,
        duration=0.22, volume=0.78,
    ))
    hihat_audio = synthesize_808_hihat(Hihat808Params(
        osc_freq=9000, decay=0.04, duration=0.08, volume=0.42,
    ))

    def add_hit(src, beat_pos, vol=1.0):
        pos = int(beat_pos * beat_dur * SR)
        end = min(pos + len(src), len(result))
        result[pos:end] += src[:end - pos] * vol

    for pos in kick:
        add_hit(kick_audio, pos)
    for pos in snare:
        add_hit(snare_audio, pos)

    # 十六分音符踩镲 + 偶尔静音增强 groove
    hihat_mute_pattern = [0, 3, 8, 11, 14]  # 静音位
    for i in range(int(total_dur / (beat_dur / 4))):
        if i % 16 not in hihat_mute_pattern:
            add_hit(hihat_audio, i / 4)

    save_wav(result, "trap_beat.wav")
    return result


# ═══════════════════════════════════════════════════════════════════════
# 风格 2: Boom Bap — 经典 90 年代嘻哈
# ═══════════════════════════════════════════════════════════════════════

def make_boom_bap_beat():
    print("\n[STYLE 2] Boom Bap (经典嘻哈)")

    bpm = 92
    bars = 80  # ~3.5 分钟
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur
    result = np.zeros(int(total_dur * SR))

    # 更温润的 Kick（正弦波 + 更慢衰减）

    def make_kick_bap(dur=0.3, freq_start=80, freq_end=35):
        """自制 Boom Bap 底鼓: 频率快速扫降"""
        n = int(dur * SR)
        t = np.linspace(0, dur, n, endpoint=False)
        freq = freq_start * np.exp(-t / 0.06) + freq_end
        freq = np.clip(freq, freq_end, freq_start)
        phase = np.cumsum(freq) / SR
        env = np.exp(-t / 0.15)
        env = np.clip(env, 0, 1)
        return np.sin(2 * np.pi * phase) * env * 0.9

    def make_snare_bap(dur=0.2):
        """自制 Boom Bap 军鼓: 噪声 + 短 tone"""
        n = int(dur * SR)
        t = np.linspace(0, dur, n, endpoint=False)
        noise = np.random.randn(n) * np.exp(-t / 0.08)
        noise = noise / (np.max(np.abs(noise)) + 1e-8)
        tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.04) * 0.3
        env = np.exp(-t / 0.12)
        return (noise * 0.7 + tone) * env * 0.8

    def make_hihat_bap(dur=0.06):
        """自制 Boom Bap 踩镲"""
        n = int(dur * SR)
        t = np.linspace(0, dur, n, endpoint=False)
        noise = np.random.randn(n) * np.exp(-t / 0.02)
        return noise / (np.max(np.abs(noise)) + 1e-8) * 0.5

    kick_audio = make_kick_bap()
    snare_audio = make_snare_bap()
    hihat_audio = make_hihat_bap()

    def add_hit(src, beat_pos, vol=1.0):
        pos = int(beat_pos * beat_dur * SR)
        end = min(pos + len(src), len(result))
        result[pos:end] += src[:end - pos] * vol

    # Boom Bap 经典 pattern: Kick=1,2.5(Swing!) Snare=3
    for bar in range(bars):
        base = bar * 4.0
        add_hit(kick_audio, base)
        add_hit(kick_audio, base + 1)
        add_hit(kick_audio, base + 2.5 * 1.02)  # Swing!
        add_hit(snare_audio, base + 2)
        add_hit(snare_audio, base + 3)

        # 加花
        if bar % 4 == 3:
            add_hit(kick_audio, base + 3.5)
            add_hit(snare_audio, base + 2.5 * 1.02)
            add_hit(snare_audio, base + 3.5)

    # 八分音符 Shuffle Hihat
    for i in range(int(total_dur / (beat_dur / 2))):
        beat_pos = i / 2
        vol = 1.0
        # 弱拍音量降低（模拟 shuffle）
        if i % 2 == 1:
            vol = 0.5
        add_hit(hihat_audio, beat_pos, vol)

    save_wav(result, "boom_bap_beat.wav")
    return result


# ═══════════════════════════════════════════════════════════════════════
# 风格 3: Lo-Fi Beat — 放松律动 + 音乐旋律
# ═══════════════════════════════════════════════════════════════════════

def make_lofi_beat():
    print("\n[STYLE 3] Lo-Fi Beat (放松律动)")

    bpm = 78
    bars = 72  # ~3.7 分钟
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur

    # ── 鼓点: 稀疏慵懒 ──
    drum = DrumPattern(
        name="lofi_drums",
        steps=16,
        bpm=bpm,
        tracks={
            "kick":  [True,  False, False, False, False, False, True,  False,
                      False, False, False, False, True,  False, False, False],
            "snare": [False, False, False, False, True,  False, False, False,
                      False, False, False, False, True,  False, False, False],
            "hihat": [True,  False, True,  False, True,  False, False, True,
                      True,  False, True,  False, False, True,  True,  False],
        },
        sounds={
            "kick":  DrumSoundParams(osc_type=OscType.SINE,  pitch_hz=55,
                                     decay=0.22, volume=0.7),
            "snare": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=180,
                                     decay=0.15, hp_hz=250, volume=0.4),
            "hihat": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=6000,
                                     decay=0.06, hp_hz=1500, volume=0.25),
        },
    )

    # ── 旋律: 柔和 SINE 波 → 自定义 Lo-Fi 和弦进行 ──
    # Am7 → Dm7 → G7 → Cmaj7  (经典的 ii-V-I 爵士进行)
    melody = MusicPattern(
        name="lofi_melody",
        chords=[
            ["A4", "C5", "E5", "G5"],      # Am7
            ["D4", "F5", "A5", "C6"],      # Dm7
            ["G4", "B5", "D6", "F6"],      # G7
            ["C4", "E5", "G5", "B5"],      # Cmaj7
        ],
        notes=[None] * 8,              # 无单音旋律, 只用和弦
        durations=[2.0] * 8,           # 每个和弦 2 拍
        bpm=bpm,
        loop=True,
        osc_type=OscType.SINE,
        volume=0.15,
        env_shape=EnvShape.PAD,
        harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1)],
        vibrato_rate=3.5,
        vibrato_depth=0.15,
        reverb_mix=0.4,
        reverb_decay=2.0,
        stereo_width=0.7,
        lp_filter_hz=3500,
    )

    multi = MultiTrackPattern(
        name="lofi_beat",
        bpm=bpm,
        loop=True,
        music_tracks=[melody],
        drum_track=drum,
    )

    audio = render_multi_track(multi, total_dur)
    save_wav(audio, "lofi_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 4: 战斗音乐 + 重鼓 (使用预设 + 欧几里得节奏)
# ═══════════════════════════════════════════════════════════════════════

def make_battle_beat():
    print("\n[STYLE 4] 战斗 Beat (游戏战斗音乐 + 鼓点)")

    # ── 使用欧几里得预设: Boss 战鼓点 ──
    tracks = get_euclidean_tracks("combat_intense")
    drum = DrumPattern(
        name="battle_drums",
        steps=16,
        bpm=145,
        tracks=tracks,
        sounds={
            "kick":  DrumSoundParams(osc_type=OscType.SINE,  pitch_hz=50,
                                     decay=0.2,  volume=0.85),
            "snare": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=200,
                                     decay=0.12, hp_hz=300, volume=0.7),
            "hihat": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=8000,
                                     decay=0.05, hp_hz=2000, volume=0.5),
        },
    )

    # ── 使用 BOSS_FIGHT_MUSIC 预设 ──
    multi = MultiTrackPattern(
        name="battle_beat",
        bpm=145,
        loop=True,
        music_tracks=[BOSS_FIGHT_MUSIC],
        drum_track=drum,
    )

    audio = render_multi_track(multi, 210.0)  # ~3.5 分钟
    save_wav(audio, "battle_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 5: 纯鼓 Beat — 仅鼓点, 适合说唱/采样
# ═══════════════════════════════════════════════════════════════════════

def make_drum_only_beat():
    print("\n[STYLE 5] 纯鼓 Beat (仅鼓点, 适合采样)")

    bpm = 95
    bars = 84  # ~3.5 分钟
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur

    # 预合成 808 鼓声
    kick = synthesize_808_kick(Kick808Params(
        freq_start=140, freq_end=42, duration=0.35,
        freq_decay=0.06, amp_decay=0.22, click_level=0.35,
        distortion=0.08, volume=0.85,
    ))
    snare = synthesize_808_snare(Snare808Params(
        tone_freq=190, tone_decay=0.1, noise_decay=0.15,
        duration=0.25, volume=0.78,
    ))
    hihat = synthesize_808_hihat(Hihat808Params(
        osc_freq=8000, decay=0.06, duration=0.1, volume=0.4,
    ))
    open_hat = synthesize_808_hihat(Hihat808Params(
        osc_freq=8000, decay=0.25, duration=0.3, volume=0.35,
    ))

    result = np.zeros(int(total_dur * SR))

    def add(src, beat_pos, vol=1.0):
        pos = int(beat_pos * beat_dur * SR)
        end = min(pos + len(src), len(result))
        result[pos:end] += src[:end - pos] * vol

    # A 段 (前 8 小节) + B 段 (后 8 小节) 格式
    for bar in range(bars):
        b = bar * 4.0

        if bar < 8:  # A 段
            add(kick, b)
            add(kick, b + 1, 0.8)
            add(kick, b + 2)
            add(kick, b + 2.5, 0.7)
            add(snare, b + 1.5, 0.6)
            add(snare, b + 3)
        else:  # B 段 — 更密集
            add(kick, b)
            add(kick, b + 0.5, 0.7)
            add(kick, b + 1)
            add(kick, b + 2)
            add(kick, b + 2.5, 0.7)
            add(kick, b + 3, 0.9)
            add(snare, b + 1)
            add(snare, b + 2, 0.6)
            add(snare, b + 3)

        # Hihat 八分音符
        for i in range(8):
            add(hihat, b + i / 2)
        # 开镲在偶数小节第 4 拍后
        if bar % 2 == 0:
            add(open_hat, b + 3.5, 0.7)

    save_wav(result, "drum_only_beat.wav")
    return result


# ═══════════════════════════════════════════════════════════════════════
# 风格 6: 电子舞曲 (EDM) — 四拍底鼓 + 合成器旋律
# ═══════════════════════════════════════════════════════════════════════

def make_edm_beat():
    print("\n[STYLE 6] EDM Beat (电子舞曲)")

    bpm = 128
    bars = 112  # ~3.5 分钟
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur

    # Four-on-the-floor 鼓点
    drum = DrumPattern(
        name="edm_drums",
        steps=16,
        bpm=bpm,
        tracks={
            "kick":  [True,  False, False, False, True,  False, False, False,
                      True,  False, False, False, True,  False, False, False],
            "snare": [False, False, False, False, True,  False, False, False,
                      False, False, False, False, True,  False, False, False],
            "hihat": [True,  False, True,  False, True,  False, True,  False,
                      True,  False, True,  False, True,  False, True,  False],
        },
        sounds={
            "kick":  DrumSoundParams(osc_type=OscType.SINE,  pitch_hz=55,
                                     decay=0.2, volume=0.85),
            "snare": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=200,
                                     decay=0.15, hp_hz=250, volume=0.65),
            "hihat": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=8000,
                                     decay=0.04, hp_hz=2000, volume=0.4),
        },
    )

    # EDM 风格旋律: 平台跳跃风格 + 明亮音色
    melody = PLATFORMER_MUSIC

    multi = MultiTrackPattern(
        name="edm_beat",
        bpm=bpm,
        loop=True,
        music_tracks=[melody],
        drum_track=drum,
    )

    audio = render_multi_track(multi, total_dur)
    save_wav(audio, "edm_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 风格 7: 氛围 Beat — 地下城氛围 + 稀疏鼓点
# ═══════════════════════════════════════════════════════════════════════

def make_ambient_beat():
    print("\n[STYLE 7] 氛围 Beat (地下城风格)")

    bpm = 70
    bars = 64  # ~3.7 分钟
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur

    # 稀疏鼓点 — 仅在大节拍使用
    drum = DrumPattern(
        name="ambient_drums",
        steps=16,
        bpm=bpm,
        tracks={
            "kick":  [True,  False, False, False, False, False, False, False,
                      True,  False, False, False, False, False, False, False],
            "snare": [False, False, False, False, False, False, False, False,
                      False, False, False, False, True,  False, False, False],
        },
        sounds={
            "kick":  DrumSoundParams(osc_type=OscType.SINE,  pitch_hz=45,
                                     decay=0.35, volume=0.75),
            "snare": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=150,
                                     decay=0.2, hp_hz=200, volume=0.4),
        },
    )

    # 地下城氛围音乐
    multi = MultiTrackPattern(
        name="ambient_beat",
        bpm=bpm,
        loop=True,
        music_tracks=[DUNGEON_MUSIC],
        drum_track=drum,
    )

    audio = render_multi_track(multi, total_dur)
    save_wav(audio, "ambient_beat.wav")
    return audio


# ═══════════════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  BloodMusic Beat 制作器")
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
