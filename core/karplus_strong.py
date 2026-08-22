"""
Karplus-Strong 物理建模合成器 — 弦乐/拨弦音色
==============================================

基于指导第 3.9 节：Karplus-Strong 算法通过简单的延迟线 + 低通滤波器
模拟拨弦乐器的物理振动，是生成吉他/贝斯/竖琴/打击弦乐最优雅的方案。

核心原理:
    1. 用白噪声填充延迟线（模拟"拨弦"瞬间的能量注入）
    2. 每次从延迟线末尾取采样，经低通滤波后写回开头
    3. 重复直到能量衰减到阈值以下

参数:
    - 频率 → 延迟线长度
    - 拨弦位置 → 噪声初始分布
    - 弦刚度 → 全通滤波器模拟 dispersion
    - 衰减 → 低通滤波器截止频率
    - 共鸣体 → 级联梳状滤波器模拟琴体共振
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ============================================================
# 数据结构
# ============================================================

@dataclass
class KSVoice:
    """Karplus-Strong 合成音色参数"""
    freq: float = 440.0              # 基频 (Hz)
    duration: float = 2.0            # 合成时长 (秒)
    volume: float = 0.3              # 音量 (0-1)

    # 核心物理参数
    pluck_position: float = 0.2      # 拨弦位置 (0=琴桥, 0.5=中点, 1=琴枕)
    stiffness: float = 0.001         # 弦刚度 (0=完全柔软, 0.01=硬, 钢丝弦)
    decay: float = 0.996             # 每采样衰减因子 (接近1=长延音)
    damping_hz: float = 5000.0       # 频率阻尼 (低通截止频率, 模拟手指/毡 hammer 阻尼)

    # 共鸣体模拟
    body_resonance: float = 0.2      # 共鸣体强度 (0-1)
    body_size: float = 0.5           # 共鸣体大小 (0=小, 1=大)

    # 激励信号
    excitation: str = "noise"        # "noise" | "impulse" | "triangle" | "saw"

    # 效果
    effect_mix: float = 0.0          # 预留效果器接口

    @property
    def delay_length(self) -> int:
        """延迟线长度（采样数）"""
        return max(1, int(44100 / self.freq))


# ============================================================
# KS 合成引擎
# ============================================================

class KarplusStrongSynth:
    """
    Karplus-Strong 合成器

    用法:
        ks = KarplusStrongSynth()
        voice = KSVoice(freq=220, pluck_position=0.2, stiffness=0.002)
        audio = ks.synthesize(voice)  # np.ndarray
    """

    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate

    def synthesize(self, voice: KSVoice) -> np.ndarray:
        """合成音频"""
        n_samples = int(voice.duration * self.sr)
        delay_len = max(2, int(self.sr / voice.freq))

        # ---------- 1. 激励信号 ----------
        excitation = self._generate_excitation(delay_len, voice)

        # ---------- 2. 拨弦位置调制 ----------
        excitation = self._apply_pluck_position(excitation, voice.pluck_position)

        # ---------- 3. Karplus-Strong 主循环 ----------
        signal = self._ks_loop(excitation, voice, n_samples)

        # ---------- 4. 弦刚度 (dispersion) ----------
        if voice.stiffness > 0:
            signal = self._apply_stiffness(signal, voice)

        # ---------- 5. 共鸣体模拟 ----------
        if voice.body_resonance > 0:
            signal = self._apply_body_resonance(signal, voice)

        # ---------- 6. 归一化 + 音量 ----------
        # 避免除零
        peak = np.max(np.abs(signal))
        if peak > 1e-10:
            signal = signal / peak

        # 软削波防止溢出的同时保留一点温暖感
        signal = np.tanh(signal * 1.2) * voice.volume

        return signal.astype(np.float32)

    # ── 内部 ──

    def _generate_excitation(self, length: int, voice: KSVoice) -> np.ndarray:
        """生成激励信号"""
        rng = np.random.default_rng()
        exc_type = voice.excitation

        if exc_type == "impulse":
            x = np.zeros(length, dtype=np.float64)
            x[0] = 1.0
        elif exc_type == "triangle":
            t = np.linspace(0, 1, length)
            x = 1.0 - 2.0 * np.abs(t - 0.5)  # 三角脉冲
        elif exc_type == "saw":
            t = np.linspace(0, 1, length)
            x = 1.0 - 2.0 * t  # 下降锯齿
        else:  # noise (default)
            x = rng.uniform(-1, 1, length)

        # 快速衰减窗口中段（模拟短暂拨弦）
        window = np.exp(-np.linspace(0, 3, length))
        x = x * window
        return x.astype(np.float64)

    @staticmethod
    def _apply_pluck_position(x: np.ndarray, position: float) -> np.ndarray:
        """
        拨弦位置影响谐波分布。
        position=0.5 (中点) → 只有奇次谐波（中空音色）
        position=0.2 (近琴桥) → 更多高次谐波（明亮）
        通过移动激励信号位置 + 带通加权模拟。
        """
        n = len(x)
        # 移动激励中心
        shift = int(n * position * 0.5)
        if shift > 0:
            x_shifted = np.zeros_like(x)
            if shift < n:
                x_shifted[shift:] = x[:n - shift]
            x = x_shifted

        # 拨弦点梳状滤波（模拟节点效应）
        if 0 < position < 1 and position != 0.5:
            comb_delay = int(n * (1.0 - position))
            if comb_delay > 0 and comb_delay < n:
                x_comb = np.zeros_like(x)
                if comb_delay < n:
                    x_comb[comb_delay:] = x[:n - comb_delay]
                x = x + x_comb * 0.5

        return x

    def _ks_loop(self, excitation: np.ndarray, voice: KSVoice, n_samples: int) -> np.ndarray:
        """
        Karplus-Strong 主循环。
        使用低通滤波的延迟线反馈：
            y[n] = decay * (y[n-D] + y[n-D-1]) / 2
        """
        D = len(excitation)
        buf = excitation.copy()
        output = np.zeros(n_samples, dtype=np.float64)
        decay = voice.decay

        # 低通系数 (一阶 IIR 模拟频率相关衰减)
        # damping_hz<=0 视为「无频率阻尼」→ alpha=0 直通（修复除零产生 inf）
        damping_hz = float(voice.damping_hz)
        if damping_hz > 0.0:
            rc = 1.0 / (2 * np.pi * damping_hz)
            dt = 1.0 / self.sr
            alpha = dt / (rc + dt)
        else:
            alpha = 0.0

        prev_sample = 0.0

        for i in range(n_samples):
            # 读取延迟线输出
            idx = i % D
            sample = buf[idx]

            # 低通滤波 + 衰减
            filtered = prev_sample + alpha * (sample - prev_sample)
            prev_sample = filtered

            # 反馈写入（下一周期使用）
            nxt = (i + 1) % D  # approximate: simple linear interpolation
            buf[idx] = filtered * decay

            output[i] = sample  # 输出原始采样（或滤波后）

        return output

    def _apply_stiffness(self, signal: np.ndarray, voice: KSVoice) -> np.ndarray:
        """
        弦刚度模拟 — 使用全通滤波器产生 dispersion。
        刚度越大，高次谐波频率偏移越明显（不和谐）。
        """
        # 简单的全通滤波器实现 frequency-dependent delay
        # stiffness 映射到全通系数
        coeff = min(voice.stiffness * 0.5, 0.8)
        result = np.zeros_like(signal)
        x1, y1 = 0.0, 0.0

        for i in range(len(signal)):
            # 一阶全通: y[n] = -c*x[n] + x[n-1] + c*y[n-1]
            y = -coeff * signal[i] + x1 + coeff * y1
            result[i] = y
            x1 = signal[i]
            y1 = y

        return result

    def _apply_body_resonance(self, signal: np.ndarray, voice: KSVoice) -> np.ndarray:
        """
        共鸣体模拟 — 级联梳状滤波器模拟琴体共振模式。
        body_size 越大 → 共振频率越低（大提琴 vs 小提琴）。
        """
        # 琴体共振频率（基于 body_size 映射）
        base_resonance_hz = 600 - voice.body_size * 450  # 150-600 Hz
        resonance_freqs = [
            base_resonance_hz,
            base_resonance_hz * 1.6,
            base_resonance_hz * 2.3,
            base_resonance_hz * 3.1,
        ]

        wet = signal * (1.0 - voice.body_resonance)
        resonance_sig = np.zeros_like(signal)

        for freq in resonance_freqs:
            # 谐振器: 二阶皮亚诺谐振
            delay_samples = max(1, int(self.sr / freq))
            res_buf = np.zeros(delay_samples * 2)
            res_out = np.zeros(len(signal))
            for i in range(len(signal)):
                idx = i % delay_samples
                res_out[i] = signal[i] + res_buf[idx] * 0.9
                res_buf[idx] = signal[i] * 0.3
            resonance_sig += res_out * 0.15

        result = wet + resonance_sig * voice.body_resonance
        return result


# ============================================================
# 便捷函数
# ============================================================

def synthesize_ks_voice(voice: KSVoice, sr: int = 44100) -> np.ndarray:
    """快捷合成函数，与 SynthVoice 接口一致"""
    synth = KarplusStrongSynth(sr)
    return synth.synthesize(voice)


# ============================================================
# 预置音色
# ============================================================

@dataclass
class KSPreset:
    """预置 Karplus-Strong 音色"""
    name: str
    description: str
    voice: KSVoice


KS_PRESETS = [
    KSPreset(
        name="nylon_guitar",
        description="尼龙弦吉他 — 温暖柔和，适合民谣/营地音乐",
        voice=KSVoice(
            freq=220.0, pluck_position=0.2, stiffness=0.002,
            decay=0.997, damping_hz=4000, body_resonance=0.3,
            body_size=0.6, excitation="noise",
        ),
    ),
    KSPreset(
        name="steel_guitar",
        description="钢弦吉他 — 明亮有金属感，适合战斗/快节奏",
        voice=KSVoice(
            freq=330.0, pluck_position=0.15, stiffness=0.005,
            decay=0.995, damping_hz=8000, body_resonance=0.25,
            body_size=0.4, excitation="noise",
        ),
    ),
    KSPreset(
        name="upright_bass",
        description="低音提琴 — 深沉厚实，适合地牢/氛围",
        voice=KSVoice(
            freq=82.0, pluck_position=0.3, stiffness=0.004,
            decay=0.998, damping_hz=2000, body_resonance=0.5,
            body_size=0.8, excitation="triangle",
        ),
    ),
    KSPreset(
        name="harp",
        description="竖琴 — 空灵优美，适合魔法/精灵/治愈",
        voice=KSVoice(
            freq=440.0, pluck_position=0.4, stiffness=0.001,
            decay=0.998, damping_hz=10000, body_resonance=0.15,
            body_size=0.3, excitation="impulse",
        ),
    ),
    KSPreset(
        name="harpsichord",
        description="羽管键琴 — 古典清脆，适合城堡/贸易场景",
        voice=KSVoice(
            freq=440.0, pluck_position=0.1, stiffness=0.008,
            decay=0.999, damping_hz=12000, body_resonance=0.2,
            body_size=0.5, excitation="saw",
        ),
    ),
    KSPreset(
        name="plucked_synth",
        description="电子拨弦 — 合成器风味，适合科幻/UI 交互",
        voice=KSVoice(
            freq=440.0, pluck_position=0.15, stiffness=0.01,
            decay=0.993, damping_hz=15000, body_resonance=0.1,
            body_size=0.2, excitation="triangle",
        ),
    ),
    KSPreset(
        name="ethnic_lute",
        description="民族琵琶/鲁特琴 — 东方韵味",
        voice=KSVoice(
            freq=330.0, pluck_position=0.35, stiffness=0.003,
            decay=0.996, damping_hz=5000, body_resonance=0.35,
            body_size=0.5, excitation="noise",
        ),
    ),
]

# 按名称索引
KS_PRESETS_BY_NAME = {p.name: p for p in KS_PRESETS}
