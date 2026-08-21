"""
内置乐器库 —— 为 MusicPattern 提供类 SoundFont 的乐器选择
============================================================

无需外部采样文件，基于 BloodMusic 自身合成引擎构建多种乐器音色。
每个乐器是一个 SoundPreset: 包含波形、谐波、包络、滤波等参数组合。

用法:
    >>> from bloodmusic.music.instruments import INSTRUMENTS, get_instrument
    >>> piano = get_instrument("acoustic_grand_piano")
    >>> pattern = MusicPattern(notes=[...], ...)
    >>> pattern = piano.apply_to(pattern)

支持 30+ GM 标准乐器 + 自定义合成器音色。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

from ..core.oscillator import OscType
from ..core.envelope import EnvShape


@dataclass
class InstrumentPreset:
    """乐器音色预设 — 定义一组合成参数来模拟特定乐器。

    这些参数直接映射到 MusicPattern 的对应字段，
    可一键应用到任意 MusicPattern 上。
    """
    name: str                      # 显示名
    gm_program: int = 0            # GM MIDI 程序号 (0-127)
    category: str = "synth"        # 分类: piano, strings, brass, woodwind, synth, percussion

    # ── 音色参数 ──
    osc_type: OscType = OscType.SINE
    harmonics: List[Tuple[float, float]] = field(default_factory=list)
    env_shape: EnvShape = EnvShape.PAD
    volume: float = 0.18

    # ── 效果 ──
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    lp_filter_hz: Optional[float] = None
    hp_filter_hz: Optional[float] = None
    stereo_width: float = 0.3

    # ── Bass 模式 (如适用) ──
    bass_osc_type: Optional[OscType] = None
    bass_harmonics: List[Tuple[float, float]] = field(default_factory=list)

    def apply_to(self, pattern):
        """将本乐器预设应用到 MusicPattern (原地修改)"""
        from .pattern import MusicPattern
        pattern.osc_type = self.osc_type
        pattern.harmonics = list(self.harmonics)
        pattern.env_shape = self.env_shape
        pattern.volume = self.volume
        pattern.vibrato_rate = self.vibrato_rate
        pattern.vibrato_depth = self.vibrato_depth
        pattern.reverb_mix = self.reverb_mix
        pattern.reverb_decay = self.reverb_decay
        if self.lp_filter_hz is not None:
            pattern.lp_filter_hz = self.lp_filter_hz
        pattern.stereo_width = self.stereo_width
        return pattern

    def make_pattern(self, name: str, notes: List[str], durations: List[float],
                     bpm: int = 120, loop: bool = True):
        """基于本乐器预设快速创建 MusicPattern"""
        from .pattern import MusicPattern
        return MusicPattern(
            name=name, notes=notes, durations=durations, bpm=bpm, loop=loop,
            osc_type=self.osc_type, volume=self.volume, env_shape=self.env_shape,
            harmonics=list(self.harmonics),
            vibrato_rate=self.vibrato_rate, vibrato_depth=self.vibrato_depth,
            reverb_mix=self.reverb_mix, reverb_decay=self.reverb_decay,
            lp_filter_hz=self.lp_filter_hz, stereo_width=self.stereo_width,
        )


# ═══════════════════════════════════════════════════════════════════════
# 钢琴类
# ═══════════════════════════════════════════════════════════════════════

ACOUSTIC_GRAND_PIANO = InstrumentPreset(
    name="Acoustic Grand Piano", gm_program=0, category="piano",
    osc_type=OscType.TRIANGLE, volume=0.2, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1), (5.0, 0.05), (6.0, 0.03)],
    vibrato_rate=2.5, vibrato_depth=0.6,
    reverb_mix=0.25, reverb_decay=1.5, lp_filter_hz=5000, stereo_width=0.4,
)

BRIGHT_PIANO = InstrumentPreset(
    name="Bright Acoustic Piano", gm_program=1, category="piano",
    osc_type=OscType.TRIANGLE, volume=0.22, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.25), (4.0, 0.15), (6.0, 0.08)],
    vibrato_rate=1.5, vibrato_depth=0.4,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=6000, stereo_width=0.35,
)

ELECTRIC_PIANO = InstrumentPreset(
    name="Electric Piano (Rhodes)", gm_program=4, category="piano",
    osc_type=OscType.SINE, volume=0.17, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.35), (3.0, 0.12), (5.0, 0.05), (7.0, 0.02)],
    vibrato_rate=4.5, vibrato_depth=1.2,
    reverb_mix=0.2, reverb_decay=1.2, lp_filter_hz=4500, stereo_width=0.5,
)

HARPSICHORD = InstrumentPreset(
    name="Harpsichord", gm_program=6, category="piano",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.3), (4.0, 0.15)],
    reverb_mix=0.1, reverb_decay=0.5, lp_filter_hz=5000,
)

CELESTA = InstrumentPreset(
    name="Celesta", gm_program=8, category="piano",
    osc_type=OscType.SINE, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1), (5.0, 0.05), (8.0, 0.02)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.35, reverb_decay=2.0, lp_filter_hz=6000, stereo_width=0.6,
)


# ═══════════════════════════════════════════════════════════════════════
# 弦乐类
# ═══════════════════════════════════════════════════════════════════════

VIOLIN = InstrumentPreset(
    name="Violin", gm_program=40, category="strings",
    osc_type=OscType.SAW, volume=0.14, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1), (5.0, 0.05)],
    vibrato_rate=5.5, vibrato_depth=2.0,
    reverb_mix=0.25, reverb_decay=1.3, lp_filter_hz=4500, stereo_width=0.5,
)

VIOLA = InstrumentPreset(
    name="Viola", gm_program=41, category="strings",
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.35), (3.0, 0.15), (4.0, 0.08)],
    vibrato_rate=4.5, vibrato_depth=1.8,
    reverb_mix=0.25, reverb_decay=1.5, lp_filter_hz=3500, stereo_width=0.45,
)

CELLO = InstrumentPreset(
    name="Cello", gm_program=42, category="strings",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.18), (5.0, 0.06)],
    vibrato_rate=4.0, vibrato_depth=1.5,
    reverb_mix=0.3, reverb_decay=1.8, lp_filter_hz=3000, stereo_width=0.4,
)

STRING_ENSEMBLE = InstrumentPreset(
    name="String Ensemble", gm_program=48, category="strings",
    osc_type=OscType.SAW, volume=0.12, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.12), (4.0, 0.06), (5.0, 0.03)],
    vibrato_rate=3.5, vibrato_depth=1.5,
    reverb_mix=0.4, reverb_decay=2.0, lp_filter_hz=4000, stereo_width=0.7,
)

PIZZICATO = InstrumentPreset(
    name="Pizzicato Strings", gm_program=45, category="strings",
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.25), (4.0, 0.1)],
    reverb_mix=0.15, reverb_decay=0.6, lp_filter_hz=5000,
)


# ═══════════════════════════════════════════════════════════════════════
# 管乐类
# ═══════════════════════════════════════════════════════════════════════

TRUMPET = InstrumentPreset(
    name="Trumpet", gm_program=56, category="brass",
    osc_type=OscType.SAW, volume=0.17, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15), (5.0, 0.08)],
    vibrato_rate=5.0, vibrato_depth=1.2,
    reverb_mix=0.15, reverb_decay=0.8, lp_filter_hz=5000, stereo_width=0.3,
)

FLUTE = InstrumentPreset(
    name="Flute", gm_program=73, category="woodwind",
    osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.08), (4.0, 0.03)],
    vibrato_rate=6.0, vibrato_depth=2.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=5000, stereo_width=0.4,
)

CLARINET = InstrumentPreset(
    name="Clarinet", gm_program=71, category="woodwind",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (3.0, 0.3), (5.0, 0.15), (7.0, 0.05)],
    vibrato_rate=4.0, vibrato_depth=1.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=4000, stereo_width=0.3,
)

SAXOPHONE = InstrumentPreset(
    name="Alto Sax", gm_program=65, category="woodwind",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1), (5.0, 0.05)],
    vibrato_rate=5.0, vibrato_depth=1.8,
    reverb_mix=0.18, reverb_decay=1.0, lp_filter_hz=4500, stereo_width=0.35,
)


# ═══════════════════════════════════════════════════════════════════════
# 吉他/弹拨类
# ═══════════════════════════════════════════════════════════════════════

ACOUSTIC_GUITAR = InstrumentPreset(
    name="Acoustic Guitar (Nylon)", gm_program=24, category="guitar",
    osc_type=OscType.TRIANGLE, volume=0.15, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.2), (4.0, 0.1), (5.0, 0.05)],
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=5000, stereo_width=0.5,
)

ELECTRIC_GUITAR_CLEAN = InstrumentPreset(
    name="Electric Guitar (Clean)", gm_program=27, category="guitar",
    osc_type=OscType.TRIANGLE, volume=0.16, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.25), (4.0, 0.12)],
    reverb_mix=0.12, lp_filter_hz=6000, stereo_width=0.4,
)

KOTO = InstrumentPreset(
    name="Koto (Japanese)", gm_program=107, category="guitar",
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.15), (5.0, 0.08)],
    vibrato_rate=3.0, vibrato_depth=2.0,
    reverb_mix=0.3, reverb_decay=2.0, lp_filter_hz=4000, stereo_width=0.5,
)

BANJO = InstrumentPreset(
    name="Banjo", gm_program=105, category="guitar",
    osc_type=OscType.SQUARE, volume=0.14, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.3), (4.0, 0.15), (6.0, 0.08)],
    reverb_mix=0.1, lp_filter_hz=6000,
)


# ═══════════════════════════════════════════════════════════════════════
# 打击乐/铃音类
# ═══════════════════════════════════════════════════════════════════════

MUSIC_BOX = InstrumentPreset(
    name="Music Box", gm_program=10, category="percussion",
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.2), (4.0, 0.05), (6.0, 0.02)],
    vibrato_rate=7.0, vibrato_depth=0.5,
    reverb_mix=0.3, reverb_decay=2.5, lp_filter_hz=6000, stereo_width=0.5,
)

VIBRAPHONE = InstrumentPreset(
    name="Vibraphone", gm_program=11, category="percussion",
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (3.0, 0.2), (5.0, 0.08), (7.0, 0.04)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.35, reverb_decay=2.0, lp_filter_hz=5000, stereo_width=0.55,
)

MARIMBA = InstrumentPreset(
    name="Marimba", gm_program=12, category="percussion",
    osc_type=OscType.SINE, volume=0.15, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (4.0, 0.1), (8.0, 0.03)],
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=4000, stereo_width=0.45,
)

TUBULAR_BELLS = InstrumentPreset(
    name="Tubular Bells", gm_program=14, category="percussion",
    osc_type=OscType.SINE, volume=0.13, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.8, 0.3), (5.4, 0.1), (8.0, 0.05)],
    vibrato_rate=6.0, vibrato_depth=2.0,
    reverb_mix=0.4, reverb_decay=3.0, lp_filter_hz=5000, stereo_width=0.6,
)


# ═══════════════════════════════════════════════════════════════════════
# 合成器类
# ═══════════════════════════════════════════════════════════════════════

SYNTH_PAD_WARM = InstrumentPreset(
    name="Warm Pad", gm_program=89, category="synth",
    osc_type=OscType.SAW, volume=0.1, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1)],
    vibrato_rate=2.0, vibrato_depth=1.0,
    reverb_mix=0.5, reverb_decay=3.0, lp_filter_hz=3000, stereo_width=0.8,
)

SYNTH_PAD_BRIGHT = InstrumentPreset(
    name="Bright Pad", gm_program=90, category="synth",
    osc_type=OscType.SAW, volume=0.12, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.15), (4.0, 0.06)],
    reverb_mix=0.4, reverb_decay=2.5, lp_filter_hz=5000, stereo_width=0.7,
)

SYNTH_LEAD = InstrumentPreset(
    name="Synth Lead", gm_program=80, category="synth",
    osc_type=OscType.SAW, volume=0.18, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.12)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.1, lp_filter_hz=8000, stereo_width=0.4,
)

SYNTH_BASS = InstrumentPreset(
    name="Synth Bass", gm_program=38, category="synth",
    osc_type=OscType.SAW, volume=0.2, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(0.5, 0.5), (1.0, 1.0), (2.0, 0.15)],
    lp_filter_hz=4000, stereo_width=0.1,
)


# ═══════════════════════════════════════════════════════════════════════
# 自定义贝斯 / 铜管扩展
# ═══════════════════════════════════════════════════════════════════════

UPRIGHT_BASS = InstrumentPreset(
    name="Upright Bass", gm_program=32, category="bass",
    osc_type=OscType.TRIANGLE, volume=0.2, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.35), (3.0, 0.2), (4.0, 0.1)],
    vibrato_rate=3.0, vibrato_depth=0.5,
    reverb_mix=0.2, reverb_decay=1.2, lp_filter_hz=2500, stereo_width=0.2,
)

DEEP_BASS = InstrumentPreset(
    name="Deep Bass", gm_program=39, category="bass",
    osc_type=OscType.SINE, volume=0.22, env_shape=EnvShape.SWELL,
    harmonics=[(0.5, 0.5), (1.0, 1.0), (1.5, 0.15)],
    reverb_mix=0.3, reverb_decay=2.5, lp_filter_hz=800, stereo_width=0.0,
)

WARM_BASS = InstrumentPreset(
    name="Warm Bass", gm_program=33, category="bass",
    osc_type=OscType.TRIANGLE, volume=0.2, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.15), (5.0, 0.05)],
    reverb_mix=0.15, reverb_decay=1.0, lp_filter_hz=1500, stereo_width=0.15,
)

BRASS_SECTION = InstrumentPreset(
    name="Brass Section", gm_program=61, category="brass",
    osc_type=OscType.SAW, volume=0.18, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.3), (4.0, 0.2), (5.0, 0.1), (6.0, 0.05)],
    vibrato_rate=0.8, vibrato_depth=0.6,
    reverb_mix=0.25, reverb_decay=1.8, lp_filter_hz=6000, stereo_width=0.4,
)


# ═══════════════════════════════════════════════════════════════════════
# 分类汇总
# ═══════════════════════════════════════════════════════════════════════

INSTRUMENTS: Dict[str, InstrumentPreset] = {}
_BY_GM: Dict[int, InstrumentPreset] = {}
_BY_CATEGORY: Dict[str, List[InstrumentPreset]] = {}

for _inst in [
    # Piano
    ACOUSTIC_GRAND_PIANO, BRIGHT_PIANO, ELECTRIC_PIANO, HARPSICHORD, CELESTA,
    # Strings
    VIOLIN, VIOLA, CELLO, STRING_ENSEMBLE, PIZZICATO,
    # Brass/Woodwind
    TRUMPET, FLUTE, CLARINET, SAXOPHONE, BRASS_SECTION,
    # Guitar/Plucked
    ACOUSTIC_GUITAR, ELECTRIC_GUITAR_CLEAN, KOTO, BANJO,
    # Percussion/Mallet
    MUSIC_BOX, VIBRAPHONE, MARIMBA, TUBULAR_BELLS,
    # Synth
    SYNTH_PAD_WARM, SYNTH_PAD_BRIGHT, SYNTH_LEAD, SYNTH_BASS,
    # Custom Bass
    UPRIGHT_BASS, DEEP_BASS, WARM_BASS,
]:
    key = _inst.name.lower().replace(" ", "_").replace("(", "").replace(")", "")
    INSTRUMENTS[key] = _inst
    _BY_GM[_inst.gm_program] = _inst
    _BY_CATEGORY.setdefault(_inst.category, []).append(_inst)


def get_instrument(name: str) -> InstrumentPreset:
    """按名称获取乐器预设。

    支持模糊匹配: "piano", "violin", "acoustic_grand_piano"
    """
    key = name.lower().replace(" ", "_").replace("(", "").replace(")", "")
    if key in INSTRUMENTS:
        return INSTRUMENTS[key]
    # 模糊搜索
    for k, v in INSTRUMENTS.items():
        if key in k or k in key:
            return v
    raise KeyError(f"Unknown instrument: '{name}'. Available: {list(INSTRUMENTS.keys())}")


def get_by_gm_program(program: int) -> Optional[InstrumentPreset]:
    """按 GM MIDI 程序号获取乐器"""
    return _BY_GM.get(program)


def list_by_category(category: str) -> List[InstrumentPreset]:
    """列出某分类下的所有乐器"""
    return _BY_CATEGORY.get(category, [])


def list_all_categories() -> List[str]:
    """列出所有分类"""
    return list(_BY_CATEGORY.keys())
