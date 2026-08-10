"""琶音器 —— 将和弦拆解为琶音序列"""

import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple


class ArpMode(Enum):
    """琶音模式"""
    UP = "up"
    DOWN = "down"
    UP_DOWN = "up_down"
    RANDOM = "random"


@dataclass
class Arpeggiator:
    """琶音器参数"""
    mode: ArpMode = ArpMode.UP
    octaves: int = 1           # 扩展八度数
    gate: float = 0.8          # 门限 (0~1)，控制音符持续时间比例


def generate_arpeggio(
    arp: Arpeggiator,
    notes: List[str],
    bpm: int = 120,
    durations: List[float] | None = None,
) -> List[Tuple[str, float]]:
    """生成琶音序列。

    Args:
        arp: 琶音器参数
        notes: 和弦音符列表，如 ["C4", "E4", "G4"]
        bpm: 速度
        durations: 每个音符的时值（拍），None = 均等
    Returns:
        [(note_name, duration_in_seconds), ...]
    """
    from ..core.note_utils import note_to_freq

    # 构建音符序列（含八度扩展）
    arp_notes = list(notes)
    for oct_ext in range(1, arp.octaves):
        for n in notes:
            # 提取音名和八度
            base = n.rstrip('0123456789')
            oct_str = n[len(base):]
            if oct_str.isdigit():
                new_oct = int(oct_str) + oct_ext
                arp_notes.append(f"{base}{new_oct}")
            else:
                arp_notes.append(n)

    # 排序音符（按频率）
    arp_notes.sort(key=lambda n: note_to_freq(n))

    # 根据模式排列
    if arp.mode == ArpMode.UP:
        sequence = arp_notes
    elif arp.mode == ArpMode.DOWN:
        sequence = list(reversed(arp_notes))
    elif arp.mode == ArpMode.UP_DOWN:
        sequence = arp_notes + list(reversed(arp_notes[1:-1]))
    elif arp.mode == ArpMode.RANDOM:
        rng = np.random.default_rng()
        sequence = list(rng.choice(arp_notes, size=len(arp_notes), replace=False))
    else:
        sequence = arp_notes

    # 分配时值
    beat_dur = 60.0 / bpm
    result = []
    for i, note in enumerate(sequence):
        if durations is not None and i < len(durations):
            dur = durations[i] * beat_dur * arp.gate
        else:
            dur = 0.5 * beat_dur * arp.gate
        result.append((note, dur))

    return result
