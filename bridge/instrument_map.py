"""
bridge/instrument_map.py —— GM program → 音色预设映射（P1-3）

命中需求: **P1-3**（音色预设映射）
关联发现: `Bass_130406.mid` 的 `program = 33` 提供了真实验证数据
          （33 // 8 = 4 → GM Bass 族 → 低通 + PLUCK）。

标定说明（C3）:
    本期只精调 4 个族（0 钢琴 / 4 贝斯 / 5 弦乐 / 11 合成 Pad），
    其余 12 族给基于 `music/presets.py` 数值外推的保守默认，待 A/B 试听再调。

约束: L2 领域层，纯函数，无 IO、无 mido。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from ..core.envelope import EnvShape
from ..core.oscillator import OscType
from ..music.pattern import MusicPattern
from .models import TrackAnalysis

__all__ = [
    "TonePreset",
    "GM_FAMILY_PRESETS",
    "GM_FAMILY_NAMES",
    "NAME_HINT_PRESETS",
    "DEFAULT_TONE_PRESET",
    "DRUM_TONE_PRESET",
    "preset_for_program",
    "preset_for_name",
    "resolve_preset",
]


@dataclass(frozen=True, slots=True)
class TonePreset:
    """一组可施加到 `MusicPattern` 的音色参数。

    字段与 `MusicPattern` 的音色字段一一对应，`apply_to()` 用
    `dataclasses.replace` 施加，不改动 pattern 的音符数据。
    """

    name: str = "default"
    osc_type: OscType = OscType.TRIANGLE
    volume: float = 0.16
    env_shape: EnvShape = EnvShape.PAD
    harmonics: tuple[tuple[float, float], ...] = ()
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    stereo_width: float = 0.3
    lp_filter_hz: float | None = None
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0

    def apply_to(self, p: MusicPattern, *, volume_scale: float = 1.0) -> MusicPattern:
        """把音色施加到 pattern 上，返回**新的** MusicPattern。

        Args:
            p: 源 pattern（不会被修改）。
            volume_scale: P1-1 力度缩放系数，最终 volume = preset.volume * scale。

        Returns:
            施加音色后的新 MusicPattern。
        """
        return dataclasses.replace(
            p,
            osc_type=self.osc_type,
            volume=round(float(self.volume) * float(volume_scale), 6),
            env_shape=self.env_shape,
            harmonics=[tuple(h) for h in self.harmonics],
            reverb_mix=self.reverb_mix,
            reverb_decay=self.reverb_decay,
            stereo_width=self.stereo_width,
            lp_filter_hz=self.lp_filter_hz,
            vibrato_rate=self.vibrato_rate,
            vibrato_depth=self.vibrato_depth,
        )


#: 未识别时的保守默认（与 music/midi_io.py 旧实现的音色保持一致）
DEFAULT_TONE_PRESET = TonePreset(
    name="default",
    osc_type=OscType.TRIANGLE,
    volume=0.16,
    env_shape=EnvShape.PAD,
    reverb_mix=0.15,
)

#: 鼓轨（不走 MusicPattern，仅用于报告展示）
DRUM_TONE_PRESET = TonePreset(
    name="drum",
    osc_type=OscType.NOISE_WHITE,
    volume=0.5,
    env_shape=EnvShape.PERCUSSIVE,
    reverb_mix=0.05,
)

#: GM 16 个乐器族的名称（program // 8）
GM_FAMILY_NAMES: dict[int, str] = {
    0: "piano",
    1: "chromatic_percussion",
    2: "organ",
    3: "guitar",
    4: "bass",
    5: "strings",
    6: "ensemble",
    7: "brass",
    8: "reed",
    9: "pipe",
    10: "synth_lead",
    11: "synth_pad",
    12: "synth_effects",
    13: "ethnic",
    14: "percussive",
    15: "sound_effects",
}

#: GM 族 → 音色预设（key = program // 8，共 16 族）
GM_FAMILY_PRESETS: dict[int, TonePreset] = {
    # 0 钢琴（Piano.mid / Chords_130406.mid 的 program=0 命中此族）—— 已精调
    0: TonePreset(
        name="piano",
        osc_type=OscType.TRIANGLE,
        volume=0.17,
        env_shape=EnvShape.PLUCK,
        harmonics=((2.0, 0.18), (3.0, 0.08)),
        reverb_mix=0.18,
        reverb_decay=0.9,
        stereo_width=0.3,
        lp_filter_hz=6000.0,
    ),
    1: TonePreset(
        name="chromatic_percussion",
        osc_type=OscType.SINE,
        volume=0.15,
        env_shape=EnvShape.PLUCK,
        harmonics=((3.0, 0.2), (5.0, 0.08)),
        reverb_mix=0.22,
        stereo_width=0.35,
    ),
    2: TonePreset(
        name="organ",
        osc_type=OscType.SQUARE,
        volume=0.14,
        env_shape=EnvShape.PAD,
        harmonics=((2.0, 0.3), (4.0, 0.12)),
        reverb_mix=0.2,
        lp_filter_hz=5000.0,
    ),
    3: TonePreset(
        name="guitar",
        osc_type=OscType.SAW,
        volume=0.15,
        env_shape=EnvShape.PLUCK,
        harmonics=((2.0, 0.15),),
        reverb_mix=0.16,
        lp_filter_hz=4500.0,
    ),
    # 4 贝斯（Bass_130406.mid program=33 命中此族）—— 已精调
    4: TonePreset(
        name="bass",
        osc_type=OscType.TRIANGLE,
        volume=0.22,
        env_shape=EnvShape.PLUCK,
        harmonics=((2.0, 0.22), (3.0, 0.06)),
        reverb_mix=0.06,
        reverb_decay=0.5,
        stereo_width=0.12,
        lp_filter_hz=800.0,
    ),
    # 5 弦乐 —— 已精调
    5: TonePreset(
        name="strings",
        osc_type=OscType.SAW,
        volume=0.13,
        env_shape=EnvShape.SWELL,
        harmonics=((2.0, 0.12),),
        reverb_mix=0.3,
        reverb_decay=1.2,
        stereo_width=0.45,
        lp_filter_hz=3800.0,
        vibrato_rate=5.0,
        vibrato_depth=0.12,
    ),
    6: TonePreset(
        name="ensemble",
        osc_type=OscType.SAW,
        volume=0.13,
        env_shape=EnvShape.PAD,
        harmonics=((2.0, 0.14),),
        reverb_mix=0.3,
        reverb_decay=1.2,
        stereo_width=0.5,
        lp_filter_hz=4000.0,
    ),
    7: TonePreset(
        name="brass",
        osc_type=OscType.SAW,
        volume=0.16,
        env_shape=EnvShape.SWELL,
        harmonics=((2.0, 0.25), (3.0, 0.1)),
        reverb_mix=0.2,
        lp_filter_hz=5200.0,
    ),
    8: TonePreset(
        name="reed",
        osc_type=OscType.SQUARE,
        volume=0.14,
        env_shape=EnvShape.SWELL,
        harmonics=((3.0, 0.12),),
        reverb_mix=0.22,
        lp_filter_hz=4200.0,
        vibrato_rate=4.5,
        vibrato_depth=0.1,
    ),
    9: TonePreset(
        name="pipe",
        osc_type=OscType.SINE,
        volume=0.14,
        env_shape=EnvShape.PAD,
        harmonics=((2.0, 0.1),),
        reverb_mix=0.28,
        stereo_width=0.4,
        vibrato_rate=5.5,
        vibrato_depth=0.08,
    ),
    10: TonePreset(
        name="synth_lead",
        osc_type=OscType.SAW,
        volume=0.16,
        env_shape=EnvShape.PLUCK,
        harmonics=((2.0, 0.2),),
        reverb_mix=0.18,
        stereo_width=0.35,
        lp_filter_hz=6500.0,
    ),
    # 11 合成 Pad —— 已精调
    11: TonePreset(
        name="synth_pad",
        osc_type=OscType.TRIANGLE,
        volume=0.12,
        env_shape=EnvShape.PAD,
        harmonics=((2.0, 0.16), (4.0, 0.06)),
        reverb_mix=0.35,
        reverb_decay=1.4,
        stereo_width=0.55,
        lp_filter_hz=3200.0,
    ),
    12: TonePreset(
        name="synth_effects",
        osc_type=OscType.SAW,
        volume=0.12,
        env_shape=EnvShape.SWELL,
        reverb_mix=0.32,
        stereo_width=0.5,
        lp_filter_hz=3000.0,
    ),
    13: TonePreset(
        name="ethnic",
        osc_type=OscType.TRIANGLE,
        volume=0.15,
        env_shape=EnvShape.PLUCK,
        harmonics=((3.0, 0.15),),
        reverb_mix=0.2,
        stereo_width=0.3,
    ),
    14: TonePreset(
        name="percussive",
        osc_type=OscType.SINE,
        volume=0.18,
        env_shape=EnvShape.PERCUSSIVE,
        harmonics=((2.0, 0.1),),
        reverb_mix=0.12,
    ),
    15: TonePreset(
        name="sound_effects",
        osc_type=OscType.NOISE_WHITE,
        volume=0.12,
        env_shape=EnvShape.PERCUSSIVE,
        reverb_mix=0.15,
    ),
}

#: 轨名关键字兜底（program 缺失时使用）；键为小写子串
NAME_HINT_PRESETS: dict[str, TonePreset] = {
    "bass": GM_FAMILY_PRESETS[4],
    "sub": GM_FAMILY_PRESETS[4],
    "piano": GM_FAMILY_PRESETS[0],
    "key": GM_FAMILY_PRESETS[0],
    "chord": GM_FAMILY_PRESETS[11],
    "pad": GM_FAMILY_PRESETS[11],
    "string": GM_FAMILY_PRESETS[5],
    "organ": GM_FAMILY_PRESETS[2],
    "guitar": GM_FAMILY_PRESETS[3],
    "lead": GM_FAMILY_PRESETS[10],
    "melody": GM_FAMILY_PRESETS[10],
    "brass": GM_FAMILY_PRESETS[7],
    "drum": DRUM_TONE_PRESET,
    "perc": DRUM_TONE_PRESET,
    "kit": DRUM_TONE_PRESET,
}


def preset_for_program(program: int | None) -> TonePreset | None:
    """按 GM program 号解析音色预设。

    Args:
        program: GM 乐器程序号 0–127；None 或越界返回 None。

    Returns:
        对应族的 TonePreset；无法解析返回 None。
    """
    if program is None:
        return None
    try:
        value = int(program)
    except (TypeError, ValueError):
        return None
    if not 0 <= value <= 127:
        return None
    return GM_FAMILY_PRESETS.get(value // 8)


def preset_for_name(track_name: str) -> TonePreset | None:
    """按轨名关键字解析音色预设。

    Args:
        track_name: MIDI 轨名，如 "Bass" / "Drum Kit"。

    Returns:
        命中的 TonePreset；未命中返回 None。
    """
    if not track_name:
        return None
    lowered = str(track_name).lower()
    for hint, preset in NAME_HINT_PRESETS.items():
        if hint in lowered:
            return preset
    return None


def resolve_preset(analysis: TrackAnalysis) -> TonePreset:
    """解析一条轨应使用的音色预设。

    优先级：GM program → 轨名关键字 → 默认。

    Args:
        analysis: 轨分析结果。

    Returns:
        TonePreset（保证非 None）。

    Note:
        真实验证数据：`Bass_130406` program=33 → family 4（bass）→ 低通 800Hz + PLUCK；
        `Piano` / `Chords_130406` program=0 → family 0（piano）→ TRIANGLE + PLUCK + 轻混响。
    """
    if analysis.is_drum or analysis.kind == "drum":
        return DRUM_TONE_PRESET
    by_program = preset_for_program(analysis.program)
    if by_program is not None:
        return by_program
    by_name = preset_for_name(analysis.name)
    if by_name is not None:
        return by_name
    return DEFAULT_TONE_PRESET
