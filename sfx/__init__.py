"""SFX 音效模块 —— 预设库 + 分层音效 + 模拟鼓合成 + Riser/Transition FX"""

from .presets import (
    UI_FX_PRESETS, CARD_FX_PRESETS,
    COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
    GAME_FX_PRESETS,
)
from .serialize import (
    voice_to_dict, voice_from_dict,
    voice_to_json, voice_from_json,
    voice_to_compact, voice_from_compact,
)
from .mutate import (
    mutate_voice, randomize_voice, mutate_preset,
    get_preset, ALL_PRESETS,
)
from .layered import (
    ImpactLayer, BodyLayer, TailLayer, LayeredSFX,
    LayeredSFXSynth, synthesize_layered_sfx,
    LayeredSFXPreset, LAYERED_SFX_PRESETS, LAYERED_SFX_BY_NAME,
    mix_voices,
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
from .riser import (
    RiserVoice, ImpactVoice, BraamVoice, RiserSynth,
    render_riser, riser_transition, impact_hit, build_and_drop,
)