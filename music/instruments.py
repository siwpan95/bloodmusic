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
from typing import List, Optional, Tuple, Dict, Any

from ..core.oscillator import OscType
from ..core.envelope import EnvShape
from .instrument_pool import SynthEngine


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

    # ── 真实合成引擎 (v2.1) ──
    # None = 走基础振荡器链路；否则用指定引擎 (如 SynthEngine.ADDITIVE / MODAL) 渲染
    engine: Optional[Any] = None
    engine_params: Dict[str, Any] = field(default_factory=dict)

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
        if self.engine is not None:
            pattern.engine = self.engine
            pattern.engine_params = dict(self.engine_params)
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
            engine=self.engine, engine_params=dict(self.engine_params),
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
# P0 扩充：GM2 主要族补全
#   organ(管风琴族) / brass(铜管扩充) / woodwind(木管·簧片扩充)
#   strings(弦乐扩充) / ethnic(民族·世界) / percussion(钟琴扩充)
#   synth(合成变体)  —— 纯参数映射，零引擎改动

# ── 管风琴族 ──
DRAWBAR_ORGAN = InstrumentPreset(
    name="Drawbar Organ", gm_program=16, category="organ",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.45), (4.0, 0.3), (5.0, 0.2), (6.0, 0.15)],
    vibrato_rate=6.0, vibrato_depth=1.0,
    reverb_mix=0.2, reverb_decay=0.8, lp_filter_hz=4000, stereo_width=0.6,
)

CHURCH_ORGAN = InstrumentPreset(
    name="Church Organ", gm_program=20, category="organ",
    osc_type=OscType.SAW, volume=0.17, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.4), (4.0, 0.3), (5.0, 0.25), (6.0, 0.2), (8.0, 0.1)],
    vibrato_rate=2.0, vibrato_depth=0.5,
    reverb_mix=0.5, reverb_decay=2.0, lp_filter_hz=5000, stereo_width=0.7,
)

REED_ORGAN = InstrumentPreset(
    name="Reed Organ", gm_program=21, category="organ",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.3), (4.0, 0.2)],
    reverb_mix=0.2, reverb_decay=0.8, lp_filter_hz=3000, stereo_width=0.5,
)

ACCORDION = InstrumentPreset(
    name="Accordion", gm_program=22, category="organ",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.35), (4.0, 0.2), (5.0, 0.1)],
    vibrato_rate=6.0, vibrato_depth=1.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=4500, stereo_width=0.5,
)

HARMONICA = InstrumentPreset(
    name="Harmonica", gm_program=23, category="organ",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15)],
    vibrato_rate=7.0, vibrato_depth=2.0,
    reverb_mix=0.15, reverb_decay=1.0, lp_filter_hz=3500, stereo_width=0.4,
)


# ── 铜管族扩充 ──
TROMBONE = InstrumentPreset(
    name="Trombone", gm_program=57, category="brass",
    osc_type=OscType.SAW, volume=0.17, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15), (5.0, 0.08)],
    vibrato_rate=4.0, vibrato_depth=1.5,
    reverb_mix=0.15, reverb_decay=1.2, lp_filter_hz=4200, stereo_width=0.3,
)

TUBA = InstrumentPreset(
    name="Tuba", gm_program=58, category="brass",
    osc_type=OscType.SAW, volume=0.2, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2)],
    vibrato_rate=2.0, vibrato_depth=0.8,
    reverb_mix=0.15, reverb_decay=1.2, lp_filter_hz=2500, stereo_width=0.25,
)

MUTED_TRUMPET = InstrumentPreset(
    name="Muted Trumpet", gm_program=59, category="brass",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15)],
    vibrato_rate=5.0, vibrato_depth=1.0,
    reverb_mix=0.1, reverb_decay=0.8, lp_filter_hz=3500, stereo_width=0.25,
)

FRENCH_HORN = InstrumentPreset(
    name="French Horn", gm_program=60, category="brass",
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.25), (4.0, 0.1)],
    vibrato_rate=3.0, vibrato_depth=1.0,
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=3500, stereo_width=0.4,
)


# ── 木管 / 簧片族扩充 ──
OBOE = InstrumentPreset(
    name="Oboe", gm_program=68, category="woodwind",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.3), (4.0, 0.15), (5.0, 0.08)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=3500, stereo_width=0.3,
)

ENGLISH_HORN = InstrumentPreset(
    name="English Horn", gm_program=69, category="woodwind",
    osc_type=OscType.SQUARE, volume=0.14, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.25)],
    vibrato_rate=4.0, vibrato_depth=1.2,
    reverb_mix=0.25, reverb_decay=1.0, lp_filter_hz=3000, stereo_width=0.3,
)

BASSOON = InstrumentPreset(
    name="Bassoon", gm_program=70, category="woodwind",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15)],
    vibrato_rate=3.0, vibrato_depth=1.0,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=2500, stereo_width=0.3,
)

SOPRANO_SAX = InstrumentPreset(
    name="Soprano Sax", gm_program=64, category="woodwind",
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1)],
    vibrato_rate=5.0, vibrato_depth=1.6,
    reverb_mix=0.18, reverb_decay=1.0, lp_filter_hz=5000, stereo_width=0.3,
)

TENOR_SAX = InstrumentPreset(
    name="Tenor Sax", gm_program=66, category="woodwind",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.45), (3.0, 0.25), (4.0, 0.12)],
    vibrato_rate=4.5, vibrato_depth=1.5,
    reverb_mix=0.18, reverb_decay=1.0, lp_filter_hz=4000, stereo_width=0.35,
)

BARITONE_SAX = InstrumentPreset(
    name="Baritone Sax", gm_program=67, category="woodwind",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15)],
    vibrato_rate=4.0, vibrato_depth=1.3,
    reverb_mix=0.18, reverb_decay=1.0, lp_filter_hz=3000, stereo_width=0.35,
)

PICCOLO = InstrumentPreset(
    name="Piccolo", gm_program=72, category="woodwind",
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=6.0, vibrato_depth=2.0,
    reverb_mix=0.2, reverb_decay=0.8, lp_filter_hz=8000, stereo_width=0.35,
)

RECORDER = InstrumentPreset(
    name="Recorder", gm_program=74, category="woodwind",
    osc_type=OscType.SINE, volume=0.13, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.15), (3.0, 0.05)],
    vibrato_rate=3.0, vibrato_depth=1.0,
    reverb_mix=0.15, reverb_decay=0.8, lp_filter_hz=6000, stereo_width=0.35,
)

PAN_FLUTE = InstrumentPreset(
    name="Pan Flute", gm_program=75, category="woodwind",
    osc_type=OscType.SINE, volume=0.13, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.1)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=5000, stereo_width=0.4,
)

SHAKUHACHI = InstrumentPreset(
    name="Shakuhachi", gm_program=77, category="woodwind",
    osc_type=OscType.SINE, volume=0.13, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.12), (3.0, 0.05)],
    vibrato_rate=4.0, vibrato_depth=1.2,
    reverb_mix=0.25, reverb_decay=1.0, lp_filter_hz=4000, stereo_width=0.45,
)

WHISTLE = InstrumentPreset(
    name="Whistle", gm_program=78, category="woodwind",
    osc_type=OscType.SINE, volume=0.11, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.08)],
    vibrato_rate=7.0, vibrato_depth=2.5,
    reverb_mix=0.15, reverb_decay=0.6, lp_filter_hz=9000, stereo_width=0.3,
)

OCARINA = InstrumentPreset(
    name="Ocarina", gm_program=79, category="woodwind",
    osc_type=OscType.SINE, volume=0.13, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.2), (3.0, 0.08)],
    vibrato_rate=4.0, vibrato_depth=1.0,
    reverb_mix=0.15, reverb_decay=0.8, lp_filter_hz=5000, stereo_width=0.35,
)


# ── 弦乐族扩充 ──
CONTRABASS = InstrumentPreset(
    name="Contrabass", gm_program=43, category="strings",
    osc_type=OscType.TRIANGLE, volume=0.2, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1)],
    vibrato_rate=2.0, vibrato_depth=0.5,
    reverb_mix=0.2, reverb_decay=1.2, lp_filter_hz=2000, stereo_width=0.2,
)

TREMOLO_STRINGS = InstrumentPreset(
    name="Tremolo Strings", gm_program=44, category="strings",
    osc_type=OscType.SAW, volume=0.12, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.12), (4.0, 0.06)],
    vibrato_rate=8.0, vibrato_depth=2.0,
    reverb_mix=0.35, reverb_decay=1.5, lp_filter_hz=4000, stereo_width=0.6,
)


# ── 民族 / 世界乐器 ──
SITAR = InstrumentPreset(
    name="Sitar", gm_program=104, category="ethnic",
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.6), (3.0, 0.4), (4.0, 0.3), (5.0, 0.2)],
    vibrato_rate=6.0, vibrato_depth=2.0,
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=5000, stereo_width=0.5,
)

SHAMISEN = InstrumentPreset(
    name="Shamisen", gm_program=108, category="ethnic",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PLUCK,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.15)],
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=5000, stereo_width=0.45,
)

KALIMBA = InstrumentPreset(
    name="Kalimba", gm_program=109, category="ethnic",
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1), (4.0, 0.05)],
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=6000, stereo_width=0.5,
)

BAGPIPE = InstrumentPreset(
    name="Bagpipe", gm_program=110, category="ethnic",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.3), (4.0, 0.2)],
    vibrato_rate=5.0, vibrato_depth=1.0,
    reverb_mix=0.2, reverb_decay=1.2, lp_filter_hz=4000, stereo_width=0.5,
)

FIDDLE = InstrumentPreset(
    name="Fiddle", gm_program=111, category="ethnic",
    osc_type=OscType.SAW, volume=0.15, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1), (5.0, 0.05)],
    vibrato_rate=6.0, vibrato_depth=2.0,
    reverb_mix=0.2, reverb_decay=1.2, lp_filter_hz=4500, stereo_width=0.45,
)

SHANAI = InstrumentPreset(
    name="Shanai", gm_program=112, category="ethnic",
    osc_type=OscType.SQUARE, volume=0.15, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.35), (4.0, 0.2)],
    vibrato_rate=6.0, vibrato_depth=1.5,
    reverb_mix=0.2, reverb_decay=1.0, lp_filter_hz=4000, stereo_width=0.4,
)


# ── 键盘打击 / 钟琴族扩充 ──
GLOCKENSPIEL = InstrumentPreset(
    name="Glockenspiel", gm_program=9, category="percussion",
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (3.0, 0.1), (5.0, 0.04)],
    vibrato_rate=7.0, vibrato_depth=0.5,
    reverb_mix=0.35, reverb_decay=2.0, lp_filter_hz=9000, stereo_width=0.5,
)

XYLOPHONE = InstrumentPreset(
    name="Xylophone", gm_program=13, category="percussion",
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (4.0, 0.1), (8.0, 0.03)],
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=7000, stereo_width=0.45,
)

DULCIMER = InstrumentPreset(
    name="Dulcimer", gm_program=15, category="percussion",
    osc_type=OscType.TRIANGLE, volume=0.13, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1)],
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=6000, stereo_width=0.5,
)


# ── 合成器变体 ──
SYNTH_POLYSYNTH = InstrumentPreset(
    name="Polysynth Pad", gm_program=91, category="synth",
    osc_type=OscType.SAW, volume=0.11, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.1)],
    vibrato_rate=2.0, vibrato_depth=1.0,
    reverb_mix=0.4, reverb_decay=2.5, lp_filter_hz=3500, stereo_width=0.7,
)

SYNTH_SPACE = InstrumentPreset(
    name="Space Voice Pad", gm_program=92, category="synth",
    osc_type=OscType.SAW, volume=0.1, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.25), (3.0, 0.1), (4.0, 0.05)],
    vibrato_rate=1.5, vibrato_depth=1.5,
    reverb_mix=0.6, reverb_decay=3.0, lp_filter_hz=3000, stereo_width=0.85,
)

SYNTH_METAL = InstrumentPreset(
    name="Metal Pad", gm_program=94, category="synth",
    osc_type=OscType.SQUARE, volume=0.11, env_shape=EnvShape.PAD,
    harmonics=[(1.0, 1.0), (2.5, 0.5), (4.2, 0.3), (6.3, 0.15)],
    vibrato_rate=3.0, vibrato_depth=1.0,
    reverb_mix=0.3, reverb_decay=2.0, lp_filter_hz=6000, stereo_width=0.6,
)

SYNTH_HALO = InstrumentPreset(
    name="Halo Pad", gm_program=95, category="synth",
    osc_type=OscType.TRIANGLE, volume=0.1, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.3), (3.0, 0.15), (5.0, 0.08)],
    vibrato_rate=2.0, vibrato_depth=1.0,
    reverb_mix=0.5, reverb_decay=3.0, lp_filter_hz=4000, stereo_width=0.8,
)

SYNTH_SWEEP = InstrumentPreset(
    name="Sweep Pad", gm_program=96, category="synth",
    osc_type=OscType.SAW, volume=0.1, env_shape=EnvShape.SWELL,
    harmonics=[(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1)],
    vibrato_rate=2.0, vibrato_depth=2.0,
    reverb_mix=0.5, reverb_decay=3.0, lp_filter_hz=5000, stereo_width=0.75,
)

SYNTH_CHARANG = InstrumentPreset(
    name="Charang Lead", gm_program=85, category="synth",
    osc_type=OscType.SAW, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[(1.0, 1.0), (2.0, 0.5), (3.0, 0.4), (4.0, 0.3), (5.0, 0.2)],
    vibrato_rate=5.0, vibrato_depth=1.5,
    reverb_mix=0.15, reverb_decay=0.8, lp_filter_hz=7000, stereo_width=0.4,
)


# ── v2.1 真实合成引擎乐器 (ADDITIVE / MODAL) ──
# 这些乐器声明 engine=SynthEngine.ADDITIVE/MODAL，渲染时走 core.additive / core.modal，
# 而非基础振荡器链路，从而解锁 glass / bell / metal / bar / membrane / bowl / gong 质感。
GLASS_BELL = InstrumentPreset(
    name="Glass Bell", gm_program=130, category="percussion",
    osc_type=OscType.SINE, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.ADDITIVE, engine_params={"preset": "glass"},
    reverb_mix=0.45, reverb_decay=2.5, lp_filter_hz=12000, stereo_width=0.6,
)

METAL_BELL = InstrumentPreset(
    name="Metal Bell", gm_program=131, category="percussion",
    osc_type=OscType.SINE, volume=0.18, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.ADDITIVE, engine_params={"preset": "bell"},
    reverb_mix=0.4, reverb_decay=3.0, lp_filter_hz=12000, stereo_width=0.5,
)

METAL_PLATE = InstrumentPreset(
    name="Metal Plate", gm_program=132, category="percussion",
    osc_type=OscType.SINE, volume=0.14, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.ADDITIVE, engine_params={"preset": "metal"},
    reverb_mix=0.35, reverb_decay=2.0, lp_filter_hz=11000, stereo_width=0.55,
)

GLASS_PAD = InstrumentPreset(
    name="Glass Pad", gm_program=133, category="synth",
    osc_type=OscType.SINE, volume=0.1, env_shape=EnvShape.PAD,
    harmonics=[], engine=SynthEngine.ADDITIVE, engine_params={"preset": "glass_pad"},
    vibrato_rate=1.2, vibrato_depth=0.6,
    reverb_mix=0.55, reverb_decay=3.0, lp_filter_hz=8000, stereo_width=0.85,
)

MARIMBA_BAR = InstrumentPreset(
    name="Marimba Bar", gm_program=134, category="percussion",
    osc_type=OscType.SINE, volume=0.18, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.MODAL, engine_params={"preset": "bar", "base_decay": 4.0},
    reverb_mix=0.3, reverb_decay=1.5, lp_filter_hz=9000, stereo_width=0.45,
)

TUBULAR_BELL_MODAL = InstrumentPreset(
    name="Tubular Bell (Modal)", gm_program=135, category="percussion",
    osc_type=OscType.SINE, volume=0.17, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.MODAL, engine_params={"preset": "tubular", "base_decay": 2.0},
    reverb_mix=0.5, reverb_decay=4.0, lp_filter_hz=10000, stereo_width=0.5,
)

SINGING_BOWL = InstrumentPreset(
    name="Singing Bowl", gm_program=136, category="ethnic",
    osc_type=OscType.SINE, volume=0.2, env_shape=EnvShape.PAD,
    harmonics=[], engine=SynthEngine.MODAL, engine_params={"preset": "bowl", "base_decay": 1.5},
    reverb_mix=0.6, reverb_decay=5.0, lp_filter_hz=7000, stereo_width=0.7,
)

GONG_MODAL = InstrumentPreset(
    name="Gong (Modal)", gm_program=137, category="percussion",
    osc_type=OscType.SINE, volume=0.22, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.MODAL, engine_params={"preset": "gong", "base_decay": 1.2},
    reverb_mix=0.55, reverb_decay=5.0, lp_filter_hz=8000, stereo_width=0.8,
)


# ── v2.2 混合声部乐器 (HYBRID) ──
# 单一声部内融合 additive + modal + tone + noise 多层，engine=SynthEngine.HYBRID。
HYBRID_BELL_METAL = InstrumentPreset(
    name="Hybrid Bell Metal", gm_program=140, category="percussion",
    osc_type=OscType.SINE, volume=0.18, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.HYBRID, engine_params={"preset": "bell_metal"},
    reverb_mix=0.5, reverb_decay=3.5, lp_filter_hz=12000, stereo_width=0.6,
)

HYBRID_GLASS_STRIKE = InstrumentPreset(
    name="Hybrid Glass Strike", gm_program=141, category="percussion",
    osc_type=OscType.SINE, volume=0.16, env_shape=EnvShape.PERCUSSIVE,
    harmonics=[], engine=SynthEngine.HYBRID, engine_params={"preset": "glass_strike"},
    reverb_mix=0.45, reverb_decay=3.0, lp_filter_hz=13000, stereo_width=0.55,
)

HYBRID_SHIMMER_PAD = InstrumentPreset(
    name="Hybrid Shimmer Pad", gm_program=142, category="synth",
    osc_type=OscType.SINE, volume=0.12, env_shape=EnvShape.PAD,
    harmonics=[], engine=SynthEngine.HYBRID, engine_params={"preset": "hybrid_pad"},
    vibrato_rate=1.0, vibrato_depth=0.5,
    reverb_mix=0.6, reverb_decay=3.5, lp_filter_hz=9000, stereo_width=0.85,
)


# ── v2.3 材质感知鼓组 (Material-aware, 鼓专用) ──
# engine=SynthEngine.MATERIAL → 鼓渲染走 sfx.material.synthesize_material_impact，
# 由 engine_params["track_materials"] 决定 kick/snare/hihat 各自材质，
# 同一套合成逻辑参数化出 wood/metal/glass/ceramic 等截然不同的撞击质感。
MATERIAL_DRUMKIT = InstrumentPreset(
    name="Material Drumkit", gm_program=118, category="drum",
    osc_type=OscType.NOISE_BROWN, volume=0.8, env_shape=EnvShape.PERCUSSIVE,
    engine=SynthEngine.MATERIAL,
    engine_params={
        "material": "wood",
        "track_materials": {
            "kick": "wood",
            "snare": "metal",
            "hihat": "ceramic",
        },
    },
)


# 分类汇总
# ═══════════════════════════════════════════════════════════════════════

INSTRUMENTS: Dict[str, InstrumentPreset] = {}
_BY_GM: Dict[int, InstrumentPreset] = {}
_BY_CATEGORY: Dict[str, List[InstrumentPreset]] = {}

for _inst in [
    # Piano
    ACOUSTIC_GRAND_PIANO, BRIGHT_PIANO, ELECTRIC_PIANO, HARPSICHORD, CELESTA,
    # Strings
    VIOLIN, VIOLA, CELLO, STRING_ENSEMBLE, PIZZICATO, CONTRABASS, TREMOLO_STRINGS,
    # Brass/Woodwind
    TRUMPET, FLUTE, CLARINET, SAXOPHONE, BRASS_SECTION,
    TROMBONE, TUBA, MUTED_TRUMPET, FRENCH_HORN,
    OBOE, ENGLISH_HORN, BASSOON, SOPRANO_SAX, TENOR_SAX, BARITONE_SAX,
    PICCOLO, RECORDER, PAN_FLUTE, SHAKUHACHI, WHISTLE, OCARINA,
    # Organ family (GM 17-24)
    DRAWBAR_ORGAN, CHURCH_ORGAN, REED_ORGAN, ACCORDION, HARMONICA,
    # Guitar/Plucked
    ACOUSTIC_GUITAR, ELECTRIC_GUITAR_CLEAN, KOTO, BANJO,
    # Ethnic / World
    SITAR, SHAMISEN, KALIMBA, BAGPIPE, FIDDLE, SHANAI,
    # Percussion/Mallet
    MUSIC_BOX, VIBRAPHONE, MARIMBA, TUBULAR_BELLS,
    GLOCKENSPIEL, XYLOPHONE, DULCIMER,
    # v2.1 真实合成引擎乐器 (ADDITIVE / MODAL)
    GLASS_BELL, METAL_BELL, METAL_PLATE, MARIMBA_BAR, TUBULAR_BELL_MODAL, GONG_MODAL,
    SINGING_BOWL, GLASS_PAD,
    # v2.2 混合声部乐器 (HYBRID)
    HYBRID_BELL_METAL, HYBRID_GLASS_STRIKE, HYBRID_SHIMMER_PAD,
    # v2.3 材质感知鼓组 (MATERIAL, 鼓专用)
    MATERIAL_DRUMKIT,
    # Synth
    SYNTH_PAD_WARM, SYNTH_PAD_BRIGHT, SYNTH_LEAD, SYNTH_BASS,
    SYNTH_POLYSYNTH, SYNTH_SPACE, SYNTH_METAL, SYNTH_HALO, SYNTH_SWEEP, SYNTH_CHARANG,
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
