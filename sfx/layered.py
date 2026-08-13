"""
分层音效合成器 — 冲击层+主体层+尾音层
=======================================

基于指导第 3.8 节和 procedural-audio.md：通过分层合成方法
将单一音效拆解为冲击/主体/尾音三个独立层，每层用不同合成方法，
最终混合为高质量的游戏音效。

核心架构:
    LayeredSFX:
      ├── impact_layer (冲击层): 噪声 + 快速衰减 → 爆发感
      ├── body_layer  (主体层): 谐波丰富 + 中等持续 → 音色身份
      └── tail_layer  (尾音层): 混响 + 延迟 → 空间感和持续时间

用法:
    from bloodmusic.sfx import LayeredSFX, synthesize_layered_sfx
    sfx = LayeredSFX(impact_type="noise_click", body_freq=220, tail_reverb=0.5)
    audio = synthesize_layered_sfx(sfx)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

from ..core.constants import SR
from ..core.oscillator import oscillator, OscType
from ..core.envelope import make_envelope, EnvShape
from ..core.note_utils import note_to_freq


# ============================================================
# 分层定义
# ============================================================

@dataclass
class ImpactLayer:
    """冲击层 — 瞬态爆发"""
    osc_type: OscType = OscType.NOISE_WHITE
    duration: float = 0.05           # 持续时间 (秒)
    volume: float = 0.7              # 音量

    # 冲击形状
    attack_ms: float = 0.5           # 起音 (ms) — 极快
    decay_ms: float = 30.0           # 衰减 (ms)

    # 频率
    freq: float = 500.0              # 噪声中心频率 (用于滤波)
    freq_sweep_start: float = 2000.0 # 频率扫描起点 (↓ 下降)
    freq_sweep_end: float = 200.0    # 频率扫描终点

    # 可选音高成分
    pitch_component: float = 0.0     # 0 = 纯噪声, 0.5 = 混合, 1 = 纯音高
    pitch_freq: float = 220.0        # 音高频率


@dataclass
class BodyLayer:
    """主体层 — 谐波/音色身份"""
    osc_type: OscType = OscType.SAW
    duration: float = 0.3            # 持续时间 (秒)
    volume: float = 0.4              # 音量

    # 频率参数
    freq: float = 440.0              # 基频
    freq_envelope: str = "stable"    # "stable" | "slide_down" | "slide_up" | "vibrato"
    freq_slide_semitones: float = 2.0

    # 谐波
    harmonics: List[Tuple[float, float]] = field(default_factory=lambda: [
        (2.0, 0.3),   # 第二谐波
        (3.0, 0.15),  # 第三谐波
        (4.0, 0.05),  # 第四谐波
    ])

    # 包络
    attack_ms: float = 5.0
    decay_ms: float = 100.0
    sustain: float = 0.3
    release_ms: float = 200.0

    # 滤波器
    lp_cutoff_hz: float = 8000.0     # 低通截止 (0 = 全关)
    lp_envelope: str = "stable"      # "stable" | "close" | "open"


@dataclass
class TailLayer:
    """尾音层 — 混响/延迟/空间感"""
    duration: float = 1.5            # 持续时间 (秒)
    volume: float = 0.2              # 音量

    # 混响
    reverb_mix: float = 0.5          # 混响混合比
    reverb_decay: float = 0.8        # 混响衰减
    reverb_size: float = 0.6         # 空间大小 (0=小, 1=大)

    # 延迟
    delay_mix: float = 0.1           # 延迟混合比
    delay_time_ms: float = 150.0     # 延迟时间
    delay_feedback: float = 0.3      # 延迟反馈

    # 音高下降（尾音特征）
    pitch_drop_semitones: float = 6.0
    pitch_drop_time: float = 0.5


@dataclass
class LayeredSFX:
    """分层音效 — 三合一"""
    name: str = "unnamed"
    impact: ImpactLayer = field(default_factory=ImpactLayer)
    body: BodyLayer = field(default_factory=BodyLayer)
    tail: TailLayer = field(default_factory=TailLayer)

    # 混合比例
    mix_ratios: Tuple[float, float, float] = (0.25, 0.5, 0.25)  # (impact, body, tail)

    # 总音量
    master_volume: float = 0.35


# ============================================================
# 合成引擎
# ============================================================

class LayeredSFXSynth:
    """分层音效合成器"""

    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate

    def synthesize(self, sfx: LayeredSFX) -> np.ndarray:
        """合成完整的分层音效"""
        impact_sig = self._render_impact(sfx.impact)
        body_sig = self._render_body(sfx.body)
        tail_sig = self._render_tail(sfx.tail, body_sig)

        # 对齐长度
        max_len = max(len(impact_sig), len(body_sig), len(tail_sig))
        impact_padded = np.pad(impact_sig, (0, max_len - len(impact_sig)))
        body_padded = np.pad(body_sig, (0, max_len - len(body_sig)))
        tail_padded = np.pad(tail_sig, (0, max_len - len(tail_sig)))

        # 混合
        ri, rb, rt = sfx.mix_ratios
        result = (impact_padded * ri + body_padded * rb + tail_padded * rt) * sfx.master_volume

        # 软削波
        result = np.tanh(result * 1.5)

        return result.astype(np.float32)

    def _render_impact(self, imp: ImpactLayer) -> np.ndarray:
        """渲染冲击层"""
        n = int(imp.duration * self.sr)
        if n < 1:
            return np.zeros(1)

        t = np.linspace(0, imp.duration, n, dtype=np.float64)
        sig = oscillator(t, imp.freq, imp.osc_type)

        # 混合音高成分
        if imp.pitch_component > 0:
            pitch_sig = oscillator(t, imp.pitch_freq, OscType.SINE) * imp.pitch_component
            noise_sig = oscillator(t, imp.freq, OscType.NOISE_WHITE) * (1 - imp.pitch_component)
            sig = pitch_sig + noise_sig

        # 频率扫描（模拟冲击下降）
        if imp.freq_sweep_start != imp.freq_sweep_end:
            sweep = np.exp(np.linspace(
                np.log(max(imp.freq_sweep_start, 20)),
                np.log(max(imp.freq_sweep_end, 20)),
                n,
            ))
            sig *= sweep / np.max(np.abs(sweep)) * 0.5

        # 快速包络
        attack_s = int(imp.attack_ms * self.sr / 1000)
        decay_s = int(imp.decay_ms * self.sr / 1000)
        env = np.zeros(n)
        if attack_s > 0 and attack_s < n:
            env[:attack_s] = np.linspace(0, 1, attack_s)
        if decay_s > 0:
            d_end = min(attack_s + decay_s, n)
            if d_end > attack_s:
                env[attack_s:d_end] = np.exp(-np.linspace(0, 3, d_end - attack_s))

        sig = sig * env * imp.volume
        return sig

    def _render_body(self, body: BodyLayer) -> np.ndarray:
        """渲染主体层"""
        n = int(body.duration * self.sr)
        if n < 1:
            return np.zeros(1)

        t = np.linspace(0, body.duration, n, dtype=np.float64)

        # 频率包络
        freq = np.full(n, body.freq, dtype=np.float64)
        if body.freq_envelope == "slide_down":
            ratio = np.linspace(1, 2 ** (-body.freq_slide_semitones / 12), n)
            freq = body.freq * ratio
        elif body.freq_envelope == "slide_up":
            ratio = np.linspace(1, 2 ** (body.freq_slide_semitones / 12), n)
            freq = body.freq * ratio
        elif body.freq_envelope == "vibrato":
            mod = 1.0 + 0.02 * np.sin(2 * np.pi * 8.0 * t)
            freq = body.freq * mod

        # 基础振荡器
        # 计算相位累积
        phase = 2 * np.pi * np.cumsum(freq) / self.sr
        sig = np.sin(phase)  # 简化: 使用正弦

        # 添加谐波
        for h_mult, h_amp in body.harmonics:
            sig += np.sin(phase * h_mult) * h_amp

        # 滤波器
        if body.lp_cutoff_hz > 0 and body.lp_cutoff_hz < 20000:
            from ..effects.filters import apply_lowpass
            if body.lp_envelope == "close":
                cutoff_env = np.linspace(body.lp_cutoff_hz, 500, n)
            elif body.lp_envelope == "open":
                cutoff_env = np.linspace(500, body.lp_cutoff_hz, n)
            else:
                cutoff_env = body.lp_cutoff_hz
            sig = apply_lowpass(sig, cutoff_env[0] if isinstance(cutoff_env, np.ndarray) else cutoff_env)

        # ADSR 包络
        adsr = self._adsr_envelope(
            n, body.attack_ms, body.decay_ms, body.sustain,
            body.release_ms, self.sr,
        )

        sig = sig * adsr * body.volume
        return sig

    def _render_tail(self, tail: TailLayer, body_sig: np.ndarray) -> np.ndarray:
        """渲染尾音层"""
        n = int(tail.duration * self.sr)
        if n < 1:
            return np.zeros(1)

        # 使用简单混响 + 延迟
        from ..effects.spatial import apply_simple_reverb

        tail_sig = np.zeros(n, dtype=np.float64)

        # 从 body 末尾取片段作为尾音种子
        seed_len = min(len(body_sig), int(0.05 * self.sr))  # 取 50ms
        if seed_len > 0:
            seed = body_sig[-seed_len:]
            padded = np.pad(seed, (0, max(n - len(seed), 0)))
            tail_sig[:len(padded)] = padded[:n]

        # 音高下降
        if tail.pitch_drop_semitones > 0:
            drop_n = int(tail.pitch_drop_time * self.sr)
            if drop_n > 0 and drop_n < n:
                ratio = np.linspace(1, 2 ** (-tail.pitch_drop_semitones / 12), drop_n)
                # 简单重采样
                indices = np.linspace(0, len(body_sig) - 1, int(len(body_sig) * ratio[0]))
                resampled = np.interp(
                    np.linspace(0, len(body_sig) - 1, drop_n),
                    np.arange(len(body_sig)),
                    body_sig,
                )
                if drop_n <= n:
                    tail_sig[:drop_n] += resampled[:drop_n] * 0.3

        # 混响
        tail_sig = apply_simple_reverb(
            tail_sig, tail.reverb_mix, tail.reverb_decay,
            int(tail.reverb_size * 50 + 20),
        )

        # 衰减包络
        env = np.exp(-np.linspace(0, 4, n))
        tail_sig = tail_sig * env * tail.volume

        return tail_sig

    @staticmethod
    def _adsr_envelope(n: int, attack_ms: float, decay_ms: float,
                       sustain: float, release_ms: float, sr: int) -> np.ndarray:
        """ADSR 包络"""
        a = int(attack_ms * sr / 1000)
        d = int(decay_ms * sr / 1000)
        r = int(release_ms * sr / 1000)

        env = np.ones(n, dtype=np.float64) * sustain

        if a > 0:
            env[:min(a, n)] = np.linspace(0, 1, min(a, n))

        if d > 0:
            d_start = a
            d_end = min(a + d, n)
            if d_end > d_start:
                env[d_start:d_end] = np.linspace(1, sustain, d_end - d_start)

        if r > 0:
            r_start = max(n - r, 0)
            env[r_start:] = np.linspace(sustain, 0, n - r_start)

        return env


# ============================================================
# 便捷函数 + 预置
# ============================================================

def synthesize_layered_sfx(sfx: LayeredSFX, sr: int = 44100) -> np.ndarray:
    """快捷分层音效合成"""
    synth = LayeredSFXSynth(sr)
    return synth.synthesize(sfx)


@dataclass
class LayeredSFXPreset:
    """分层音效预置"""
    name: str
    description: str
    sfx: LayeredSFX


LAYERED_SFX_PRESETS = [
    LayeredSFXPreset(
        name="explosion",
        description="爆炸 — 强烈冲击+低频主体+长混响尾音",
        sfx=LayeredSFX(
            name="explosion",
            impact=ImpactLayer(
                osc_type=OscType.NOISE_PINK, duration=0.08,
                volume=0.9, freq_sweep_start=4000, freq_sweep_end=100,
                pitch_component=0.2, pitch_freq=60,
            ),
            body=BodyLayer(
                osc_type=OscType.NOISE_BROWN, duration=0.8,
                volume=0.5, freq=80,
                freq_envelope="slide_down", freq_slide_semitones=12,
                harmonics=[], lp_cutoff_hz=2000, lp_envelope="close",
            ),
            tail=TailLayer(
                duration=2.0, volume=0.3,
                reverb_mix=0.7, reverb_decay=0.9, reverb_size=0.9,
                pitch_drop_semitones=6,
            ),
            mix_ratios=(0.3, 0.4, 0.3), master_volume=0.4,
        ),
    ),
    LayeredSFXPreset(
        name="sword_clash",
        description="剑击 — 金属噪声冲击+谐波主体+快速衰减",
        sfx=LayeredSFX(
            name="sword_clash",
            impact=ImpactLayer(
                osc_type=OscType.NOISE_WHITE, duration=0.03,
                volume=0.8, freq_sweep_start=8000, freq_sweep_end=2000,
                pitch_component=0.3, pitch_freq=2000,
            ),
            body=BodyLayer(
                osc_type=OscType.SAW, duration=0.2,
                volume=0.3, freq=1200,
                freq_envelope="slide_down", freq_slide_semitones=7,
                harmonics=[(2,0.2),(3,0.1)], lp_cutoff_hz=6000, lp_envelope="close",
            ),
            tail=TailLayer(
                duration=0.5, volume=0.15,
                reverb_mix=0.3, reverb_decay=0.5, reverb_size=0.3,
                pitch_drop_semitones=12,
            ),
            mix_ratios=(0.3, 0.5, 0.2), master_volume=0.35,
        ),
    ),
    LayeredSFXPreset(
        name="magic_cast",
        description="施法 — chirp冲击+丰富谐波+闪闪尾音",
        sfx=LayeredSFX(
            name="magic_cast",
            impact=ImpactLayer(
                osc_type=OscType.SINE, duration=0.04,
                volume=0.6, freq_sweep_start=800, freq_sweep_end=3000,
                pitch_component=1.0, pitch_freq=1000,
            ),
            body=BodyLayer(
                osc_type=OscType.TRIANGLE, duration=0.5,
                volume=0.35, freq=660,
                freq_envelope="vibrato",
                harmonics=[(2,0.3),(3,0.15),(5,0.05)],
                lp_cutoff_hz=10000, lp_envelope="open",
            ),
            tail=TailLayer(
                duration=1.5, volume=0.25,
                reverb_mix=0.6, reverb_decay=0.8, reverb_size=0.7,
                delay_mix=0.2, delay_time_ms=200,
                pitch_drop_semitones=2,
            ),
            mix_ratios=(0.15, 0.5, 0.35), master_volume=0.3,
        ),
    ),
    LayeredSFXPreset(
        name="footstep",
        description="脚步 — 短促噪声+轻微低频",
        sfx=LayeredSFX(
            name="footstep",
            impact=ImpactLayer(
                osc_type=OscType.NOISE_BROWN, duration=0.02,
                volume=0.5, freq_sweep_start=500, freq_sweep_end=50,
                pitch_component=0.0,
            ),
            body=BodyLayer(
                osc_type=OscType.NOISE_BROWN, duration=0.1,
                volume=0.2, freq=100,
                freq_envelope="slide_down", freq_slide_semitones=24,
                harmonics=[], lp_cutoff_hz=800,
            ),
            tail=TailLayer(
                duration=0.3, volume=0.1,
                reverb_mix=0.2, reverb_decay=0.3, reverb_size=0.2,
                pitch_drop_semitones=0,
            ),
            mix_ratios=(0.35, 0.5, 0.15), master_volume=0.2,
        ),
    ),
    LayeredSFXPreset(
        name="level_up",
        description="升级 — 上行频率+钟声音色+闪亮尾音",
        sfx=LayeredSFX(
            name="level_up",
            impact=ImpactLayer(
                osc_type=OscType.SINE, duration=0.03,
                volume=0.4, freq_sweep_start=500, freq_sweep_end=2000,
                pitch_component=1.0, pitch_freq=800,
            ),
            body=BodyLayer(
                osc_type=OscType.TRIANGLE, duration=1.0,
                volume=0.3, freq=880,
                freq_envelope="slide_up", freq_slide_semitones=5,
                harmonics=[(2,0.25),(4,0.1)],
                lp_cutoff_hz=12000, lp_envelope="open",
            ),
            tail=TailLayer(
                duration=1.5, volume=0.2,
                reverb_mix=0.5, reverb_decay=0.85, reverb_size=0.8,
                delay_mix=0.15, delay_time_ms=300,
                pitch_drop_semitones=0,
            ),
            mix_ratios=(0.1, 0.5, 0.4), master_volume=0.3,
        ),
    ),
    LayeredSFXPreset(
        name="ambient_drone",
        description="环境嗡声 — 持续低频+粒子质感",
        sfx=LayeredSFX(
            name="ambient_drone",
            impact=ImpactLayer(
                osc_type=OscType.SINE, duration=0.1,
                volume=0.3, freq_sweep_start=100, freq_sweep_end=100,
                pitch_component=1.0, pitch_freq=55,
            ),
            body=BodyLayer(
                osc_type=OscType.SINE, duration=4.0,
                volume=0.25, freq=55,
                freq_envelope="stable",
                harmonics=[(2,0.2),(3,0.1),(4,0.05),(5,0.02)],
                lp_cutoff_hz=800, lp_envelope="stable",
            ),
            tail=TailLayer(
                duration=4.0, volume=0.2,
                reverb_mix=0.8, reverb_decay=0.95, reverb_size=1.0,
                pitch_drop_semitones=0,
            ),
            mix_ratios=(0.1, 0.4, 0.5), master_volume=0.25,
        ),
    ),
]

LAYERED_SFX_BY_NAME = {p.name: p for p in LAYERED_SFX_PRESETS}


# ============================================================
# 多声部叠加混合（仿 bfxr Mixer 的 N 路叠加，不限数量）
# ============================================================

def mix_voices(
    voices: List,
    weights: Optional[List[float]] = None,
    normalize: bool = True,
    target_dbfs: float = -1.0,
) -> np.ndarray:
    """将任意 N 个 SynthVoice 加权叠加为单段音频。

    仿 bfxr 的 Mixer（最多 5 路叠加），此处不限数量。每个 voice
    用 synthesize_voice 合成后按权重累加，输出统一归一化到
    target_dbfs（默认 -1dBFS）并硬限幅，保证无削波。

    Args:
        voices: SynthVoice 列表（长度可不一致，按最长对齐补零）
        weights: 各 voice 的权重（None = 全部 1.0）
        normalize: 是否归一化到 target_dbfs（False 保留原始电平）
        target_dbfs: 归一化目标峰值 (dBFS)

    Returns:
        float32 混合音频 (mono)

    Raises:
        ValueError: voices 为空或 weights 长度不匹配
    """
    from ..core.voice import SynthVoice, synthesize_voice

    if not voices:
        raise ValueError("mix_voices requires at least one SynthVoice")
    if not all(isinstance(v, SynthVoice) for v in voices):
        raise TypeError("all voices must be SynthVoice instances")
    if weights is None:
        weights = [1.0] * len(voices)
    if len(weights) != len(voices):
        raise ValueError(
            f"weights length {len(weights)} != voices length {len(voices)}"
        )

    rendered = [synthesize_voice(v) for v in voices]
    max_len = max(len(a) for a in rendered)
    mix = np.zeros(max_len, dtype=np.float64)
    for audio, w in zip(rendered, weights):
        if w == 0.0:
            continue
        padded = np.zeros(max_len, dtype=np.float64)
        padded[: len(audio)] = audio
        mix += padded * w

    if normalize and max_len > 0:
        peak = float(np.max(np.abs(mix))) if mix.size else 0.0
        if peak > 0:
            target = 10.0 ** (target_dbfs / 20.0)
            mix = mix * (target / peak)
    return np.clip(mix, -1.0, 1.0).astype(np.float32)
