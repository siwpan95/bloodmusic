"""音阶/调式系统 —— Scale 类 + 预定义音阶"""

from dataclasses import dataclass
from typing import List


# 预定义音阶间隔（半音数）
SCALE_INTERVALS = {
    # 自然调式
    "major":          [0, 2, 4, 5, 7, 9, 11],
    "minor":          [0, 2, 3, 5, 7, 8, 10],
    "dorian":         [0, 2, 3, 5, 7, 9, 10],
    "phrygian":       [0, 1, 3, 5, 7, 8, 10],
    "lydian":         [0, 2, 4, 6, 7, 9, 11],
    "mixolydian":     [0, 2, 4, 5, 7, 9, 10],
    "locrian":        [0, 1, 3, 5, 6, 8, 10],
    # 五声/蓝调
    "pentatonic":     [0, 2, 4, 7, 9],
    "pentatonic_minor":[0, 3, 5, 7, 10],
    "blues":          [0, 3, 5, 6, 7, 10],
    "blues_major":    [0, 2, 3, 4, 7, 9],
    # 和声/旋律
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor":  [0, 2, 3, 5, 7, 9, 11],
    "harmonic_major": [0, 2, 4, 5, 7, 8, 11],
    # 对称音阶
    "whole_tone":     [0, 2, 4, 6, 8, 10],
    "diminished":     [0, 2, 3, 5, 6, 8, 9, 11],
    "augmented":      [0, 3, 4, 7, 8, 11],
    "chromatic":      list(range(12)),
    # 民族/世界
    "japanese":       [0, 1, 5, 7, 8],       # 日本音阶 (In Sen)
    "chinese":        [0, 2, 4, 7, 9],       # 中国五声音阶
    "indian":         [0, 2, 4, 5, 7, 9, 11], # 印度 Bilawal
    "flamenco":       [0, 1, 4, 5, 7, 8, 10], # 弗拉明戈
    # 爵士
    "bebop_dominant": [0, 2, 4, 5, 7, 9, 10, 11],
    "bebop_major":    [0, 2, 4, 5, 7, 8, 9, 11],
    "altered":        [0, 1, 3, 4, 6, 8, 10],  # 超级 Locrian
}

# 功能和声进行模板 (级数表示)
CHORD_PROGRESSIONS = {
    # 经典进行
    "I-IV-V-I":        [1, 4, 5, 1],
    "I-V-vi-IV":       [1, 5, 6, 4],
    "ii-V-I":          [2, 5, 1],
    "I-vi-IV-V":       [1, 6, 4, 5],
    "vi-IV-I-V":       [6, 4, 1, 5],
    # 爵士进行
    "jazz_ii-V-I":     [2, 5, 1, 1],
    "jazz_turnaround": [1, 6, 2, 5],
    "jazz_blues":      [1, 4, 1, 1, 4, 4, 1, 1, 2, 5, 1, 2],
    # 小调进行
    "minor_i-iv-v":    [1, 4, 5, 1],
    "minor_i-VI-III-VII":[1, 6, 3, 7],
    # 进行曲/史诗
    "epic":            [1, 5, 6, 4],
    "heroic":          [1, 4, 6, 5],
    # 流行
    "pop_verse":       [1, 6, 4, 5],
    "pop_chorus":      [4, 5, 1, 6],
    # 氛围/新世纪
    "ambient":         [1, 4, 1, 5],
    "dreamy":          [1, 3, 4, 5],
    # 民谣
    "folk":            [1, 4, 1, 5],
    "folk_minor":      [1, 7, 6, 5],
    # 电子
    "edm_build":       [1, 5, 6, 4],
    "edm_drop":        [6, 4, 1, 5],
}

# 音名映射
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class Scale:
    """音阶/调式

    Usage:
        scale = Scale("C", "dorian", octave=4)
        notes = scale.get_notes()      # ["C4", "D4", "Eb4", "F4", "G4", "A4", "Bb4"]
        freqs = scale.get_freqs()      # [261.63, 293.66, ...]
        chord = scale.get_chord(1)     # ["C4", "Eb4", "G4"] (i 和弦)
    """
    root: str = "C"
    scale_type: str = "major"
    octave: int = 4

    @property
    def intervals(self) -> List[int]:
        """获取音阶间隔列表"""
        return SCALE_INTERVALS.get(self.scale_type, SCALE_INTERVALS["major"])

    def _root_semitone(self) -> int:
        """根音的半音偏移"""
        idx = _NOTE_NAMES.index(self.root) if self.root in _NOTE_NAMES else 0
        return idx

    def get_notes(self) -> List[str]:
        """获取音阶内所有音符名"""
        root_idx = self._root_semitone()
        notes = []
        for interval in self.intervals:
            semitone = (root_idx + interval) % 12
            note_name = _NOTE_NAMES[semitone]
            oct_shift = (root_idx + interval) // 12
            notes.append(f"{note_name}{self.octave + oct_shift}")
        return notes

    def get_freqs(self) -> List[float]:
        """获取音阶内所有音符频率"""
        from ..core.note_utils import note_to_freq
        return [note_to_freq(n) for n in self.get_notes()]

    def get_chord(self, degree: int, quality: str = "triad") -> List[str]:
        """获取指定级数的和弦。

        Args:
            degree: 级数 (1=I, 2=II, ..., 7=VII)
            quality: "triad" (三和弦) 或 "seventh" (七和弦)
        Returns:
            和弦音符列表
        """
        notes = self.get_notes()
        degree_idx = (degree - 1) % len(notes)

        if quality == "seventh":
            indices = [degree_idx, (degree_idx + 2) % len(notes),
                       (degree_idx + 4) % len(notes), (degree_idx + 6) % len(notes)]
        else:
            indices = [degree_idx, (degree_idx + 2) % len(notes),
                       (degree_idx + 4) % len(notes)]

        return [notes[i] for i in indices]

    def get_progression(
        self,
        name: str = "I-IV-V-I",
        quality: str = "triad",
        bars_per_chord: int = 1,
    ) -> List[List[str]]:
        """根据预设名称生成和弦进行。

        Args:
            name: 进行名称 (如 "I-V-vi-IV", "jazz_ii-V-I")
            quality: "triad" 或 "seventh"
            bars_per_chord: 每个和弦占多少小节

        Returns:
            和弦列表，每个元素是一个和弦的音符列表
        """
        degrees = CHORD_PROGRESSIONS.get(name, CHORD_PROGRESSIONS["I-IV-V-I"])
        chords = []
        for d in degrees:
            chord = self.get_chord(d, quality)
            for _ in range(bars_per_chord):
                chords.append(chord)
        return chords

    def get_progression_names(self) -> List[str]:
        """列出所有可用的和弦进行名称"""
        return list(CHORD_PROGRESSIONS.keys())

    def get_chord_voicings(
        self, degree: int, inversion: int = 0, spread: int = 0
    ) -> List[str]:
        """获取和弦的特定排列（转位 + 八度展开）。

        Args:
            degree: 级数
            inversion: 转位 (0=原位, 1=第一转位, 2=第二转位)
            spread: 八度偏移 (0=紧凑, 1=略展开)
        Returns:
            和弦音符列表（已转位）
        """
        notes = self.get_chord(degree)
        if len(notes) < 3:
            return notes

        # 转位: 将前 inversion 个音符提升八度
        for i in range(inversion):
            note = notes[i]
            name = note[:-1]
            octave = int(note[-1]) + 1
            notes.append(f"{name}{octave}")

        voiced = notes[inversion:inversion + len(notes) - inversion]
        if spread > 0:
            # 每隔一个音提升八度
            voiced = [
                f"{n[:-1]}{int(n[-1]) + (spread if idx % 2 == 0 else 0)}"
                for idx, n in enumerate(voiced)
            ]
        return voiced


def list_scales() -> List[str]:
    """列出所有可用音阶"""
    return sorted(SCALE_INTERVALS.keys())


def list_progressions() -> List[str]:
    """列出所有可用和弦进行"""
    return sorted(CHORD_PROGRESSIONS.keys())
