"""
垂直分层混音器 — 基于强度的实时多轨混音
==========================================

基于指导第 6.2 节：多个垂直层根据游戏强度动态调节音量和效果。

核心概念:
- 每层 = 一段循环音频 + 独立的合成参数
- 强度 0→1 控制各层的音量、效果和活跃状态
- 支持层的渐入/渐出和交叉淡化
- 强度变化有平滑过渡（防止突兀切换）
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple
import numpy as np


class LayerRole(Enum):
    """层角色"""
    AMBIENT = auto()     # 环境底层 — 持续氛围
    HARMONY = auto()     # 和声层 — 和弦铺底
    MELODY = auto()      # 旋律层 — 主旋律
    RHYTHM = auto()      # 节奏层 — 打击/脉冲
    ACCENT = auto()      # 点缀层 — 装饰音/特殊效果


@dataclass
class MusicLayer:
    """单个音乐层"""
    role: LayerRole = LayerRole.HARMONY
    name: str = "layer"

    # 激活范围 — 强度在此范围内本层生效
    intensity_range: Tuple[float, float] = (0.0, 1.0)  # (min, max)

    # 音量曲线 — (强度, 音量) 控制点，线性插值
    volume_curve: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.0, 0.0),   # 强度0 → 静音
        (0.5, 0.5),   # 强度0.5 → 半音量
        (1.0, 1.0),   # 强度1 → 全音量
    ])

    # 效果调制
    filter_open_curve: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.0, 0.3), (1.0, 1.0),
    ])

    reverb_curve: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.0, 0.5), (1.0, 0.2),
    ])

    # 合成生成参数
    osc_type: str = "sine"
    base_octave: int = 3
    notes: List[str] = field(default_factory=lambda: ["C", "E", "G"])
    rhythm_pattern: List[float] = field(default_factory=lambda: [0.5])  # 节奏模式（拍）

    # 运行时状态
    _active: bool = False
    _target_volume: float = 0.0
    _current_volume: float = 0.0
    _audio_buf: Optional[np.ndarray] = None
    _playhead: int = 0


@dataclass
class LayerMixerConfig:
    """混音器配置"""
    intensity_smoothing: float = 0.05     # 强度平滑因子 (EMA, 0=无平滑, 1=无限)
    volume_smoothing: float = 0.1          # 音量平滑因子 (EMA)
    sample_rate: int = 44100
    buffer_size: int = 512                 # 每帧处理的采样数
    master_volume: float = 0.7             # 主音量


class VerticalLayerMixer:
    """
    垂直分层混音器

    用法:
        mixer = VerticalLayerMixer()
        mixer.add_layer(MusicLayer(role=LayerRole.AMBIENT, name="pad", ...))
        mixer.add_layer(MusicLayer(role=LayerRole.MELODY, name="lead", ...))

        # 每帧
        mixer.set_intensity(0.7)           # 设置当前游戏强度
        audio = mixer.process_frame()      # 获取一帧音频输出
    """

    def __init__(self, config: Optional[LayerMixerConfig] = None):
        self.config = config or LayerMixerConfig()
        self._layers: List[MusicLayer] = []
        self._current_intensity: float = 0.0
        self._smoothed_intensity: float = 0.0
        self._layer_generators: dict = {}  # {layer_name: generator_func}

    def add_layer(self, layer: MusicLayer):
        """添加一个音乐层"""
        self._layers.append(layer)

    def remove_layer(self, name: str):
        """移除指定层"""
        self._layers = [l for l in self._layers if l.name != name]

    def set_layer_generator(self, layer_name: str, generator):
        """
        为层设置音频生成器回调。
        generator(layer, intensity, buffer_size, sample_rate) -> np.ndarray
        """
        self._layer_generators[layer_name] = generator

    def set_intensity(self, intensity: float):
        """设置当前游戏强度 (0-1)，自动平滑"""
        self._current_intensity = max(0.0, min(1.0, intensity))

    def tick(self, dt: float):
        """更新平滑值 (dt 秒)"""
        alpha = min(dt / self.config.intensity_smoothing, 1.0) if self.config.intensity_smoothing > 0 else 1.0
        self._smoothed_intensity += (self._current_intensity - self._smoothed_intensity) * alpha

    def process_frame(self, generator_callback=None) -> np.ndarray:
        """
        混合所有层，生成一帧音频。
        generator_callback: (layer, intensity, n_samples, sr) -> np.ndarray
        如果不提供，使用 set_layer_generator 预设的生成器。
        """
        n = self.config.buffer_size
        sr = self.config.sample_rate
        intensity = self._smoothed_intensity
        output = np.zeros(n, dtype=np.float32)

        for layer in self._layers:
            # 确定目标音量
            vol = self._evaluate_curve(layer.volume_curve, intensity)
            # 检查激活范围
            low, high = layer.intensity_range
            if intensity < low or intensity > high:
                vol *= 0.0  # 完全静音

            # 平滑音量过渡
            alpha_v = self.config.volume_smoothing
            layer._target_volume = vol
            layer._current_volume += (vol - layer._current_volume) * alpha_v

            if layer._current_volume < 0.001:
                continue

            # 生成或使用已有音频
            gen = generator_callback or self._layer_generators.get(layer.name)
            if gen is not None:
                chunk = gen(layer, intensity, n, sr)
            else:
                # 默认生成正弦波测试信号
                chunk = self._default_sine(layer, intensity, n, sr)

            # 应用效果参数
            # 根据强度调制滤波器
            filter_open = self._evaluate_curve(layer.filter_open_curve, intensity)
            chunk = self._apply_simple_lowpass(chunk, filter_open, sr)

            # 混响量
            reverb = self._evaluate_curve(layer.reverb_curve, intensity)
            # （混响在 engine 层统一处理，此处只返回元数据）

            output += chunk * layer._current_volume

        # 主音量 + 限幅
        output = np.clip(output * self.config.master_volume, -1.0, 1.0)
        return output

    @staticmethod
    def _evaluate_curve(curve: List[Tuple[float, float]], x: float) -> float:
        """在曲线上插值求值"""
        if len(curve) == 0:
            return 0.0
        if len(curve) == 1:
            return curve[0][1]

        # 查找最接近的两个点
        curve = sorted(curve, key=lambda p: p[0])
        for i in range(len(curve) - 1):
            x0, y0 = curve[i]
            x1, y1 = curve[i + 1]
            if x0 <= x <= x1:
                t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
                return y0 + (y1 - y0) * t

        # 超出范围 — 夹到最近的端点
        if x < curve[0][0]:
            return curve[0][1]
        return curve[-1][1]

    @staticmethod
    def _default_sine(layer: MusicLayer, intensity: float, n_samples: int, sr: int) -> np.ndarray:
        """默认正弦波测试信号"""
        from bloodmusic.core.note_utils import note_to_freq
        freqs = [note_to_freq(f"{n}{layer.base_octave}") for n in layer.notes]
        t = np.linspace(0, n_samples / sr, n_samples, endpoint=False)
        result = np.zeros(n_samples, dtype=np.float32)
        for f in freqs:
            result += np.sin(2 * np.pi * f * t)
        return result / len(freqs)

    @staticmethod
    def _apply_simple_lowpass(audio: np.ndarray, openness: float, sr: int) -> np.ndarray:
        """简单一阶低通滤波器 (openness 0→极暗, 1→全开)"""
        if openness >= 1.0:
            return audio
        if openness <= 0.0:
            return np.zeros_like(audio)

        # cutoff: 映射 openness 0-1 到 cutoff 200Hz-20kHz
        cutoff = 200 + (20000 - 200) * openness
        # 一阶 IIR 低通
        rc = 1.0 / (2 * np.pi * cutoff)
        dt = 1.0 / sr
        alpha = dt / (rc + dt)
        result = np.zeros_like(audio)
        y = 0.0
        for i in range(len(audio)):
            y += alpha * (audio[i] - y)
            result[i] = y
        return result
