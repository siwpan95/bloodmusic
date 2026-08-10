"""
MIDI 文件导出模块
=================

将 BloodMusic 生成的音乐模式/鼓点模式导出为标准 MIDI 文件，
与所有主流 DAW (Ableton Live / FL Studio / Logic Pro / Cubase 等) 兼容。

依赖:
    - mido (可选): pip install mido
    - 如果不安装 mido，MIDI 导出功能将不可用

使用方式:
    >>> from bloodmusic.export.midi_export import export_music_to_midi, export_drums_to_midi
    >>> export_music_to_midi(pattern, "output.mid")
    >>> export_drums_to_midi(drum_pattern, "drums.mid")

MIDI 标准鼓映射 (General MIDI):
    - 36 = Kick (Bass Drum 1)
    - 38 = Snare (Acoustic Snare)
    - 42 = Closed Hi-hat
    - 46 = Open Hi-hat
    - 49 = Crash Cymbal
    - 51 = Ride Cymbal
    - 48 = High Tom
    - 45 = Mid Tom
    - 41 = Low Tom
"""

import numpy as np
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass


# MIDI 鼓音符映射 (General MIDI Standard)
MIDI_DRUM_MAP: Dict[str, int] = {
    "kick": 36,
    "bass_drum": 36,
    "bd": 36,
    "snare": 38,
    "sd": 38,
    "clap": 39,
    "hihat": 42,
    "hihat_closed": 42,
    "ch": 42,
    "hh": 42,
    "hihat_open": 46,
    "oh": 46,
    "hihat_pedal": 44,
    "crash": 49,
    "cc": 49,
    "ride": 51,
    "rc": 51,
    "high_tom": 48,
    "ht": 48,
    "mid_tom": 45,
    "mt": 45,
    "low_tom": 41,
    "lt": 41,
    "rimshot": 37,
    "cowbell": 56,
    "tambourine": 54,
    "shaker": 70,
}


def _check_mido() -> bool:
    """检查 mido 是否可用。"""
    try:
        import mido  # noqa: F401
        return True
    except ImportError:
        return False


def _get_midi_note(note_name: str) -> int:
    """将音符名 (如 'C4') 转换为 MIDI 音符号。

    Args:
        note_name: 音符名，如 'C4', 'F#3', 'Ab5'

    Returns:
        MIDI 音符号 (0~127)
    """
    from ..core.note_utils import note_to_freq

    freq = note_to_freq(note_name)
    # 频率 → MIDI: midi = 69 + 12 * log2(freq / 440)
    return int(round(69 + 12 * np.log2(freq / 440.0)))


def export_music_to_midi(
    pattern,
    output_path: str,
    tempo: Optional[int] = None,
    channel: int = 0,
    program: int = 0,  # 0 = Acoustic Grand Piano
    velocity: int = 80,
) -> str:
    """将 MusicPattern 导出为 MIDI 文件。

    Args:
        pattern: MusicPattern 对象
        output_path: 输出 .mid 文件路径
        tempo: BPM (None = 使用 pattern.bpm)
        channel: MIDI 通道 (0~15)
        program: MIDI 乐器编号 (0=钢琴, 参见 GM 标准)
        velocity: 力度 (0~127)

    Returns:
        输出文件路径

    Raises:
        ImportError: 如果没有安装 mido
    """
    if not _check_mido():
        raise ImportError(
            "MIDI 导出需要 mido 库。请运行: pip install mido"
        )
    import mido

    bpm = tempo or getattr(pattern, 'bpm', 120)
    ticks_per_beat = 480  # 标准 MIDI 分辨率

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # 设置速度
    tempo_us = mido.bpm2tempo(bpm)
    track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))

    # 设置乐器
    track.append(mido.Message('program_change', channel=channel, program=program, time=0))

    # 获取音符和时长
    notes = getattr(pattern, 'notes', [])
    durations = getattr(pattern, 'durations', [])
    octave_shifts = getattr(pattern, 'octave_shifts', None) or [0] * len(notes)

    beat_dur = 60.0 / bpm

    for i, (note_name, dur_beats, oct_shift) in enumerate(zip(notes, durations, octave_shifts)):
        if note_name is None:
            # 休止符
            ticks = int(dur_beats * ticks_per_beat)
            last_event_time = ticks
            continue

        # 含八度的音符名
        if oct_shift != 0:
            # 解析原始音符并调整八度
            base = ''.join(c for c in note_name if c.isalpha() or c == '#')
            octave = int(''.join(c for c in note_name if c.isdigit()))
            note_name_shifted = f"{base}{octave + oct_shift}"
        else:
            note_name_shifted = note_name

        midi_note = _get_midi_note(note_name_shifted)
        note_ticks = int(dur_beats * ticks_per_beat)

        # Note On
        track.append(mido.Message(
            'note_on', channel=channel, note=midi_note,
            velocity=velocity, time=0
        ))
        # Note Off
        track.append(mido.Message(
            'note_off', channel=channel, note=midi_note,
            velocity=0, time=note_ticks
        ))

    # 添加和弦 (如果有)
    chords = getattr(pattern, 'chords', None)
    if chords:
        # 和弦叠加在同一轨道上
        chord_track = mido.MidiTrack()
        mid.tracks.append(chord_track)
        chord_track.append(mido.Message('program_change', channel=channel + 1, program=program, time=0))

        for chord_idx, chord_notes in enumerate(chords):
            start_ticks = int(chord_idx * sum(durations) / len(chords) * beat_dur * ticks_per_beat)
            chord_dur_ticks = int(beat_dur * ticks_per_beat)

            for cn in chord_notes:
                midi_n = _get_midi_note(cn)
                chord_track.append(mido.Message(
                    'note_on', channel=channel + 1, note=midi_n,
                    velocity=int(velocity * 0.6), time=start_ticks if cn == chord_notes[0] else 0
                ))
            for cn in chord_notes:
                midi_n = _get_midi_note(cn)
                chord_track.append(mido.Message(
                    'note_off', channel=channel + 1, note=midi_n,
                    velocity=0, time=chord_dur_ticks if cn == chord_notes[-1] else 0
                ))

    mid.save(output_path)
    return output_path


def export_drums_to_midi(
    drum_pattern,
    output_path: str,
    tempo: Optional[int] = None,
    velocity: int = 100,
) -> str:
    """将 DrumPattern 导出为 MIDI 文件 (通道 10 = 鼓组)。

    Args:
        drum_pattern: DrumPattern 对象
        output_path: 输出 .mid 文件路径
        tempo: BPM (None = 使用 pattern.bpm)
        velocity: 默认力度 (0~127)

    Returns:
        输出文件路径

    Raises:
        ImportError: 如果没有安装 mido
    """
    if not _check_mido():
        raise ImportError(
            "MIDI 导出需要 mido 库。请运行: pip install mido"
        )
    import mido

    bpm = tempo or getattr(drum_pattern, 'bpm', 120)
    steps = getattr(drum_pattern, 'steps', 16)
    tracks = getattr(drum_pattern, 'tracks', {})

    ticks_per_beat = 480
    step_ticks = ticks_per_beat // 4  # 16 分音符 = 1/4 拍

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)

    tempo_us = mido.bpm2tempo(bpm)

    # 每个鼓轨对应一个 MIDI track
    for track_name, step_pattern in tracks.items():
        midi_track = mido.MidiTrack()
        mid.tracks.append(midi_track)

        midi_track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))

        # 鼓使用通道 9 (MIDI 标准通道 10)
        drum_note = MIDI_DRUM_MAP.get(track_name.lower(), 60)
        last_time = 0

        for step_idx, is_hit in enumerate(step_pattern):
            if is_hit:
                midi_track.append(mido.Message(
                    'note_on', channel=9, note=drum_note,
                    velocity=velocity, time=last_time
                ))
                midi_track.append(mido.Message(
                    'note_off', channel=9, note=drum_note,
                    velocity=0, time=step_ticks
                ))
                last_time = 0
            else:
                last_time += step_ticks

    mid.save(output_path)
    return output_path


def export_euclidean_drums_to_midi(
    tracks: Dict[str, List[int]],
    output_path: str,
    bpm: int = 120,
    velocity: int = 100,
) -> str:
    """将欧几里得节奏鼓轨导出为 MIDI 文件。

    Args:
        tracks: 鼓轨字典 {"kick": [1,0,0,1,...], "snare": [...], ...}
        output_path: 输出 .mid 文件路径
        bpm: BPM
        velocity: 力度

    Returns:
        输出文件路径
    """
    if not _check_mido():
        raise ImportError(
            "MIDI 导出需要 mido 库。请运行: pip install mido"
        )
    import mido

    ticks_per_beat = 480
    step_ticks = ticks_per_beat // 4
    tempo_us = mido.bpm2tempo(bpm)

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)

    for track_name, step_pattern in tracks.items():
        midi_track = mido.MidiTrack()
        mid.tracks.append(midi_track)
        midi_track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))

        drum_note = MIDI_DRUM_MAP.get(track_name.lower(), 60)
        last_time = 0

        for is_hit in step_pattern:
            if is_hit:
                midi_track.append(mido.Message(
                    'note_on', channel=9, note=drum_note,
                    velocity=velocity, time=last_time
                ))
                midi_track.append(mido.Message(
                    'note_off', channel=9, note=drum_note,
                    velocity=0, time=step_ticks
                ))
                last_time = 0
            else:
                last_time += step_ticks

    mid.save(output_path)
    return output_path


def export_multi_track_to_midi(
    multi_pattern,
    output_path: str,
    tempo: Optional[int] = None,
) -> str:
    """将 MultiTrackPattern 导出为多轨 MIDI 文件。

    Args:
        multi_pattern: MultiTrackPattern 对象
        output_path: 输出 .mid 文件路径
        tempo: BPM

    Returns:
        输出文件路径
    """
    if not _check_mido():
        raise ImportError(
            "MIDI 导出需要 mido 库。请运行: pip install mido"
        )
    import mido

    bpm = tempo or getattr(multi_pattern, 'bpm', 120)
    ticks_per_beat = 480
    tempo_us = mido.bpm2tempo(bpm)

    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)

    # 每个音乐轨一个 MIDI track
    music_tracks = getattr(multi_pattern, 'music_tracks', [])
    for idx, music_track in enumerate(music_tracks):
        channel = idx % 15  # 留出通道 9 给鼓
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))
        track.append(mido.Message('program_change', channel=channel, program=0, time=0))

        notes = getattr(music_track, 'notes', [])
        durations = getattr(music_track, 'durations', [])
        octave_shifts = getattr(music_track, 'octave_shifts', None) or [0] * len(notes)
        beat_dur = 60.0 / bpm

        time_acc = 0
        for note_name, dur_beats, oct_shift in zip(notes, durations, octave_shifts):
            note_ticks = int(dur_beats * ticks_per_beat)
            if note_name is not None:
                base = ''.join(c for c in note_name if c.isalpha() or c == '#')
                octave = int(''.join(c for c in note_name if c.isdigit()))
                note_name_shifted = f"{base}{octave + oct_shift}"
                midi_note = _get_midi_note(note_name_shifted)

                track.append(mido.Message(
                    'note_on', channel=channel, note=midi_note,
                    velocity=80, time=time_acc
                ))
                track.append(mido.Message(
                    'note_off', channel=channel, note=midi_note,
                    velocity=0, time=note_ticks
                ))
                time_acc = 0
            else:
                time_acc += note_ticks

    # 鼓轨
    drum_track = getattr(multi_pattern, 'drum_track', None)
    if drum_track is not None:
        drum_midi_track = mido.MidiTrack()
        mid.tracks.append(drum_midi_track)
        drum_midi_track.append(mido.MetaMessage('set_tempo', tempo=tempo_us, time=0))

        steps = getattr(drum_track, 'steps', 16)
        drum_tracks = getattr(drum_track, 'tracks', {})
        step_ticks = ticks_per_beat // 4

        for track_name, step_pattern in drum_tracks.items():
            drum_note = MIDI_DRUM_MAP.get(track_name.lower(), 60)
            last_time = 0
            for is_hit in step_pattern:
                if is_hit:
                    drum_midi_track.append(mido.Message(
                        'note_on', channel=9, note=drum_note,
                        velocity=100, time=last_time
                    ))
                    drum_midi_track.append(mido.Message(
                        'note_off', channel=9, note=drum_note,
                        velocity=0, time=step_ticks
                    ))
                    last_time = 0
                else:
                    last_time += step_ticks

    mid.save(output_path)
    return output_path
