# -*- coding: utf-8 -*-
"""
pools.py —— 13 个机生成声池（镜像 musickit 的 13 采样池，同名）

musickit：磁盘采样文件 + manifest；bloodmusic：合成引擎实时渲染，license_tier 恒 selfgen。

每个池注册若干「生成乐器」（engine+preset）。渲染走 render_source()：
    spec(池/乐器/角色/kind/bars) → np.float64 单声道 @44100

kind 语义镜像采样侧：
    loop      —— 生成 1 小节循环素材（渲染时按曲式平铺）
    one_shot  —— 单次触发（点缀层）
    stem      —— 全长生成（骨架层保底可用）

所有 melodic 源在 22050Hz 内部渲染再升采样（纯 Python 振荡器，减半算力），
鼓/riser 等向量化合成直接 44100Hz。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

# bloodmusic 合成引擎
from bloodmusic.core.constants import SR as _SR
from bloodmusic.sfx.drum_synth import (
    synthesize_808_kick, synthesize_808_snare, synthesize_808_hihat,
    synthesize_808_open_hihat, synthesize_808_clap,
    synthesize_tom, synthesize_crash, synthesize_shaker,
    KICK_808_PRESETS, SNARE_808_PRESETS,
)
from bloodmusic.sfx.riser import render_riser

# autowav 零依赖合成核心（已并入本仓）
from bloodmusic.autowav.synthesis import render_note
from bloodmusic.autowav.effects import apply_reverb, apply_chorus, low_pass_filter
from bloodmusic.autowav.vocal_formant import sing
from bloodmusic.autowav.theory import NOTE_NAMES, SCALES, build_scale_notes

_LOW_SR = 22050  # melodic 源内部渲染采样率（升采样到 44100）


# ═══════════════════════════════════════════════════════════════
# 13 池注册表：pool -> [生成乐器]
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PoolInstrument:
    name: str           # 乐器名（镜像采样文件名语义）
    subcategory: str    # 子类（镜像采样子目录）
    engine: str         # 合成引擎（见 render_source 分派）
    preset: str         # 预设/音色
    kind: str = "loop"  # stem | loop | one_shot
    role: str = "melody"


POOL_INSTRUMENTS: dict[str, list[PoolInstrument]] = {
    "bass": [
        PoolInstrument("808_bass", "808", "autowav", "贝斯", "loop", "bass"),
        PoolInstrument("sub_bass", "sub", "autowav", "锯齿波", "loop", "bass"),
        PoolInstrument("bass_pluck", "guitar", "autowav", "贝斯", "loop", "bass"),
    ],
    "drum": [
        PoolInstrument("kick", "kick", "drum808", "kick", "loop", "drum"),
        PoolInstrument("snare", "snare", "drum808", "snare", "loop", "drum"),
        PoolInstrument("hihat", "hihat", "drum808", "hihat", "loop", "drum"),
        PoolInstrument("percussion", "percussion", "drumac", "percussion", "loop", "drum"),
    ],
    "guita": [
        PoolInstrument("electric_guitar", "electric", "autowav", "吉他", "loop", "guita"),
        PoolInstrument("acoustic_guitar", "acoustic", "autowav", "竖琴", "loop", "guita"),
    ],
    "cowbell": [
        PoolInstrument("cowbell", "cowbell", "noise_ring", "cowbell", "one_shot", "fx"),
    ],
    "synth": [
        PoolInstrument("synth_lead", "lead", "autowav", "方波", "loop", "melody"),
        PoolInstrument("synth_pad", "pad", "autowav", "管风琴", "loop", "pad"),
        PoolInstrument("synth_pluck", "pluck", "autowav", "电钢琴", "loop", "melody"),
    ],
    "acapella": [
        PoolInstrument("vocal_vowels", "vowels", "formant", "vowels", "loop", "vocal"),
    ],
    "animal": [
        PoolInstrument("animal_calls", "calls", "noise_chirp", "animal", "one_shot", "fx"),
    ],
    "sfx": [
        PoolInstrument("riser", "riser", "riser", "edm_build", "one_shot", "fx"),
        PoolInstrument("impact", "impact", "impact", "impact_hit", "one_shot", "fx"),
    ],
    "keys": [
        PoolInstrument("piano", "piano", "autowav", "钢琴", "loop", "melody"),
        PoolInstrument("organ", "organ", "autowav", "管风琴", "loop", "pad"),
        PoolInstrument("bells", "bells", "autowav", "铃声", "loop", "melody"),
    ],
    "strings": [
        PoolInstrument("strings", "bowed", "autowav", "管风琴", "loop", "pad"),
        PoolInstrument("harp", "harp", "autowav", "竖琴", "loop", "melody"),
    ],
    "brass": [
        PoolInstrument("brass", "brass", "autowav", "铜管", "loop", "melody"),
        PoolInstrument("saxophone", "sax", "autowav", "铜管", "loop", "melody"),
    ],
    "woodwind": [
        PoolInstrument("flute", "flute", "autowav", "三角波", "loop", "melody"),
        PoolInstrument("oboe", "oboe", "autowav", "三角波", "loop", "melody"),
    ],
    "ethnic": [
        PoolInstrument("ethnic_pluck", "plucked", "autowav", "竖琴", "loop", "melody"),
        PoolInstrument("ethnic_pad", "pad", "autowav", "管风琴", "loop", "pad"),
    ],
}

# 池名列表（镜像 taxonomy.POOLS）
POOLS = list(POOL_INSTRUMENTS.keys())


def get_pool(pool: str) -> list[PoolInstrument]:
    if pool not in POOL_INSTRUMENTS:
        raise KeyError(f"未知声池: {pool}（可用: {POOLS}）")
    return POOL_INSTRUMENTS[pool]


def list_pool_instruments() -> dict[str, list[str]]:
    return {p: [i.name for i in insts] for p, insts in POOL_INSTRUMENTS.items()}


# ═══════════════════════════════════════════════════════════════
# 调性工具
# ═══════════════════════════════════════════════════════════════

def _parse_key(key: str) -> tuple[str, str]:
    """'C' / 'Am' / 'F#m' → (根音名, 调式中文名)。"""
    k = key.strip()
    if not k:
        return "C", "大调"
    if k.endswith("m"):
        return k[:-1], "自然小调"
    if k.endswith("M"):
        return k[:-1], "大调"
    return k, "大调"


def _scale_freqs(key: str, octave: int = 3, mode: str | None = None) -> list[float]:
    root, default_mode = _parse_key(key)
    mode = mode or default_mode
    scale_name = mode if mode in SCALES else default_mode
    if root not in NOTE_NAMES:
        root = "C"
    return build_scale_notes(root, octave, SCALES[scale_name])


# ═══════════════════════════════════════════════════════════════
# 合成工具
# ═══════════════════════════════════════════════════════════════

def _upsample(audio: np.ndarray, src_sr: int, dst_sr: int = _SR) -> np.ndarray:
    if src_sr == dst_sr:
        return audio
    n_out = int(len(audio) * dst_sr / src_sr)
    xs = np.linspace(0.0, len(audio) - 1, n_out)
    return np.interp(xs, np.arange(len(audio)), audio).astype(np.float64)


def _autowav_note(freq: float, dur: float, timbre: str, volume: float,
                  sr: int, seed: int) -> np.ndarray:
    """经 autowav 渲染单音（内部采样率渲染，升采样到 44100）。"""
    samples = render_note(freq, dur, sr, timbre, volume=volume, tension=0.5)
    return _upsample(np.asarray(samples, dtype=np.float64), sr)


def _melodic_phrase(freqs: list[float], durs: list[float], timbre: str,
                    volume: float, sr: int, seed: int, reverb: bool = True,
                    chorus: bool = False) -> np.ndarray:
    """渲染旋律短语并应用 autowav 混响/合唱。"""
    total = int(sum(durs) * sr) + sr // 4
    out = np.zeros(total, dtype=np.float64)
    t = 0
    for f, d in zip(freqs, durs):
        seg = _autowav_note(f, d, timbre, volume, sr, seed)
        end = min(t + len(seg), total)
        out[t:end] += seg[:end - t]
        t += int(d * sr)
    if reverb:
        out = np.asarray(apply_reverb(list(out), sr, delay_ms=90, decay=0.35, mix=0.3))
    if chorus:
        out = np.asarray(apply_chorus(list(out), sr, rate=0.5, depth=0.002, mix=0.25))
    return out


def _place_events(events: list[tuple[float, np.ndarray]], total_sec: float,
                  sr: int = _SR) -> np.ndarray:
    """把 (起始秒, 音频) 事件铺到总长轨道。"""
    out = np.zeros(int(total_sec * sr), dtype=np.float64)
    for t0, seg in events:
        i0 = int(t0 * sr)
        if i0 >= len(out) or len(seg) == 0:
            continue
        end = min(i0 + len(seg), len(out))
        out[i0:end] += seg[:end - i0]
    return out


# ═══════════════════════════════════════════════════════════════
# 各引擎分派
# ═══════════════════════════════════════════════════════════════

def _drum_events(spec_preset: str, bars: int, bpm: int, intensity: float,
                 sr: int, rng: random.Random) -> list[tuple[float, np.ndarray]]:
    """808/原声鼓 pattern 事件列表（按小节循环）。"""
    beat = 60.0 / max(1, bpm)
    events: list[tuple[float, np.ndarray]] = []
    kick = synthesize_808_kick(KICK_808_PRESETS["punchy"])
    snare = synthesize_808_snare(SNARE_808_PRESETS["standard"])
    hh_c = synthesize_808_hihat()
    hh_o = synthesize_808_open_hihat()
    clap = synthesize_808_clap()
    shaker = synthesize_shaker()
    tom = synthesize_tom()
    crash = synthesize_crash()

    for b in range(bars):
        t0 = b * 4 * beat
        # kick: 1/3 拍（强度低时只 1 拍）
        events.append((t0, kick * 0.9))
        if intensity > 0.35:
            events.append((t0 + 2 * beat, kick * 0.8))
        if intensity > 0.7:
            events.append((t0 + 3.5 * beat, kick * 0.6))
        # snare: 2/4 拍
        events.append((t0 + beat, snare * 0.7))
        events.append((t0 + 3 * beat, snare * 0.7))
        if intensity > 0.8 and rng.random() < 0.4:
            events.append((t0 + 3.75 * beat, snare * 0.5))
        # hihat：8 分（第 4 个八分换开镲）
        for k in range(8):
            t = t0 + k * 0.5 * beat
            use_open = (k == 7) and rng.random() < 0.5
            hh = (hh_o if use_open else hh_c) * (0.4 if k % 2 else 0.3)
            events.append((t, hh))
        # shaker 16 分（intensity 高）
        if intensity > 0.55:
            for k in range(16):
                t = t0 + k * 0.25 * beat
                if rng.random() < 0.7:
                    events.append((t, shaker * 0.2))
        # 第 4 小节：tom fill + crash
        if b % 4 == 3:
            events.append((t0, crash * 0.5))
            for k, dt in enumerate([0.0, 0.5, 1.0, 1.5]):
                events.append((t0 + 3 * beat + dt * beat * 0.5, tom * 0.5))
        # clap 点缀
        if intensity > 0.75 and rng.random() < 0.3:
            events.append((t0 + 2.5 * beat, clap * 0.5))
    return events


def _note_sequence(freqs: list[float], bars: int, bpm: int, role: str,
                   seed: int) -> list[tuple[float, float]]:
    """按角色生成 (freq, dur) 序列。"""
    rng = random.Random(seed)
    beat = 60.0 / max(1, bpm)
    n_freqs = len(freqs) or 1
    seq: list[tuple[float, float]] = []

    if role == "pad":
        # 和弦音同时铺底（叠奏）：每小节一个三和弦
        chords = [(freqs[i % n_freqs], freqs[(i + 2) % n_freqs], freqs[(i + 4) % n_freqs])
                  for i in (0, 3, 5, 4)]
        for b in range(bars):
            for f in chords[b % len(chords)]:
                seq.append((f, beat * 4))
            seq.append((0.0, 0.0))  # 叠奏标记由渲染器处理
    elif role == "bass":
        roots = [freqs[i % n_freqs] / 4 for i in (0, 5, 3, 4)]  # I-VI-IV-V 低八度
        for b in range(bars):
            root = roots[b % len(roots)]
            seq.append((root, beat * 2))
            seq.append((root * 2, beat * 0.5))
            seq.append((root, beat * 1.5))
    elif role == "pad_legacy":
        thirds = [(freqs[i % n_freqs], freqs[(i + 2) % n_freqs], freqs[(i + 4) % n_freqs])
                  for i in (0, 3, 5, 4)]
        for b in range(bars):
            for f in thirds[b % len(thirds)]:
                seq.append((f, beat * 4))
    elif role == "vocal":
        pool = [f for f in freqs]
        for b in range(bars):
            for _ in range(2):
                i = rng.randrange(len(pool))
                seq.append((pool[i], beat * rng.choice([1, 1.5, 2])))
    else:  # melody / guita / arp
        for b in range(bars):
            n_notes = 4 if role in ("guita", "melody") else 8
            for k in range(n_notes):
                i = rng.randrange(len(freqs))
                if rng.random() < 0.15:
                    continue  # 休止
                seq.append((freqs[i], beat * rng.choice([0.5, 0.5, 1.0])))
    return seq


def _render_loop_phrase(spec_name: str, engine: str, preset: str, role: str,
                        key: str, bpm: int, bars_loop: int, seed: int,
                        volume: float) -> np.ndarray:
    """渲染 loop 素材：bars_loop 小节长的乐句（内部采样率）。"""
    rng = random.Random(seed)
    freqs = _scale_freqs(key)
    seq = _note_sequence(freqs, bars_loop, bpm, role, seed)

    if engine == "formant":
        syls = ["ah", "o", "e", "i", "u", "m"]
        notes = [(f, d) for f, d in seq]
        audio = sing(notes, syllables=syls, sample_rate=_LOW_SR,
                     volume=volume * 0.9, seed=seed)
        out = np.asarray(audio, dtype=np.float64)
        out = _upsample(out, _LOW_SR)
        out = np.asarray(apply_reverb(list(out), _SR, delay_ms=110, decay=0.4, mix=0.35))
        return out

    # melodic：autowav 音色
    chorus = preset in ("方波", "锯齿波", "三角波")
    if role == "pad":
        # 叠奏：把每小节 3 个和弦音同时渲染再叠加（seq 中 (0,0) 为小节分隔标记）
        chords: list[list[tuple[float, float]]] = []
        cur: list[tuple[float, float]] = []
        for f, d in seq:
            if f <= 0.0 and d <= 0.0:
                if cur:
                    chords.append(cur)
                cur = []
            else:
                cur.append((f, d))
        if cur:
            chords.append(cur)
        n_ch = len(chords) or 1
        bar_sec = bars_loop * 4 * 60.0 / max(1, bpm)
        total_n = int(bar_sec * _LOW_SR) + _LOW_SR // 4
        audio = np.zeros(total_n, dtype=np.float64)
        for ch_i, notes in enumerate(chords):
            i0 = ch_i * int(bar_sec / max(1, n_ch) * _LOW_SR)
            for f, d in notes:
                tone = _melodic_phrase([f], [d], preset, volume * 0.5,
                                       _LOW_SR, seed + ch_i, chorus=chorus)
                end = min(i0 + len(tone), total_n)
                audio[i0:end] += tone[:end - i0]
        return _upsample(audio, _LOW_SR)
    audio = _melodic_phrase([f for f, _ in seq], [d for _, d in seq], preset,
                            volume, _LOW_SR, seed, chorus=chorus)
    return _upsample(audio, _LOW_SR)


def render_source(spec: "object", bpm: int, key: str, bars: int,
                  intensity: float = 0.7, seed: int = 0, volume: float = 0.8,
                  sr: int = _SR) -> np.ndarray:
    """渲染单个生成音源为全长轨道。

    Args:
        spec: 含 pool/name/engine/preset/role/kind/bars_loop 的规格对象。
        bpm / key / bars: 曲目级参数。
        intensity: 0-1，影响鼓密度与音量。
        seed: 可复现种子。
        volume: 基础音量。
        sr: 输出采样率（默认 44100）。

    Returns:
        np.float64 单声道音频（长度 = bars * 4 * 60/bpm 秒）。
    """
    total_sec = bars * 4 * 60.0 / max(1, bpm)
    total = int(total_sec * sr)
    out = np.zeros(total, dtype=np.float64)
    rng = random.Random(seed)
    beat = 60.0 / max(1, bpm)

    engine = spec.engine
    preset = spec.preset
    role = spec.role
    bars_loop = getattr(spec, "bars_loop", 1)

    if engine in ("drum808", "drumac"):
        events = _drum_events(preset, bars, bpm, intensity, sr, rng)
        return _place_events(events, total_sec, sr)

    if engine == "riser":
        dur = min(total_sec * 0.4, 4.0)
        seg = render_riser(preset_name=preset, duration_sec=dur) * volume
        # 放在全曲最后（过渡进尾声），intro 处再放一次小的
        return _place_events([(total_sec - dur, seg)], total_sec, sr)

    if engine == "impact":
        dur = min(1.2, total_sec)
        seg = render_riser(preset_name="impact_hit", duration_sec=dur) * volume
        return _place_events([(0.0, seg)], total_sec, sr)

    if engine == "noise_ring":
        # 牛铃：两个正弦分音 + 快衰减，点缀在第 2/4 拍
        n = int(0.18 * sr)
        t = np.arange(n) / sr
        env = np.exp(-t * 28.0)
        seg = (np.sin(2 * np.pi * 540 * t) * 0.7 + np.sin(2 * np.pi * 800 * t) * 0.3) * env
        events = [(t0, seg * volume) for b in range(bars)
                  for t0 in ((b * 4 + 2.5) * beat, (b * 4 + 3.5) * beat)
                  if rng.random() < 0.6]
        return _place_events(events, total_sec, sr)

    if engine == "noise_chirp":
        # 动物叫声：扫频噪声啁啾，稀疏点缀
        events = []
        for _ in range(max(1, bars // 4)):
            t0 = rng.uniform(0, max(0.1, total_sec - 0.5))
            dur = rng.uniform(0.08, 0.25)
            n = int(dur * sr)
            tt = np.arange(n) / sr
            f0 = rng.uniform(1800, 4200)
            f1 = rng.uniform(1200, 3200)
            phase = 2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / sr
            seg = np.sin(phase) * np.exp(-tt * 9.0) * 0.25 * volume
            events.append((t0, seg))
        return _place_events(events, total_sec, sr)

    # ── melodic 引擎：loop 平铺到全长 ──
    loop_audio = _render_loop_phrase(spec.name, engine, preset, role, key,
                                     bpm, bars_loop, seed, volume)
    loop_len = int(bars_loop * 4 * beat * sr)
    if len(loop_audio) == 0:
        return out
    # 对齐到整小节长度（乐句不足补静音，超出截断），保证平铺形状一致
    if len(loop_audio) < loop_len:
        loop_audio = np.concatenate([loop_audio, np.zeros(loop_len - len(loop_audio))])
    elif len(loop_audio) > loop_len:
        loop_audio = loop_audio[:loop_len]
    # 平铺（每小节重置循环，相位连续）
    for b in range(bars):
        i0 = int(b * 4 * beat * sr)
        n_copy = min(loop_len, total - i0)
        if n_copy > 0:
            out[i0:i0 + n_copy] += loop_audio[:n_copy]
    return out
