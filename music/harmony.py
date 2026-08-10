"""
多声部和声系统 —— 和声生成 + 声部排列 + 和弦进行
====================================================

提供从单旋律自动生成多声部和声的工具：

  - HarmonyVoice: 和声声部定义 (音程偏移/音量/八度)
  - generate_parallel_harmony:  平行和声 (三度/五度/八度)
  - generate_diatonic_harmony:  调内自然和声 (大小三度交替)
  - generate_chordal_harmony:   基于和弦进行的和声
  - voice_leading:              声部引导 (最小移动原则)
  - render_harmony_tracks:      将多声部渲染为音频轨道列表

用法:
    >>> from bloodmusic.music.harmony import HarmonyVoice, generate_parallel_harmony
    >>> voices = generate_parallel_harmony(
    ...     melody_notes=["C4","D4","E4","F4"],
    ...     intervals=[3, 5],  # 三度和五度和声
    ... )
    >>> for v in voices:
    ...     print(v.notes)  # 各声部音符
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum

from ..core.note_utils import note_to_freq


# ═══════════════════════════════════════════════════════════════════════
# 音阶/调性数据结构
# ═══════════════════════════════════════════════════════════════════════

# 大调音阶级数 (半音偏移)
_MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]

# 小调音阶级数 (自然小调)
_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# 半音名
_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _note_to_semitones(note: str) -> int:
    """音符 → 半音编号 (C0=0)。支持 "C4" 和 "C" 两种格式"""
    if note is None:
        return -1
    if not note or not note.strip():
        return -1
    # 分离音名和八度
    if note[-1].isdigit():
        name = note[:-1].upper()
        octave = int(note[-1])
    else:
        name = note.upper()
        octave = 0  # 默认八度
    idx = _NOTE_NAMES.index(name)
    return idx + octave * 12


def _semitones_to_note(st: int) -> str:
    """半音编号 → 音符名"""
    octave = st // 12
    idx = st % 12
    return f"{_NOTE_NAMES[idx]}{octave}"


def _is_in_major_scale(note_semitones: int, tonic_offset: int = 0) -> bool:
    """检查音符是否在 C 大调音阶内 (可偏移主音)"""
    degree = (note_semitones - tonic_offset) % 12
    return degree in _MAJOR_SCALE


# 音符名到半音的缓存
_NOTE_CACHE: Dict[str, int] = {}


def _get_semitones(note: str) -> int:
    if note not in _NOTE_CACHE:
        _NOTE_CACHE[note] = _note_to_semitones(note)
    return _NOTE_CACHE[note]


# ═══════════════════════════════════════════════════════════════════════
# 和声声部定义
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HarmonyVoice:
    """一个和声声部。

    Args:
        name: 声部名 ("third_up", "fifth_down" 等)
        notes: 音符列表 (None=休止符)
        volume: 相对音量 0~1
        octave_shift: 八度偏移
    """
    name: str = "harmony"
    notes: List[Optional[str]] = field(default_factory=list)
    volume: float = 0.6
    octave_shift: int = 0

    def with_octave_shift(self) -> List[Optional[str]]:
        """应用八度偏移后的音符"""
        result = []
        for note in self.notes:
            if note is None:
                result.append(None)
            else:
                st = _get_semitones(note)
                result.append(_semitones_to_note(st + self.octave_shift * 12))
        return result


# ═══════════════════════════════════════════════════════════════════════
# 和声生成函数
# ═══════════════════════════════════════════════════════════════════════

def generate_parallel_harmony(
    melody_notes: List[Optional[str]],
    intervals: List[int],
    direction: str = "up",
    volumes: Optional[List[float]] = None,
    names: Optional[List[str]] = None,
) -> List[HarmonyVoice]:
    """平行和声：每个旋律音按固定音程叠加。

    这是最简单直接的和声方式。每个旋律音上方/下方叠加固定音程的另一个音。

    Args:
        melody_notes: 旋律音符列表
        intervals: 音程列表 (半音数)，如 [3] = 小三度, [4] = 大三度,
                   [7] = 纯五度, [12] = 八度
        direction: "up" (上方) 或 "down" (下方)
        volumes: 各声部音量 (默认 0.6)
        names: 各声部名称 (默认 "harmony_1", "harmony_2", ...)

    Returns:
        和声声部列表

    Example:
        >>> voices = generate_parallel_harmony(
        ...     ["C4","D4","E4","F4"], intervals=[4, 7]
        ... )
        >>> voices[0].notes  # 上方大三度: ["E4","F#4","G#4","A4"]
        >>> voices[1].notes  # 上方纯五度: ["G4","A4","B4","C5"]
    """
    sign = 1 if direction == "up" else -1
    voices = []

    for i, interval in enumerate(intervals):
        name = (names[i] if names and i < len(names)
                else f"{direction}_{interval}st")
        vol = volumes[i] if volumes and i < len(volumes) else 0.6

        harmony_notes = []
        for note in melody_notes:
            if note is None:
                harmony_notes.append(None)
            else:
                st = _get_semitones(note) + sign * interval
                harmony_notes.append(_semitones_to_note(st))

        voices.append(HarmonyVoice(name=name, notes=harmony_notes, volume=vol))

    return voices


def generate_diatonic_harmony(
    melody_notes: List[Optional[str]],
    interval_above: int = 2,
    key: str = "C",
    scale_type: str = "major",
    volumes: Optional[List[float]] = None,
) -> List[HarmonyVoice]:
    """调内自然和声：三度堆叠，自动在大小三度间切换以保持调性。

    与平行和声不同，调内和声会自动使用大三度或小三度，
    确保所有和声音都在指定的调内。

    Args:
        melody_notes: 旋律音符列表
        interval_above: 音程基数 (2=二度, 3=三度, 4=四度...)
        key: 调性 ("C", "Am", "G" 等)
        scale_type: "major" 或 "minor"
        volumes: 各声部音量

    Returns:
        和声声部列表

    Example:
        >>> # C大调下, C→E(大三度), D→F(小三度=A调外), E→G(小三度)
        >>> voices = generate_diatonic_harmony(["C4","D4","E4"], interval_above=2)
        >>> voices[0].notes  # 调内二度: ["E4","F4","G4"]
    """
    tonic_offset = _get_semitones(key)
    scale = _MAJOR_SCALE if scale_type == "major" else _MINOR_SCALE

    # 映射: 音阶级数 → 该级上的音程对应的目标音
    harmony_notes = []
    for note in melody_notes:
        if note is None:
            harmony_notes.append(None)
            continue

        st = _get_semitones(note)
        # 该音在调内的度数
        degree = (st - tonic_offset) % 12
        if degree not in scale:
            # 非调内音, 向上取最近的调内音作为和声
            target_st = st + 1
            while (target_st - tonic_offset) % 12 not in scale:
                target_st += 1
            harmony_notes.append(_semitones_to_note(target_st))
            continue

        # 找到该级数在音阶中的索引
        scale_deg_idx = scale.index(degree)

        # 堆叠 interval_above 个音阶级
        target_scale_deg = (scale_deg_idx + interval_above) % len(scale)
        octave_jump = (scale_deg_idx + interval_above) // len(scale)
        target_degree = scale[target_scale_deg]
        target_st = st - degree + target_degree + octave_jump * 12
        harmony_notes.append(_semitones_to_note(target_st))

    vol = volumes[0] if volumes else 0.6
    name = f"diatonic_{interval_above}th_{scale_type}"
    return [HarmonyVoice(name=name, notes=harmony_notes, volume=vol)]


def generate_chordal_harmony(
    melody_notes: List[Optional[str]],
    chord_progression: List[List[str]],
    chord_durations: List[int],  # 每个和弦持续多少音符
    voice_count: int = 2,
    volumes: Optional[List[float]] = None,
) -> List[HarmonyVoice]:
    """和弦式和声：根据和弦进行，将旋律音分配到和弦的不同声部。

    适合从和弦进行自动生成多声部伴奏/和声。

    Args:
        melody_notes: 旋律音符列表
        chord_progression: 和弦进行，如 [["C4","E4","G4"], ["F4","A4","C5"], ...]
        chord_durations: 每个和弦持续的旋律音符数，如 [4, 4, 2, 2, 4]
        voice_count: 生成多少个和声声部
        volumes: 各声部音量

    Returns:
        和声声部列表

    Example:
        >>> chords = [["C4","E4","G4"], ["F4","A4","C5"], ["G4","B4","D5"], ["C4","E4","G4"]]
        >>> voices = generate_chordal_harmony(
        ...     ["C4","C4","C4","C4","F4","F4","F4","F4",
        ...      "G4","G4","G4","G4","C4","C4","C4","C4"],
        ...     chords, [4, 4, 4, 4],
        ...     voice_count=2,
        ... )
    """
    # 为每个旋律音符确定当前和弦
    current_chord_idx = 0
    notes_in_chord = 0

    # 初始化各声部
    voice_notes: List[List[Optional[str]]] = [[] for _ in range(voice_count)]

    for i, note in enumerate(melody_notes):
        # 确定当前和弦
        if notes_in_chord >= chord_durations[current_chord_idx]:
            current_chord_idx = min(current_chord_idx + 1, len(chord_progression) - 1)
            notes_in_chord = 0

        chord = chord_progression[current_chord_idx]
        notes_in_chord += 1

        if note is None:
            for v in range(voice_count):
                voice_notes[v].append(None)
            continue

        # 跳过旋律音本身，用其余和弦音填充各声部
        chord_semitones = sorted([_get_semitones(n) for n in chord])

        # 找与旋律最接近的和弦音
        melody_st = _get_semitones(note)

        # 用和弦中其他音填充声部
        remaining = [s for s in chord_semitones
                     if s % 12 != melody_st % 12]  # 不同音高类的音

        for v in range(voice_count):
            if v < len(remaining):
                voice_notes[v].append(_semitones_to_note(remaining[v % len(remaining)]))
            else:
                voice_notes[v].append(None)

    voices = []
    for v in range(voice_count):
        vol = volumes[v] if volumes and v < len(volumes) else 0.5
        voices.append(HarmonyVoice(
            name=f"chord_voice_{v+1}",
            notes=voice_notes[v],
            volume=vol,
        ))
    return voices


# ═══════════════════════════════════════════════════════════════════════
# 声部引导
# ═══════════════════════════════════════════════════════════════════════

def voice_leading(
    melody_notes: List[Optional[str]],
    chord_progression: List[List[str]],
    chord_durations: List[int],
    n_voices: int = 3,
) -> List[List[str]]:
    """声部引导：基于最小移动原则排列和弦内声部。

    确保和弦切换时各声部移动最小, 类似钢琴/合唱的经典排列。

    Args:
        melody_notes: 旋律音符 (最上声部)
        chord_progression: 和弦进行
        chord_durations: 每个和弦持续的旋律音符数
        n_voices: 声部数 (含旋律)

    Returns:
        各声部的音符列表 (第一个 = 旋律)

    Example:
        >>> voices = voice_leading(
        ...     ["C4","","","","F4","","","","G4","","","","C4","","",""],
        ...     [["C4","E4","G4"], ["F4","A4","C5"], ["G4","B4","D5"], ["C4","E4","G4"]],
        ...     [4, 4, 4, 4],
        ... )
    """
    result: List[List[str]] = [[] for _ in range(n_voices)]
    current_voicing: List[int] = []  # 上一个和弦的各声部半音编号

    current_chord_idx = 0
    notes_in_chord = 0

    for i, note in enumerate(melody_notes):
        if notes_in_chord >= chord_durations[current_chord_idx]:
            current_chord_idx = min(current_chord_idx + 1, len(chord_progression) - 1)
            notes_in_chord = 0
            current_voicing = []  # 新和弦重新排列

        chord = chord_progression[current_chord_idx]
        notes_in_chord += 1

        if note is None or note == "":
            for v in range(n_voices):
                result[v].append("")
            continue

        chord_sts = sorted([_get_semitones(n) for n in chord])

        if not current_voicing:
            # 首次: 从上到下分配和弦音 (最高声部 = 旋律)
            melody_st = _get_semitones(note)
            current_voicing.append(melody_st)
            # 剩余声部用其他和弦音
            remaining = [s for s in chord_sts if s % 12 != melody_st % 12]
            for v in range(1, n_voices):
                if v - 1 < len(remaining):
                    # 选择比旋律低的最近音
                    target = remaining[v - 1]
                    while target >= melody_st:
                        target -= 12
                    current_voicing.append(target)
                else:
                    # 不够就用最低音向下八度
                    current_voicing.append(chord_sts[0] - 12 * v)
        else:
            # 后续: 最小移动
            melody_st = _get_semitones(note)
            new_voicing = [melody_st]

            for v in range(1, n_voices):
                best = None
                best_dist = float('inf')
                # 在可用和弦音中找距离上一声部最近的
                for st in chord_sts:
                    # 需要比当前声部低一个半音级 (至少)
                    for oct_shift in range(2, -3, -1):  # 优先接近的音
                        candidate = st - oct_shift * 12
                        if candidate >= melody_st:
                            continue  # 必须在旋律下方
                        dist = abs(candidate - current_voicing[v])
                        if dist < best_dist:
                            best_dist = dist
                            best = candidate
                if best is None:
                    best = chord_sts[0] - 12 * v
                new_voicing.append(best)

            current_voicing = new_voicing

        for v in range(n_voices):
            result[v].append(_semitones_to_note(current_voicing[v]))

    return result


# ═══════════════════════════════════════════════════════════════════════
# 和声轨道渲染
# ═══════════════════════════════════════════════════════════════════════

def render_harmony_tracks(
    melody_notes: List[Optional[str]],
    durations: List[float],
    harmony_voices: List[HarmonyVoice],
    bpm: int = 120,
    osc_type=None,
    volume_mult: float = 1.0,
    sr: int = 44100,
) -> List[np.ndarray]:
    """将旋律+和声渲染为多条音轨数组。

    每条轨道 = 一条和声声部，返回列表可分别混合。

    Args:
        melody_notes: 旋律音符列表
        durations: 各音符持续时间 (拍)
        bpm: BPM
        harmony_voices: 和声声部列表
        osc_type: 振荡器类型 (默认 SINE)
        volume_mult: 音量倍率
        sr: 采样率

    Returns:
        [melody_audio, harmony_1_audio, harmony_2_audio, ...]
    """
    from ..core.oscillator import oscillator, OscType

    if osc_type is None:
        osc_type = OscType.SINE

    beat_dur = 60.0 / bpm
    total_len = int(sum(durations) * beat_dur * sr)

    tracks = []
    all_voice_lists = [melody_notes] + [v.notes for v in harmony_voices]
    all_volumes = [1.0] + [v.volume * volume_mult for v in harmony_voices]

    for voice_notes, vol in zip(all_voice_lists, all_volumes):
        track = np.zeros(total_len, dtype=np.float64)
        pos = 0

        for note, dur_beats in zip(voice_notes, durations):
            dur_sec = dur_beats * beat_dur
            n_samp = int(dur_sec * sr)

            if note is not None:
                t = np.linspace(0, dur_sec, n_samp, dtype=np.float64)
                freq = note_to_freq(note)
                sig = oscillator(t, freq, osc_type)
                from ..core.envelope import make_envelope, EnvShape
                env = make_envelope(n_samp, EnvShape.PAD)
                sig = sig * env * vol
                end_pos = min(pos + n_samp, total_len)
                track[pos:end_pos] += sig[:end_pos - pos]

            pos += n_samp
            if pos >= total_len:
                break

        tracks.append(track)

    return tracks
