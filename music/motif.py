"""
主题动机发展系统 — Motif + 作曲变换 + 预设发展链
==================================================

基于传统作曲技法，对一个旋律动机施加标准变换操作，
产生有逻辑关联的衍生素材。这是从"定义旋律"到"发展旋律"的质变。

变换算子:
  - transpose:    移调
  - invert:       倒影（以首音为轴翻转音程方向）
  - retrograde:   逆行（反转时间顺序）
  - augment:      扩展（时值翻倍）
  - diminish:     缩短（时值减半）
  - rhythmic_vary: 节奏变形（保持音高，随机调换时值）
  - fragment:     截取片段
  - sequence:     模进（连续移调）

预设发展链 (DevelopmentPreset):
  classical_development / tension_build / variation_ab / retrograde_variant

用法:
    >>> from bloodmusic.music.motif import Motif, DevelopmentPreset
    >>> m = Motif([("C4", 1.0, 0.7), ("E4", 0.5, 0.6), ("G4", 0.5, 0.8)])
    >>> v = m.invert().transpose(2)
    >>> pat = m.to_pattern("my_motif", 120, "acoustic_grand_piano")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import copy
import random


# ═══════════════════════════════════════════════════════════════════════
# MotifEvent — 动机中的一个音符事件
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MotifEvent:
    """动机中的单个音符事件。

    pitch 可以是:
      - 音符名 "C4", "Eb3"  — 推荐，与 MusicPattern 风格一致
      - 半音值 (int for transpose math)
      - None — 休止符

    内部统一用 semitones(相对于 C0) 做数学运算，
    但公开 API 接受音符名以保持用户友好。
    """
    pitch_name: Optional[str]  # 音符名 ("C4", "Eb3") 或 None(休止)
    duration: float            # 时值 (拍)
    velocity: float            # 力度 (0.0~1.0)

    @property
    def is_rest(self) -> bool:
        return self.pitch_name is None

    def clone(self) -> "MotifEvent":
        return MotifEvent(self.pitch_name, self.duration, self.velocity)

    def __repr__(self):
        if self.is_rest:
            return f"R[{self.duration}]"
        return f"{self.pitch_name}[{self.duration}]"


# ═══════════════════════════════════════════════════════════════════════
# 音符名 ↔ 半音值 转换
# ═══════════════════════════════════════════════════════════════════════

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

def note_to_semitones(note_name: str) -> int:
    """将音符名转为绝对半音值（C0=0）"""
    import re
    # 先转换降号
    letter = note_name.rstrip("0123456789")
    digits = note_name[len(letter):]
    if letter in _FLAT_TO_SHARP:
        note_name = _FLAT_TO_SHARP[letter] + digits
    m = re.match(r'^([A-G]#?)(\d+)$', note_name)
    if not m:
        raise ValueError(f"无效音符名: {note_name}")
    letter, octave = m.groups()
    idx = _NOTE_NAMES.index(letter)
    return idx + int(octave) * 12

def semitones_to_note(semitones: int) -> str:
    """将绝对半音值转为音符名"""
    letter = _NOTE_NAMES[semitones % 12]
    octave = semitones // 12
    return f"{letter}{octave}"


# ═══════════════════════════════════════════════════════════════════════
# Motif — 动机
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Motif:
    """旋律动机 — 一个可变换的音符序列。

    Args:
        events: 动机中的音符事件列表
        name: 动机名称（可选，用于调试）
        root_semitones: 基准音高 (绝对半音值)，用于 invert 的对称轴
    """
    events: List[MotifEvent] = field(default_factory=list)
    name: str = ""
    root_semitones: Optional[int] = None  # invert 轴心

    def __post_init__(self):
        if self.root_semitones is None and self.events:
            # 取第一个非休止音符作为默认轴心
            for ev in self.events:
                if not ev.is_rest:
                    self.root_semitones = note_to_semitones(ev.pitch_name)
                    break

    # ── 工厂方法 ──

    @classmethod
    def from_note_names(cls, notes: List[Optional[str]],
                        durations: List[float],
                        velocities: Optional[List[float]] = None,
                        name: str = "") -> "Motif":
        """从音符名列表创建动机"""
        vels = velocities or [0.7] * len(notes)
        events = [MotifEvent(n, d, v) for n, d, v in zip(notes, durations, vels)]
        return cls(events=events, name=name)

    @classmethod
    def from_music_pattern(cls, pattern, name: str = "") -> "Motif":
        """从 MusicPattern 提取动机"""
        from .pattern import MusicPattern
        velocities = [pattern.volume] * len(pattern.notes)
        return cls.from_note_names(pattern.notes, pattern.durations, velocities, name)

    # ── 转换到 MusicPattern ──

    def to_pattern(self, bpm: int = 120,
                   inst_key: str = "acoustic_grand_piano",
                   loop: bool = True,
                   **overrides):
        """将动机转换为 MusicPattern。

        Args:
            bpm: 速度
            inst_key: 乐器键名（从 INSTRUMENTS 中查找）
            loop: 是否循环
            **overrides: 覆盖 MusicPattern 属性 (volume, env_shape 等)
        """
        from .pattern import MusicPattern
        from .instruments import get_instrument

        notes = [ev.pitch_name for ev in self.events]
        durations = [ev.duration for ev in self.events]

        inst = get_instrument(inst_key)
        pat = inst.make_pattern(
            self.name or "motif_pattern",
            notes, durations, bpm=bpm, loop=loop,
        )
        for k, v in overrides.items():
            if hasattr(pat, k):
                setattr(pat, k, v)
        return pat

    # ── 信息方法 ──

    def __len__(self):
        return len(self.events)

    def total_duration(self) -> float:
        return sum(ev.duration for ev in self.events)

    def note_count(self) -> int:
        return sum(1 for ev in self.events if not ev.is_rest)

    def pitch_range(self) -> Tuple[Optional[int], Optional[int]]:
        """返回 (最低半音值, 最高半音值)"""
        semis = [note_to_semitones(ev.pitch_name)
                 for ev in self.events if not ev.is_rest]
        if not semis:
            return None, None
        return min(semis), max(semis)

    # ═══════════════════════════════════════════════════════
    # 变换算子 (每个返回新的 Motif，不可变风格)
    # ═══════════════════════════════════════════════════════

    def clone(self) -> "Motif":
        """深拷贝"""
        return Motif(
            events=[ev.clone() for ev in self.events],
            name=self.name,
            root_semitones=self.root_semitones,
        )

    def transpose(self, semitones: int) -> "Motif":
        """移调。

        Args:
            semitones: 移调半音数（正=升, 负=降）

        Returns:
            移调后的新 Motif
        """
        new_events = []
        for ev in self.events:
            if ev.is_rest:
                new_events.append(ev.clone())
            else:
                old_semi = note_to_semitones(ev.pitch_name)
                new_name = semitones_to_note(old_semi + semitones)
                new_events.append(MotifEvent(new_name, ev.duration, ev.velocity))
        return Motif(
            events=new_events,
            name=f"{self.name}_T{semitones:+d}",
            root_semitones=(self.root_semitones + semitones
                            if self.root_semitones is not None else None),
        )

    def invert(self, axis_semitones: Optional[int] = None) -> "Motif":
        """倒影 — 以指定轴心翻转音程方向。

        如果原动机是 C4→E4→G4（上行），倒影后变为 C4→Ab3→F3（下行）。

        Args:
            axis_semitones: 对称轴（绝对半音值），默认使用 root_semitones

        Returns:
            倒影后的新 Motif
        """
        axis = axis_semitones if axis_semitones is not None else self.root_semitones
        if axis is None:
            raise ValueError("倒影需要指定 axis_semitones 或确保动机有非休止音符")

        new_events = []
        for ev in self.events:
            if ev.is_rest:
                new_events.append(ev.clone())
            else:
                old_semi = note_to_semitones(ev.pitch_name)
                # 关于轴的镜像: axis - (old - axis) = 2*axis - old
                mirrored = 2 * axis - old_semi
                new_name = semitones_to_note(mirrored)
                new_events.append(MotifEvent(new_name, ev.duration, ev.velocity))
        return Motif(
            events=new_events,
            name=f"{self.name}_invert",
            root_semitones=axis,
        )

    def retrograde(self) -> "Motif":
        """逆行 — 反转时间顺序。

        Returns:
            逆行后的新 Motif
        """
        new_events = [ev.clone() for ev in reversed(self.events)]
        return Motif(
            events=new_events,
            name=f"{self.name}_retro",
            root_semitones=self.root_semitones,
        )

    def augment(self, factor: float = 2.0) -> "Motif":
        """扩展 — 将所有时值乘以 factor。

        Args:
            factor: 时值倍数（>1=扩展, <1=缩短）

        Returns:
            扩展后的新 Motif
        """
        new_events = [
            MotifEvent(ev.pitch_name, ev.duration * factor, ev.velocity)
            for ev in self.events
        ]
        return Motif(
            events=new_events,
            name=f"{self.name}_aug",
            root_semitones=self.root_semitones,
        )

    def diminish(self, factor: float = 0.5) -> "Motif":
        """缩短 — 将所有时值乘以 factor（默认 0.5）。

        等同于 augment(0.5)，语义上更清晰的别名。
        """
        return self.augment(factor)

    def rhythmic_vary(self, seed: int = 0) -> "Motif":
        """节奏变形 — 保持音高顺序，随机调换音符间的时值。

        产生与原始动机节奏不同但音高相同的变体。

        Args:
            seed: 随机种子（可重现）

        Returns:
            节奏变形后的新 Motif
        """
        rng = random.Random(seed)
        durations = [ev.duration for ev in self.events]
        rng.shuffle(durations)

        new_events = [
            MotifEvent(ev.pitch_name, durations[i], ev.velocity)
            for i, ev in enumerate(self.events)
        ]
        return Motif(
            events=new_events,
            name=f"{self.name}_rhyvar",
            root_semitones=self.root_semitones,
        )

    def fragment(self, start: int, end: int) -> "Motif":
        """截取片段。

        Args:
            start: 起始索引（包含）
            end: 结束索引（不含）

        Returns:
            截取的片段
        """
        new_events = [ev.clone() for ev in self.events[start:end]]
        return Motif(
            events=new_events,
            name=f"{self.name}_frag{start}:{end}",
            root_semitones=self.root_semitones,
        )

    def sequence(self, transpositions: List[int]) -> "Motif":
        """模进 — 连续移调，将各次移调结果拼接。

        Args:
            transpositions: 每次的半音偏移量列表

        Returns:
            拼接后的长 Motif
        """
        new_events = []
        for semis in transpositions:
            transposed = self.transpose(semis)
            new_events.extend(transposed.events)
        return Motif(
            events=new_events,
            name=f"{self.name}_seq",
            root_semitones=self.root_semitones,
        )

    def merge_with(self, other: "Motif", offset_ratio: float = 1.0) -> "Motif":
        """将另一个动机追加到末尾，可选八度偏移。

        Args:
            other: 要合并的另一个 Motif
            offset_ratio: 音高偏移比例（如 0.5=升五度, 1.0=升八度）

        Returns:
            合并后的新 Motif
        """
        semitones_offset = int(offset_ratio * 12)
        other_shifted = other.transpose(semitones_offset)
        return Motif(
            events=self.events + other_shifted.events,
            name=f"{self.name}+{other.name}",
            root_semitones=self.root_semitones,
        )

    # ── 调试 ──

    def __repr__(self):
        body = " ".join(str(ev) for ev in self.events)
        return f"Motif({self.name}): [{body}]"

    def to_abc(self) -> str:
        """导出为 ABC 记谱法片段（方便可视化调试）"""
        parts = []
        for ev in self.events:
            if ev.is_rest:
                parts.append(f"z{ev.duration}")
            else:
                parts.append(f"{ev.pitch_name}{ev.duration}")
        return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# DevelopmentPreset — 预置发展链
# ═══════════════════════════════════════════════════════════════════════

class DevelopmentPreset:
    """预设的主题发展策略 — 对动机按顺序施加一系列变换。

    用法:
        >>> motif = Motif.from_note_names(["C4","E4","G4","C5"], [1,1,1,1])
        >>> developed = DevelopmentPreset.classical_development(motif)
        >>> pattern = developed.to_pattern(120, "violin")
    """

    @staticmethod
    def classical_development(motif: Motif) -> Motif:
        """古典奏鸣曲式发展：片段→倒影→模进→扩展"""
        return (motif
                .fragment(0, min(len(motif), 4))
                .invert()
                .sequence([0, 5, 7])
                .augment(2.0))

    @staticmethod
    def tension_build(motif: Motif) -> Motif:
        """紧张递进：片段→节奏变形→连续半音上移→缩短"""
        return (motif
                .fragment(0, min(len(motif), 4))
                .rhythmic_vary(seed=42)
                .sequence([0, 1, 2, 3, 5])
                .diminish(0.5))

    @staticmethod
    def variation_ab(motif: Motif) -> Tuple[Motif, Motif]:
        """A-B 变奏对：A=原形, B=逆行+倒影+移调"""
        a = motif.clone()
        b = motif.retrograde().invert().transpose(-3)
        return a, b

    @staticmethod
    def retrograde_variant(motif: Motif) -> Motif:
        """逆行变奏：逆行→倒影→合并原形"""
        rev = motif.retrograde().invert()
        return motif.merge_with(rev)

    @staticmethod
    def call_and_response(motif: Motif) -> Motif:
        """呼应式：原形(call) + 倒影移调(response)"""
        response = motif.invert().transpose(7)  # 五度上移
        return motif.merge_with(response)

    @staticmethod
    def fragmentation_build(motif: Motif) -> Motif:
        """碎片化递进：取前2音→模进→缩短→再模进"""
        head = motif.fragment(0, min(2, len(motif)))
        return (head
                .sequence([0, 2, 4, 5])
                .diminish(0.5)
                .sequence([0, 1, 2, 3]))

    # ── 所有预置列表 ──

    @staticmethod
    def list_presets() -> List[str]:
        return [
            "classical_development",
            "tension_build",
            "variation_ab",
            "retrograde_variant",
            "call_and_response",
            "fragmentation_build",
        ]

    @staticmethod
    def apply(preset_name: str, motif: Motif):
        """按名称应用预置发展策略"""
        mapping = {
            "classical_development": DevelopmentPreset.classical_development,
            "tension_build": DevelopmentPreset.tension_build,
            "variation_ab": DevelopmentPreset.variation_ab,
            "retrograde_variant": DevelopmentPreset.retrograde_variant,
            "call_and_response": DevelopmentPreset.call_and_response,
            "fragmentation_build": DevelopmentPreset.fragmentation_build,
        }
        if preset_name not in mapping:
            raise ValueError(f"未知预置 '{preset_name}'。可选: {DevelopmentPreset.list_presets()}")
        return mapping[preset_name](motif)
