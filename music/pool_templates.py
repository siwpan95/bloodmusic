"""
乐器池模板库 —— 3 个预置乐器池配置
===================================

提供开箱即用的乐器池配置，通过 PoolTemplate 封装：
  - orchestral_small: 管弦小编制（弦乐+木管+定音鼓）
  - electronic_group: 电子合成器组（波表+FM+电子鼓）
  - jazz_trio: 爵士三重奏（钢琴+Double Bass+鼓）

用法:
    >>> from bloodmusic.music.pool_templates import POOL_TEMPLATES
    >>> pool = POOL_TEMPLATES["orchestral_small"].to_pool()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .instrument_pool import (
    InstrumentPool,
    InstrumentRole,
    PoolConfig,
    PoolInstrument,
    SynthEngine,
)


@dataclass
class PoolTemplate:
    """乐器池模板 — 预定义的乐器组合。

    通过 to_pool() 方法转换为可用的 InstrumentPool 实例。

    Args:
        name: 模板名称
        description: 模板描述
        instruments: 预定义的乐器列表
        bpm: 默认 BPM
        key: 默认调性
        scale: 默认音阶
    """
    name: str
    description: str = ""
    instruments: List[PoolInstrument] = field(default_factory=list)
    bpm: int = 120
    key: str = "C"
    scale: str = "major"

    def to_pool(self, style: Optional[str] = None) -> InstrumentPool:
        """转换为 InstrumentPool 实例。

        Args:
            style: 可选风格名称

        Returns:
            InstrumentPool 实例
        """
        pool = InstrumentPool(
            name=self.name.replace("_", " ").title(),
            version="1.0",
            instruments=list(self.instruments),
            bpm=self.bpm,
            key=self.key,
            scale=self.scale,
            config=PoolConfig(),
            style=style,
        )
        return pool


# ═══════════════════════════════════════════════════════════════════════
# 内置模板
# ═══════════════════════════════════════════════════════════════════════

# 管弦小编制：弦乐+木管+定音鼓
TEMPLATE_ORCHESTRAL_SMALL = PoolTemplate(
    name="orchestral_small",
    description="管弦小编制（弦乐+木管+定音鼓）",
    bpm=100,
    key="C",
    scale="dorian",
    instruments=[
        PoolInstrument(
            name="Violin Lead",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            preset="violin",
            volume=0.9,
            pan=0.0,
        ),
        PoolInstrument(
            name="String Ensemble",
            role=InstrumentRole.CHORD,
            engine=SynthEngine.SUBTRACTIVE,
            preset="string_ensemble",
            volume=0.6,
            pan=-0.3,
        ),
        PoolInstrument(
            name="Cello Bass",
            role=InstrumentRole.BASS,
            engine=SynthEngine.SUBTRACTIVE,
            preset="cello",
            volume=0.8,
            pan=0.0,
            octave=-1,
        ),
        PoolInstrument(
            name="Timpani Drums",
            role=InstrumentRole.DRUM,
            engine=SynthEngine.NOISE,
            volume=0.7,
            pan=0.0,
        ),
    ],
)

# 电子合成器组：波表+FM+电子鼓
TEMPLATE_ELECTRONIC_GROUP = PoolTemplate(
    name="electronic_group",
    description="电子合成器组（波表+FM+电子鼓）",
    bpm=128,
    key="Am",
    scale="minor",
    instruments=[
        PoolInstrument(
            name="Synth Lead",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            preset="synth_lead",
            volume=0.85,
            pan=0.1,
        ),
        PoolInstrument(
            name="Bright Pad Chords",
            role=InstrumentRole.CHORD,
            engine=SynthEngine.FM_ADVANCED,
            preset="bright_pad",
            volume=0.5,
            pan=-0.2,
        ),
        PoolInstrument(
            name="FM Bass",
            role=InstrumentRole.BASS,
            engine=SynthEngine.FM,
            preset="synth_bass",
            volume=0.9,
            pan=0.0,
        ),
        PoolInstrument(
            name="Electronic Drums",
            role=InstrumentRole.DRUM,
            engine=SynthEngine.NOISE,
            volume=0.75,
            pan=0.0,
        ),
        PoolInstrument(
            name="Arpeggio Pad",
            role=InstrumentRole.PAD,
            engine=SynthEngine.GRANULAR,
            preset="warm_pad",
            volume=0.4,
            pan=0.3,
        ),
    ],
)

# 爵士三重奏：钢琴+Double Bass+鼓
TEMPLATE_JAZZ_TRIO = PoolTemplate(
    name="jazz_trio",
    description="爵士三重奏（钢琴+Double Bass+鼓）",
    bpm=110,
    key="F",
    scale="mixolydian",
    instruments=[
        PoolInstrument(
            name="Jazz Piano",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            preset="acoustic_grand_piano",
            volume=0.85,
            pan=0.0,
        ),
        PoolInstrument(
            name="Piano Chords",
            role=InstrumentRole.CHORD,
            engine=SynthEngine.WAVETABLE,
            preset="electric_piano_rhodes",
            volume=0.55,
            pan=-0.2,
        ),
        PoolInstrument(
            name="Double Bass",
            role=InstrumentRole.BASS,
            engine=SynthEngine.KARPLUS_STRONG,
            preset="cello",
            volume=0.8,
            pan=0.0,
            octave=-1,
        ),
        PoolInstrument(
            name="Jazz Drums",
            role=InstrumentRole.DRUM,
            engine=SynthEngine.NOISE,
            volume=0.7,
            pan=0.0,
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════════
# 模板注册表
# ═══════════════════════════════════════════════════════════════════════

POOL_TEMPLATES: Dict[str, PoolTemplate] = {
    "orchestral_small": TEMPLATE_ORCHESTRAL_SMALL,
    "electronic_group": TEMPLATE_ELECTRONIC_GROUP,
    "jazz_trio": TEMPLATE_JAZZ_TRIO,
}


def get_template(name: str) -> PoolTemplate:
    """按名称获取模板。

    Raises:
        KeyError: 未知模板名
    """
    name_lower = name.lower().strip()
    if name_lower in POOL_TEMPLATES:
        return POOL_TEMPLATES[name_lower]
    raise KeyError(
        f"未知模板: '{name}'。可用: {list(POOL_TEMPLATES.keys())}"
    )


def list_templates() -> List[str]:
    """列出所有可用模板。"""
    return list(POOL_TEMPLATES.keys())
