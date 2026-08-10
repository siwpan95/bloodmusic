"""
风格预设系统 —— 12 个内置风格模板
==================================

每种风格为乐器池提供角色级生成参数覆盖。
游戏风格 (5):
  - exploration: 探索/漫游（宽广、明亮）
  - battle: 战斗（激烈、快速、压迫）
  - town: 城镇/村庄（温暖、舒缓）
  - dungeon: 地下城（阴暗、紧张、沉重）
  - ambient: 氛围/环境（空灵、缓慢、空间感）

纯音乐流派风格 (7):
  - classical: 古典/钢琴
  - jazz: 爵士/摇摆
  - electronic: 电子/EDM
  - cinematic: 影视史诗
  - lofi: Lo-Fi 低保真
  - meditation: 冥想/自然
  - folk: 民谣/世界音乐

用法:
    >>> from bloodmusic.music.pool_styles import STYLES, StylePreset
    >>> style = STYLES["battle"]
    >>> pool = style.apply_to(pool)
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .instrument_pool import InstrumentPool, InstrumentRole, PoolConfig


@dataclass
class StylePreset:
    """风格预设 — 角色级生成参数覆盖模板。

    每种风格定义了不同角色的生成参数（密度、音阶偏好、BPM 范围等），
    通过 apply_to() 方法应用到 InstrumentPool。

    Args:
        name: 风格名称
        description: 风格描述
        role_params: {InstrumentRole → {param_name: value}} 按角色的参数覆盖
        config_overrides: PoolConfig 级别的参数覆盖（仅覆盖未显式设置的字段）
        arrangement_template: 曲式模板名 ("pop", "electronic", "ambient" 等)
        mix_params: 混音参数指导 (target_rms_db, compression_ratio 等)
    """
    name: str
    description: str = ""
    role_params: Dict[str, dict] = field(default_factory=dict)
    config_overrides: Optional[dict] = None
    arrangement_template: Optional[str] = None
    mix_params: Optional[dict] = None

    def apply_to(self, pool: "InstrumentPool") -> "InstrumentPool":
        """将风格预设应用到乐器池（创建新副本，不修改原对象）。

        pool.config 中的显式设置优先于 style 覆盖值。

        Args:
            pool: 原始乐器池

        Returns:
            应用风格后的新 InstrumentPool 副本
        """
        new_pool = deepcopy(pool)

        # 设置 style 引用
        new_pool.style = self.name

        # 应用 config_overrides（pool.config 优先）
        if self.config_overrides:
            for key, value in self.config_overrides.items():
                current = getattr(new_pool.config, key, None)
                # 只覆盖默认值（用户显式设置的保留）
                if current is None or current == getattr(
                    type(new_pool.config)(), key, None
                ):
                    setattr(new_pool.config, key, value)

        # 应用 arrangement_template（如果 pool 未显式设置 sections）
        if self.arrangement_template is not None and not new_pool.config.sections:
            from .arrangement import create_song_template
            template = create_song_template(self.arrangement_template)
            new_pool.config.sections = [s.name for s in template.sections]
            new_pool.config.section_bars = [s.bars for s in template.sections]

        # role_params 通过 pool_generator 中的 _resolve_style_params 在运行时应用
        # 这里只是确保 style 引用正确

        return new_pool


# ═══════════════════════════════════════════════════════════════════════
# 内置风格预设 —— 游戏风格 (5)
# ═══════════════════════════════════════════════════════════════════════

# 宏定义：常用角色参数
_MELODY_PARAMS = "melody"
_CHORD_PARAMS = "chord"
_BASS_PARAMS = "bass"
_DRUM_PARAMS = "drum"
_PAD_PARAMS = "pad"
_FX_PARAMS = "fx"

# 探索风格：宽广、明亮、中等速度
STYLE_EXPLORATION = StylePreset(
    name="exploration",
    description="探索/漫游 — 宽广、明亮的旋律，中等速度，适合开放世界探索场景",
    arrangement_template="ambient",
    config_overrides={
        "diversity": 0.4,
        "humanize": True,
        "chord_progression": "dreamy",
    },
    mix_params={
        "target_rms_db": -18.0,
        "target_headroom_db": 6.0,
        "reverb_mix": 0.35,
        "compression_ratio": 1.5,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 1.5,
            "temperature": 0.8,
            "rest_probability": 0.08,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "natural",
            "scale_preference": ["major", "dorian", "lydian", "mixolydian"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.5,
            "voice_count": 3,
            "chord_progression": "dreamy",
            "bpm_range": (70, 100),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.5,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "exploration",
            "pulse_density": 0.3,
            "bpm_range": (70, 100),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.5,
            "reverb_mix": 0.5,
            "octaves": 2,
            "arpeggio_mode": "up_down",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 战斗风格：激烈、快速、沉重
STYLE_BATTLE = StylePreset(
    name="battle",
    description="战斗 — 激烈、快速、节奏感强，适合战斗场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.25,
        "humanize": True,
        "chord_progression": "epic",
    },
    mix_params={
        "target_rms_db": -14.0,
        "target_headroom_db": 3.0,
        "reverb_mix": 0.15,
        "compression_ratio": 3.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 2.5,
            "temperature": 0.6,
            "rest_probability": 0.03,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "groovy",
            "scale_preference": ["phrygian", "harmonic_minor", "minor"],
        },
        _CHORD_PARAMS: {
            "note_density": 1.0,
            "voice_count": 3,
            "chord_progression": "heroic",
            "bpm_range": (130, 180),
        },
        _BASS_PARAMS: {
            "preset_type": "fm",
            "note_density": 1.0,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "combat_intense",
            "pulse_density": 0.7,
            "bpm_range": (140, 180),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.3,
            "reverb_mix": 0.2,
            "octaves": 1,
            "arpeggio_mode": "up",
        },
        _FX_PARAMS: {
            "enabled": True,
            "fx_type": "riser",
        },
    },
)

# 城镇风格：温暖、舒缓、亲切
STYLE_TOWN = StylePreset(
    name="town",
    description="城镇/村庄 — 温暖、舒缓、亲切的氛围",
    arrangement_template="lo-fi",
    config_overrides={
        "diversity": 0.3,
        "humanize": True,
        "chord_progression": "folk",
    },
    mix_params={
        "target_rms_db": -16.0,
        "target_headroom_db": 5.0,
        "reverb_mix": 0.25,
        "compression_ratio": 2.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 1.5,
            "temperature": 0.9,
            "rest_probability": 0.06,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "natural",
            "scale_preference": ["major", "pentatonic", "mixolydian"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.6,
            "voice_count": 3,
            "chord_progression": "pop_verse",
            "bpm_range": (80, 110),
        },
        _BASS_PARAMS: {
            "preset_type": "pluck",
            "note_density": 0.5,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "minimal",
            "pulse_density": 0.4,
            "bpm_range": (80, 110),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.4,
            "reverb_mix": 0.4,
            "octaves": 1,
            "arpeggio_mode": "up",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 地下城风格：阴暗、紧张、沉重
STYLE_DUNGEON = StylePreset(
    name="dungeon",
    description="地下城 — 阴暗、紧张、沉重的氛围，低频为主",
    arrangement_template="ambient",
    config_overrides={
        "diversity": 0.2,
        "humanize": False,
        "chord_progression": "ambient",
    },
    mix_params={
        "target_rms_db": -16.0,
        "target_headroom_db": 4.0,
        "reverb_mix": 0.4,
        "compression_ratio": 2.5,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 0.8,
            "temperature": 0.5,
            "rest_probability": 0.15,
            "min_octave": 3,
            "max_octave": 5,
            "humanize_level": "subtle",
            "scale_preference": ["phrygian", "locrian", "diminished"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.3,
            "voice_count": 2,
            "chord_progression": "minor_i-iv-v",
            "bpm_range": (60, 90),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.4,
            "min_octave": 0,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "stealth_tension",
            "pulse_density": 0.25,
            "bpm_range": (60, 90),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.7,
            "reverb_mix": 0.6,
            "octaves": 2,
            "arpeggio_mode": "random",
        },
        _FX_PARAMS: {
            "enabled": True,
            "fx_type": "drone",
        },
    },
)

# 氛围风格：空灵、缓慢、空间感
STYLE_AMBIENT = StylePreset(
    name="ambient",
    description="氛围/环境 — 空灵、缓慢、空间感强，适合场景背景",
    arrangement_template="ambient",
    config_overrides={
        "diversity": 0.5,
        "humanize": True,
        "chord_progression": "ambient",
    },
    mix_params={
        "target_rms_db": -20.0,
        "target_headroom_db": 8.0,
        "reverb_mix": 0.6,
        "compression_ratio": 1.2,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 0.5,
            "temperature": 1.0,
            "rest_probability": 0.2,
            "min_octave": 3,
            "max_octave": 6,
            "humanize_level": "human",
            "scale_preference": ["major", "dorian", "pentatonic", "whole_tone"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.2,
            "voice_count": 4,
            "chord_progression": "dreamy",
            "bpm_range": (40, 80),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.2,
            "min_octave": 0,
            "max_octave": 1,
        },
        _DRUM_PARAMS: {
            "preset_name": "minimal",
            "pulse_density": 0.1,
            "bpm_range": (40, 80),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.8,
            "reverb_mix": 0.7,
            "octaves": 3,
            "arpeggio_mode": "random",
        },
        _FX_PARAMS: {
            "enabled": True,
            "fx_type": "atmosphere",
        },
    },
)

# ═══════════════════════════════════════════════════════════════════════
# 内置风格预设 —— 纯音乐流派 (7)
# ═══════════════════════════════════════════════════════════════════════

# 古典风格：钢琴为主、旋律优雅、无鼓
STYLE_CLASSICAL = StylePreset(
    name="classical",
    description="古典/钢琴 — 优雅旋律、中等偏慢，适合钢琴独奏/室内乐场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.15,
        "humanize": True,
        "chord_progression": "dreamy",
    },
    mix_params={
        "target_rms_db": -20.0,
        "target_headroom_db": 6.0,
        "reverb_mix": 0.30,
        "compression_ratio": 1.5,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 1.2,
            "temperature": 0.7,
            "rest_probability": 0.05,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "subtle",
            "scale_preference": ["major", "minor", "pentatonic"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.4,
            "voice_count": 4,
            "chord_progression": "dreamy",
            "bpm_range": (60, 80),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.4,
            "min_octave": 2,
            "max_octave": 3,
        },
        _DRUM_PARAMS: {
            "enabled": False,
        },
        _PAD_PARAMS: {
            "volume_mult": 0.6,
            "reverb_mix": 0.5,
            "octaves": 2,
            "arpeggio_mode": "up_down",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 爵士风格：摇摆律动、复杂和声、walking bass
STYLE_JAZZ = StylePreset(
    name="jazz",
    description="爵士/摇摆 — 复杂和声、摇摆律动、walking bass 线条，适合咖啡馆/背景场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.3,
        "humanize": True,
        "chord_progression": "jazz",
    },
    mix_params={
        "target_rms_db": -18.0,
        "target_headroom_db": 5.0,
        "reverb_mix": 0.20,
        "compression_ratio": 2.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 2.0,
            "temperature": 0.8,
            "rest_probability": 0.06,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "groovy",
            "scale_preference": ["major", "dorian", "mixolydian", "blues"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.6,
            "voice_count": 4,
            "chord_progression": "jazz",
            "bpm_range": (80, 120),
        },
        _BASS_PARAMS: {
            "preset_type": "pluck",
            "note_density": 1.5,
            "min_octave": 1,
            "max_octave": 3,
        },
        _DRUM_PARAMS: {
            "preset_name": "jazz",
            "pulse_density": 0.4,
            "bpm_range": (80, 120),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.4,
            "reverb_mix": 0.3,
            "octaves": 1,
            "arpeggio_mode": "up_down",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 电子/EDM 风格：高压缩、快速、强力节拍
STYLE_ELECTRONIC = StylePreset(
    name="electronic",
    description="电子/EDM — 高能量、强力节拍、合成器音色，适合舞曲/club 场景",
    arrangement_template="electronic",
    config_overrides={
        "diversity": 0.2,
        "humanize": False,
        "chord_progression": "driving",
    },
    mix_params={
        "target_rms_db": -12.0,
        "target_headroom_db": 2.0,
        "reverb_mix": 0.10,
        "compression_ratio": 4.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 3.0,
            "temperature": 0.5,
            "rest_probability": 0.02,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "none",
            "scale_preference": ["minor", "phrygian", "harmonic_minor"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.8,
            "voice_count": 3,
            "chord_progression": "driving",
            "bpm_range": (120, 140),
        },
        _BASS_PARAMS: {
            "preset_type": "acid",
            "note_density": 2.5,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "edm",
            "pulse_density": 0.9,
            "bpm_range": (120, 140),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.4,
            "reverb_mix": 0.3,
            "octaves": 2,
            "arpeggio_mode": "up",
        },
        _FX_PARAMS: {
            "enabled": True,
            "fx_type": "riser",
        },
    },
)

# 影视史诗风格：宏大管弦、强力打击乐、渐进式展开
STYLE_CINEMATIC = StylePreset(
    name="cinematic",
    description="影视史诗 — 宏大管弦、渐进展开、史诗打击乐，适合预告片/高潮场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.2,
        "humanize": True,
        "chord_progression": "epic",
    },
    mix_params={
        "target_rms_db": -14.0,
        "target_headroom_db": 4.0,
        "reverb_mix": 0.25,
        "compression_ratio": 2.5,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 2.0,
            "temperature": 0.6,
            "rest_probability": 0.04,
            "min_octave": 3,
            "max_octave": 5,
            "humanize_level": "natural",
            "scale_preference": ["minor", "harmonic_minor", "dorian", "phrygian"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.4,
            "voice_count": 5,
            "chord_progression": "epic",
            "bpm_range": (90, 120),
        },
        _BASS_PARAMS: {
            "preset_type": "fm",
            "note_density": 1.0,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "cinematic",
            "pulse_density": 0.7,
            "bpm_range": (90, 120),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.7,
            "reverb_mix": 0.4,
            "octaves": 3,
            "arpeggio_mode": "up_down",
        },
        _FX_PARAMS: {
            "enabled": True,
            "fx_type": "atmosphere",
        },
    },
)

# Lo-Fi 风格：温暖、低保真、松弛律动
STYLE_LOFI = StylePreset(
    name="lofi",
    description="Lo-Fi 低保真 — 温暖、松弛、低保真质感，适合学习/休闲/背景场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.35,
        "humanize": True,
        "chord_progression": "jazz",
    },
    mix_params={
        "target_rms_db": -18.0,
        "target_headroom_db": 5.0,
        "reverb_mix": 0.30,
        "compression_ratio": 2.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 1.5,
            "temperature": 0.8,
            "rest_probability": 0.08,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "human",
            "scale_preference": ["major", "dorian", "pentatonic"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.5,
            "voice_count": 4,
            "chord_progression": "jazz",
            "bpm_range": (70, 90),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.6,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "preset_name": "lofi",
            "pulse_density": 0.3,
            "bpm_range": (70, 90),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.5,
            "reverb_mix": 0.4,
            "octaves": 1,
            "arpeggio_mode": "random",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 冥想风格：极缓、长混响、自然空间感
STYLE_MEDITATION = StylePreset(
    name="meditation",
    description="冥想/自然 — 极缓节奏、长混响、空灵氛围，适合冥想/瑜伽/放松场景",
    arrangement_template="ambient",
    config_overrides={
        "diversity": 0.1,
        "humanize": True,
        "chord_progression": "dreamy",
    },
    mix_params={
        "target_rms_db": -22.0,
        "target_headroom_db": 8.0,
        "reverb_mix": 0.60,
        "compression_ratio": 1.0,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 0.5,
            "temperature": 1.0,
            "rest_probability": 0.20,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "subtle",
            "scale_preference": ["major", "pentatonic", "dorian"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.2,
            "voice_count": 3,
            "chord_progression": "dreamy",
            "bpm_range": (40, 60),
        },
        _BASS_PARAMS: {
            "preset_type": "sub",
            "note_density": 0.2,
            "min_octave": 1,
            "max_octave": 2,
        },
        _DRUM_PARAMS: {
            "enabled": False,
        },
        _PAD_PARAMS: {
            "volume_mult": 0.8,
            "reverb_mix": 0.7,
            "octaves": 3,
            "arpeggio_mode": "random",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# 民谣风格：自然音色、五声音阶、手工质感
STYLE_FOLK = StylePreset(
    name="folk",
    description="民谣/世界音乐 — 自然音色、五声音阶、手工质感，适合田园/旅行/叙事场景",
    arrangement_template="pop",
    config_overrides={
        "diversity": 0.3,
        "humanize": True,
        "chord_progression": "dreamy",
    },
    mix_params={
        "target_rms_db": -18.0,
        "target_headroom_db": 6.0,
        "reverb_mix": 0.22,
        "compression_ratio": 1.5,
    },
    role_params={
        _MELODY_PARAMS: {
            "note_density": 1.5,
            "temperature": 0.7,
            "rest_probability": 0.06,
            "min_octave": 4,
            "max_octave": 6,
            "humanize_level": "natural",
            "scale_preference": ["pentatonic", "major"],
        },
        _CHORD_PARAMS: {
            "note_density": 0.5,
            "voice_count": 3,
            "chord_progression": "dreamy",
            "bpm_range": (70, 90),
        },
        _BASS_PARAMS: {
            "preset_type": "pluck",
            "note_density": 0.5,
            "min_octave": 2,
            "max_octave": 3,
        },
        _DRUM_PARAMS: {
            "preset_name": "folk",
            "pulse_density": 0.25,
            "bpm_range": (70, 90),
        },
        _PAD_PARAMS: {
            "volume_mult": 0.4,
            "reverb_mix": 0.3,
            "octaves": 1,
            "arpeggio_mode": "up",
        },
        _FX_PARAMS: {
            "enabled": False,
        },
    },
)

# ═══════════════════════════════════════════════════════════════════════
# 风格预设注册表
# ═══════════════════════════════════════════════════════════════════════

STYLES: Dict[str, StylePreset] = {
    "exploration": STYLE_EXPLORATION,
    "battle": STYLE_BATTLE,
    "town": STYLE_TOWN,
    "dungeon": STYLE_DUNGEON,
    "ambient": STYLE_AMBIENT,
    "classical": STYLE_CLASSICAL,
    "jazz": STYLE_JAZZ,
    "electronic": STYLE_ELECTRONIC,
    "cinematic": STYLE_CINEMATIC,
    "lofi": STYLE_LOFI,
    "meditation": STYLE_MEDITATION,
    "folk": STYLE_FOLK,
}


def get_style(name: str) -> StylePreset:
    """按名称获取风格预设。

    Args:
        name: 风格名称（12 种之一：exploration|battle|town|dungeon|ambient|
              classical|jazz|electronic|cinematic|lofi|meditation|folk）

    Returns:
        StylePreset 实例

    Raises:
        KeyError: 未知风格名称
    """
    name_lower = name.lower().strip()
    if name_lower in STYLES:
        return STYLES[name_lower]
    raise KeyError(
        f"未知风格: '{name}'。可用: {list(STYLES.keys())}"
    )


def list_styles() -> List[str]:
    """列出所有可用风格预设名称。"""
    return list(STYLES.keys())
