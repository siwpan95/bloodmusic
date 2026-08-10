"""核心模块 —— 振荡器 / 包络 / 合成引擎 / 波导物理建模"""

from .constants import SR, BPM_DEFAULT, BEAT_DEFAULT, VOL_SFX, VOL_MUSIC, NORMALIZE_DBFS, DEFAULT_OGG_BITRATE
from .note_utils import note_to_freq, midi_to_freq, NOTES
from .oscillator import (
    OscType, oscillator,
    osc_saw, osc_square, osc_sine, osc_triangle,
    osc_noise_white, osc_noise_pink, osc_noise_brown,
)
from .envelope import EnvShape, ADSRParams, make_envelope
from .voice import SynthVoice, synthesize_voice, LFOParams, LFOTarget
from .fm_synth import FMSynthVoice, synthesize_fm_voice
from .karplus_strong import (
    KSVoice, KarplusStrongSynth, synthesize_ks_voice, KS_PRESETS, KS_PRESETS_BY_NAME,
)
from .granular import (
    GrainCloud, GranularSynth, synthesize_grain_cloud, GrainPreset, GRAIN_PRESETS, GRAIN_PRESETS_BY_NAME,
)
from .wavetable import (
    Wavetable, WavetableOscillator, MultiWavetable,
    InterpolationMode, list_wavetable_presets,
)
from .fm_advanced import (  # P2
    MultiOpFM, FMAlgorithm, FMOpParams,
    create_dx7_bell, create_dx7_epiano, create_dx7_bass,
)
from .waveguide import (
    WaveguideVoice, render_waveguide,
    render_clarinet, render_flute, render_brass, render_saxophone,
    render_waveguide_preset,
)