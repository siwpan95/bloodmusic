"""
Riser / Transition FX 合成器 — 电子音乐与影视配乐的过渡音效
==========================================================

提供 EDM / 影视配乐中标志性的过渡音效：
  - noise_riser:   白噪声谐振低通扫频（最常用）
  - tonal_riser:   音高扫频上升
  - impact:        重击（sub drop + noise burst + reverb tail）
  - downlifter:    下沉音效（riser 反向）
  - braam:         影视低音铜管冲击

并与 arrangement.py 的 Transition 系统集成（新增 type="fx"）。

用法:
    >>> from bloodmusic.sfx.riser import RiserSynth, render_riser
    >>> audio = render_riser("noise_riser", duration_sec=2.0)
    >>> riser = RiserSynth.preset("edm_build")
    >>> audio = riser.render(2.0)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal
import numpy as np

from ..core.constants import SR
from ..core.oscillator import oscillator, OscType
from ..effects.filters import apply_lowpass, apply_highpass
from ..effects.spatial import apply_simple_reverb, apply_schroeder_reverb
from ..effects.distortion import apply_distortion


# ═══════════════════════════════════════════════════════════════════════
# RiserVoice — 单个 riser 音色参数
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class RiserVoice:
    """Riser 音色定义参数"""
    # 时长
    duration_sec: float = 2.0

    # ── 频率范围 ──
    start_freq: float = 200.0       # 起始频率 (Hz)
    end_freq: float = 12000.0       # 结束频率 (Hz)

    # ── 曲线类型 ──
    curve: str = "exponential"      # "linear" | "exponential" | "logarithmic"
    q_resonance: float = 2.0        # 谐振 Q 值 (0.5~20+)

    # ── 层叠 ──
    noise_type: str = "white"       # "white" | "pink" | "brown"
    sine_layers: int = 0            # 叠加正弦波层数 (0=纯噪声)
    octave_spread: float = 1.0      # 正弦波八度扩散
    detune_cents: float = 5.0       # 正弦波微失谐

    # ── 音量包络 ──
    volume: float = 0.7
    fade_in_sec: float = 0.05
    fade_out_sec: float = 0.1

    # ── 效果 ──
    reverb_mix: float = 0.3
    reverb_decay: float = 1.5
    distortion: float = 0.0         # 失真量 (0~1)

    def _freq_at(self, t: float, total: float) -> float:
        """计算在时间 t 处的频率值"""
        if total <= 0:
            return self.end_freq
        ratio = max(0.0, min(1.0, t / total))

        if self.curve == "exponential":
            # 对数频率扫频 (听感均匀)
            log_start = np.log2(max(self.start_freq, 1.0))
            log_end = np.log2(max(self.end_freq, 1.0))
            return 2.0 ** (log_start + (log_end - log_start) * ratio)
        elif self.curve == "logarithmic":
            # 反指数 (快速上升后减速)
            return self.start_freq + (self.end_freq - self.start_freq) * np.sqrt(ratio)
        else:  # linear
            return self.start_freq + (self.end_freq - self.start_freq) * ratio


# ═══════════════════════════════════════════════════════════════════════
# ImpactVoice — 重击音色参数
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ImpactVoice:
    """Impact 重击音色参数"""
    # Sub drop
    sub_freq: float = 45.0          # 低频频率 (Hz)
    sub_duration: float = 1.5       # Sub 时长 (秒)
    sub_volume: float = 0.8

    # Noise burst
    noise_burst_dur: float = 0.3    # 噪声爆发时长 (秒)
    noise_volume: float = 0.5
    noise_lp_start: float = 8000.0  # 噪声低通起始频率
    noise_lp_end: float = 200.0     # 噪声低通结束频率

    # Tail
    reverb_mix: float = 0.8
    reverb_decay: float = 3.0
    reverb_type: str = "hall"       # "simple" | "schroeder"

    # 整体
    volume: float = 0.9
    fade_in_sec: float = 0.01
    fade_out_sec: float = 0.5


# ═══════════════════════════════════════════════════════════════════════
# BraamVoice — 影视低音铜管冲击参数
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BraamVoice:
    """Braam 影视低音铜管音色参数"""
    duration_sec: float = 1.5
    start_note: str = "C2"          # 起始音高
    end_note: str = "C3"            # 结束音高

    # FM 合成参数
    fm_ratio: float = 1.5           # modulator/carrier 频率比
    fm_index: float = 3.0           # 调制指数

    # 音色
    distortion: float = 0.5         # 失真量
    volume: float = 0.75
    fade_in_sec: float = 0.02
    fade_out_sec: float = 0.3

    # 效果
    reverb_mix: float = 0.4
    reverb_decay: float = 2.0


# ═══════════════════════════════════════════════════════════════════════
# RiserSynth — 合成器
# ═══════════════════════════════════════════════════════════════════════

class RiserSynth:
    """Riser / Transition FX 合成器。

    用法:
        >>> riser = RiserSynth(voice)
        >>> audio = riser.render()
        >>>
        >>> # 或使用预置
        >>> audio = RiserSynth.preset("edm_build").render(2.0)
    """

    _PRESETS: dict = {}

    def __init__(self, voice: RiserVoice):
        self.voice = voice

    # ── 工厂 ──

    @classmethod
    def noise_riser(cls, duration_sec: float = 2.0,
                    start_freq: float = 200.0,
                    end_freq: float = 12000.0,
                    curve: str = "exponential",
                    q: float = 4.0) -> "RiserSynth":
        """创建纯噪声 riser"""
        return cls(RiserVoice(
            duration_sec=duration_sec,
            start_freq=start_freq,
            end_freq=end_freq,
            curve=curve,
            q_resonance=q,
            noise_type="white",
            volume=0.7,
            reverb_mix=0.3,
        ))

    @classmethod
    def tonal_riser(cls, duration_sec: float = 2.0,
                    start_note: str = "C2",
                    end_note: str = "C6",
                    curve: str = "linear") -> "RiserSynth":
        """创建纯正弦波扫频 riser"""
        from ..core.note_utils import note_to_freq
        return cls(RiserVoice(
            duration_sec=duration_sec,
            start_freq=note_to_freq(start_note),
            end_freq=note_to_freq(end_note),
            curve=curve,
            noise_type="white",
            sine_layers=3,
            octave_spread=1.0,
            detune_cents=7.0,
            volume=0.6,
            reverb_mix=0.4,
            q_resonance=1.5,
        ))

    @classmethod
    def impact_hit(cls, sub_freq: float = 45.0,
                   duration_sec: float = 2.0) -> np.ndarray:
        """一键生成 impact 重击"""
        return RiserSynth._render_impact(ImpactVoice(
            sub_freq=sub_freq,
            sub_duration=duration_sec * 0.75,
            noise_burst_dur=duration_sec * 0.15,
        ))

    @classmethod
    def downlifter(cls, duration_sec: float = 2.0,
                   start_freq: float = 8000.0,
                   end_freq: float = 100.0) -> "RiserSynth":
        """创建下沉音效（频率从高到低）"""
        return cls(RiserVoice(
            duration_sec=duration_sec,
            start_freq=start_freq,
            end_freq=end_freq,
            curve="exponential",
            q_resonance=2.5,
            noise_type="white",
            volume=0.6,
            reverb_mix=0.4,
            reverb_decay=2.0,
        ))

    @classmethod
    def braam(cls, duration_sec: float = 1.5,
              start_note: str = "C2",
              end_note: str = "C3") -> np.ndarray:
        """一键生成 braam 铜管冲击"""
        return RiserSynth._render_braam(BraamVoice(
            duration_sec=duration_sec,
            start_note=start_note,
            end_note=end_note,
        ))

    # ── 渲染 ──

    def render(self, duration_sec: Optional[float] = None) -> np.ndarray:
        """渲染 riser 为音频数组。

        Args:
            duration_sec: 覆盖时长（秒），默认使用 voice.duration_sec

        Returns:
            mono float64 音频数组
        """
        dur = duration_sec if duration_sec is not None else self.voice.duration_sec
        v = self.voice
        n = int(dur * SR)
        t = np.linspace(0, dur, n, dtype=np.float64)

        result = np.zeros(n, dtype=np.float64)

        # ── 噪声层 ──
        if v.noise_type == "pink":
            # 粉红噪声 (简化: brown → 白化)
            raw = np.random.randn(n).astype(np.float64)
            result += raw * 0.6
        elif v.noise_type == "brown":
            # 棕噪声 (积分白噪声)
            raw = np.random.randn(n).astype(np.float64)
            result += np.cumsum(raw) / max(np.max(np.abs(np.cumsum(raw))), 1e-8) * 0.4
        else:  # white
            result += np.random.randn(n).astype(np.float64) * 0.5

        # ── 正弦波层 ──
        for layer in range(max(v.sine_layers, 1)):
            # 每层的频率范围略微偏移
            layer_offset = layer * v.octave_spread * 12 * v.detune_cents / 100.0
            detune = (layer - v.sine_layers / 2) * v.detune_cents

            # 逐采样生成扫频正弦波
            phase = 0.0
            for i in range(n):
                t_i = i / SR
                base_f = v._freq_at(t_i, dur)
                f = base_f * (2.0 ** (layer_offset / 12.0))
                f *= (2.0 ** (detune / 1200.0))
                phase += 2.0 * np.pi * f / SR
                if phase > 2.0 * np.pi * 1000:
                    phase -= 2.0 * np.pi * 1000
                result[i] += np.sin(phase) * 0.3

        # ── 音量包络 ──
        env = np.ones(n, dtype=np.float64)
        fi = int(v.fade_in_sec * SR)
        fo = int(v.fade_out_sec * SR)
        if fi > 0 and fi < n:
            env[:fi] = np.linspace(0, 1, fi)
        if fo > 0 and fo < n:
            env[-fo:] = np.linspace(1, 0, fo)
        result *= env * v.volume

        # ── 谐振低通滤波 ──
        result = self._apply_resonant_filter_sweep(result, v, dur)

        # ── 失真 ──
        if v.distortion > 0:
            result = apply_distortion(result, v.distortion)

        # ── 混响 ──
        if v.reverb_mix > 0:
            result = apply_simple_reverb(
                result, mix=v.reverb_mix, decay=v.reverb_decay,
                delay_ms=30.0, sr=SR,
            )

        # 归一化
        result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)
        peak = np.max(np.abs(result))
        if peak > 0:
            result = result / peak * 0.95

        return result.astype(np.float64)

    def _apply_resonant_filter_sweep(self, audio: np.ndarray,
                                      voice: RiserVoice,
                                      dur: float) -> np.ndarray:
        """逐块应用低通扫频"""
        from ..effects.filters import apply_lowpass
        n = len(audio)
        result = np.zeros(n, dtype=np.float64)
        block_size = int(SR * 0.05)  # 50ms 块

        for start in range(0, n, block_size):
            end = min(start + block_size, n)
            block = audio[start:end]
            t_center = (start + (end - start) / 2) / SR
            cutoff = voice._freq_at(t_center, dur)
            cutoff = max(20.0, min(cutoff, SR / 2 - 1))

            try:
                result[start:end] = apply_lowpass(block, cutoff, SR)
            except Exception:
                result[start:end] = block

        return result

    # ── 预置系统 ──

    @classmethod
    def preset(cls, name: str, **overrides) -> "RiserSynth":
        """按预置名创建 RiserSynth。

        可用预置:
            edm_build, cinematic_rise, ambient_uplift,
            trap_riser, short_riser, long_tension
        """
        presets = {
            "edm_build": dict(
                duration_sec=2.0, start_freq=150, end_freq=15000,
                curve="exponential", q_resonance=5.0,
                sine_layers=2, detune_cents=12, volume=0.75,
                reverb_mix=0.4, distortion=0.1,
            ),
            "cinematic_rise": dict(
                duration_sec=3.0, start_freq=100, end_freq=18000,
                curve="exponential", q_resonance=3.0,
                sine_layers=4, octave_spread=1.5, volume=0.7,
                reverb_mix=0.5, reverb_decay=2.5,
            ),
            "ambient_uplift": dict(
                duration_sec=4.0, start_freq=300, end_freq=6000,
                curve="logarithmic", q_resonance=1.5,
                sine_layers=1, volume=0.5,
                reverb_mix=0.7, reverb_decay=4.0,
            ),
            "trap_riser": dict(
                duration_sec=1.0, start_freq=500, end_freq=10000,
                curve="exponential", q_resonance=6.0,
                volume=0.8, distortion=0.2,
            ),
            "short_riser": dict(
                duration_sec=0.5, start_freq=400, end_freq=8000,
                curve="exponential", q_resonance=3.0,
                volume=0.6,
            ),
            "long_tension": dict(
                duration_sec=8.0, start_freq=80, end_freq=14000,
                curve="exponential", q_resonance=4.0,
                sine_layers=3, volume=0.6,
                reverb_mix=0.5, reverb_decay=3.0,
            ),
        }

        params = presets.get(name, presets["edm_build"])
        params.update(overrides)
        return cls(RiserVoice(**params))

    @classmethod
    def list_presets(cls) -> List[str]:
        return ["edm_build", "cinematic_rise", "ambient_uplift",
                "trap_riser", "short_riser", "long_tension"]

    # ── Impact 渲染 ──

    @staticmethod
    def _render_impact(voice: ImpactVoice) -> np.ndarray:
        """渲染 impact 重击音效"""
        total_dur = voice.sub_duration + voice.noise_burst_dur + voice.reverb_decay * 0.5
        n = int(total_dur * SR)
        result = np.zeros(n, dtype=np.float64)

        # Sub drop (频率下降的正弦波)
        sub_n = int(voice.sub_duration * SR)
        t_sub = np.linspace(0, voice.sub_duration, sub_n, dtype=np.float64)
        # 频率从 sub_freq*1.5 线性降到 sub_freq
        freq_sweep = voice.sub_freq * 1.5 - (voice.sub_freq * 0.5) * t_sub / voice.sub_duration
        phase = np.cumsum(2 * np.pi * freq_sweep / SR)
        sub_sig = np.sin(phase) * voice.sub_volume
        # Sub 包络: 快速起音 + 指数衰减
        sub_env = np.exp(-t_sub * 4.0 / voice.sub_duration)
        result[:sub_n] += sub_sig * sub_env

        # Noise burst
        burst_n = int(voice.noise_burst_dur * SR)
        t_burst = np.linspace(0, voice.noise_burst_dur, burst_n, dtype=np.float64)
        noise = np.random.randn(burst_n).astype(np.float64) * voice.noise_volume
        # 低通扫频: 高→低
        for i in range(0, burst_n, int(SR * 0.02)):
            end_i = min(i + int(SR * 0.02), burst_n)
            ratio = t_burst[i] / voice.noise_burst_dur if voice.noise_burst_dur > 0 else 1.0
            cutoff = voice.noise_lp_start + (voice.noise_lp_end - voice.noise_lp_start) * ratio
            noise[i:end_i] = apply_lowpass(noise[i:end_i], max(20, cutoff))
        burst_env = np.exp(-t_burst * 3.0 / voice.noise_burst_dur)
        offset = sub_n
        if offset + burst_n <= n:
            result[offset:offset + burst_n] += noise * burst_env

        # 混响尾
        if voice.reverb_mix > 0:
            if voice.reverb_type == "schroeder":
                result = apply_schroeder_reverb(
                    result, mix=voice.reverb_mix, decay=voice.reverb_decay, sr=SR,
                )
            else:
                result = apply_simple_reverb(
                    result, mix=voice.reverb_mix, decay=voice.reverb_decay,
                    delay_ms=50.0, sr=SR,
                )

        # 包络
        env = np.ones(n, dtype=np.float64)
        fi = int(voice.fade_in_sec * SR)
        fo = int(voice.fade_out_sec * SR)
        if fi > 0 and fi < n:
            env[:fi] = np.linspace(0, 1, fi)
        if fo > 0 and fo < n:
            env[-fo:] = np.linspace(1, 0, fo)
        result *= env * voice.volume

        result = np.nan_to_num(result, nan=0.0)
        peak = np.max(np.abs(result))
        if peak > 0:
            result = result / peak * 0.95

        return result.astype(np.float64)

    # ── Braam 渲染 ──

    @staticmethod
    def _render_braam(voice: BraamVoice) -> np.ndarray:
        """渲染 braam 影视低音铜管"""
        from ..core.note_utils import note_to_freq
        n = int(voice.duration_sec * SR)
        t = np.linspace(0, voice.duration_sec, n, dtype=np.float64)
        result = np.zeros(n, dtype=np.float64)

        f_start = note_to_freq(voice.start_note)
        f_end = note_to_freq(voice.end_note)

        # 多层 FM 合成
        for layer in range(3):
            oct_offset = layer * 12  # 叠加八度
            # 音高扫频
            freq_sweep = f_start + (f_end - f_start) * t / voice.duration_sec
            f_carrier = freq_sweep * (2.0 ** (oct_offset / 12.0))
            f_modulator = f_carrier * voice.fm_ratio

            # FM 合成
            mod_phase = np.cumsum(2 * np.pi * f_modulator / SR)
            modulator = np.sin(mod_phase) * voice.fm_index * f_modulator
            car_phase = np.cumsum(2 * np.pi * (f_carrier + modulator) / SR)
            carrier = np.sin(car_phase)

            vol = voice.volume * (0.5 ** layer)  # 每高八度减半
            result += carrier * vol

        # 失真
        if voice.distortion > 0:
            result = apply_distortion(result, voice.distortion)

        # 混响
        if voice.reverb_mix > 0:
            result = apply_simple_reverb(
                result, mix=voice.reverb_mix, decay=voice.reverb_decay, sr=SR,
            )

        # 包络
        env = np.ones(n, dtype=np.float64)
        fi = int(voice.fade_in_sec * SR)
        fo = int(voice.fade_out_sec * SR)
        if fi > 0 and fi < n:
            env[:fi] = np.linspace(0, 1, fi)
        if fo > 0 and fo < n:
            env[-fo:] = np.linspace(1, 0, fo)
        result *= env

        result = np.nan_to_num(result, nan=0.0)
        peak = np.max(np.abs(result))
        if peak > 0:
            result = result / peak * 0.95

        return result.astype(np.float64)


# ═══════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════

def render_riser(preset_name: str = "edm_build",
                 duration_sec: float = 2.0,
                 **overrides) -> np.ndarray:
    """一键渲染 riser。

    Args:
        preset_name: 预置名
        duration_sec: 时长（覆盖预置）
        **overrides: 覆盖 voice 参数

    Returns:
        mono float64 音频
    """
    return RiserSynth.preset(preset_name, **overrides).render(duration_sec)


def riser_transition(duration_bars: float, bpm: float,
                     preset: str = "edm_build") -> np.ndarray:
    """生成 N 小节的 riser 过渡音效。

    Args:
        duration_bars: 小节数
        bpm: BPM
        preset: riser 预置

    Returns:
        mono float64 音频
    """
    duration_sec = duration_bars * 4.0 * (60.0 / bpm)
    return render_riser(preset, duration_sec=duration_sec)


def impact_hit(duration_sec: float = 2.0,
               sub_freq: float = 45.0) -> np.ndarray:
    """一键生成 impact 重击。"""
    return RiserSynth.impact_hit(sub_freq=sub_freq, duration_sec=duration_sec)


def build_and_drop(build_bars: float, bpm: float,
                   riser_preset: str = "edm_build",
                   silence_bars: float = 0.25) -> np.ndarray:
    """生成 build → silence → impact 的完整过渡。

    Returns:
        mono float64 音频 (riser + silence + impact)
    """
    beat_dur = 60.0 / bpm
    riser = riser_transition(build_bars, bpm, riser_preset)
    silence = np.zeros(int(silence_bars * 4.0 * beat_dur * SR), dtype=np.float64)
    imp = impact_hit(1.5)
    return np.concatenate([riser, silence, imp])
