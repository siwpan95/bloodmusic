"""音乐模块 —— MusicPattern + 预设库 + DrumPattern + 多轨 + 琶音 + 音阶"""

from .pattern import (
    MusicPattern, generate_music_wav,
    DrumSoundParams, DrumPattern, render_drum_pattern,
    MultiTrackPattern, render_pattern_to_array, render_multi_track,
)
from .presets import (
    MENU_MUSIC, BATTLE_LOW_MUSIC, BATTLE_HIGH_MUSIC,
    EVENT_MUSIC, MERCHANT_MUSIC, CAMPFIRE_MUSIC,
    BOSS_FIGHT_MUSIC, DUNGEON_MUSIC, TAVERN_MUSIC,
    FOREST_MUSIC, PUZZLE_MUSIC, TITLE_SCREEN_MUSIC,
    GAME_OVER_MUSIC, CREDITS_MUSIC, PLATFORMER_MUSIC,
    ALL_MUSIC_PATTERNS,
    TRAP_DRUMS, BOOM_BAP_DRUMS, LOFI_DRUMS, EDM_DRUMS,
    BATTLE_DRUMS, AMBIENT_DRUMS, DRUM_ONLY, DRUM_PRESETS,
    LOFI_CHAIN, TRAP_CHAIN, AMBIENT_CHAIN, EDM_CHAIN,
    BATTLE_CHAIN, CLEAN_MASTER, SUBTLE_MASTER, EFFECT_PRESETS,
    TRAP_MELODY, TRAP_PAD, LOFI_MELODY, BOOM_BAP_MELODY,
    EDM_LEAD, EDM_CHORDS, BATTLE_MELODY, AMBIENT_MELODY, MELODY_PRESETS,
    TRAP_BASS, BOOM_BAP_BASS, LOFI_BASS, EDM_BASS,
    BATTLE_BASS, AMBIENT_BASS, BASS_PRESETS,
    STYLE_KITS,
)
from .arpeggiator import Arpeggiator, ArpMode, generate_arpeggio
from .scale import Scale, SCALE_INTERVALS, CHORD_PROGRESSIONS, list_scales, list_progressions
from .markov import (
    MelodyNote, Melody, MarkovChain, MelodyGenerator, MelodyGeneratorConfig,
    melody_from_note_string, melody_from_music_pattern,
    create_default_chain, SAMPLE_MELODIES,
)
from .micro_variation import (
    MicroVariation, MicroVariationProcessor,
)
from .emotion import (
    EmotionCurve, EmotionMapper, MusicEmotionParams, ChordProgressionGenerator,
)
from .euclidean import (
    euclidean_rhythm, euclidean_phases, generate_euclidean_drum_pattern,
    EuclideanPreset, EUCLIDEAN_PRESETS, EUCLIDEAN_PRESETS_BY_NAME,
    get_euclidean_tracks, list_euclidean_presets,
)
from .arrangement import (
    TrackChannel, Section, Transition, SongArrangement,
    MixBus, SongMixer, render_song, create_song_template,
)
from .automation import (
    AutomationPoint, AutomationLane, AutomationTrack,
    apply_filter_sweep, apply_volume_automation, apply_pan_automation,
    build_up_lowpass, fade_in_out, auto_pan_sine, drop_filter_resonance,
    TempoLane,  # P1
)
from .bass import (
    BassSynth, render_bass_pattern,
)
from .harmony import (
    HarmonyVoice, generate_parallel_harmony, generate_diatonic_harmony,
    generate_chordal_harmony, voice_leading, render_harmony_tracks,
)
from .sampler import (
    Sample, SamplePad, PadSlot,
    load_sample, play_sample, render_pad_sequence, render_sampler_pattern,
)
from .humanize import (
    HumanizeParams, apply_humanize_to_note, apply_humanize_to_sequence,
    HUMANIZE_NONE, HUMANIZE_SUBTLE, HUMANIZE_NATURAL, HUMANIZE_GROOVY, HUMANIZE_HUMAN,
)
from .instruments import (
    InstrumentPreset, get_instrument, get_by_gm_program,
    list_by_category, list_all_categories, INSTRUMENTS,
)
from .midi_io import (
    music_pattern_to_midi, drum_pattern_to_midi,
    midi_to_patterns, song_to_midi,
)
from .motif import (
    Motif, MotifEvent, DevelopmentPreset,
    note_to_semitones, semitones_to_note,
)
from .loop_utils import (
    zero_crossing_detect, find_loop_points, seamless_splice,
    make_loopable, loop_game_bgm, auto_loop, check_loop_quality,
)