"""SFX 音效模块 —— 预设库 + 分层音效 + 模拟鼓合成"""

from .presets import (
    UI_FX_PRESETS, CARD_FX_PRESETS,
    COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
)
from .layered import (
    ImpactLayer, BodyLayer, TailLayer, LayeredSFX,
    LayeredSFXSynth, synthesize_layered_sfx,
    LayeredSFXPreset, LAYERED_SFX_PRESETS, LAYERED_SFX_BY_NAME,
)
from .drum_synth import (
    Kick808Params, Snare808Params, Hihat808Params,
    synthesize_808_kick, synthesize_808_snare, synthesize_808_hihat,
    synthesize_808_open_hihat, synthesize_808_clap,
    DrumLayer, layer_drums, DrumKit808, create_808_kit,
    KICK_808_PRESETS, SNARE_808_PRESETS,
    # 原声鼓 (P1)
    TomParams, synthesize_tom, TOM_PRESETS,
    CrashParams, synthesize_crash, ShakerParams, synthesize_shaker,
    AcousticSnareParams, synthesize_acoustic_snare,
    AcousticKickParams, synthesize_acoustic_kick,
)
