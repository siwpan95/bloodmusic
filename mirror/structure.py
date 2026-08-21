# -*- coding: utf-8 -*-
"""
structure.py —— 曲式模板（镜像 musickit remix/templates/structures.json）

每个模板 = 若干段落 (name, bars, intensity)；渲染时按段落决定各层
（骨架/点缀）的进出与强度，实现 intro→drop→outro 的曲式动态。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    name: str        # intro / build / drop / verse / outro / a / b / loop
    bars: int        # 小节数
    intensity: float = 0.7   # 0-1：鼓密度/音量/点缀活跃度
    skeleton_only: bool = False  # True = 只留骨架层（鼓/贝斯/旋律轨）
    break_bars: int = 0     # 段落结尾留白小节数（riser 过渡空间）


def _sec(name: str, bars: int, intensity: float, skeleton_only: bool = False,
         break_bars: int = 0) -> Section:
    return Section(name, bars, intensity, skeleton_only, break_bars)


STRUCTURES: dict[str, list[Section]] = {
    "classic_drop": [
        _sec("intro", 2, 0.5, skeleton_only=True),
        _sec("build", 2, 0.75, break_bars=1),
        _sec("drop", 4, 1.0),
        _sec("outro", 2, 0.4, skeleton_only=True),
    ],
    "intro_verse_drop_outro": [
        _sec("intro", 2, 0.45, skeleton_only=True),
        _sec("verse", 4, 0.7),
        _sec("drop", 4, 1.0, break_bars=1),
        _sec("outro", 2, 0.35, skeleton_only=True),
    ],
    "verse_chorus": [
        _sec("verse", 4, 0.6),
        _sec("chorus", 4, 0.9, break_bars=1),
        _sec("verse", 4, 0.65),
        _sec("chorus", 4, 0.95),
    ],
    "ab": [
        _sec("a", 4, 0.7),
        _sec("b", 4, 0.9),
        _sec("a", 4, 0.75),
    ],
    "loop": [
        _sec("loop", 4, 0.8),
    ],
}


def resolve_structure(name: str | None, bars: int) -> list[Section]:
    """按名字取模板；bars 给定时按比例缩放到总小节数（loop 除外）。"""
    if name and name not in STRUCTURES:
        raise KeyError(f"未知曲式 '{name}'。可用: {list(STRUCTURES)}")
    template = list(STRUCTURES[name or "classic_drop"])

    total = sum(s.bars for s in template)
    if name == "loop" or bars is None or bars <= 0 or total == bars:
        return template

    # 按比例缩放（保底每段 1 小节），余数并入 drop 段
    scaled: list[Section] = []
    assigned = 0
    for s in template:
        n = max(1, round(s.bars * bars / total))
        scaled.append(Section(s.name, n, s.intensity, s.skeleton_only, s.break_bars))
        assigned += n
    # 调整误差：找最大段补差
    diff = bars - assigned
    if diff:
        biggest = max(range(len(scaled)), key=lambda i: scaled[i].bars)
        scaled[biggest] = Section(
            scaled[biggest].name,
            scaled[biggest].bars + diff,
            scaled[biggest].intensity,
            scaled[biggest].skeleton_only,
            scaled[biggest].break_bars,
        )
    return scaled


def list_structures() -> list[str]:
    return list(STRUCTURES)
