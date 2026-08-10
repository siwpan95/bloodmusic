"""
Bass 合成器 —— 专门优化低频的合成引擎
========================================

提供四种 Bass 类型，基于现有振荡器/FM/波表引擎：

  - Sub Bass:  纯正弦波，30-80Hz 超低频，适合 Trap/Hip-Hop
  - FM Bass:   FM 合成器的金属质感低音，类似 DX7 E.Bass
  - Acid Bass: 锯齿波 + 谐振低通，类似 TB-303
  - Pluck Bass: 快速衰减的低频拨弦

用法:
    >>> from bloodmusic.music.bass import BassSynth, render_bass_pattern
    >>> bass = BassSynth.preset("sub", note="C2")
    >>> audio = bass.render(2.0)  # 2 秒音频
    >>> # 或从 MusicPattern 批量渲染
    >>> pattern = MusicPattern(name="bass", notes=["C2","C2","F2","G2"], ...)
    >>> audio = render_bass_pattern(pattern, BassSynth.preset("sub"))
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from ..core.constants import SR
from ..core.oscillator import oscillator, OscType
from ..core.envelope import make_envelope, EnvShape, ADSRParams
from ..core.note_utils import note_to_freq
from ..effects.chain import EffectChain
from ..effects.filters import apply_resonant_lpf, apply_lowpass
from ..effects.distortion import apply_distortion
from .pattern import MusicPattern


# ═══════════════════════════════════════════════════════════════════════
# Bass 合成参数
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BassSynth:
    """Bass 合成器参数定义。

    Args:
        preset_name: 预设名 ("sub" | "fm" | "acid" | "pluck")
        note: 音符 (如 "C2", "E1") — 会自动转为频率
        freq: 直接指定频率 (Hz), None 则从 note 转换
        osc_type: 振荡器类型
        volume: 音量 0~1
        decay: 衰减时间 (秒) — Sub/FM 使用
        fm_depth: FM 调制深度 — 仅 FM Bass
        fm_ratio: FM 调制器频率比 — 仅 FM Bass
        filter_cutoff: 低通截止频率 — Acid Bass 使用
        filter_q: 滤波器谐振 Q — Acid Bass 使用
        distortion: 失真量 0~1 — Acid Bass 可加
        env_shape: 包络形状
    """
    preset_name: str = "sub"
    note: str = "C2"
    freq: Optional[float] = None
    osc_type: OscType = OscType.SINE
    volume: float = 0.8
    decay: float = 1.0           # Sub/FM: 音符持续衰减
    fm_depth: float = 80.0       # FM: 调制深度
    fm_ratio: float = 1.0        # FM: 调制器频率比 (1.0=同频, 2.0=八度)
    filter_cutoff: float = 800.0 # Acid: 滤波器截止频率
    filter_q: float = 3.0        # Acid: 谐振 Q
    distortion: float = 0.0      # Acid: 失真
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    adsr: Optional[ADSRParams] = None
    effect_chain: Optional[EffectChain] = None

    @property
    def frequency(self) -> float:
        """获取实际频率"""
        if self.freq is not None:
            return self.freq
        return note_to_freq(self.note)

    def render(self, duration_sec: float) -> np.ndarray:
        """渲染该 Bass 声音为音频。

        Args:
            duration_sec: 持续时间 (秒)

        Returns:
            float64 音频数组
        """
        n_samples = int(duration_sec * SR)
        if n_samples < 1:
            return np.zeros(1)
        t = np.linspace(0, duration_sec, n_samples, dtype=np.float64)
        freq = self.frequency

        if self.preset_name == "sub":
            return self._render_sub(n_samples, t, freq)
        elif self.preset_name == "fm":
            return self._render_fm(n_samples, t, freq)
        elif self.preset_name == "acid":
            return self._render_acid(n_samples, t, freq)
        elif self.preset_name == "pluck":
            return self._render_pluck(n_samples, t, freq)
        else:
            # fallback to sub
            return self._render_sub(n_samples, t, freq)

    def _render_sub(self, n: int, t: np.ndarray, freq: float) -> np.ndarray:
        """Sub Bass: 纯正弦 + 温和的二次谐波"""
        sig = oscillator(t, freq, OscType.SINE)
        # 加微量二次谐波增厚
        sig += oscillator(t, freq * 2, OscType.SINE) * 0.15
        # 加三次谐波增加在小型扬声器上的可听度
        sig += oscillator(t, freq * 3, OscType.SINE) * 0.05

        # 包络: 默认快速起音 + 持续
        if self.adsr is not None:
            env = make_envelope(n, EnvShape.PERCUSSIVE, self.adsr)
        else:
            attack_samp = int(n * 0.01)
            env = np.ones(n)
            env[:attack_samp] = np.linspace(0, 1, attack_samp)
            decay_start = int(n * 0.85)
            if decay_start < n:
                env[decay_start:] = np.linspace(1, 0, n - decay_start)

        sig = sig * env * self.volume

        if self.effect_chain is not None:
            from ..effects.chain import process_effects
            sig = process_effects(sig, self.effect_chain)

        return np.clip(sig, -1.0, 1.0)

    def _render_fm(self, n: int, t: np.ndarray, freq: float) -> np.ndarray:
        """FM Bass: 正弦载波 + 正弦调制器 → 金属质感"""
        mod_freq = freq * self.fm_ratio
        modulator = oscillator(t, mod_freq, OscType.SINE)

        # FM: carrier = sin(2π * (freq + fm_depth * modulator))
        mod_f = freq + self.fm_depth * modulator
        carrier = np.sin(2.0 * np.pi * np.cumsum(mod_f) / SR)

        # 包络
        attack_samp = int(n * 0.005)
        env = np.ones(n)
        env[:attack_samp] = np.linspace(0, 1, attack_samp)
        decay_start = int(n * 0.7)
        if decay_start < n:
            env[decay_start:] = np.linspace(1, 0, n - decay_start)

        sig = carrier * env * self.volume

        if self.effect_chain is not None:
            from ..effects.chain import process_effects
            sig = process_effects(sig, self.effect_chain)

        return np.clip(sig, -1.0, 1.0)

    def _render_acid(self, n: int, t: np.ndarray, freq: float) -> np.ndarray:
        """Acid Bass: 锯齿波 → 谐振低通 (类似 TB-303)"""
        # 锯齿波基频
        sig = oscillator(t, freq, OscType.SAW)
        # 加入方波分量丰富泛音
        sig += oscillator(t, freq, OscType.SQUARE) * 0.3

        # 谐振低通滤波
        sig = apply_resonant_lpf(sig, self.filter_cutoff, self.filter_q)

        # 失真增强侵略性
        if self.distortion > 0:
            sig = apply_distortion(sig, self.distortion)

        # 包络: 打击乐风格
        env = make_envelope(n, EnvShape.PERCUSSIVE)
        sig = sig * env * self.volume

        if self.effect_chain is not None:
            from ..effects.chain import process_effects
            sig = process_effects(sig, self.effect_chain)

        return np.clip(sig, -1.0, 1.0)

    def _render_pluck(self, n: int, t: np.ndarray, freq: float) -> np.ndarray:
        """Pluck Bass: 快速衰减的低频拨弦"""
        sig = oscillator(t, freq, OscType.TRIANGLE)
        sig += oscillator(t, freq * 2, OscType.SINE) * 0.3

        # Karplus-Strong 风格的快速衰减包络
        env = np.exp(-t * (8.0 / max(self.decay, 0.05)))
        attack_samp = int(n * 0.003)
        env[:attack_samp] = np.linspace(0, 1, attack_samp)
        sig = sig * env * self.volume

        # 轻微低通，去掉刺耳高频
        sig = apply_lowpass(sig, freq * 4, SR)

        if self.effect_chain is not None:
            from ..effects.chain import process_effects
            sig = process_effects(sig, self.effect_chain)

        return np.clip(sig, -1.0, 1.0)

    @staticmethod
    def preset(name: str, note: str = "C2", **kwargs) -> "BassSynth":
        """快捷创建预设 Bass 音色。

        Args:
            name: "sub" | "fm" | "acid" | "pluck"
            note: 音符名
            **kwargs: 覆盖默认参数

        Returns:
            BassSynth 实例
        """
        presets = {
            "sub": BassSynth(
                preset_name="sub", note=note,
                osc_type=OscType.SINE, volume=0.85,
                decay=1.5,
            ),
            "fm": BassSynth(
                preset_name="fm", note=note,
                osc_type=OscType.SINE, volume=0.75,
                fm_depth=120.0, fm_ratio=1.5, decay=1.2,
            ),
            "acid": BassSynth(
                preset_name="acid", note=note,
                osc_type=OscType.SAW, volume=0.7,
                filter_cutoff=600.0, filter_q=3.5,
                distortion=0.15,
            ),
            "pluck": BassSynth(
                preset_name="pluck", note=note,
                osc_type=OscType.TRIANGLE, volume=0.8,
                decay=0.3, env_shape=EnvShape.PLUCK,
            ),
        }

        bass = presets.get(name, presets["sub"])
        # 覆盖用户指定的参数
        for k, v in kwargs.items():
            if hasattr(bass, k):
                setattr(bass, k, v)
        return bass


# ═══════════════════════════════════════════════════════════════════════
# 从 MusicPattern 批量渲染 Bass
# ═══════════════════════════════════════════════════════════════════════

def render_bass_pattern(
    pattern: MusicPattern,
    bass: BassSynth,
    duration_sec: float,
) -> np.ndarray:
    """逐音符渲染 Bass 轨道音频。

    按 MusicPattern 中的 notes/durations 逐个音符合成 Bass 声音。

    Args:
        pattern: 音乐模式 (bass line)
        bass: BassSynth 音色 (note 字段会被逐个覆盖)
        duration_sec: 总时长 (秒)

    Returns:
        float64 音频数组
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

    target_len = int(duration_sec * SR)
    result = np.zeros(target_len, dtype=np.float64)
    pos = 0

    for note, dur, oct_v in all_notes:
        if note is not None:
            # 计算有八度偏移的频率
            f = note_to_freq(note) * (2 ** oct_v)
            bass_note = BassSynth(
                preset_name=bass.preset_name,
                freq=f,
                osc_type=bass.osc_type,
                volume=bass.volume,
                decay=bass.decay,
                fm_depth=bass.fm_depth,
                fm_ratio=bass.fm_ratio,
                filter_cutoff=bass.filter_cutoff,
                filter_q=bass.filter_q,
                distortion=bass.distortion,
                env_shape=bass.env_shape,
                adsr=bass.adsr,
                effect_chain=bass.effect_chain,
            )
            note_audio = bass_note.render(dur)
        else:
            # 休止符
            note_audio = np.zeros(int(dur * SR))

        end_pos = min(pos + len(note_audio), target_len)
        result[pos:end_pos] += note_audio[:end_pos - pos]
        pos = end_pos

        if pos >= target_len:
            break

    return result
