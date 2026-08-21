"""
BloodMusic — 程序化游戏音频合成引擎
======================================

通用音频素材处理程序，为游戏开发生成 BGM + SFX。

架构分层：
  core/      — 振荡器 / 包络 / SynthVoice / FM 合成引擎
  effects/   — 滤波器 / 失真 / 混响 / 效果链 / 动态 / EQ / 调制
  music/     — MusicPattern + DrumPattern + 多轨 + 琶音 + 音阶 + 预设
  sfx/       — 音效预设库 (UI / 卡牌 / 战斗 / 系统)
  export/    — 批量多格式导出 (WAV/OGG/FLAC)
  playback/  — sounddevice 实时预览
  gui/       — Tkinter 工作站界面 (可选)

基础用法:
  >>> from bloodmusic import SynthVoice, synthesize_voice, OscType, EnvShape
  >>> voice = SynthVoice(freq=440, osc_type=OscType.SINE, duration=0.3)
  >>> audio = synthesize_voice(voice)  # np.ndarray, float32

批量导出:
  >>> from bloodmusic import AudioBatchExporter
  >>> AudioBatchExporter("./output").export_everything()

CLI:
  $ python -m bloodmusic --help
  $ python -m bloodmusic batch --output ./audio --duration 30 --format ogg
"""

__version__ = "2.0.0"

# ── 核心引擎 ──
from .core import (
    # 常量
    SR, BPM_DEFAULT, BEAT_DEFAULT, VOL_SFX, VOL_MUSIC,
    NORMALIZE_DBFS, DEFAULT_OGG_BITRATE,
    # 音符
    note_to_freq, midi_to_freq, NOTES,
    # 振荡器
    OscType, oscillator,
    osc_saw, osc_square, osc_sine, osc_triangle,
    osc_noise_white, osc_noise_pink, osc_noise_brown,
    # 包络
    EnvShape, ADSRParams, make_envelope,
    # 合成
    SynthVoice, synthesize_voice,
    # 新增核心
    LFOParams, LFOTarget,
    FMSynthVoice, synthesize_fm_voice,
    KSVoice, KarplusStrongSynth, synthesize_ks_voice,
    KS_PRESETS, KS_PRESETS_BY_NAME,
    GrainCloud, GranularSynth, synthesize_grain_cloud,
    GrainPreset, GRAIN_PRESETS, GRAIN_PRESETS_BY_NAME,
    # 波表合成
    Wavetable, WavetableOscillator, MultiWavetable,
    InterpolationMode, list_wavetable_presets,
)

# ── 效果器 ──
from .effects import (
    EffectChain, process_effects,
    apply_lowpass, apply_highpass,
    apply_bandpass, apply_notch,
    apply_distortion, apply_bit_crush,
    apply_simple_reverb, apply_stereo,
    apply_schroeder_reverb,
    apply_compressor, apply_limiter, CompressorParams,
    apply_parametric_eq, ParametricEQParams,
    apply_chorus,
    # 新增效果
    apply_flanger, apply_phaser, apply_delay,
    apply_pingpong_delay, apply_multitap_delay,
    SidechainParams, sidechain_duck, sidechain_envelope_method,
    detect_transients, drum_bus_compressor,
)

# ── 音乐 ──
from .music import (
    MusicPattern, generate_music_wav,
    DrumSoundParams, DrumPattern, render_drum_pattern,
    MultiTrackPattern, render_pattern_to_array, render_multi_track,
    Arpeggiator, ArpMode, generate_arpeggio,
    Scale, SCALE_INTERVALS,
    MENU_MUSIC, BATTLE_LOW_MUSIC, BATTLE_HIGH_MUSIC,
    EVENT_MUSIC, MERCHANT_MUSIC, CAMPFIRE_MUSIC,
    BOSS_FIGHT_MUSIC, DUNGEON_MUSIC, TAVERN_MUSIC,
    FOREST_MUSIC, PUZZLE_MUSIC, TITLE_SCREEN_MUSIC,
    GAME_OVER_MUSIC, CREDITS_MUSIC, PLATFORMER_MUSIC,
    ALL_MUSIC_PATTERNS,
    # 马尔可夫链旋律生成
    MelodyNote, Melody, MarkovChain, MelodyGenerator, MelodyGeneratorConfig,
    melody_from_note_string, melody_from_music_pattern,
    create_default_chain, SAMPLE_MELODIES,
    # 循环微变化
    MicroVariation, MicroVariationProcessor,
    # 情绪曲线
    EmotionCurve, EmotionMapper, MusicEmotionParams, ChordProgressionGenerator,
    # 欧几里得节奏
    euclidean_rhythm, euclidean_phases, generate_euclidean_drum_pattern,
    EuclideanPreset, EUCLIDEAN_PRESETS, EUCLIDEAN_PRESETS_BY_NAME,
    get_euclidean_tracks, list_euclidean_presets,
    # 编曲系统
    TrackChannel, Section, Transition, SongArrangement, render_song,
    create_song_template,
    # 自动化
    AutomationPoint, AutomationLane,
    apply_filter_sweep, apply_volume_automation, apply_pan_automation,
    build_up_lowpass, fade_in_out, auto_pan_sine, drop_filter_resonance,
    # Bass 合成
    BassSynth, render_bass_pattern,
    # 和声
    HarmonyVoice, generate_parallel_harmony, generate_diatonic_harmony,
    generate_chordal_harmony, voice_leading, render_harmony_tracks,
    # 人性化引擎 (NEW)
    HumanizeParams, apply_humanize_to_sequence,
    HUMANIZE_NONE, HUMANIZE_SUBTLE, HUMANIZE_NATURAL,
    HUMANIZE_GROOVY, HUMANIZE_HUMAN,
    # 乐器库 (NEW)
    InstrumentPreset, get_instrument, INSTRUMENTS,
    # MIDI I/O (NEW)
    music_pattern_to_midi, midi_to_patterns, song_to_midi,
)

# ── 音效 ──
from .sfx import (
    UI_FX_PRESETS, CARD_FX_PRESETS,
    COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
    ImpactLayer, BodyLayer, TailLayer, LayeredSFX,
    LayeredSFXSynth, synthesize_layered_sfx,
    LAYERED_SFX_PRESETS, LAYERED_SFX_BY_NAME,
    # 模拟鼓合成
    Kick808Params, Snare808Params, Hihat808Params,
    synthesize_808_kick, synthesize_808_snare, synthesize_808_hihat,
    synthesize_808_open_hihat, synthesize_808_clap,
    DrumLayer, layer_drums, DrumKit808, create_808_kit,
    KICK_808_PRESETS, SNARE_808_PRESETS,
)

# ── 导出 ──
from .export import (
    AudioBatchExporter, export_audio,
    export_music_to_midi, export_drums_to_midi,
    export_euclidean_drums_to_midi, export_multi_track_to_midi,
    MIDI_DRUM_MAP,
)

# ── 播放 ──
from .playback import PreviewPlayer

# ── 互动音乐引擎 (可选) ──
from .interactive import (
    MusicState, StateParams, TransitionParams, MusicStateMachine,
    LayerRole, MusicLayer, LayerMixerConfig, VerticalLayerMixer,
    SegmentCategory, MusicSegment, BranchRule, HorizontalSequencer,
    ParameterMapping, MappingSet, ParameterMapper,
    COMBAT_MAPPINGS, EXPLORE_MAPPINGS, STEALTH_MAPPINGS,
    EngineConfig, RealtimeMusicEngine,
)

# ── 简单音效 ──
from .simple_sfx import (
    SimpleSFX,
    play,
    export,
    export_game_pack,
    pygame_sound,
    generate,
)

# ── GUI (可选) ──
from .gui import GameAudioWorkstationGUI, _HAS_GUI as _HAS_GUI

