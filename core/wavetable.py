"""
波表合成 (Wavetable Synthesis) — 自定义波形查找表 + 波形渐变
=============================================================

PRD P2-1: 实现波表合成，允许用户自定义波形形状并在多个波表间平滑过渡。

核心概念:
    1. Wavetable: 一个单周期波形 (如 2048 采样)
    2. 相位累加器: 以目标频率递进相位
    3. 查表 + 插值: 线性/三次插值读取波表
    4. 波表变形: 在多个波表间平滑 morph (位置 = 0~1)

使用方式:
    >>> from bloodmusic.core.wavetable import Wavetable, WavetableOscillator
    >>> wt = Wavetable.from_preset("sine")
    >>> osc = WavetableOscillator(wt, freq=440.0)
    >>> audio = osc.render(3.0)  # 3 秒音频
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum

from .constants import SR


# ══════════════════════════════════════════════════════════════
# 波表数据结构
# ══════════════════════════════════════════════════════════════

class InterpolationMode(Enum):
    """插值模式"""
    NONE = "none"          # 最近邻采样
    LINEAR = "linear"      # 线性插值
    CUBIC = "cubic"        # 三次插值


@dataclass
class Wavetable:
    """单周期波表。

    存储归一化的单周期波形（-1 ~ 1），可通过相位索引读取。

    Attributes:
        data: 波形采样数组（长度 = table_size + 1 用于插值包裹）
        name: 波表名称
        table_size: 波表大小（不含包裹采样）
    """
    data: np.ndarray
    name: str = "custom"
    table_size: int = 2048

    def __post_init__(self):
        """确保波表末尾包裹到开头"""
        if len(self.data) == self.table_size:
            # 添加包裹采样
            self.data = np.append(self.data, self.data[0])
        elif len(self.data) != self.table_size + 1:
            raise ValueError(
                f"波表数据长度必须为 {self.table_size} 或 {self.table_size + 1}，"
                f"实际 {len(self.data)}"
            )

    # ── 工厂方法 ──

    @classmethod
    def from_function(
        cls,
        fn,
        table_size: int = 2048,
        name: str = "custom",
    ) -> "Wavetable":
        """从数学函数生成波表。

        Args:
            fn: 函数 f(phase: float 0~1) -> amplitude: float
            table_size: 波表大小
            name: 名称

        Example:
            >>> wt = Wavetable.from_function(lambda p: np.sin(2*np.pi*p), name="sine")
        """
        phases = np.linspace(0, 1, table_size, endpoint=False)
        data = np.array([fn(p) for p in phases], dtype=np.float64)
        # 归一化
        peak = np.max(np.abs(data))
        if peak > 0:
            data = data / peak
        return cls(data=data, name=name, table_size=table_size)

    @classmethod
    def from_preset(cls, preset_name: str, table_size: int = 2048) -> "Wavetable":
        """从预置名称创建波表。

        支持的预置:
            - sine, triangle, saw, square
            - pwm_10..pwm_90 (方波占空比 10%~90%)
            - organ (管风琴风格)
            - brass (铜管风格)
            - bell (铃铛风格)
            - vocal (人声风格)
        """
        if preset_name in _WAVETABLE_PRESET_FNS:
            fn = _WAVETABLE_PRESET_FNS[preset_name]
            return cls.from_function(fn, table_size, name=preset_name)

        # 尝试 PWM 预置
        if preset_name.startswith("pwm_"):
            try:
                duty = float(preset_name.split("_")[1]) / 100
                duty = max(0.05, min(0.95, duty))

                def pwm_fn(p):
                    return 1.0 if p < duty else -1.0

                return cls.from_function(pwm_fn, table_size, name=preset_name)
            except (ValueError, IndexError):
                pass

        raise ValueError(f"未知波表预置: {preset_name}")

    @classmethod
    def morph(cls, wt_a: "Wavetable", wt_b: "Wavetable", t: float) -> "Wavetable":
        """在两个波表间线性插值变形。

        Args:
            wt_a: 起始波表
            wt_b: 目标波表
            t: 变形参数 0~1 (0=纯A, 1=纯B)

        Returns:
            新的混合波表
        """
        if wt_a.table_size != wt_b.table_size:
            raise ValueError("两个波表大小必须一致")
        data = wt_a.data * (1 - t) + wt_b.data * t
        return cls(data=data, name=f"morph_{wt_a.name}_{wt_b.name}_t{t:.2f}",
                   table_size=wt_a.table_size)

    def sample(self, phase: float, mode: InterpolationMode = InterpolationMode.LINEAR) -> float:
        """从波表采样。

        Args:
            phase: 相位 0~1
            mode: 插值模式

        Returns:
            采样值
        """
        phase = phase % 1.0
        idx = phase * self.table_size

        if mode == InterpolationMode.NONE:
            return self.data[int(idx)]

        elif mode == InterpolationMode.LINEAR:
            i0 = int(idx)
            i1 = i0 + 1
            frac = idx - i0
            return self.data[i0] * (1 - frac) + self.data[i1] * frac

        elif mode == InterpolationMode.CUBIC:
            i0 = int(idx)
            # Hermite 三次插值
            i_1 = (i0 - 1) % self.table_size
            i1  = (i0 + 1) % self.table_size
            i2  = (i0 + 2) % self.table_size

            p0 = self.data[i_1]
            p1 = self.data[i0]
            p2 = self.data[i1]
            p3 = self.data[i2]

            t = idx - i0
            t2 = t * t
            t3 = t2 * t

            # Catmull-Rom 样条
            a = -0.5 * p0 + 1.5 * p1 - 1.5 * p2 + 0.5 * p3
            b = p0 - 2.5 * p1 + 2.0 * p2 - 0.5 * p3
            c = -0.5 * p0 + 0.5 * p2
            d = p1

            return a * t3 + b * t2 + c * t + d


# ══════════════════════════════════════════════════════════════
# 波表振荡器
# ══════════════════════════════════════════════════════════════

@dataclass
class WavetableOscillator:
    """波表振荡器 —— 相位累加器 + 查表。

    Attributes:
        wavetable: 当前波表
        freq: 基频 (Hz)
        sr: 采样率
        interp: 插值模式
    """
    wavetable: Wavetable
    freq: float = 440.0
    sr: int = SR
    interp: InterpolationMode = InterpolationMode.LINEAR

    def render(self, duration: float) -> np.ndarray:
        """渲染固定频率的音频。

        Args:
            duration: 时长 (秒)

        Returns:
            音频数组 (float64, 归一化到 -1~1)
        """
        n = int(duration * self.sr)
        if n < 1:
            return np.array([], dtype=np.float64)

        phase_increment = self.freq / self.sr
        phases = (np.arange(n, dtype=np.float64) * phase_increment) % 1.0

        # 批量线性插值
        indices = phases * self.wavetable.table_size
        i0 = np.floor(indices).astype(int)
        i1 = i0 + 1
        frac = indices - i0

        # 确保索引在范围内 (i1 可能等于 table_size = data[-1] 的索引)
        i1 = np.where(i1 > self.wavetable.table_size, 0, i1)

        samples = self.wavetable.data[i0] * (1 - frac) + self.wavetable.data[i1] * frac

        return samples

    def render_with_pitch_bend(
        self,
        duration: float,
        pitch_curve: np.ndarray,
    ) -> np.ndarray:
        """渲染带音高弯音的音频。

        Args:
            duration: 时长 (秒)
            pitch_curve: 每个采样的音高倍率 (1.0 = 原始频率)

        Returns:
            音频数组
        """
        n = int(duration * self.sr)
        if n < 1:
            return np.array([], dtype=np.float64)

        # 确保 pitch_curve 长度匹配
        if len(pitch_curve) < n:
            pitch_curve = np.tile(pitch_curve, int(np.ceil(n / len(pitch_curve))))[:n]
        else:
            pitch_curve = pitch_curve[:n]

        phase = 0.0
        samples = np.zeros(n, dtype=np.float64)

        for i in range(n):
            samples[i] = self.wavetable.sample(phase % 1.0, self.interp)
            phase += (self.freq * pitch_curve[i]) / self.sr

        return samples


# ══════════════════════════════════════════════════════════════
# 多维波表 (2D Morphing)
# ══════════════════════════════════════════════════════════════

@dataclass
class MultiWavetable:
    """多维波表 —— 支持多个波表间平滑渐变 morphing。

    Attributes:
        tables: 波表列表
        names: 波表名称列表
    """
    tables: List[Wavetable]
    names: List[str]

    def __post_init__(self):
        if not self.tables:
            raise ValueError("至少需要一个波表")
        size = self.tables[0].table_size
        for wt in self.tables:
            if wt.table_size != size:
                raise ValueError("所有波表大小必须一致")

    @classmethod
    def from_presets(cls, preset_names: List[str], table_size: int = 2048) -> "MultiWavetable":
        """从预置名列表创建多维波表。"""
        tables = [Wavetable.from_preset(name, table_size) for name in preset_names]
        return cls(tables=tables, names=preset_names)

    def sample_at_position(self, phase: float, position: float,
                           interp: InterpolationMode = InterpolationMode.LINEAR) -> float:
        """在多维波表空间中采样。

        Args:
            phase: 波形相位 0~1
            position: 波表位置 0~1 (在多波表间线性插值)
            interp: 插值模式

        Returns:
            采样值
        """
        if len(self.tables) == 1:
            return self.tables[0].sample(phase, interp)

        # 将 position 映射到两个最近的波表之间
        idx_f = position * (len(self.tables) - 1)
        idx_a = int(np.floor(idx_f))
        idx_b = min(idx_a + 1, len(self.tables) - 1)
        frac = idx_f - idx_a

        if idx_a == idx_b:
            return self.tables[idx_a].sample(phase, interp)

        val_a = self.tables[idx_a].sample(phase, interp)
        val_b = self.tables[idx_b].sample(phase, interp)
        return val_a * (1 - frac) + val_b * frac


# ══════════════════════════════════════════════════════════════
# 波表预置库
# ══════════════════════════════════════════════════════════════

_WAVETABLE_PRESET_FNS: Dict[str, callable] = {
    # ── 基础波形 ──
    "sine": lambda p: np.sin(2 * np.pi * p),

    "triangle": lambda p: 2.0 * np.abs(2.0 * (p - np.floor(p + 0.5))) - 1.0,

    "saw": lambda p: 2.0 * (p % 1.0) - 1.0,

    "square": lambda p: 1.0 if (p % 1.0) < 0.5 else -1.0,

    # ── 音乐化波形 ──
    "organ": lambda p: np.sin(2*np.pi*p) * 0.5
                       + np.sin(4*np.pi*p) * 0.3
                       + np.sin(6*np.pi*p) * 0.15
                       + np.sin(8*np.pi*p) * 0.05,

    "brass": lambda p: np.sin(2*np.pi*p) * 0.6
                       + np.sin(4*np.pi*p) * 0.3
                       + np.sin(6*np.pi*p) * 0.2
                       + np.sin(8*np.pi*p) * 0.1
                       + np.sin(10*np.pi*p) * 0.08
                       + np.sin(12*np.pi*p) * 0.05
                       + np.sin(14*np.pi*p) * 0.03,

    "bell": lambda p: np.sin(2*np.pi*p) * 0.5
                      + np.sin(2*np.pi*2.76*p) * 0.3
                      + np.sin(2*np.pi*5.4*p) * 0.2
                      + np.sin(2*np.pi*8.93*p) * 0.1,

    "vocal": lambda p: np.sin(2*np.pi*p) * 0.4
                       + np.sin(2*np.pi*2*p) * 0.25
                       + np.sin(2*np.pi*3*p) * 0.2
                       + np.sin(2*np.pi*4*p) * 0.1
                       + np.sin(2*np.pi*5*p) * 0.05,

    # ── 噪声/纹理 ──
    "noise": lambda p: np.random.uniform(-1, 1),

    "warm_noise": lambda p: np.sin(2*np.pi*p) * 0.3
                             + np.random.uniform(-0.7, 0.7),

    # ── 特殊波形 ──
    "half_sine": lambda p: np.sin(np.pi * (p % 1.0)),

    "impulse": lambda p: 1.0 if (p % 1.0) < 0.01 else -1.0,

    "formant_a": lambda p: np.sin(2*np.pi*p) * 0.5
                           + np.sin(2*np.pi*3*p) * 0.3
                           + np.sin(2*np.pi*5*p) * 0.15
                           + np.sin(2*np.pi*7*p) * 0.05,

    "formant_e": lambda p: np.sin(2*np.pi*p) * 0.4
                           + np.sin(2*np.pi*2*p) * 0.35
                           + np.sin(2*np.pi*4*p) * 0.2
                           + np.sin(2*np.pi*6*p) * 0.05,

    # ── 游戏/芯片音乐 ──
    "chip_square25": lambda p: 1.0 if (p % 1.0) < 0.25 else -1.0,
    "chip_square75": lambda p: 1.0 if (p % 1.0) < 0.75 else -1.0,
    "chip_square12": lambda p: 1.0 if (p % 1.0) < 0.125 else -1.0,
}

# 列出所有可用预置
def list_wavetable_presets() -> List[str]:
    """列出所有可用波表预置名称。"""
    return sorted(_WAVETABLE_PRESET_FNS.keys())
