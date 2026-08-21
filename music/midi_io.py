"""
MIDI 导入导出 —— MusicPattern ↔ MIDI 双向转换
=================================================

使用 mido 实现:
  - music_pattern_to_midi: MusicPattern → MIDI 文件
  - drum_pattern_to_midi:  DrumPattern → MIDI 文件
  - midi_to_patterns:     MIDI 文件 → MusicPattern 列表

支持多轨 MIDI 读写，可导入 DAW 编辑后再导回渲染。

用法:
    >>> from bloodmusic.music.midi_io import music_pattern_to_midi, midi_to_patterns
    >>> music_pattern_to_midi(pattern, "my_melody.mid")
    >>> patterns = midi_to_patterns("my_song.mid")

.. deprecated::
    本模块的 **导入方向**（``midi_to_patterns``）已被
    ``bloodmusic.bridge.midi_import.midi_to_patterns_v2`` 取代：
    旧实现会把和弦拆成连续单音、整体丢弃 GM 鼓轨、且把 PPQ 硬编码成 480。
    导出方向的三个函数暂无替代，可继续使用。
"""

import os
from typing import List, Optional, Tuple, Dict
import numpy as np

from ..core.note_utils import note_to_freq, NOTES


# ── 音符名 ↔ MIDI 音符号互转 ──

def _note_to_midi(note_name: str) -> int:
    """音符名 → MIDI 音符号 (如 C4 → 60)"""
    if note_name is None or not note_name.strip():
        return -1
    name = note_name.strip()
    # 处理升降号
    if len(name) >= 2 and name[1] in ('#', 'b'):
        pitch_class = name[:2].upper()
        octave_str = name[2:]
    else:
        pitch_class = name[0].upper()
        octave_str = name[1:]

    pitch_map = {
        'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3,
        'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8,
        'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11,
    }
    pitch = pitch_map.get(pitch_class, 0)
    octave = int(octave_str) if octave_str else 4
    return (octave + 1) * 12 + pitch


def _midi_to_note(midi_num: int) -> str:
    """MIDI 音符号 → 音符名 (如 60 → C4)"""
    if midi_num < 0:
        return "C4"
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = midi_num // 12 - 1
    note = note_names[midi_num % 12]
    return f"{note}{octave}"


# ── MusicPattern → MIDI ──

def music_pattern_to_midi(
    pattern,
    filepath: str,
    program: int = 0,
    channel: int = 0,
    velocity: int = 80,
) -> str:
    """将 MusicPattern 导出为 MIDI 文件。

    Args:
        pattern: MusicPattern 实例
        filepath: 输出 MIDI 路径
        program: GM 乐器程序号 (0-127)
        channel: MIDI 通道 (0-15)
        velocity: 默认力度 (0-127)

    Returns:
        输出文件路径
    """
    try:
        import mido
    except ImportError:
        raise ImportError("需要 mido 库: pip install mido")

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # 设置速度和乐器
    tempo = mido.bpm2tempo(pattern.bpm)
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
    track.append(mido.Message('program_change', program=program, channel=channel, time=0))

    # 转换为 MIDI 音符
    beat_dur_ticks = mid.ticks_per_beat  # ticks per beat

    for i, note in enumerate(pattern.notes):
        dur_beats = pattern.durations[i] if i < len(pattern.durations) else 1.0
        dur_ticks = int(dur_beats * beat_dur_ticks)

        if note is not None:
            midi_note = _note_to_midi(note)
            if midi_note >= 0:
                track.append(mido.Message('note_on', note=midi_note,
                                         velocity=velocity, channel=channel, time=0))
                track.append(mido.Message('note_off', note=midi_note,
                                         velocity=0, channel=channel, time=dur_ticks))
        else:
            # 休止符
            track.append(mido.Message('note_on', note=0, velocity=0,
                                     channel=channel, time=0))
            track.append(mido.Message('note_off', note=0, velocity=0,
                                     channel=channel, time=dur_ticks))

    mid.save(filepath)
    return filepath


def drum_pattern_to_midi(pattern, filepath: str, channel: int = 9) -> str:
    """将 DrumPattern 导出为 MIDI 文件 (通道 10 = 鼓通道)。

    Args:
        pattern: DrumPattern 实例
        filepath: 输出 MIDI 路径
        channel: MIDI 通道 (通常 9 = GM 鼓通道)
    """
    try:
        import mido
    except ImportError:
        raise ImportError("需要 mido 库: pip install mido")

    # GM 鼓映射 (简化版)
    GM_DRUM_MAP = {
        "kick": 36,    # Bass Drum 1
        "snare": 38,   # Acoustic Snare
        "hihat": 42,   # Closed Hi-hat
        "open_hat": 46, # Open Hi-hat
        "clap": 39,    # Hand Clap
        "tom_hi": 50,  # High Tom
        "tom_mid": 47, # Low-Mid Tom
        "tom_lo": 43,  # High Floor Tom
        "rim": 37,     # Side Stick
        "crash": 49,   # Crash Cymbal
        "ride": 51,    # Ride Cymbal
    }

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)

    tempo = mido.bpm2tempo(pattern.bpm)
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

    beat_dur_ticks = mid.ticks_per_beat
    step_ticks = beat_dur_ticks // 4  # 16 分音符

    # 收集各轨的触发时间
    note_events = []  # [(start_tick, midi_note, velocity)]

    for track_name, steps in pattern.tracks.items():
        midi_note = GM_DRUM_MAP.get(track_name, 60)
        velocity = 90
        for step_i, hit in enumerate(steps):
            if hit:
                start_tick = step_i * step_ticks
                note_events.append((start_tick, midi_note, velocity))

    # 按时间排序
    note_events.sort(key=lambda x: x[0])

    # 创建 note_on/note_off 事件
    current_tick = 0
    active_notes = {}  # {midi_note: start_tick}
    events = []

    for tick, note, vel in note_events:
        # 先关闭在这个 tick 之前的音符 (鼓音通常很短)
        to_close = [(n, t) for n, t in active_notes.items()
                    if t + step_ticks <= tick]
        for n, _ in to_close:
            events.append(('note_off', tick, n, 0))
            del active_notes[n]

        events.append(('note_on', tick, note, vel))
        active_notes[note] = tick

    # 关闭剩余音符
    for n, t in active_notes.items():
        events.append(('note_off', t + step_ticks, n, 0))

    # 按时间写入
    events.sort(key=lambda x: x[1])
    prev_tick = 0
    for evt_type, tick, note, vel in events:
        delta = tick - prev_tick
        if evt_type == 'note_on':
            track.append(mido.Message('note_on', note=note, velocity=vel,
                                     channel=channel, time=delta))
        else:
            track.append(mido.Message('note_off', note=note, velocity=0,
                                     channel=channel, time=delta))
        prev_tick = tick

    mid.save(filepath)
    return filepath


# ── MIDI → MusicPattern ──

def midi_to_patterns(
    filepath: str,
    bpm: Optional[int] = None,
    ticks_per_beat: int = 480,
) -> List["MusicPattern"]:
    """从 MIDI 文件导入所有轨道为 MusicPattern 列表。

    @deprecated，请用 bridge.midi_import.midi_to_patterns_v2。

    弃用原因（本函数保留仅为向后兼容，行为不再变更）:
        1. **和弦被拆成连续单音** —— 同时发音的音符被逐个串成旋律，
           4 个三和弦会变成 12 个先后弹奏的单音；
        2. **鼓轨被整体丢弃** —— GM 通道 10 未做识别，鼓素材导入后为空；
        3. **PPQ 硬编码 480** —— 实测素材 PPQ = 220，时值会被整体算错 ~2.18 倍；
        4. 超出 C0–C7 的音高会被 note_to_freq() 静默降级为 440Hz。

    替代方案:
        >>> from bloodmusic.bridge import midi_to_patterns_v2   # doctest: +SKIP
        >>> result = midi_to_patterns_v2("song.mid")            # doctest: +SKIP
        >>> result.melody_patterns, result.chord_patterns, result.drum_patterns  # doctest: +SKIP

    Args:
        filepath: 输入 MIDI 文件路径
        bpm: 覆盖 BPM (None = 从 MIDI 读取)
        ticks_per_beat: 分辨率

    Returns:
        MusicPattern 列表 (每个 MIDI 轨道一个)
    """
    try:
        import mido
    except ImportError:
        raise ImportError("需要 mido 库: pip install mido")

    from .pattern import MusicPattern
    from ..core.oscillator import OscType
    from ..core.envelope import EnvShape

    mid = mido.MidiFile(filepath)
    detected_bpm = bpm or 120

    # 尝试从 MIDI 读取 BPM
    if bpm is None:
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    detected_bpm = int(mido.tempo2bpm(msg.tempo))
                    break

    patterns = []
    track_idx = 0

    for midi_track in mid.tracks:
        notes_events = []  # [(start_tick, end_tick, midi_note, velocity)]
        current_time = 0
        active_notes = {}  # {midi_note: (start_tick, velocity)}

        for msg in midi_track:
            current_time += msg.time

            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes[msg.note] = (current_time, msg.velocity)
            elif (msg.type == 'note_off' or
                  (msg.type == 'note_on' and msg.velocity == 0)):
                if msg.note in active_notes:
                    start_tick, vel = active_notes.pop(msg.note)
                    notes_events.append((start_tick, current_time, msg.note, vel))

        # 关闭剩余音符
        for note, (start_tick, vel) in active_notes.items():
            notes_events.append((start_tick, current_time, note, vel))

        if not notes_events:
            track_idx += 1
            continue

        # 按时间排序
        notes_events.sort(key=lambda x: x[0])

        # 转换为 MusicPattern
        pattern_notes = []
        pattern_durs = []
        prev_end_tick = 0

        for start_tick, end_tick, midi_note, velocity in notes_events:
            # 处理休止 (gap between notes)
            gap_ticks = start_tick - prev_end_tick
            if gap_ticks > 0:
                gap_beats = gap_ticks / mid.ticks_per_beat
                # 将长休止拆分为最大 1 拍的块
                while gap_beats > 0:
                    chunk = min(gap_beats, 1.0)
                    pattern_notes.append(None)
                    pattern_durs.append(round(chunk, 2))
                    gap_beats -= chunk

            note_name = _midi_to_note(midi_note)
            dur_ticks = end_tick - start_tick
            dur_beats = max(0.1, dur_ticks / mid.ticks_per_beat)

            pattern_notes.append(note_name)
            pattern_durs.append(round(dur_beats, 2))
            prev_end_tick = end_tick

        if pattern_notes:
            pat = MusicPattern(
                name=f"midi_track_{track_idx}",
                notes=pattern_notes,
                durations=pattern_durs,
                bpm=detected_bpm,
                loop=False,
                osc_type=OscType.TRIANGLE,
                volume=0.16,
                env_shape=EnvShape.PAD,
            )
            patterns.append(pat)

        track_idx += 1

    return patterns


def song_to_midi(
    arrangement,
    filepath: str,
    programs: Optional[Dict[int, int]] = None,
) -> str:
    """将 SongArrangement 导出为多轨 MIDI 文件。

    Args:
        arrangement: SongArrangement 实例
        filepath: 输出路径
        programs: {track_index: gm_program} 乐器映射

    Returns:
        输出文件路径
    """
    try:
        import mido
    except ImportError:
        raise ImportError("需要 mido 库: pip install mido")

    mid = mido.MidiFile()

    # 检查是否有 music patterns
    all_has_patterns = any(
        sec.music_patterns for sec in arrangement.sections
    )
    all_has_drums = any(
        sec.drum_pattern is not None for sec in arrangement.sections
    )

    # 为每个 music track 创建 MIDI track
    max_tracks = max(
        len(sec.music_patterns) for sec in arrangement.sections
    ) if all_has_patterns else 0

    for t_idx in range(max_tracks):
        track = mido.MidiTrack()
        mid.tracks.append(track)
        prog = (programs or {}).get(t_idx, 0)
        track.append(mido.Message('program_change', program=prog, channel=t_idx, time=0))

    # 鼓轨道
    if all_has_drums:
        drum_track = mido.MidiTrack()
        mid.tracks.append(drum_track)

    # 设置全局速度
    tempo_track = mid.tracks[0]
    tempo = mido.bpm2tempo(arrangement.bpm)
    tempo_track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

    # 按段落写入音符
    current_tick = 0
    tick_per_beat = mid.ticks_per_beat

    for sec_idx, section in enumerate(arrangement.sections):
        sec_bpm = section.bpm or arrangement.bpm
        sec_tempo = mido.bpm2tempo(sec_bpm)
        beat_dur_ticks = tick_per_beat

        # 更新速度 (如果变化)
        if sec_bpm != arrangement.bpm and sec_idx > 0:
            tempo_track.append(mido.MetaMessage(
                'set_tempo', tempo=sec_tempo, time=current_tick))

        # 写入 music tracks
        for t_idx, pattern in enumerate(section.music_patterns):
            midi_track = mid.tracks[t_idx + 1]  # +1 跳过 tempo track
            channel = t_idx % 16

            for i, note in enumerate(pattern.notes):
                dur_beats = pattern.durations[i] if i < len(pattern.durations) else 1.0
                dur_ticks = int(dur_beats * beat_dur_ticks)

                if note is not None:
                    midi_note = _note_to_midi(note)
                    if midi_note >= 0:
                        midi_track.append(mido.Message(
                            'note_on', note=midi_note, velocity=80,
                            channel=channel, time=0))
                        midi_track.append(mido.Message(
                            'note_off', note=midi_note, velocity=0,
                            channel=channel, time=dur_ticks))
                else:
                    midi_track.append(mido.Message(
                        'note_on', note=0, velocity=0,
                        channel=channel, time=0))
                    midi_track.append(mido.Message(
                        'note_off', note=0, velocity=0,
                        channel=channel, time=dur_ticks))

        # 写入鼓轨
        if section.drum_pattern is not None and all_has_drums:
            drum_midi_track = mid.tracks[max_tracks + 1]
            dp = section.drum_pattern
            step_ticks = beat_dur_ticks // 4
            GM_DRUM = { "kick": 36, "snare": 38, "hihat": 42 }

            for track_name, steps in dp.tracks.items():
                midi_note = GM_DRUM.get(track_name, 60)
                for step_i, hit in enumerate(steps):
                    if hit:
                        drum_midi_track.append(mido.Message(
                            'note_on', note=midi_note, velocity=90,
                            channel=9, time=step_i * step_ticks))
                        drum_midi_track.append(mido.Message(
                            'note_off', note=midi_note, velocity=0,
                            channel=9, time=step_ticks))

        # 累加时间
        section_ticks = int(section.bars * 4 * beat_dur_ticks *
                           (arrangement.bpm / sec_bpm))
        current_tick += section_ticks

    mid.save(filepath)
    return filepath
