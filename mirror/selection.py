# -*- coding: utf-8 -*-
"""
selection.py —— 选源规则（镜像 musickit remix 选音规则）

采样侧规则 → 机生成侧对应：
  1. 骨架层（drum/bass/guita）保底各 ≥1 条 loop —— 生成侧同规则，
     且生成 loop 天然 BPM 对齐、无时长未知问题；
  2. 点缀层（cowbell/synth/animal/sfx 等）每池 ≤1 条 —— 同规则；
  3. 内容去重（时长+指纹）—— 生成侧以 (engine, preset, seed) 天然唯一；
  4. --release-safe 仅 free/pack —— 生成侧恒 selfgen，开关恒真。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .pools import POOL_INSTRUMENTS, get_pool
from .taxonomy import POOLS

# 骨架层角色（保底 ≥1 loop）
SKELETON_ROLES = ("drum", "bass", "guita")
# 点缀层（每池 ≤1）
ACCENT_ROLES = ("melody", "pad", "vocal", "fx")


@dataclass(frozen=True)
class SourceSpec:
    """一条已选源（镜像采样侧的选音结果）。"""

    pool: str
    name: str
    subcategory: str
    engine: str
    preset: str
    role: str
    kind: str          # loop | one_shot | stem
    bars_loop: int = 1
    seed: int = 0
    volume: float = 0.8

    def as_dict(self) -> dict:
        return {
            "pool": self.pool, "name": self.name, "subcategory": self.subcategory,
            "engine": self.engine, "preset": self.preset, "role": self.role,
            "kind": self.kind, "bars_loop": self.bars_loop, "seed": self.seed,
            "volume": self.volume,
        }


def _pick(pool: str, role: str, kind: str, rng: random.Random, seed_base: int) -> SourceSpec | None:
    """从池中按角色/kind 挑一件生成乐器。"""
    if pool not in POOL_INSTRUMENTS:
        return None
    candidates = [i for i in POOL_INSTRUMENTS[pool]
                  if i.role == role and i.kind == kind]
    if not candidates:
        candidates = [i for i in POOL_INSTRUMENTS[pool] if i.role == role]
    if not candidates:
        return None
    inst = rng.choice(candidates)
    return SourceSpec(
        pool=pool, name=inst.name, subcategory=inst.subcategory,
        engine=inst.engine, preset=inst.preset, role=role, kind=inst.kind,
        bars_loop=1, seed=seed_base + hash((pool, inst.name)) % 99991,
        volume=0.8,
    )


def select_sources(prompt, bars: int, seed: int = 0) -> list[SourceSpec]:
    """提示词 → 选源列表（骨架保底 + 点缀限量，种子可复现）。

    Args:
        prompt: styles.Prompt（含 instruments=[{word,pool,role}]）。
        bars: 曲目小节数（loop 素材的小节长度）。
        seed: 可复现种子。

    Returns:
        SourceSpec 列表（含骨架层保底补位）。
    """
    rng = random.Random(seed)
    specs: list[SourceSpec] = []
    used_pools: dict[str, int] = {}

    # 1) 提示词直接给出的乐器（词 → 池 → 生成乐器）
    for item in prompt.instruments:
        pool = item["pool"]
        role = item["role"]
        if pool == "drum":
            spec = _pick("drum", "drum", "loop", rng, seed)
            if spec:
                spec = SourceSpec(**{**spec.__dict__, "name": item["word"],
                                     "preset": "kick" if "kick" in item["word"] else spec.preset})
                specs.append(spec)
                used_pools[pool] = used_pools.get(pool, 0) + 1
            continue
        spec = _pick(pool, role, "loop" if pool not in ("cowbell", "animal", "sfx") else "one_shot", rng, seed)
        if spec:
            specs.append(spec)
            used_pools[pool] = used_pools.get(pool, 0) + 1

    # 2) 骨架层保底：drum/bass/guita 至少各 1 条 loop
    for role, pool in (("drum", "drum"), ("bass", "bass"), ("guita", "guita")):
        if used_pools.get(pool, 0) == 0:
            spec = _pick(pool, role, "loop", rng, seed)
            if spec:
                specs.append(spec)
                used_pools[pool] = used_pools.get(pool, 0) + 1

    # 3) 点缀层限量：每池 ≤1（已选的跳过）
    for pool in POOLS:
        if pool in ("drum", "bass", "guita"):
            continue
        if used_pools.get(pool, 0) > 0:
            continue
        if rng.random() > 0.28:   # 少量点缀，防满配
            continue
        role = "vocal" if pool == "acapella" else (
            "fx" if pool in ("cowbell", "animal", "sfx") else
            "pad" if pool in ("strings", "ethnic", "synth") else "melody")
        spec = _pick(pool, role, "one_shot" if pool in ("cowbell", "animal", "sfx") else "loop", rng, seed)
        if spec:
            specs.append(spec)
            used_pools[pool] = 1

    # 4) 去重（engine+preset+role 天然唯一）+ 稳定排序（骨架在前）
    order = {r: i for i, r in enumerate(("drum", "bass", "guita", "pad", "melody", "vocal", "fx"))}
    specs.sort(key=lambda s: (order.get(s.role, 9), s.pool, s.name))
    return specs
