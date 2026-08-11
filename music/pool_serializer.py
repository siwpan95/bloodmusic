"""
乐器池序列化器 —— YAML/JSON 保存与加载
========================================

提供 InstrumentPool ↔ YAML/JSON 的双向转换，以及内置预设的管理。

用法:
    >>> from bloodmusic.music.pool_serializer import PoolSerializer
    >>> pool = PoolSerializer.load_yaml("my_pool.yaml")
    >>> PoolSerializer.save_yaml(pool, "my_pool.yaml")
    >>> presets = PoolSerializer.list_presets()
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .instrument_pool import (
    InstrumentPool,
    InstrumentRole,
    PoolConfig,
    PoolInstrument,
    SynthEngine,
)

if TYPE_CHECKING:
    from ..effects.chain import EffectChain

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 自定义异常
# ═══════════════════════════════════════════════════════════════════════

class PoolSerializationError(Exception):
    """乐器池序列化/反序列化错误。

    用于包装底层异常（YAML 解析错误、JSON 解码错误等），
    方便调用者统一捕获处理。
    """
    pass


# ═══════════════════════════════════════════════════════════════════════
# 预设目录
# ═══════════════════════════════════════════════════════════════════════

def _get_presets_dir() -> Path:
    """获取 pool_presets/ 目录的绝对路径。"""
    return Path(__file__).parent / "pool_presets"


# ═══════════════════════════════════════════════════════════════════════
# PoolSerializer
# ═══════════════════════════════════════════════════════════════════════

class PoolSerializer:
    """乐器池 YAML/JSON 序列化器。

    所有方法为静态方法，无需实例化。
    """

    # ── 加载 ──

    @staticmethod
    def load_yaml(path: str) -> InstrumentPool:
        """从 YAML 文件加载 InstrumentPool。

        Args:
            path: YAML 文件路径

        Returns:
            InstrumentPool 实例

        Raises:
            PoolSerializationError: 文件不存在、解析失败或数据校验失败
        """
        filepath = Path(path)
        if not filepath.exists():
            raise PoolSerializationError(f"YAML 文件不存在: {path}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PoolSerializationError(f"YAML 解析失败 ({path}): {e}") from e
        except OSError as e:
            raise PoolSerializationError(f"读取文件失败 ({path}): {e}") from e

        if data is None:
            raise PoolSerializationError(f"YAML 文件为空: {path}")

        if not isinstance(data, dict):
            raise PoolSerializationError(
                f"YAML 文件内容格式错误: 期望 dict，实际 {type(data).__name__}"
            )

        return PoolSerializer._dict_to_pool(data)

    @staticmethod
    def load_json(path: str) -> InstrumentPool:
        """从 JSON 文件加载 InstrumentPool。

        Args:
            path: JSON 文件路径

        Returns:
            InstrumentPool 实例

        Raises:
            PoolSerializationError: 文件不存在、解析失败或数据校验失败
        """
        filepath = Path(path)
        if not filepath.exists():
            raise PoolSerializationError(f"JSON 文件不存在: {path}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise PoolSerializationError(f"JSON 解析失败 ({path}): {e}") from e
        except OSError as e:
            raise PoolSerializationError(f"读取文件失败 ({path}): {e}") from e

        if not isinstance(data, dict):
            raise PoolSerializationError(
                f"JSON 文件内容格式错误: 期望 dict，实际 {type(data).__name__}"
            )

        return PoolSerializer._dict_to_pool(data)

    # ── 保存 ──

    @staticmethod
    def save_yaml(pool: InstrumentPool, path: str) -> None:
        """将 InstrumentPool 保存为 YAML 文件。

        Args:
            pool: 乐器池实例
            path: 输出路径

        Raises:
            PoolSerializationError: 保存失败
        """
        data = PoolSerializer._pool_to_dict(pool)
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(
                    data, f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                    indent=2,
                )
        except (OSError, yaml.YAMLError) as e:
            raise PoolSerializationError(f"保存 YAML 失败 ({path}): {e}") from e

    @staticmethod
    def save_json(pool: InstrumentPool, path: str) -> None:
        """将 InstrumentPool 保存为 JSON 文件。

        Args:
            pool: 乐器池实例
            path: 输出路径

        Raises:
            PoolSerializationError: 保存失败
        """
        data = PoolSerializer._pool_to_dict(pool)
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise PoolSerializationError(f"保存 JSON 失败 ({path}): {e}") from e

    # ── 预设管理 ──

    @staticmethod
    def list_presets() -> List[str]:
        """列出所有内置乐器池预设（YAML 文件）。"""
        presets_dir = _get_presets_dir()
        if not presets_dir.exists():
            return []
        presets = []
        for f in sorted(presets_dir.glob("*.yaml")):
            presets.append(f.stem)
        return presets

    @staticmethod
    def load_preset(name: str) -> InstrumentPool:
        """按名称加载内置乐器池预设。

        Args:
            name: 预设名称（不含扩展名），如 "orchestral_small"

        Returns:
            InstrumentPool 实例

        Raises:
            PoolSerializationError: 预设不存在或加载失败
        """
        presets_dir = _get_presets_dir()
        path = presets_dir / f"{name}.yaml"

        if not path.exists():
            available = PoolSerializer.list_presets()
            raise PoolSerializationError(
                f"预设 '{name}' 不存在。可用预设: {available}"
            )

        return PoolSerializer.load_yaml(str(path))

    # ── 内部方法 ──

    @staticmethod
    def _pool_to_dict(pool: InstrumentPool) -> Dict[str, Any]:
        """InstrumentPool → dict（调用 pool.to_dict()）。"""
        return pool.to_dict()

    @staticmethod
    def _dict_to_pool(data: Dict[str, Any]) -> InstrumentPool:
        """dict → InstrumentPool。"""
        # 解析 instruments 列表
        instruments: List[PoolInstrument] = []
        for inst_data in data.get("instruments", []):
            instruments.append(PoolSerializer._dict_to_instrument(inst_data))

        # 解析 config（YAML 中 key 为 "generation"）
        gen_data = data.get("generation", {})
        if not isinstance(gen_data, dict):
            gen_data = {}
        config = PoolConfig(
            sections=gen_data.get("sections", []),
            section_bars=gen_data.get("section_bars", []),
            diversity=gen_data.get("diversity", 0.3),
            seed=gen_data.get("seed"),
            humanize=gen_data.get("humanize", True),
            chord_progression=gen_data.get("chord_progression"),
            target_bars=gen_data.get("target_bars"),
        )

        # 解析 master_chain（可选）
        master_chain: Optional["EffectChain"] = None
        mc_data = data.get("master_chain")
        if mc_data is not None and isinstance(mc_data, dict) and mc_data:
            master_chain = _dict_to_effect_chain(mc_data)

        pool = InstrumentPool(
            name=data.get("name", "Untitled Pool"),
            version=data.get("version", "1.0"),
            instruments=instruments,
            style=data.get("style"),
            bpm=data.get("bpm", 120),
            key=data.get("key", "C"),
            scale=data.get("scale", "major"),
            config=config,
            master_chain=master_chain,
            global_volume=data.get("global_volume", 0.9),
            automation=data.get("automation"),
        )

        return pool

    @staticmethod
    def _dict_to_instrument(data: Dict[str, Any]) -> PoolInstrument:
        """dict → PoolInstrument。"""
        # 解析 role（字符串 → 枚举）
        role_raw = data.get("role", "melody")
        if isinstance(role_raw, str):
            role = InstrumentRole.from_string(role_raw)
        else:
            role = InstrumentRole.MELODY

        # 解析 engine（字符串 → 枚举）
        engine_raw = data.get("engine", "wavetable")
        if isinstance(engine_raw, str):
            engine = SynthEngine.from_string(engine_raw)
        else:
            engine = SynthEngine.WAVETABLE

        # 解析 effect_chain（可选）
        effect_chain: Optional["EffectChain"] = None
        ec_data = data.get("effect_chain")
        if ec_data is not None and isinstance(ec_data, dict) and ec_data:
            effect_chain = _dict_to_effect_chain(ec_data)

        # 解析 note_sequence
        note_sequence: Optional[List[Optional[str]]] = None
        ns_data = data.get("note_sequence")
        if ns_data is not None and isinstance(ns_data, list):
            note_sequence = ns_data

        return PoolInstrument(
            name=data.get("name", "Unnamed"),
            role=role,
            engine=engine,
            preset=data.get("preset"),
            params=data.get("params", {}),
            engine_params=data.get("engine_params", {}),
            automation=data.get("automation"),
            effect_chain=effect_chain,
            pan=data.get("pan", 0.0),
            volume=data.get("volume", 1.0),
            note_sequence=note_sequence,
            octave=data.get("octave"),
            sample_path=data.get("sample_path", ""),
        )


# ═══════════════════════════════════════════════════════════════════════
# EffectChain 字典 ↔ 对象 转换
# ═══════════════════════════════════════════════════════════════════════

def _dict_to_effect_chain(data: Dict[str, Any]) -> "EffectChain":
    """dict → EffectChain 实例。"""
    from ..effects.chain import EffectChain

    # EffectChain 的所有字段名
    chain_field_names = {f.name for f in dc_fields(EffectChain)}

    # 只取 EffectChain 已有的字段
    filtered: Dict[str, Any] = {}
    for key, value in data.items():
        if key in chain_field_names:
            filtered[key] = value

    return EffectChain(**filtered)
