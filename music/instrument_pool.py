"""
乐器池核心数据模型 —— InstrumentPool / PoolInstrument / PoolConfig / 枚举
====================================================================

乐器池系统的心脏：定义乐器池的完整数据结构，支持 YAML/JSON 序列化、
角色分配、校验等功能。

用法:
    >>> from bloodmusic.music.instrument_pool import (
    ...     InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine
    ... )
    >>> pool = InstrumentPool(name="My Pool", bpm=120, key="C")
    >>> pool.instruments.append(PoolInstrument("Piano", role=InstrumentRole.MELODY, ...))
    >>> pool.validate()
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..effects.chain import EffectChain

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════════════════

class InstrumentRole(Enum):
    """乐器在编曲中的角色。

    Values:
        MELODY  — 主旋律
        CHORD   — 和弦/和声
        BASS    — 低音线
        DRUM    — 打击乐
        PAD     — 铺底/氛围
        FX      — 特殊效果
    """
    MELODY = "melody"
    CHORD = "chord"
    BASS = "bass"
    DRUM = "drum"
    PAD = "pad"
    FX = "fx"

    @classmethod
    def from_string(cls, value: str) -> "InstrumentRole":
        """从字符串创建 InstrumentRole（支持大小写不敏感）。"""
        value_lower = value.lower().strip()
        for role in cls:
            if role.value == value_lower:
                return role
        raise ValueError(
            f"未知的乐器角色: '{value}'。"
            f"有效值: {[r.value for r in cls]}"
        )

    def __str__(self) -> str:
        return self.value


class SynthEngine(Enum):
    """合成引擎类型。

    所有引擎均为 BloodMusic 内置合成器，无需外部采样。
    """
    SUBTRACTIVE = "subtractive"       # 减法合成 (滤波器 + 波形)
    FM = "fm"                         # 2-operator FM 合成
    FM_ADVANCED = "fm_advanced"       # 多 operator FM (DX7 风格)
    KARPLUS_STRONG = "karplus_strong" # Karplus-Strong 物理建模
    GRANULAR = "granular"             # 粒子合成
    WAVETABLE = "wavetable"           # 波表合成
    WAVEGUIDE = "waveguide"           # 波导物理建模
    NOISE = "noise"                   # 噪声合成 (鼓专用)
    SAMPLER = "sampler"               # 采样器引擎 (真实 .wav 采样回放)

    @classmethod
    def from_string(cls, value: str) -> "SynthEngine":
        """从字符串创建 SynthEngine（支持大小写不敏感）。"""
        value_lower = value.lower().strip()
        for engine in cls:
            if engine.value == value_lower:
                return engine
        raise ValueError(
            f"未知的合成引擎: '{value}'。"
            f"有效值: {[e.value for e in cls]}"
        )

    def __str__(self) -> str:
        return self.value


# ═══════════════════════════════════════════════════════════════════════
# 角色→引擎智能映射表
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_ENGINE_MAP: Dict[InstrumentRole, SynthEngine] = {
    InstrumentRole.MELODY: SynthEngine.WAVETABLE,
    InstrumentRole.CHORD: SynthEngine.FM_ADVANCED,
    InstrumentRole.BASS: SynthEngine.SUBTRACTIVE,
    InstrumentRole.DRUM: SynthEngine.NOISE,
    InstrumentRole.PAD: SynthEngine.GRANULAR,
    InstrumentRole.FX: SynthEngine.KARPLUS_STRONG,
}


def get_default_engine(role: InstrumentRole) -> SynthEngine:
    """获取某角色的默认合成引擎。"""
    return DEFAULT_ENGINE_MAP.get(role, SynthEngine.SUBTRACTIVE)


# ═══════════════════════════════════════════════════════════════════════
# 核心数据模型
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PoolInstrument:
    """乐器池中的单件乐器定义。

    包含角色分配、合成引擎选择、音色预设引用、效果链等完整配置。

    Args:
        name: 显示名称（如 "主旋律钢琴"）
        role: 编曲角色 (InstrumentRole)
        engine: 合成引擎类型 (SynthEngine)
        preset: 引用 instruments.py 中的预设名（如 "acoustic_grand_piano"），
                None 表示使用默认参数
        params: 合成参数覆盖字典（直接传给引擎的参数）
        effect_chain: 该乐器专属效果链
        pan: 声像位置 (-1.0=左, 0.0=中, 1.0=右)
        volume: 相对音量 (0.0~1.0)
        note_sequence: 可选的用户指定音符序列（覆盖自动生成）
                       格式: ["C4","D4",null,"E4"]（null=休止符）
        octave: 八度偏移，None=默认
        sample_path: 采样文件路径（仅 SAMPLER 引擎使用），默认空字符串
    """
    name: str
    role: InstrumentRole = InstrumentRole.MELODY
    engine: SynthEngine = SynthEngine.WAVETABLE
    preset: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    engine_params: Dict[str, Any] = field(default_factory=dict)
    automation: Optional[Dict[str, Any]] = None
    effect_chain: Optional["EffectChain"] = None
    pan: float = 0.0
    volume: float = 1.0
    note_sequence: Optional[List[Optional[str]]] = None
    octave: Optional[int] = None
    sample_path: str = ""

    def __post_init__(self) -> None:
        """类型转换与校验。"""
        # 确保 role 是枚举类型
        if isinstance(self.role, str):
            self.role = InstrumentRole.from_string(self.role)
        # 确保 engine 是枚举类型
        if isinstance(self.engine, str):
            self.engine = SynthEngine.from_string(self.engine)
        # 如果未指定 engine，使用角色默认引擎
        if self.engine is None:
            self.engine = get_default_engine(self.role)
        # 校验 volume 范围
        if self.volume is not None and (self.volume < 0.0 or self.volume > 2.0):
            logger.warning(
                f"PoolInstrument '{self.name}': volume={self.volume} 超出合理范围 [0, 2]，"
                f"将钳制。"
            )
            self.volume = max(0.0, min(2.0, self.volume))
        # 校验 pan 范围
        self.pan = max(-1.0, min(1.0, self.pan))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为纯字典（用于 YAML/JSON 导出）。"""
        d: Dict[str, Any] = {
            "name": self.name,
            "role": self.role.value,
            "engine": self.engine.value,
            "volume": self.volume,
            "pan": self.pan,
        }
        if self.preset is not None:
            d["preset"] = self.preset
        if self.params:
            d["params"] = self.params
        if self.engine_params:
            d["engine_params"] = self.engine_params
        if self.automation is not None:
            d["automation"] = self.automation
        if self.note_sequence is not None:
            d["note_sequence"] = self.note_sequence
        if self.octave is not None:
            d["octave"] = self.octave
        if self.sample_path:
            d["sample_path"] = self.sample_path
        # EffectChain 序列化：仅序列化非 None/非默认字段
        if self.effect_chain is not None:
            d["effect_chain"] = _effect_chain_to_dict(self.effect_chain)
        return d

    def validate(self) -> List[str]:
        """校验本乐器配置，返回警告列表（空列表=无问题）。"""
        warnings: List[str] = []
        if not self.name.strip():
            warnings.append("PoolInstrument: name 为空")
        if self.volume <= 0.0:
            warnings.append(f"PoolInstrument '{self.name}': volume=0，该乐器将静音")
        if self.role == InstrumentRole.DRUM and self.note_sequence is not None:
            warnings.append(
                f"PoolInstrument '{self.name}': drum 角色设置了 note_sequence，"
                f"将被忽略（鼓使用 euclidean 节奏生成）"
            )
        return warnings


@dataclass
class PoolConfig:
    """乐器池的生成与编排参数。

    Args:
        sections: 曲式段落名称列表（如 ["intro","verse","chorus","outro"]），
                  空列表=使用风格默认
        section_bars: 各段落的小节数，空列表=使用风格默认
        diversity: 生成多样性 (0.0=固定/可复现, 0.5=默认, 1.0=最大随机)
        seed: 随机种子 (None=随机)
        humanize: 是否应用人性化处理
        chord_progression: 自定义和弦进行名称 (如 "I-V-vi-IV")，None=自动选择
        target_bars: 目标总小节数，None=由 sections/section_bars 自动计算
    """
    sections: List[str] = field(default_factory=list)
    section_bars: List[int] = field(default_factory=list)
    diversity: float = 0.3
    seed: Optional[int] = None
    humanize: bool = True
    chord_progression: Optional[str] = None
    target_bars: Optional[int] = None

    def __post_init__(self) -> None:
        """校验 diversity 范围。"""
        self.diversity = max(0.0, min(1.0, self.diversity))

    def to_dict(self) -> Dict[str, Any]:
        """序列化为纯字典。"""
        d: Dict[str, Any] = {
            "diversity": self.diversity,
            "humanize": self.humanize,
        }
        if self.sections:
            d["sections"] = self.sections
        if self.section_bars:
            d["section_bars"] = self.section_bars
        if self.seed is not None:
            d["seed"] = self.seed
        if self.chord_progression is not None:
            d["chord_progression"] = self.chord_progression
        if self.target_bars is not None:
            d["target_bars"] = self.target_bars
        return d

    def validate(self) -> List[str]:
        """校验配置，返回警告列表。"""
        warnings: List[str] = []
        if len(self.sections) != len(self.section_bars) and self.section_bars:
            warnings.append(
                f"PoolConfig: sections 数量 ({len(self.sections)}) "
                f"与 section_bars 数量 ({len(self.section_bars)}) 不匹配"
            )
        return warnings


@dataclass
class InstrumentPool:
    """乐器池 — 配器师的核心数据结构。

    一个乐器池定义了：用哪些乐器、什么角色、什么风格、怎么生成。

    Args:
        name: 乐池名称
        version: 配置版本号（用于向前兼容）
        instruments: 乐器列表
        style: 关联的风格预设名称（如 "exploration"），None=不关联
        bpm: 默认速度
        key: 调性（如 "C", "Am", "D"）
        scale: 音阶类型（如 "major", "dorian", "pentatonic_minor"）
        config: 生成/编排参数
        master_chain: 母带效果链（应用于最终混音）
        global_volume: 全局音量倍率 (0.0~1.0)
    """
    name: str
    version: str = "1.0"
    instruments: List[PoolInstrument] = field(default_factory=list)
    style: Optional[str] = None
    bpm: int = 120
    key: str = "C"
    scale: str = "major"
    config: PoolConfig = field(default_factory=PoolConfig)
    master_chain: Optional["EffectChain"] = None
    global_volume: float = 0.9
    automation: Optional[Dict[str, Any]] = None

    # ── 工厂方法 ──

    @classmethod
    def from_yaml(cls, path: str) -> "InstrumentPool":
        """从 YAML 文件加载乐器池。

        Args:
            path: YAML 文件路径

        Returns:
            InstrumentPool 实例

        Raises:
            PoolSerializationError: 加载失败时
        """
        from .pool_serializer import PoolSerializer
        return PoolSerializer.load_yaml(path)

    @classmethod
    def from_json(cls, path: str) -> "InstrumentPool":
        """从 JSON 文件加载乐器池。

        Args:
            path: JSON 文件路径

        Returns:
            InstrumentPool 实例

        Raises:
            PoolSerializationError: 加载失败时
        """
        from .pool_serializer import PoolSerializer
        return PoolSerializer.load_json(path)

    # ── 序列化方法 ──

    def to_yaml(self, path: str) -> None:
        """将乐器池导出为 YAML 文件。

        Args:
            path: 输出路径

        Raises:
            PoolSerializationError: 保存失败时
        """
        from .pool_serializer import PoolSerializer
        PoolSerializer.save_yaml(self, path)

    def to_json(self, path: str) -> None:
        """将乐器池导出为 JSON 文件。

        Args:
            path: 输出路径

        Raises:
            PoolSerializationError: 保存失败时
        """
        from .pool_serializer import PoolSerializer
        PoolSerializer.save_json(self, path)

    # ── 查询方法 ──

    def get_by_role(self, role: InstrumentRole) -> List[PoolInstrument]:
        """按角色筛选乐器。

        Args:
            role: InstrumentRole 枚举值

        Returns:
            匹配该角色的 PoolInstrument 列表
        """
        if isinstance(role, str):
            role = InstrumentRole.from_string(role)
        return [inst for inst in self.instruments if inst.role == role]

    def has_role(self, role: InstrumentRole) -> bool:
        """检查乐池中是否包含某角色的乐器。"""
        return len(self.get_by_role(role)) > 0

    # ── 校验 ──

    def validate(self) -> List[str]:
        """校验整个乐器池配置，返回警告/错误列表。

        Returns:
            字符串列表，每个元素是一条警告或错误信息。
            空列表表示配置合法。

        注意：此方法不抛异常，由调用者决定如何处理警告。
        """
        warnings: List[str] = []

        if not self.name.strip():
            warnings.append("InstrumentPool: name 为空")

        if not self.instruments:
            warnings.append("InstrumentPool: instruments 列表为空，乐器池无乐器")

        if self.bpm <= 0:
            warnings.append(f"InstrumentPool: bpm={self.bpm} 无效，应为正数")

        if self.global_volume <= 0.0:
            warnings.append("InstrumentPool: global_volume=0，乐池将完全静音")
        elif self.global_volume > 1.0:
            warnings.append(
                f"InstrumentPool: global_volume={self.global_volume} > 1.0，"
                f"可能导致削波"
            )

        # 校验每个乐器
        for inst in self.instruments:
            warnings.extend(inst.validate())

        # 校验配置
        warnings.extend(self.config.validate())

        # 检查角色覆盖
        roles_found = set()
        for inst in self.instruments:
            roles_found.add(inst.role)
        if InstrumentRole.DRUM not in roles_found:
            warnings.append("InstrumentPool: 缺少 drum 角色，节奏轨将缺失")
        if InstrumentRole.BASS not in roles_found:
            warnings.append("InstrumentPool: 缺少 bass 角色，低频可能空洞")

        return warnings

    # ── 序列化辅助 ──

    def to_dict(self) -> Dict[str, Any]:
        """将整个乐器池序列化为纯字典。"""
        d: Dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "bpm": self.bpm,
            "key": self.key,
            "scale": self.scale,
            "global_volume": self.global_volume,
            "instruments": [inst.to_dict() for inst in self.instruments],
            "generation": self.config.to_dict(),
        }
        if self.style is not None:
            d["style"] = self.style
        if self.master_chain is not None:
            d["master_chain"] = _effect_chain_to_dict(self.master_chain)
        if self.automation is not None:
            d["automation"] = self.automation
        return d

    def __repr__(self) -> str:
        roles = ", ".join(
            f"{r.value}:{len(self.get_by_role(r))}"
            for r in InstrumentRole
            if self.has_role(r)
        )
        return (
            f"InstrumentPool(name='{self.name}', "
            f"bpm={self.bpm}, key={self.key}, "
            f"instruments={len(self.instruments)} [{roles}])"
        )


# ═══════════════════════════════════════════════════════════════════════
# EffectChain 序列化辅助
# ═══════════════════════════════════════════════════════════════════════

def _effect_chain_to_dict(chain: "EffectChain") -> Dict[str, Any]:
    """将 EffectChain 转为仅包含非默认/非 None 字段的字典。

    默认值参考 EffectChain 的 dataclass 定义。
    """
    from dataclasses import fields as dc_fields
    from ..effects.chain import EffectChain

    default_chain = EffectChain()
    result: Dict[str, Any] = {}

    for f in dc_fields(EffectChain):
        value = getattr(chain, f.name)
        default_value = getattr(default_chain, f.name)

        # 只序列化非 None 且与默认值不同的字段
        if value is not None and value != default_value:
            # 对于 CompressorParams 和 ParametricEQParams，递归序列化
            if hasattr(value, "to_dict"):
                result[f.name] = value.to_dict()
            elif isinstance(value, Enum):
                result[f.name] = value.value
            else:
                result[f.name] = value

    return result
