"""
音乐生成器 —— MusicPattern + DrumPattern + MultiTrackPattern + 渲染引擎
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, TYPE_CHECKING

from scipy.io import wavfile

from ..core.constants import SR
from ..core.note_utils import note_to_freq
from ..core.oscillator import oscillator, OscType
from ..core.envelope import make_envelope, EnvShape
from ..effects.chain import EffectChain
from .humanize import HumanizeParams, apply_humanize_to_sequence

if TYPE_CHECKING:
    from .instrument_pool import SynthEngine


@dataclass
class MusicPattern:
    """音乐模式数据"""

    name: str
    notes: List[Optional[str]]              # 音符名 (None=休止符)
    durations: List[float]                  # 每音持续 (拍)
    octave_shifts: Optional[List[int]] = None  # 八度偏移
    bpm: int = 120
    loop: bool = True

    # ── 音色 ──
    osc_type: OscType = OscType.SINE
    volume: float = 0.18
    env_shape: EnvShape = EnvShape.PAD
    harmonics: List[Tuple[float, float]] = field(default_factory=list)

    # ── 颤音 ──
    vibrato_rate: float = 0.0
    vibrato_depth: float = 0.0

    # ── 效果 ──
    reverb_mix: float = 0.15
    reverb_decay: float = 0.8
    stereo_width: float = 0.3
    lp_filter_hz: Optional[float] = None

    # ── 和弦 ──
    chords: Optional[List[List[str]]] = None  # 和弦列表，如 [["C4","E4","G4"], ["F4","A4","C5"]]

    # ── 人性化 (可选) ──
    humanize_params: Optional["HumanizeParams"] = None  # None=不启用

    # ── 乐器池角色 (可选) ──
    pool_role: Optional[str] = None  # None=非乐器池生成，非 None="melody"|"chord"|"bass"|"drum"|"pad"|"fx"

    # ── 真实合成引擎 (v2.0 全性能压榨) ──
    engine: Optional["SynthEngine"] = None           # 合成引擎类型，None=走基础振荡器
    engine_params: Dict[str, Any] = field(default_factory=dict)  # 引擎专属参数
    automation: Optional[Dict[str, Any]] = None      # 自动化配置 (filter_sweep / volume_curve)

    def __post_init__(self):
        """校验字段一致性"""
        if len(self.notes) != len(self.durations):
            raise ValueError(
                f"MusicPattern '{self.name}': notes 数量 ({len(self.notes)}) "
                f"与 durations 数量 ({len(self.durations)}) 不匹配！"
                f"\n  提示: 每个音符必须对应一个时长，请检查是否遗漏。"
            )
        if self.octave_shifts is not None and len(self.octave_shifts) < len(self.notes):
            raise ValueError(
                f"MusicPattern '{self.name}': octave_shifts 数量 ({len(self.octave_shifts)}) "
                f"少于 notes 数量 ({len(self.notes)})！"
                f"\n  提示: octave_shifts 需要与 notes 一一对应或省略（默认为 0）。"
            )

    def to_motif(self):
        """将 MusicPattern 转换为 Motif，用于主题动机发展。

        Returns:
            Motif 对象，可施加变换后再转回 MusicPattern。
        """
        from .motif import Motif
        return Motif.from_music_pattern(self, name=self.name)


@dataclass
class DrumSoundParams:
    """单个鼓声合成参数"""
    osc_type: OscType = OscType.NOISE_BROWN
    pitch_hz: float = 100.0
    decay: float = 0.15
    volume: float = 0.6
    hp_hz: float = 0.0        # 高通截止
    lp_hz: float = 0.0        # 低通截止


@dataclass
class DrumPattern:
    """鼓点步进序列器"""
    name: str
    steps: int = 16
    bpm: int = 120
    tracks: dict = field(default_factory=dict)  # {"kick": [True,False,...], "snare": [...], "hihat": [...]}
    sounds: dict = field(default_factory=dict)
    loop: bool = True

    def __post_init__(self):
        """校验 tracks 与 sounds 一致性"""
        for track_name, track_steps in self.tracks.items():
            if len(track_steps) != self.steps:
                raise ValueError(
                    f"DrumPattern '{self.name}': track '{track_name}' 步数 ({len(track_steps)}) "
                    f"与 steps ({self.steps}) 不匹配！每个 track 必须恰好有 {self.steps} 步。"
                )
        # 对未在 sounds 中定义的 track 给出友好提示，但不强制报错（使用默认音色）
        missing_sounds = set(self.tracks.keys()) - set(self.sounds.keys())
        if missing_sounds:
            import warnings
            warnings.warn(
                f"DrumPattern '{self.name}': tracks {missing_sounds} 未在 sounds 中定义，将使用默认音色。"
            )


@dataclass
class MultiTrackPattern:
    """多轨音乐模式"""
    name: str
    bpm: int = 120
    loop: bool = True
    music_tracks: list = field(default_factory=list)
    drum_track: Optional[DrumPattern] = None


def _render_single_drum_hit(params: DrumSoundParams, duration: float) -> np.ndarray:
    """合成单个鼓声 hit

    Args:
        params: 鼓声参数
        duration: 持续时间 (秒)
    Returns:
        鼓声音频数组
    """
    n_samp = int(duration * SR)
    if n_samp < 1:
        return np.zeros(1, dtype=np.float64)
    t = np.linspace(0, duration, n_samp, dtype=np.float64)

    if params.osc_type in (OscType.NOISE_WHITE, OscType.NOISE_PINK, OscType.NOISE_BROWN):
        sig = oscillator(t, params.pitch_hz, params.osc_type)
    else:
        sig = oscillator(t, params.pitch_hz, params.osc_type)

    # 指数衰减包络
    env = np.exp(-t / max(params.decay, 0.001))
    sig = sig * env * params.volume

    # 可选滤波
    if params.hp_hz > 0:
        from ..effects.filters import apply_highpass
        sig = apply_highpass(sig, params.hp_hz)
    if params.lp_hz > 0:
        from ..effects.filters import apply_lowpass
        sig = apply_lowpass(sig, params.lp_hz)

    return sig


def render_drum_pattern(pattern: DrumPattern, duration_sec: float) -> np.ndarray:
    """渲染鼓点模式为音频数组。

    Args:
        pattern: 鼓点模式
        duration_sec: 总时长 (秒)
    Returns:
        鼓点音频数组 (float64)
    """
    beat_dur = 60.0 / pattern.bpm
    step_dur = beat_dur / 4  # 16 分音符
    n_samples = int(duration_sec * SR)
    result = np.zeros(n_samples, dtype=np.float64)

    current_step = 0
    pos = 0
    while pos < n_samples:
        for track_name, steps in pattern.tracks.items():
            if current_step < len(steps) and steps[current_step]:
                sound = pattern.sounds.get(track_name, DrumSoundParams())
                hit = _render_single_drum_hit(sound, step_dur * 1.5)
                end = min(pos + len(hit), n_samples)
                result[pos:end] += hit[:end - pos]

        current_step = (current_step + 1) % pattern.steps
        pos += int(step_dur * SR)
        if not pattern.loop and current_step == 0:
            break

    return result


def render_pattern_to_array(pattern: MusicPattern, duration_sec: float) -> np.ndarray:
    """将 MusicPattern 渲染为音频数组（不写入文件）。

    Args:
        pattern: 音乐模式
        duration_sec: 目标时长 (秒)
    Returns:
        音频数组 (float64)
    """
    beat_dur = 60.0 / pattern.bpm
    total_beats = sum(pattern.durations)
    loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

    octaves = pattern.octave_shifts or [0] * len(pattern.notes)
    all_notes = []
    for _ in range(loops):
        for i, note in enumerate(pattern.notes):
            dur = pattern.durations[i] * beat_dur
            oct_v = octaves[i] if i < len(octaves) else 0
            all_notes.append((note, dur, oct_v))

    samples_list = []
    for idx, (note, dur, oct_v) in enumerate(all_notes):
        n_samp = int(dur * SR)
        if n_samp < 1:
            n_samp = 1
        t = np.linspace(0, dur, n_samp, dtype=np.float64)
        if note is None:
            sig = np.zeros(n_samp)
        else:
            f = note_to_freq(note) * (2 ** oct_v)
            sig = oscillator(t, f, pattern.osc_type)
            for h_mult, h_amp in pattern.harmonics:
                sig += oscillator(t, f * h_mult, pattern.osc_type) * h_amp
            if pattern.vibrato_depth > 0:
                vib_env = make_envelope(n_samp, EnvShape.PAD)
                vib = 1.0 + (pattern.vibrato_depth / 12) * np.sin(2 * np.pi * pattern.vibrato_rate * t) * vib_env
                sig = oscillator(t, f * vib, pattern.osc_type)
                for h_mult, h_amp in pattern.harmonics:
                    sig += oscillator(t, f * vib * h_mult, pattern.osc_type) * h_amp
            env = make_envelope(n_samp, pattern.env_shape)
            sig = sig * env * pattern.volume

        # 和弦叠加
        if pattern.chords is not None:
            chord_idx = idx % len(pattern.chords) if pattern.chords else -1
            if 0 <= chord_idx < len(pattern.chords):
                chord_notes = pattern.chords[chord_idx]
                for cn in chord_notes:
                    cf = note_to_freq(cn)
                    chord_sig = oscillator(t, cf, pattern.osc_type)
                    for h_mult, h_amp in pattern.harmonics:
                        chord_sig += oscillator(t, cf * h_mult, pattern.osc_type) * h_amp
                    env = make_envelope(n_samp, pattern.env_shape)
                    sig += chord_sig * env * pattern.volume * 0.5

        samples_list.append(sig)

    if not samples_list:
        return np.zeros(int(duration_sec * SR))

    full_signal = np.concatenate(samples_list)
    # 截断或循环到目标时长
    target_len = int(duration_sec * SR)
    if len(full_signal) < target_len:
        reps = int(np.ceil(target_len / len(full_signal)))
        full_signal = np.tile(full_signal, reps)
    full_signal = full_signal[:target_len]

    # ── 人性化处理 ──
    if pattern.humanize_params is not None and pattern.humanize_params.is_active:
        # all_notes 中的 dur 已经是秒了
        all_durations_sec = [dur for _, dur, _ in all_notes]
        # 展开到目标时长所需的循环
        note_durs_sec = []
        while sum(note_durs_sec) < duration_sec:
            note_durs_sec.extend(all_durations_sec)
        full_signal = apply_humanize_to_sequence(
            full_signal, note_durs_sec, pattern.humanize_params
        )
        # 确保长度正确（人性化可能略微改变长度）
        if len(full_signal) < target_len:
            full_signal = np.pad(full_signal, (0, target_len - len(full_signal)))
        full_signal = full_signal[:target_len]

    return full_signal


def render_multi_track(pattern: MultiTrackPattern, duration_sec: float) -> np.ndarray:
    """渲染多轨音乐为音频数组。

    Args:
        pattern: 多轨模式
        duration_sec: 目标时长 (秒)
    Returns:
        混合音频数组 (float32)
    """
    target_len = int(duration_sec * SR)
    mix_buffer = np.zeros(target_len, dtype=np.float64)

    # 渲染每个音乐轨道
    for track in pattern.music_tracks:
        track_sig = render_pattern_to_array(track, duration_sec)
        # 应用轨道效果链
        chain = EffectChain(
            reverb_mix=track.reverb_mix,
            reverb_decay=track.reverb_decay,
            stereo_width=0.0,  # 多轨混合时不做立体声，最后统一处理
            lp_filter_hz=track.lp_filter_hz,
        )
        from ..effects.chain import process_effects
        track_sig = process_effects(track_sig, chain)
        min_len = min(len(track_sig), target_len)
        mix_buffer[:min_len] += track_sig[:min_len]

    # 渲染鼓点轨道
    if pattern.drum_track is not None:
        drum_sig = render_drum_pattern(pattern.drum_track, duration_sec)
        min_len = min(len(drum_sig), target_len)
        mix_buffer[:min_len] += drum_sig[:min_len]

    # 归一化 + 限幅
    from ..core.constants import NORMALIZE_DBFS
    target_amp = 10 ** (NORMALIZE_DBFS / 20.0)
    peak = np.max(np.abs(mix_buffer))
    if peak > 0:
        mix_buffer = mix_buffer * (target_amp / peak)
    mix_buffer = np.clip(mix_buffer, -1.0, 1.0)

    return mix_buffer.astype(np.float32)


def generate_music_wav(
    pattern: MusicPattern,
    output_path: str,
    duration_sec: Optional[float] = None,
) -> str:
    """将 MusicPattern 渲染为 WAV 文件。

    Args:
        pattern: 音乐模式
        output_path: 输出 .wav 路径
        duration_sec: 总时长 (秒)，None = 自动 (pattern × 2)
    Returns:
        输出文件路径
    """
    beat_dur = 60.0 / pattern.bpm
    total_beats = sum(pattern.durations)
    loops = (2 if pattern.loop else 1) if duration_sec is None else \
            max(1, int(duration_sec / (total_beats * beat_dur)))

    octaves = pattern.octave_shifts or [0] * len(pattern.notes)

    all_notes: list[tuple] = []
    for _ in range(loops):
        for i, note in enumerate(pattern.notes):
            dur = pattern.durations[i] * beat_dur
            oct_v = octaves[i] if i < len(octaves) else 0
            all_notes.append((note, dur, oct_v))

    # 逐音合成
    samples_list: list[np.ndarray] = []
    for idx, (note, dur, oct_v) in enumerate(all_notes):
        n_samp = int(dur * SR)
        t = np.linspace(0, dur, n_samp, dtype=np.float64)

        if note is None:
            sig = np.zeros(n_samp)
        else:
            f = note_to_freq(note) * (2 ** oct_v)
            sig = oscillator(t, f, pattern.osc_type)

            for h_mult, h_amp in pattern.harmonics:
                sig += oscillator(t, f * h_mult, pattern.osc_type) * h_amp

            if pattern.vibrato_depth > 0:
                vib_env = make_envelope(n_samp, EnvShape.PAD)
                vib = 1.0 + (pattern.vibrato_depth / 12) * np.sin(
                    2 * np.pi * pattern.vibrato_rate * t) * vib_env
                sig = oscillator(t, f * vib, pattern.osc_type)
                for h_mult, h_amp in pattern.harmonics:
                    sig += oscillator(t, f * vib * h_mult, pattern.osc_type) * h_amp

            env = make_envelope(n_samp, pattern.env_shape)
            sig = sig * env * pattern.volume

        # 和弦叠加
        if pattern.chords is not None:
            chord_idx = idx % len(pattern.chords) if pattern.chords else -1
            if 0 <= chord_idx < len(pattern.chords):
                chord_notes = pattern.chords[chord_idx]
                for cn in chord_notes:
                    cf = note_to_freq(cn)
                    chord_sig = oscillator(t, cf, pattern.osc_type)
                    for h_mult, h_amp in pattern.harmonics:
                        chord_sig += oscillator(t, cf * h_mult, pattern.osc_type) * h_amp
                    env = make_envelope(n_samp, pattern.env_shape)
                    sig += chord_sig * env * pattern.volume * 0.5

        samples_list.append(sig)

    # 拼接
    full_signal = np.concatenate(samples_list) if samples_list else np.zeros(SR)

    # 效果链
    from ..effects.chain import process_effects
    chain = EffectChain(
        reverb_mix=pattern.reverb_mix,
        reverb_decay=pattern.reverb_decay,
        stereo_width=pattern.stereo_width,
        lp_filter_hz=pattern.lp_filter_hz,
    )
    full_signal = process_effects(full_signal, chain)

    # 归一化 + 限幅
    from ..core.constants import NORMALIZE_DBFS
    target_amp = 10 ** (NORMALIZE_DBFS / 20.0)
    peak = np.max(np.abs(full_signal))
    if peak > 0:
        full_signal = full_signal * (target_amp / peak)
    full_signal = np.clip(full_signal, -1.0, 1.0)

    # 写入 WAV
    final_int16 = np.clip(full_signal * 32767, -32768, 32767).astype(np.int16)
    wavfile.write(output_path, SR, final_int16)
    return output_path
