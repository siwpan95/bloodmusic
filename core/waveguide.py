"""
数字波导管乐合成 — 简化物理建模用于管乐音色
==============================================

基于数字波导 (Digital Waveguide) 原理实现基础管乐器模型：
  - 圆柱管 (clarinet):  延迟线 + 低通 + 奇次谐波特征
  - 圆锥管 (sax/brass): 延迟线 + 低通 + 全谐波 + 锥形展开补偿
  - 边棱音管 (flute):   噪声激励 + 共振管 + 气流噪声混合

与现有 Karplus-Strong (拨弦) 互补，覆盖管乐合成。

用法:
    >>> from bloodmusic.core.waveguide import WaveguideVoice, render_waveguide
    >>> voice = WaveguideVoice.preset("clarinet")
    >>> audio = render_waveguide(voice)
    >>>
    >>> # 或快捷函数
    >>> from bloodmusic.core.waveguide import render_clarinet
    >>> audio = render_clarinet("C4", 2.0)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import numpy as np

from .constants import SR
from .note_utils import note_to_freq


# ═══════════════════════════════════════════════════════════════════════
# WaveguideVoice — 管乐音色参数
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class WaveguideVoice:
    """数字波导管乐音色参数。

    Args:
        freq: 基频 (Hz)
        duration: 合成时长 (秒)
        volume: 音量 (0-1)

        bore_type: 管型 "cylindrical" | "conical" | "edge_tone"
        breath: 气息强度 (0-1)，影响噪声混合 + 谐波丰富度
        embouchure: 口型松紧 (0-1)，影响起音速度 + 泛音结构
        bell_openness: 喇叭口开度 (0-1)，0=完全封闭, 1=完全开放

        物理参数:
        loss_factor:   管内损耗 (0.9~1.0, 越低衰减越快)
        reflection:    端面反射系数 (-1~1, 负值=开放端反相)
        dispersion:    色散量 (0~0.01, 模拟高频相速变化)
    """
    freq: float = 440.0
    duration: float = 2.0
    volume: float = 0.5

    bore_type: str = "cylindrical"   # cylindrical | conical | edge_tone
    breath: float = 0.5              # 气息强度
    embouchure: float = 0.5          # 口型
    bell_openness: float = 0.7       # 喇叭口

    # 物理参数
    loss_factor: float = 0.995       # 每采样衰减
    reflection: float = -0.5         # 端面反射
    dispersion: float = 0.0          # 色散

    # 噪声混合
    noise_mix: float = 0.1           # 气息噪声
    noise_filter_hz: float = 3000.0  # 噪声过滤

    # 效果
    reverb_mix: float = 0.15
    reverb_decay: float = 1.0

    @classmethod
    def clarinet(cls, freq: float, duration: float = 2.0, **overrides) -> "WaveguideVoice":
        """单簧管（圆柱管，奇次谐波）"""
        params = dict(
            freq=freq, duration=duration, volume=0.45,
            bore_type="cylindrical", breath=0.6, embouchure=0.4,
            loss_factor=0.994, reflection=-0.7,
            noise_mix=0.08, noise_filter_hz=4000,
            reverb_mix=0.12, reverb_decay=0.8,
        )
        params.update(overrides)
        return cls(**params)

    @classmethod
    def flute(cls, freq: float, duration: float = 2.0, **overrides) -> "WaveguideVoice":
        """长笛（边棱音管，气流声显著）"""
        params = dict(
            freq=freq, duration=duration, volume=0.4,
            bore_type="edge_tone", breath=0.7, embouchure=0.6,
            loss_factor=0.992, reflection=-0.6,
            noise_mix=0.25, noise_filter_hz=6000,
            reverb_mix=0.2, reverb_decay=1.5,
        )
        params.update(overrides)
        return cls(**params)

    @classmethod
    def brass(cls, freq: float, duration: float = 2.0, **overrides) -> "WaveguideVoice":
        """铜管（圆锥管，全谐波，明亮）"""
        params = dict(
            freq=freq, duration=duration, volume=0.55,
            bore_type="conical", breath=0.8, embouchure=0.3,
            loss_factor=0.996, reflection=-0.3,
            noise_mix=0.05, noise_filter_hz=5000,
            bell_openness=0.9,
            reverb_mix=0.15, reverb_decay=1.2,
        )
        params.update(overrides)
        return cls(**params)

    @classmethod
    def saxophone(cls, freq: float, duration: float = 2.0, **overrides) -> "WaveguideVoice":
        """萨克斯（圆锥管，柔和圆润）"""
        params = dict(
            freq=freq, duration=duration, volume=0.48,
            bore_type="conical", breath=0.55, embouchure=0.5,
            loss_factor=0.993, reflection=-0.5,
            noise_mix=0.12, noise_filter_hz=4500,
            bell_openness=0.6,
            reverb_mix=0.18, reverb_decay=1.4,
        )
        params.update(overrides)
        return cls(**params)

    @classmethod
    def preset(cls, name: str, freq: float = 440.0, **overrides) -> "WaveguideVoice":
        """按名称获取预设"""
        presets = {
            "clarinet": cls.clarinet,
            "flute": cls.flute,
            "brass": cls.brass,
            "saxophone": cls.saxophone,
        }
        if name not in presets:
            raise ValueError(f"未知预置 '{name}'。可选: {list(presets.keys())}")
        return presets[name](freq, **overrides)

    @classmethod
    def list_presets(cls) -> List[str]:
        return ["clarinet", "flute", "brass", "saxophone"]


# ═══════════════════════════════════════════════════════════════════════
# 核心合成
# ═══════════════════════════════════════════════════════════════════════

def render_waveguide(
    voice: WaveguideVoice,
    sr: int = SR,
) -> np.ndarray:
    """渲染波导管乐音色为音频。

    Args:
        voice: WaveguideVoice 参数
        sr: 采样率

    Returns:
        mono float64 音频
    """
    v = voice
    n = int(v.duration * sr)
    freq = max(20.0, min(v.freq, sr / 2 - 1))

    # 延迟线长度（采样数）
    delay_len = int(sr / freq)
    if delay_len < 2:
        delay_len = 2

    # 初始化延迟线
    delay_line = np.zeros(delay_len, dtype=np.float64)
    output = np.zeros(n, dtype=np.float64)

    # 阅读指针（循环读写）
    read_ptr = 0
    write_ptr = 0

    # 滤波状态
    filter_state = 0.0

    # 气流噪声（预生成）
    rng = np.random.RandomState(42)
    breath_noise = rng.randn(n).astype(np.float64) * v.noise_mix * 0.3

    for i in range(n):
        # ── 激励信号 ──
        if v.bore_type == "edge_tone":
            # 边棱音：噪声激励 + 反馈
            excitation = breath_noise[i] * v.breath * 0.5
        else:
            # 簧片激励：脉冲（模拟簧片每次开合）
            # 更频繁的脉冲 = 更丰富的谐波
            pulse_rate = int(sr / freq * (0.5 + v.breath * 0.5))
            if i % max(1, pulse_rate) == 0:
                excitation = 1.0 * v.breath
            else:
                excitation = 0.0

        # ── 从延迟线读取 ──
        tube_output = delay_line[read_ptr]

        # ── 波导循环：输出 → 滤波（管内损耗）→ 反射 → 写回 ──
        # 低通滤波模拟管内高频损耗
        loss_amount = v.loss_factor * (0.9 + v.bell_openness * 0.1)
        filtered = loss_amount * tube_output + (1 - loss_amount) * filter_state
        filter_state = filtered

        # 锥形管补偿：全通滤波器减少奇次谐波偏重
        if v.bore_type == "conical":
            # 简单全通近似：混合相邻采样
            prev_sample = delay_line[(read_ptr - 1) % delay_len]
            filtered = filtered * 0.7 + prev_sample * 0.3 * v.bell_openness

        # 端面反射（反相 = 开放端）
        reflected = filtered * v.reflection

        # ── 激励 + 反射写回延迟线 ──
        delay_line[write_ptr] = excitation * (1.0 - v.embouchure * 0.3) + reflected

        # ── 输出 = 管口辐射 ──
        output[i] = tube_output * (1.0 - abs(v.reflection)) * v.volume

        # ── 指针推进 ──
        read_ptr = (read_ptr + 1) % delay_len
        write_ptr = (write_ptr + 1) % delay_len

    # ── 噪声混合 ──
    if v.noise_mix > 0:
        from ..effects.filters import apply_lowpass
        noise_filtered = apply_lowpass(breath_noise, v.noise_filter_hz, sr)
        output += noise_filtered * v.noise_mix * 0.25

    # ── 包络 ──
    env = _make_wind_envelope(n, v, sr)
    output *= env

    # ── 谐振增强（模拟管体共振） ──
    output = _add_body_resonance(output, v, sr)

    # ── 混响 ──
    if v.reverb_mix > 0:
        from ..effects.spatial import apply_simple_reverb
        output = apply_simple_reverb(
            output, mix=v.reverb_mix, decay=v.reverb_decay, sr=sr,
        )

    # 归一化
    output = np.nan_to_num(output, nan=0.0)
    peak = np.max(np.abs(output))
    if peak > 0:
        output = output / peak * 0.95

    return output.astype(np.float64)


# ═══════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════

def _make_wind_envelope(n: int, v: WaveguideVoice, sr: int) -> np.ndarray:
    """生成管乐特有的包络：起音 + 持续 + 释放"""
    env = np.ones(n, dtype=np.float64)

    # 起音时间（口型越紧越快）
    attack_s = 0.01 + (1.0 - v.embouchure) * 0.2
    attack_n = int(attack_s * sr)
    if attack_n > 0 and attack_n < n:
        env[:attack_n] = np.linspace(0, 1, attack_n) ** 0.5

    # 释放
    release_s = 0.05 + v.embouchure * 0.3
    release_n = int(release_s * sr)
    if release_n > 0 and release_n < n:
        env[-release_n:] = np.linspace(1, 0, release_n) ** 2

    return env


def _add_body_resonance(audio: np.ndarray,
                         v: WaveguideVoice,
                         sr: int) -> np.ndarray:
    """添加管体共鸣（简化：多个谐振峰）"""
    n = len(audio)
    result = audio.copy()

    # 基础共鸣频率（基频的倍数）
    resonances = [
        (v.freq * 1.0, 0.3 * v.bell_openness),    # 基频
        (v.freq * 2.0, 0.15 * v.bell_openness),    # 第二泛音
        (v.freq * 3.0, 0.08 * v.bell_openness),    # 第三泛音
        (v.freq * 5.0, 0.04 * v.bell_openness),    # 第五泛音
    ]

    # 奇次/全谐波选择
    if v.bore_type == "cylindrical":
        # 圆柱管侧重奇次谐波
        resonances = [
            (v.freq * 1.0, 0.35 * v.bell_openness),
            (v.freq * 3.0, 0.18 * v.bell_openness),
            (v.freq * 5.0, 0.08 * v.bell_openness),
            (v.freq * 7.0, 0.04 * v.bell_openness),
        ]

    for freq, strength in resonances:
        if freq < sr / 2 and strength > 0.001:
            t = np.linspace(0, n / sr, n, dtype=np.float64)
            resonance = np.sin(2 * np.pi * freq * t) * np.exp(-t * 3.0)
            result += resonance * strength * 0.15

    return result


# ═══════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════

def render_clarinet(note: str = "C4", duration: float = 2.0,
                    **overrides) -> np.ndarray:
    """一键生成单簧管音色"""
    freq = note_to_freq(note)
    return render_waveguide(WaveguideVoice.clarinet(freq, duration, **overrides))


def render_flute(note: str = "C5", duration: float = 2.0,
                 **overrides) -> np.ndarray:
    """一键生成长笛音色"""
    freq = note_to_freq(note)
    return render_waveguide(WaveguideVoice.flute(freq, duration, **overrides))


def render_brass(note: str = "C4", duration: float = 2.0,
                 **overrides) -> np.ndarray:
    """一键生成铜管音色"""
    freq = note_to_freq(note)
    return render_waveguide(WaveguideVoice.brass(freq, duration, **overrides))


def render_saxophone(note: str = "C4", duration: float = 2.0,
                     **overrides) -> np.ndarray:
    """一键生成萨克斯音色"""
    freq = note_to_freq(note)
    return render_waveguide(WaveguideVoice.saxophone(freq, duration, **overrides))


def render_waveguide_preset(preset: str, note: str = "C4",
                             duration: float = 2.0,
                             **overrides) -> np.ndarray:
    """按预置名生成管乐音色"""
    freq = note_to_freq(note)
    voice = WaveguideVoice.preset(preset, freq, **overrides)
    return render_waveguide(voice)
