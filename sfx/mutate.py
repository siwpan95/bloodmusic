"""SFX 变异(mutation)引擎 — 仿 bfxr Randomize/Mutation 与 lock 机制。

在现有 SynthVoice 基础上做 ±amount 比例扰动生成风格相近的变体，
支持锁定指定字段（仿 bfxr 的 lock 图标）。也可在合理范围内全随机
生成全新音色（仿 sfxr Randomize）。

用法:
    >>> from bloodmusic.sfx.mutate import mutate_voice, mutate_preset
    >>> variants = mutate_preset("button_click", n=5)
    >>> v2 = mutate_voice(variants[0], amount=0.2, locked_fields={"freq"})
"""

import copy
import random
from typing import Iterable, List, Optional, Set

from ..core.voice import SynthVoice, LFOParams, LFOTarget
from ..core.oscillator import OscType
from ..core.envelope import EnvShape
from ..effects.chain import EffectChain
from ..sfx.presets import (
    UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
    GAME_FX_PRESETS,
)

__all__ = [
    "mutate_voice", "randomize_voice", "mutate_preset",
    "get_preset", "ALL_PRESETS",
]

#: 所有 SFX 预设字典的合并视图（名称 → SynthVoice）
ALL_PRESETS = {
    **UI_FX_PRESETS, **CARD_FX_PRESETS,
    **COMBAT_FX_PRESETS, **SYSTEM_FX_PRESETS, **GAME_FX_PRESETS,
}

#: 顶层可扰动的数值字段（比例扰动）
_TOP_LEVEL_NUMERIC = [
    "freq", "duration", "volume", "pitch_mod",
    "vibrato_rate", "vibrato_depth", "detune",
]

#: EffectChain 内可扰动的数值字段
_CHAIN_NUMERIC = [
    "lp_filter_hz", "hp_filter_hz", "distortion", "bit_crush",
    "reverb_mix", "reverb_decay", "reverb_delay_ms", "stereo_width",
    "bp_center_hz", "bp_q", "notch_hz", "notch_q",
    "chorus_mix", "chorus_rate", "chorus_depth",
    "delay_mix", "delay_time", "delay_feedback", "delay_stereo_spread",
    "flanger_mix", "flanger_rate", "flanger_depth", "flanger_feedback",
    "phaser_mix", "phaser_rate", "phaser_depth",
]

#: randomize 时各字段的合理范围（min, max）
_RANDOM_RANGES = {
    "freq": (80.0, 2400.0),
    "duration": (0.02, 0.8),
    "volume": (0.15, 0.9),
    "pitch_mod": (-12.0, 12.0),
    "vibrato_rate": (0.0, 10.0),
    "vibrato_depth": (0.0, 4.0),
    "detune": (0.0, 12.0),
    "lp_filter_hz": (300.0, 12000.0),
    "hp_filter_hz": (40.0, 800.0),
    "distortion": (0.0, 0.8),
    "bit_crush": (4, 12),
    "reverb_mix": (0.0, 0.6),
    "reverb_decay": (0.2, 1.5),
    "reverb_delay_ms": (10.0, 120.0),
    "stereo_width": (0.0, 1.0),
    "chorus_mix": (0.0, 0.5),
    "chorus_rate": (0.1, 3.0),
    "chorus_depth": (0.001, 0.008),
    "delay_mix": (0.0, 0.5),
    "delay_time": (0.1, 0.8),
    "delay_feedback": (0.0, 0.7),
    "flanger_mix": (0.0, 0.6),
    "flanger_rate": (0.1, 2.0),
    "flanger_depth": (0.001, 0.01),
    "phaser_mix": (0.0, 0.7),
    "phaser_rate": (0.1, 2.0),
    "phaser_depth": (0.3, 1.0),
}


def get_preset(name: str) -> SynthVoice:
    """按名称取预设（跨 UI/CARD/COMBAT/SYSTEM 四类）。"""
    if name not in ALL_PRESETS:
        raise KeyError(
            f"未知预设 '{name}'，可用: {', '.join(sorted(ALL_PRESETS))}"
        )
    return ALL_PRESETS[name]


def _in_locked(field_path: str, locked: Set[str]) -> bool:
    """字段路径（'freq' 或 'effect_chain.lp_filter_hz'）是否被锁定。"""
    return field_path in locked


def _perturb(value: float, amount: float) -> float:
    """±amount 比例随机扰动。"""
    return value * (1.0 + random.uniform(-amount, amount))


def _mutate_chain(
    chain: Optional[EffectChain],
    amount: float,
    locked: Set[str],
) -> Optional[EffectChain]:
    if chain is None:
        return None
    chain = copy.deepcopy(chain)
    for field_name in _CHAIN_NUMERIC:
        v = getattr(chain, field_name, None)
        if v is None:
            continue
        if _in_locked(f"effect_chain.{field_name}", locked):
            continue
        setattr(chain, field_name, _perturb(float(v), amount))
    return chain


def mutate_voice(
    voice: SynthVoice,
    amount: float = 0.15,
    locked_fields: Optional[Iterable[str]] = None,
) -> SynthVoice:
    """生成一个风格相近的变异版本。

    对可扰动的数值字段做 ±amount 比例随机扰动；枚举/结构字段不变。
    locked_fields 指定不参与变异的字段（点路径，如 "freq"、
    "effect_chain.reverb_mix"）— 仿 bfxr 的 lock 图标。

    Args:
        voice: 基础 SynthVoice
        amount: 扰动幅度 (0~1 比例，0.15 = ±15%)
        locked_fields: 锁定的字段路径集合

    Returns:
        变异后的新 SynthVoice（原对象不变）
    """
    locked = set(locked_fields or ())
    result = copy.deepcopy(voice)

    for field_name in _TOP_LEVEL_NUMERIC:
        if _in_locked(field_name, locked):
            continue
        v = getattr(result, field_name, None)
        if v is None:
            continue
        setattr(result, field_name, _perturb(float(v), amount))

    # harmonics 振幅扰动
    if not _in_locked("harmonics", locked) and result.harmonics:
        result.harmonics = [
            (mult, amp * (1.0 + random.uniform(-amount, amount)))
            for mult, amp in result.harmonics
        ]

    # LFO 扰动
    if result.lfo is not None and not _in_locked("lfo", locked):
        result.lfo.rate = _perturb(result.lfo.rate, amount)
        result.lfo.depth = _perturb(result.lfo.depth, amount)

    result.effect_chain = _mutate_chain(result.effect_chain, amount, locked)
    return result


def randomize_voice(
    base: Optional[SynthVoice] = None,
    locked_fields: Optional[Iterable[str]] = None,
) -> SynthVoice:
    """在合理范围内全随机生成音色（仿 sfxr Randomize）。

    Args:
        base: 可选基础 voice（保留其结构/枚举/未随机字段），None 则全默认
        locked_fields: 锁定的字段路径集合

    Returns:
        随机化的新 SynthVoice
    """
    locked = set(locked_fields or ())
    result = copy.deepcopy(base) if base is not None else SynthVoice()

    if not _in_locked("osc_type", locked):
        result.osc_type = random.choice(list(OscType))
    if not _in_locked("env_shape", locked):
        result.env_shape = random.choice(list(EnvShape))

    for field_name, (lo, hi) in _RANDOM_RANGES.items():
        if "." not in field_name and not _in_locked(field_name, locked):
            if hasattr(result, field_name):
                setattr(result, field_name, random.uniform(lo, hi) if isinstance(lo, float) else random.randint(lo, hi))

    if result.effect_chain is None:
        result.effect_chain = EffectChain()
    for field_name, (lo, hi) in _RANDOM_RANGES.items():
        if "." in field_name:
            path = f"effect_chain.{field_name}"
            if _in_locked(path, locked):
                continue
            cur = getattr(result.effect_chain, field_name, None)
            if cur is not None:
                setattr(
                    result.effect_chain, field_name,
                    random.uniform(lo, hi) if isinstance(lo, float) else random.randint(lo, hi),
                )
    return result


def mutate_preset(name: str, n: int = 5, amount: float = 0.15,
                  locked_fields: Optional[Iterable[str]] = None) -> List[SynthVoice]:
    """基于预设生成 n 个变异版本。

    Args:
        name: 预设名（如 "button_click"）
        n: 变体数量
        amount: 变异幅度
        locked_fields: 锁定的字段路径集合

    Returns:
        [变异1, 变异2, ...]（原预设不在其中）
    """
    base = get_preset(name)
    return [mutate_voice(base, amount=amount, locked_fields=locked_fields)
            for _ in range(n)]
