"""效果器模块 —— 滤波器 / 失真 / 混响 / 效果链 / 动态 / EQ / 调制"""

from .chain import EffectChain, process_effects
from .filters import apply_lowpass, apply_highpass, apply_bandpass, apply_notch
from .filters import apply_resonant_lpf, apply_resonant_hpf
from .distortion import apply_distortion, apply_bit_crush
from .spatial import apply_simple_reverb, apply_stereo, apply_schroeder_reverb
from .spatial import apply_convolution_reverb, _synthesize_ir, load_ir_wav  # P2
from .dynamics import CompressorParams, apply_compressor, apply_limiter
from .dynamics import MultibandCompressorParams, apply_multiband_compressor  # P2
from .eq import ParametricEQParams, apply_parametric_eq
from .modulation import apply_chorus
from .flanger import apply_flanger, apply_phaser, apply_delay, apply_pingpong_delay, apply_multitap_delay
from .sidechain import (
    SidechainParams, sidechain_duck, sidechain_envelope_method,
    detect_transients, drum_bus_compressor,
)
