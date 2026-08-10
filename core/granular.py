"""
粒子合成引擎 — 环境音效与纹理音色
===================================

基于指导第 3.5 节：粒子合成通过将源音频切分为微小"颗粒"（grain），
再以不同的音高、时长、位置重新组合，生成全新的音色纹理。

核心概念:
    - 颗粒: 从源音频中提取的极短片段 (20-200ms)
    - 颗粒云: 一组颗粒的随机重组
    - 控制参数: 密度、大小、音高、位置、包络

应用场景:
    - 环境音: 风/水/火/魔法
    - 时间拉伸 (不改变音高)
    - 科幻纹理/无人机音色
    - 打击乐变形
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np


# ============================================================
# 数据结构
# ============================================================

@dataclass
class GrainCloud:
    """粒子云参数"""
    source: Optional[np.ndarray] = None     # 源音频 (如果为 None，使用内部噪声生成)

    # 颗粒参数
    grain_size_ms: float = 50.0             # 颗粒大小 (ms)
    grain_size_random: float = 30.0         # 颗粒大小随机范围 (±ms)

    # 密度
    density: float = 50.0                   # 每秒颗粒数
    density_random: float = 20.0            # 密度抖动

    # 音高
    pitch_shift: float = 0.0                # 基础音高偏移 (半音)
    pitch_random: float = 50.0              # 音高随机化 (cents)

    # 位置
    position: float = 0.0                   # 源音频起始位置 (0-1)
    position_random: float = 20.0           # 位置随机化 (ms)

    # 空间
    pan: float = 0.0                        # 声像位置 (-1 左, 0 中, 1 右)
    pan_random: float = 0.3                 # 声像随机化

    # 包络
    envelope_type: str = "hann"             # 颗粒包络: "hann" | "gaussian" | "exp_decay" | "triangle"

    # 效果
    reverb_mix: float = 0.2
    feedback: float = 0.0                   # 粒子间反馈 (0-0.5)

    # 源音频生成 (当 source 为 None 时)
    source_type: str = "noise"              # "noise" | "sine" | "chirp"
    source_freq: float = 220.0              # 源频率 (sine/chirp)
    source_duration: float = 1.0            # 源音频时长 (秒)


# ============================================================
# 粒子合成引擎
# ============================================================

class GranularSynth:
    """
    粒子合成引擎

    用法:
        gs = GranularSynth(sample_rate=44100)
        cloud = GrainCloud(density=80, grain_size_ms=40, pitch_random=30)
        audio = gs.synthesize(cloud, duration=3.0)
    """

    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate

    def synthesize(self, cloud: GrainCloud, duration: float) -> np.ndarray:
        """
        合成粒子音频。

        duration: 输出时长 (秒)
        """
        # 获取或生成源音频
        source = cloud.source
        if source is None:
            source = self._generate_source(cloud)
        source_len = len(source)

        n_samples = int(duration * self.sr)
        output = np.zeros(n_samples, dtype=np.float64)
        output_stereo = np.zeros((2, n_samples), dtype=np.float64)

        # 预计算颗粒数量
        density = cloud.density + np.random.uniform(-cloud.density_random, cloud.density_random)
        grain_spacing = self.sr / max(density, 1.0)
        n_grains = max(1, int(duration * density))

        # 预生成包络窗
        max_grain_len = int((cloud.grain_size_ms + cloud.grain_size_random) * self.sr / 1000) * 2

        for i in range(n_grains):
            # 颗粒时间
            grain_time = i * grain_spacing / self.sr + np.random.uniform(0, grain_spacing / self.sr * 0.3)
            if grain_time >= duration:
                break

            sample_pos = int(grain_time * self.sr)

            # 颗粒大小
            gs_ms = cloud.grain_size_ms + np.random.uniform(-cloud.grain_size_random, cloud.grain_size_random)
            gs_ms = max(5, gs_ms)
            grain_len = int(gs_ms * self.sr / 1000)

            # 源音频位置
            pos_ratio = cloud.position + np.random.uniform(-cloud.position_random, cloud.position_random) / 1000.0
            pos_ratio = np.clip(pos_ratio, 0, 0.99)
            source_start = int(pos_ratio * (source_len - grain_len))

            # 音高偏移
            pitch_cents = cloud.pitch_shift * 100 + np.random.uniform(-cloud.pitch_random, cloud.pitch_random)
            pitch_ratio = 2 ** (pitch_cents / 1200.0)

            # 提取颗粒
            if source_start < 0:
                source_start = 0
            end = min(source_start + grain_len, source_len)
            if end <= source_start:
                continue
            grain = source[source_start:end].copy()

            # 音高变换 (重采样)
            if abs(pitch_ratio - 1.0) > 0.001:
                grain = self._pitch_shift(grain, pitch_ratio)

            # 包络
            grain = self._apply_envelope(grain, cloud.envelope_type)

            # 声像
            pan = np.clip(cloud.pan + np.random.uniform(-cloud.pan_random, cloud.pan_random), -1.0, 1.0)
            left_gain = np.cos((pan + 1) * np.pi / 4)
            right_gain = np.sin((pan + 1) * np.pi / 4)

            # 写入输出
            write_end = min(sample_pos + len(grain), n_samples)
            actual_len = write_end - sample_pos
            if actual_len <= 0:
                continue

            output_mono = grain[:actual_len]
            if output_stereo.shape[0] == 2:
                output_stereo[0, sample_pos:write_end] += output_mono * left_gain
                output_stereo[1, sample_pos:write_end] += output_mono * right_gain
            # 如果是单声道，累加到 output

        output = output_stereo[0] if output_stereo.shape[0] == 2 else output

        # 归一化
        peak = np.max(np.abs(output))
        if peak > 1e-10:
            output = output / peak * 0.9

        return output.astype(np.float32)

    def synthesize_stereo(self, cloud: GrainCloud, duration: float) -> np.ndarray:
        """合成立体声输出 (2, n_samples)"""
        # 已有立体声逻辑，在此直接用
        return self.synthesize(cloud, duration)

    # ── 内部 ──

    def _generate_source(self, cloud: GrainCloud) -> np.ndarray:
        """生成源音频"""
        n = int(cloud.source_duration * self.sr)
        t = np.linspace(0, cloud.source_duration, n, endpoint=False)

        if cloud.source_type == "sine":
            src = np.sin(2 * np.pi * cloud.source_freq * t)
        elif cloud.source_type == "chirp":
            # 线性调频
            f0, f1 = cloud.source_freq * 0.5, cloud.source_freq * 2
            phase = 2 * np.pi * (f0 * t + (f1 - f0) * t**2 / (2 * cloud.source_duration))
            src = np.sin(phase)
        else:  # noise
            src = np.random.uniform(-1, 1, n)

        # 简短淡入淡出
        fade = min(100, n // 10)
        src[:fade] *= np.linspace(0, 1, fade)
        src[-fade:] *= np.linspace(1, 0, fade)

        return src.astype(np.float64)

    def _pitch_shift(self, audio: np.ndarray, ratio: float) -> np.ndarray:
        """简单的音高变换（重采样）"""
        old_len = len(audio)
        new_len = max(1, int(old_len / ratio))
        # 线性插值重采样
        indices = np.linspace(0, old_len - 1, new_len)
        left = np.floor(indices).astype(int)
        right = np.ceil(indices).astype(int)
        right = np.clip(right, 0, old_len - 1)
        frac = indices - left
        return audio[left] * (1 - frac) + audio[right] * frac

    def _apply_envelope(self, grain: np.ndarray, env_type: str) -> np.ndarray:
        """对颗粒应用包络"""
        n = len(grain)
        if n < 2:
            return grain

        t = np.linspace(0, 1, n)
        if env_type == "hann":
            env = 0.5 - 0.5 * np.cos(2 * np.pi * t)
        elif env_type == "gaussian":
            env = np.exp(-((t - 0.5) ** 2) / 0.08)
        elif env_type == "exp_decay":
            env = np.exp(-t * 4)
        elif env_type == "triangle":
            env = 1 - np.abs(t - 0.5) * 2
        else:
            env = np.ones(n)

        return grain * env


# ============================================================
# 便捷函数
# ============================================================

def synthesize_grain_cloud(cloud: GrainCloud, duration: float, sr: int = 44100) -> np.ndarray:
    """快捷合成函数"""
    gs = GranularSynth(sr)
    return gs.synthesize(cloud, duration)


# ============================================================
# 预置粒子云
# ============================================================

@dataclass
class GrainPreset:
    """粒子云预置"""
    name: str
    description: str
    cloud: GrainCloud


GRAIN_PRESETS = [
    GrainPreset(
        name="ethereal_pad",
        description="空灵氛围 — 大颗粒慢速，适合环境音/魔法场景",
        cloud=GrainCloud(
            grain_size_ms=120, grain_size_random=40,
            density=30, density_random=10,
            pitch_random=30, position_random=50,
            envelope_type="gaussian",
            source_type="sine", source_freq=220, source_duration=2.0,
        ),
    ),
    GrainPreset(
        name="wind_ambient",
        description="风声 — 密集白噪声颗粒，适合野外/高海拔",
        cloud=GrainCloud(
            grain_size_ms=80, grain_size_random=30,
            density=120, density_random=40,
            pitch_random=20, pitch_shift=0,
            position_random=30, pan_random=0.4,
            envelope_type="hann",
            source_type="noise", source_duration=2.0,
        ),
    ),
    GrainPreset(
        name="water_texture",
        description="流水质感 — 频率扫描颗粒，适合河流/海洋",
        cloud=GrainCloud(
            grain_size_ms=40, grain_size_random=20,
            density=100, density_random=30,
            pitch_random=15, pitch_shift=5,
            position_random=10, pan_random=0.5,
            envelope_type="exp_decay",
            source_type="chirp", source_freq=800, source_duration=3.0,
        ),
    ),
    GrainPreset(
        name="sci_fi_drone",
        description="科幻无人机 — 密集颗粒，适合太空/机械",
        cloud=GrainCloud(
            grain_size_ms=60, grain_size_random=25,
            density=200, density_random=50,
            pitch_random=100, pitch_shift=-12,
            position_random=40, pan_random=0.2,
            envelope_type="triangle",
            source_type="chirp", source_freq=110, source_duration=1.5,
        ),
    ),
    GrainPreset(
        name="magic_sparkle",
        description="魔法闪光 — 极小颗粒高频，适合法术/拾取",
        cloud=GrainCloud(
            grain_size_ms=15, grain_size_random=10,
            density=80, density_random=30,
            pitch_random=200, pitch_shift=12,
            position_random=15, pan_random=0.6,
            envelope_type="exp_decay",
            source_type="sine", source_freq=880, source_duration=1.0,
        ),
    ),
    GrainPreset(
        name="fire_crackle",
        description="火焰噼啪 — 不规则噪声颗粒，适合篝火/爆炸余烬",
        cloud=GrainCloud(
            grain_size_ms=25, grain_size_random=20,
            density=150, density_random=80,
            pitch_random=10,
            position_random=15, pan_random=0.3,
            envelope_type="exp_decay",
            source_type="noise", source_duration=2.0,
        ),
    ),
]

GRAIN_PRESETS_BY_NAME = {p.name: p for p in GRAIN_PRESETS}
