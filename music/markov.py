"""
马尔可夫链旋律生成器 — 学习风格并生成旋律变奏
===============================================

基于指导第 5.8.1 节：使用马尔可夫链从现有旋律中学习音符转换概率，
生成风格一致但不同的旋律变奏。

核心概念:
- 训练: 从 MIDI/音符序列中统计转换概率矩阵
- 生成: 从起始音符出发，按概率矩阵随机游走
- 控制: 温度参数调节随机性、长度、节奏模式
"""

from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union
import random
import math


# ============================================================
# 数据结构
# ============================================================

@dataclass
class MelodyNote:
    """单个旋律音符"""
    pitch: str          # 音名 eg "C4", "Eb3"
    duration: float     # 时值 (拍数)
    velocity: int = 80  # 力度 (0-127)
    rest: bool = False  # 是否为休止符

    def midi(self) -> int:
        """音名转 MIDI 编号"""
        from bloodmusic.core.note_utils import note_to_freq, freq_to_midi
        if self.rest:
            return 0
        return freq_to_midi(note_to_freq(self.pitch))

    def __repr__(self):
        return f"{"R" if self.rest else self.pitch}({self.duration})"


@dataclass
class Melody:
    """旋律序列"""
    notes: List[MelodyNote] = field(default_factory=list)
    name: str = ""
    bpm: int = 120
    scale: str = "minor"
    root: str = "C"

    def total_duration(self) -> float:
        return sum(n.duration for n in self.notes)

    def to_pitch_sequence(self) -> List[str]:
        return ["R" if n.rest else n.pitch for n in self.notes]

    def to_duration_sequence(self) -> List[float]:
        return [n.duration for n in self.notes]

    def __len__(self):
        return len(self.notes)

    def __repr__(self):
        return f"Melody({self.name}, {len(self.notes)} notes)"


# ============================================================
# 马尔可夫链核心
# ============================================================

class MarkovChain:
    """一阶马尔可夫链 — 音符到音符的概率模型"""

    def __init__(self, order: int = 1):
        """
        order: 马尔可夫阶数
          1 = 只看前一音符
          2 = 看前两个音符的上下文
        """
        self.order = order
        # transitions[context_tuple] = Counter{next_note: count}
        self._transitions: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)
        self._all_notes: Set[str] = set()
        self._trained: bool = False

    def train(self, sequences: List[List[str]]):
        """
        训练模型。
        sequences: 音名序列列表 (每个序列是一条旋律)
        """
        for seq in sequences:
            if len(seq) <= self.order:
                continue
            self._all_notes.update(seq)
            for i in range(len(seq) - self.order):
                context = tuple(seq[i:i + self.order])
                next_note = seq[i + self.order]
                self._transitions[context][next_note] += 1
        self._trained = True

    def train_from_melodies(self, melodies: List[Melody]):
        """从 Melody 对象列表训练"""
        sequences = [m.to_pitch_sequence() for m in melodies]
        self.train(sequences)

    def next_note(
        self,
        context: Tuple[str, ...],
        temperature: float = 1.0,
        avoid_repeat: int = 0,
        recent: Optional[List[str]] = None,
    ) -> str:
        """
        从上下文中采样下一个音符。

        temperature: 随机度 (0=最确定, >1=更随机)
        avoid_repeat: 避免重复前 N 个音符 (0=不限制)
        recent: 最近已播放的音符列表
        """
        counts = self._transitions.get(context)
        if not counts:
            # 回退到随机选择
            return random.choice(list(self._all_notes)) if self._all_notes else "C4"

        # 构建候选并排除近期重复
        candidates = dict(counts)
        if avoid_repeat > 0 and recent:
            recent_set = set(recent[-avoid_repeat:])
            candidates = {k: v for k, v in candidates.items() if k not in recent_set}
            if not candidates:
                candidates = dict(counts)

        # 温度调节
        if temperature != 1.0:
            items = list(candidates.items())
            weights = [c ** (1.0 / max(temperature, 0.01)) for _, c in items]
            total = sum(weights)
            if total == 0:
                return random.choice(list(candidates.keys()))
            # 加权随机采样
            r = random.random() * total
            cumsum = 0
            for (note, _), w in zip(items, weights):
                cumsum += w
                if r <= cumsum:
                    return note
            return items[-1][0]

        # 标准加权随机采样
        items = list(candidates.items())
        total = sum(candidates.values())
        r = random.random() * total
        cumsum = 0
        for note, count in items:
            cumsum += count
            if r <= cumsum:
                return note
        return items[-1][0]

    def probability(self, context: Tuple[str, ...], next_note: str) -> float:
        """查询转移概率 P(next_note | context)"""
        counts = self._transitions.get(context)
        if not counts:
            return 0.0
        total = sum(counts.values())
        return counts.get(next_note, 0) / total if total > 0 else 0.0

    def transition_matrix(self) -> Dict[str, Dict[str, float]]:
        """导出完整转移概率矩阵（仅一阶时有效）"""
        if self.order != 1:
            raise ValueError("Transition matrix only available for order=1")
        result = {}
        for (ctx,), counts in self._transitions.items():
            total = sum(counts.values())
            result[ctx] = {note: cnt / total for note, cnt in counts.items()}
        return result

    @property
    def trained(self) -> bool:
        return self._trained

    @property
    def vocabulary(self) -> Set[str]:
        return self._all_notes


# ============================================================
# 旋律生成器
# ============================================================

@dataclass
class MelodyGeneratorConfig:
    """生成器配置"""
    # 马尔可夫链
    markov_order: int = 2
    temperature: float = 1.0           # 0.5=保守, 1.0=正常, 2.0=随机
    avoid_repeat: int = 2              # 避免重复前 N 个音符

    # 旋律结构
    target_bars: int = 8               # 目标小节数
    beats_per_bar: int = 4             # 每小节拍数
    note_density: float = 2.0          # 每拍平均音符数

    # 节奏模式
    duration_weights: Dict[float, float] = field(default_factory=lambda: {
        0.25: 0.15,   # 十六分
        0.5: 0.35,    # 八分
        1.0: 0.30,    # 四分
        2.0: 0.15,    # 二分
        4.0: 0.05,    # 全音符
    })

    # 休止符
    rest_probability: float = 0.05     # 每个音符后出现休止符的概率

    # 音域约束
    min_octave: int = 3
    max_octave: int = 5

    # 音阶约束 (如果指定，只生成音阶内的音高)
    scale_constraint: Optional[List[int]] = None  # 半音间隔列表


class MelodyGenerator:
    """
    基于马尔可夫链的旋律生成器

    用法:
        # 训练
        chain = MarkovChain(order=2)
        chain.train_from_melodies(training_melodies)

        # 生成
        gen = MelodyGenerator(chain)
        melody = gen.generate(start_note="C4", bars=8)
    """

    def __init__(
        self,
        chain: MarkovChain,
        config: Optional[MelodyGeneratorConfig] = None,
    ):
        self.chain = chain
        self.config = config or MelodyGeneratorConfig()

    def generate(
        self,
        start_note: str = "C4",
        bars: Optional[int] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> Melody:
        """
        生成旋律。

        start_note: 起始音名
        bars: 小节数 (覆盖配置)
        temperature: 温度 (覆盖配置)
        seed: 随机种子
        """
        if seed is not None:
            random.seed(seed)

        cfg = self.config
        n_bars = bars or cfg.target_bars
        temp = temperature if temperature is not None else cfg.temperature
        total_beats = n_bars * cfg.beats_per_bar
        target_notes = int(total_beats * cfg.note_density)

        recent: List[str] = []
        notes: List[MelodyNote] = []
        current_pitch = start_note
        total_dur = 0.0

        for _ in range(target_notes):
            if total_dur >= total_beats:
                break

            # 采样时值
            duration = self._sample_duration()

            # 是否有休止符
            if random.random() < cfg.rest_probability:
                notes.append(MelodyNote(
                    pitch="R", duration=duration, rest=True,
                ))
                total_dur += duration
                recent.append("R")
                continue

            # 选择下一个音高
            if len(recent) >= cfg.markov_order:
                context = tuple(recent[-cfg.markov_order:])
            else:
                # 不足 order 时用单音符填充
                padding = (current_pitch,) * (cfg.markov_order - len(recent))
                context = tuple(recent[-len(recent):]) + padding if recent else (current_pitch,) * cfg.markov_order

            next_pitch = self.chain.next_note(
                context,
                temperature=temp,
                avoid_repeat=cfg.avoid_repeat,
                recent=recent,
            )

            # 音域约束 — 如果超出范围，尝试调整八度
            next_pitch = self._apply_octave_constraint(
                next_pitch, current_pitch,
                cfg.min_octave, cfg.max_octave,
            )

            # 音阶约束 — 调整到音阶内最接近的音高
            if cfg.scale_constraint:
                next_pitch = self._apply_scale_constraint(
                    next_pitch, cfg.scale_constraint,
                )

            notes.append(MelodyNote(pitch=next_pitch, duration=duration))
            recent.append(next_pitch)
            if len(recent) > 20:
                recent = recent[-20:]
            current_pitch = next_pitch
            total_dur += duration

        return Melody(
            notes=notes,
            name="generated",
            bpm=120,
            scale="minor",
            root="C",
        )

    def generate_variations(
        self,
        n: int = 4,
        start_note: str = "C4",
        bars: int = 8,
        temperature_range: Tuple[float, float] = (0.7, 1.5),
    ) -> List[Melody]:
        """生成多个变奏（不同温度和种子）"""
        variations = []
        for i in range(n):
            temp = temperature_range[0] + (temperature_range[1] - temperature_range[0]) * i / max(n - 1, 1)
            m = self.generate(start_note=start_note, bars=bars, temperature=temp, seed=42 + i)
            m.name = f"variation_{i + 1}"
            variations.append(m)
        return variations

    def _sample_duration(self) -> float:
        """按权重采样时值"""
        items = list(self.config.duration_weights.items())
        weights = [w for _, w in items]
        total = sum(weights)
        r = random.random() * total
        cumsum = 0
        for (dur, w) in items:
            cumsum += w
            if r <= cumsum:
                return dur
        return items[-1][0]

    def _apply_octave_constraint(
        self,
        pitch: str,
        prev_pitch: str,
        min_octave: int,
        max_octave: int,
    ) -> str:
        """确保音高在指定八度范围内"""
        from bloodmusic.core.note_utils import note_to_freq, freq_to_midi

        try:
            midi = freq_to_midi(note_to_freq(pitch))
        except (KeyError, ValueError):
            return pitch
        octave = midi // 12 - 1
        if octave < min_octave:
            midi += (min_octave - octave) * 12
        elif octave > max_octave:
            midi -= (octave - max_octave) * 12
        # 简单 MIDI→音名 (近似)
        name = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_name = name[midi % 12]
        new_octave = midi // 12 - 1
        return f"{note_name}{new_octave}"

    def _apply_scale_constraint(
        self,
        pitch: str,
        scale_intervals: List[int],
    ) -> str:
        """将音高调整到音阶内最接近的合法音高"""
        from bloodmusic.core.note_utils import note_to_freq, freq_to_midi

        try:
            midi = freq_to_midi(note_to_freq(pitch))
        except (KeyError, ValueError):
            return pitch

        # 根音
        root_midi = midi - (midi % 12)
        degree = (midi - root_midi) % 12

        # 找最接近的音阶音
        # scale_intervals 是累计半音 [0,2,4,5,7,9,11] for major
        if degree in scale_intervals:
            return pitch  # 已在音阶内

        # 找到最近的音阶音
        best = min(scale_intervals, key=lambda x: abs(x - degree))
        adjusted = root_midi + best + (midi // 12) * 12

        name = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        note_name = name[adjusted % 12]
        octave = adjusted // 12 - 1
        return f"{note_name}{octave}"


# ============================================================
# 训练数据加载
# ============================================================

def melody_from_note_string(note_str: str, bpm: int = 120, name: str = "") -> Melody:
    """
    从简谱字符串解析旋律。
    格式:  "C4,0.5; D4,0.5; E4,1.0; R,0.25; G4,0.5"
    """
    notes = []
    for part in note_str.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            pitch_str, dur_str = part.split(",")
            pitch = pitch_str.strip()
            dur = float(dur_str.strip())
            notes.append(MelodyNote(
                pitch=pitch, duration=dur,
                rest=(pitch.upper() == "R"),
            ))
        except (ValueError, IndexError):
            continue
    return Melody(notes=notes, name=name, bpm=bpm)


def melody_from_music_pattern(pattern) -> Melody:
    """
    从 MusicPattern 对象提取旋律（用于训练）。
    """
    from bloodmusic.core.note_utils import NOTES

    notes = []
    for note_name, duration in zip(pattern.notes, pattern.durations):
        octave_shifted = f"{note_name}{pattern.base_octave if hasattr(pattern, 'base_octave') else 4}"
        try:
            _ = NOTES.get(note_name + "4")  # 验证
        except KeyError:
            continue
        notes.append(MelodyNote(pitch=octave_shifted, duration=duration))
    return Melody(notes=notes, name=pattern.name if hasattr(pattern, 'name') else "",
                  bpm=pattern.bpm)


# ============================================================
# 预置训练旋律
# ============================================================

SAMPLE_MELODIES = [
    # 简单的 C 小调旋律
    "C4,0.5; Eb4,0.5; G4,1.0; Bb4,0.5; C5,0.5; Bb4,0.5; G4,1.0; Eb4,0.5; C4,0.5",
    # G 弗里几亚战斗旋律
    "G4,0.25; Ab4,0.25; G4,0.5; F4,0.5; Eb4,1.0; D4,0.5; Eb4,0.5; F4,0.25; G4,0.25",
    # D 多利亚探索旋律
    "D4,1.0; E4,0.5; F4,0.5; G4,1.0; A4,0.5; G4,1.0; E4,1.0; D4,0.5",
    # 胜利旋律 (C 大调)
    "C4,0.5; E4,0.5; G4,1.0; C5,1.0; G4,0.5; E4,0.5; C5,2.0",
]


def create_default_chain(seed: int = 42) -> MarkovChain:
    """用预置旋律创建默认训练好的马尔可夫链"""
    melodies = [melody_from_note_string(s, name=f"sample_{i}")
                for i, s in enumerate(SAMPLE_MELODIES)]
    chain = MarkovChain(order=2)
    chain.train_from_melodies(melodies)
    return chain
