"""
欧几里得节奏生成器 —— Björklund 算法 + 节奏实用工具
=====================================================

基于 Godfried Toussaint 2005 年论文 "The Euclidean Algorithm Generates
Traditional Musical Rhythms" 的实现。

欧几里得节奏将 k 个脉冲均匀分布在 n 个步进中，产生的节奏模式覆盖了大量世界音乐风格:

    E(3, 8)   → Tresillo (古巴 Son Clave)
    E(5, 8)   → Cinquillo
    E(5, 12)  → 非洲 Bell Pattern
    E(7, 12)  → 保加利亚舞曲
    E(7, 16)  → Acid Shuffle
    E(9, 16)  → 密集 Techno Groove
    E(11, 16) → 极繁 Techno
    E(13, 16) → 接近填满的变体

使用方式:
    >>> from bloodmusic.music.euclidean import euclidean_rhythm, EUCLIDEAN_PRESETS
    >>> pattern = euclidean_rhythm(3, 8)  # [1, 0, 0, 1, 0, 0, 1, 0]
    >>> pattern = euclidean_rhythm(7, 16, rotate=4)  # 旋转 4 位
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass


def euclidean_rhythm(k: int, n: int, rotate: int = 0) -> List[int]:
    """使用 Bjorklund 算法生成欧几里得节奏模式。

    将 k 个脉冲尽可能均匀地分布在 n 个步进中。
    基于 Godfried Toussaint 2005 年论文 "The Euclidean Algorithm
    Generates Traditional Musical Rhythms"。

    欧几里得节奏覆盖了大量世界音乐风格:
        E(3, 8)   → Tresillo (古巴 Son Clave)
        E(5, 8)   → Cinquillo
        E(7, 16)  → Acid Shuffle

    Args:
        k: 脉冲数 (1~n)
        n: 总步进数
        rotate: 旋转偏移量 (0~n-1)

    Returns:
        长度为 n 的列表，1=脉冲，0=休止

    Raises:
        ValueError: k > n 或 k < 0 或 n <= 0

    Examples:
        >>> euclidean_rhythm(3, 8)
        [1, 0, 0, 1, 0, 0, 1, 0]
        >>> euclidean_rhythm(5, 8)
        [1, 0, 1, 1, 0, 1, 1, 0]
    """
    if n <= 0:
        raise ValueError(f"n 必须 > 0，收到 {n}")
    if k < 0:
        raise ValueError(f"k 必须 >= 0，收到 {k}")
    if k > n:
        raise ValueError(f"k ({k}) 不能大于 n ({n})")

    # 边界情况
    if k == 0:
        result = [0] * n
    elif k == n:
        result = [1] * n
    else:
        result = _bjorklund(k, n)

    # 旋转
    if rotate:
        rotate = rotate % n
        result = result[-rotate:] + result[:-rotate]

    return result


def _bjorklund(pulses: int, steps: int) -> List[int]:
    """Bjorklund 算法的递归实现。

    参考: https://github.com/brianhouse/bjorklund
    """
    pattern: List[int] = []
    counts: List[int] = []
    remainders: List[int] = []

    divisor = steps - pulses
    remainders.append(pulses)
    level = 0

    while True:
        counts.append(divisor // remainders[level])
        remainders.append(divisor % remainders[level])
        divisor = remainders[level]
        level += 1
        if remainders[level] <= 1:
            break

    counts.append(divisor)

    def _build(lev: int) -> None:
        if lev == -1:
            pattern.append(0)
        elif lev == -2:
            pattern.append(1)
        else:
            for _ in range(counts[lev]):
                _build(lev - 1)
            if remainders[lev] != 0:
                _build(lev - 2)

    _build(level)
    # 旋转使模式从第一个脉冲开始
    first_one = pattern.index(1)
    return pattern[first_one:] + pattern[:first_one]


def euclidean_phases(k: int, n: int, rotate: int = 0) -> List[float]:
    """生成欧几里得节奏的相位位置（0~1 之间的浮点数）。

    用于精确控制鼓点 hit 的时间位置。

    Args:
        k: 脉冲数
        n: 总步进数
        rotate: 旋转偏移量

    Returns:
        长度为 k 的相位位置列表（归一化到 0~1）

    Example:
        >>> euclidean_phases(3, 8)
        [0.0, 0.375, 0.625]
    """
    pattern = euclidean_rhythm(k, n, rotate)
    return [i / n for i, x in enumerate(pattern) if x == 1]


def generate_euclidean_drum_pattern(
    kick_pulses: int = 4,
    snare_pulses: int = 4,
    hihat_pulses: int = 8,
    steps: int = 16,
    kick_rotate: int = 0,
    snare_rotate: int = 4,
    hihat_rotate: int = 0,
) -> Dict[str, List[int]]:
    """便捷函数：为三种核心鼓生成欧几里得节奏模式。

    Args:
        kick_pulses: 底鼓脉冲数
        snare_pulses: 军鼓脉冲数
        snare_rotate: 军鼓旋转 (默认 4 = 2-4 拍)
        hihat_pulses: 踩镲脉冲数
        steps: 总步进数 (通常 16)
        kick_rotate: 底鼓旋转
        hihat_rotate: 踩镲旋转

    Returns:
        字典 {"kick": [...], "snare": [...], "hihat": [...]}

    Example:
        >>> tracks = generate_euclidean_drum_pattern(4, 4, 8, 16)
        >>> tracks["kick"]
        [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    """
    return {
        "kick":  euclidean_rhythm(kick_pulses,  steps, kick_rotate),
        "snare": euclidean_rhythm(snare_pulses, steps, snare_rotate),
        "hihat": euclidean_rhythm(hihat_pulses, steps, hihat_rotate),
    }


# ══════════════════════════════════════════════════════════════
# 预置欧几里得节奏库
# ══════════════════════════════════════════════════════════════

@dataclass
class EuclideanPreset:
    """欧几里得节奏预置"""
    name: str
    description: str
    kick: Tuple[int, int, int]   # (pulses, steps, rotate)
    snare: Tuple[int, int, int]
    hihat: Tuple[int, int, int]
    bpm_range: Tuple[int, int] = (100, 140)


EUCLIDEAN_PRESETS: Dict[str, EuclideanPreset] = {
    # ── 经典电子音乐 ──
    "four_on_floor": EuclideanPreset(
        name="Four-on-the-Floor",
        description="四拍底鼓，经典 House/Techno",
        kick=(4, 16, 0),
        snare=(4, 16, 4),
        hihat=(8, 16, 0),
        bpm_range=(120, 130),
    ),
    "tech_house": EuclideanPreset(
        name="Tech House",
        description="四拍底鼓 + 密集踩镲",
        kick=(4, 16, 0),
        snare=(4, 16, 4),
        hihat=(13, 16, 0),
        bpm_range=(120, 128),
    ),
    "deep_house": EuclideanPreset(
        name="Deep House",
        description="稀疏踩镲的深浩室",
        kick=(4, 16, 0),
        snare=(4, 16, 4),
        hihat=(7, 16, 1),
        bpm_range=(115, 125),
    ),
    "acid_shuffle": EuclideanPreset(
        name="Acid Shuffle",
        description="Acid 风格 shuffle 节奏",
        kick=(3, 16, 0),
        snare=(4, 16, 4),
        hihat=(7, 16, 0),
        bpm_range=(120, 135),
    ),
    "techno_basic": EuclideanPreset(
        name="Techno Basic",
        description="基础 Techno，底鼓密集",
        kick=(4, 16, 0),
        snare=(2, 16, 5),
        hihat=(8, 16, 0),
        bpm_range=(125, 140),
    ),
    "techno_dark": EuclideanPreset(
        name="Dark Techno",
        description="暗黑 Techno，军鼓稀疏",
        kick=(4, 16, 0),
        snare=(2, 16, 7),
        hihat=(11, 16, 0),
        bpm_range=(128, 140),
    ),
    "techno_dense": EuclideanPreset(
        name="Dense Techno",
        description="密集 Techno Groove",
        kick=(3, 16, 0),
        snare=(5, 16, 2),
        hihat=(11, 16, 0),
        bpm_range=(130, 145),
    ),

    # ── 嘻哈 / Trap ──
    "trap_basic": EuclideanPreset(
        name="Trap Basic",
        description="基础 Trap 节奏",
        kick=(3, 16, 0),
        snare=(3, 16, 7),
        hihat=(8, 16, 0),
        bpm_range=(130, 160),
    ),
    "boom_bap": EuclideanPreset(
        name="Boom Bap",
        description="经典 Boom Bap 嘻哈",
        kick=(3, 16, 0),
        snare=(1, 16, 10),
        hihat=(5, 16, 0),
        bpm_range=(85, 100),
    ),
    "trap_hats": EuclideanPreset(
        name="Trap Hats",
        description="高速踩镲 Trap",
        kick=(3, 16, 0),
        snare=(3, 16, 7),
        hihat=(13, 16, 0),
        bpm_range=(140, 170),
    ),

    # ── 拉丁 / 世界音乐 ──
    "tresillo": EuclideanPreset(
        name="Tresillo",
        description="古巴 Son Clave 节奏 (3-3-2)",
        kick=(3, 8, 0),
        snare=(2, 8, 2),
        hihat=(5, 8, 0),
        bpm_range=(90, 120),
    ),
    "cinquillo": EuclideanPreset(
        name="Cinquillo",
        description="古巴 Cinquillo 节奏",
        kick=(5, 8, 0),
        snare=(3, 8, 2),
        hihat=(7, 8, 0),
        bpm_range=(100, 130),
    ),
    "afro_cuban": EuclideanPreset(
        name="Afro-Cuban",
        description="非裔古巴复合节奏",
        kick=(5, 12, 0),
        snare=(3, 12, 4),
        hihat=(7, 12, 0),
        bpm_range=(100, 130),
    ),

    # ── 实验 / 复合节奏 ──
    "poly_34_on_44": EuclideanPreset(
        name="Polyrhythm 3:4",
        description="3拍底鼓叠加4拍军鼓的复合节奏",
        kick=(3, 16, 0),
        snare=(4, 16, 0),
        hihat=(8, 16, 0),
        bpm_range=(100, 140),
    ),
    "poly_58_on_44": EuclideanPreset(
        name="Polyrhythm 5:8",
        description="5拍元素叠加在4/4上",
        kick=(5, 16, 0),
        snare=(4, 16, 3),
        hihat=(8, 16, 0),
        bpm_range=(100, 130),
    ),
    "minimal": EuclideanPreset(
        name="Minimal",
        description="极简节奏，几乎只有底鼓",
        kick=(2, 16, 0),
        snare=(1, 16, 8),
        hihat=(3, 16, 0),
        bpm_range=(110, 130),
    ),

    # ── 游戏场景专用 ──
    "combat_intense": EuclideanPreset(
        name="Combat Intense",
        description="激烈战斗鼓点",
        kick=(5, 16, 0),
        snare=(5, 16, 2),
        hihat=(13, 16, 0),
        bpm_range=(140, 180),
    ),
    "stealth_tension": EuclideanPreset(
        name="Stealth Tension",
        description="潜行/紧张氛围",
        kick=(2, 16, 0),
        snare=(3, 16, 5),
        hihat=(7, 16, 2),
        bpm_range=(80, 100),
    ),
    "boss_fight": EuclideanPreset(
        name="Boss Fight",
        description="Boss 战鼓点 (密集+变化)",
        kick=(5, 16, 0),
        snare=(4, 16, 3),
        hihat=(11, 16, 0),
        bpm_range=(150, 200),
    ),
    "exploration": EuclideanPreset(
        name="Exploration",
        description="探索/漫游节奏",
        kick=(2, 16, 0),
        snare=(3, 16, 6),
        hihat=(5, 16, 0),
        bpm_range=(70, 100),
    ),

    # ── Drum & Bass / 高速 ──
    "dnb_basic": EuclideanPreset(
        name="DnB Basic",
        description="基础 Drum & Bass",
        kick=(3, 16, 0),
        snare=(2, 16, 4),
        hihat=(13, 16, 0),
        bpm_range=(160, 180),
    ),
    "dnb_jungle": EuclideanPreset(
        name="DnB Jungle",
        description="Jungle 风格碎拍",
        kick=(2, 16, 0),
        snare=(3, 16, 2),
        hihat=(11, 16, 0),
        bpm_range=(160, 180),
    ),
}

# 按名称索引
EUCLIDEAN_PRESETS_BY_NAME = {p.name: p for p in EUCLIDEAN_PRESETS.values()}


def get_euclidean_tracks(preset_name: str) -> Optional[Dict[str, List[int]]]:
    """获取指定预置的鼓轨模式。

    Args:
        preset_name: 预置名称 (如 "four_on_floor")

    Returns:
        {"kick": [...], "snare": [...], "hihat": [...]} 或 None
    """
    preset = EUCLIDEAN_PRESETS.get(preset_name)
    if preset is None:
        return None

    return {
        "kick":  euclidean_rhythm(*preset.kick),
        "snare": euclidean_rhythm(*preset.snare),
        "hihat": euclidean_rhythm(*preset.hihat),
    }


def list_euclidean_presets() -> List[Dict[str, str]]:
    """列出所有欧几里得节奏预置。"""
    return [
        {
            "key": key,
            "name": p.name,
            "description": p.description,
            "bpm": f"{p.bpm_range[0]}-{p.bpm_range[1]}",
        }
        for key, p in EUCLIDEAN_PRESETS.items()
    ]
