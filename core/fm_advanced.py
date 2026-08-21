"""
多算子 FM 合成器 —— DX7 风格 4-6 算子 FM 合成 (P2)
======================================================

扩展 BloodMusic 的双算子 FM 为多算子矩阵，支持:
  - 4-op / 6-op 配置
  - 可配置的路由算法 (类似 DX7 的 32 种算法)
  - 每个算子独立的包络和频率比
  - 反馈回路

用法:
    >>> from bloodmusic.core.fm_advanced import MultiOpFM, FMAlgorithm
    >>> fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.STACK)
    >>> fm.set_operator(0, ratio=1.0, env_shape=EnvShape.PAD)
    >>> audio = fm.render(freq=440, duration=2.0)
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

from .constants import SR
from .envelope import EnvShape, make_envelope
from .oscillator import OscType, oscillator


class FMAlgorithm(Enum):
    """FM 路由算法 — 定义算子间的调制连接方式。

    STACK:    Op0→Op1→Op2→Op3 (串联, 经典 FM)
    PAIR:     (Op0→Op1) + (Op2→Op3) (两对并行)
    BRANCH:   Op0→(Op1, Op2)→Op3 (分支合并)
    FEEDBACK: Op0↻ + Op0→Op1→Op2→Op3 (带反馈)
    """
    STACK = "stack"
    PAIR = "pair"
    BRANCH = "branch"
    FEEDBACK = "feedback"


@dataclass
class FMOpParams:
    """单个 FM 算子的参数"""
    freq_ratio: float = 1.0       # 频率比 (相对于基频)
    detune_cents: float = 0.0     # 微调 (音分)
    osc_type: OscType = OscType.SINE
    env_shape: EnvShape = EnvShape.PERCUSSIVE
    level: float = 1.0            # 输出电平
    feedback: float = 0.0         # 自反馈量 (0-1)


@dataclass
class MultiOpFM:
    """多算子 FM 合成器。

    Args:
        operators: 算子数量 (2-6)
        algorithm: 路由算法
        ops: 各算子参数列表 (长度应等于 operators)
    """
    operators: int = 4
    algorithm: FMAlgorithm = FMAlgorithm.STACK
    ops: List[FMOpParams] = field(default_factory=list)

    def __post_init__(self):
        if not self.ops:
            self.ops = [FMOpParams() for _ in range(self.operators)]
        elif len(self.ops) < self.operators:
            self.ops.extend([FMOpParams() for _ in
                            range(self.operators - len(self.ops))])

    def set_operator(self, idx: int, **kwargs):
        """设置指定算子的参数"""
        if 0 <= idx < len(self.ops):
            for k, v in kwargs.items():
                if hasattr(self.ops[idx], k):
                    setattr(self.ops[idx], k, v)

    def render(self, freq: float, duration: float,
               sr: int = SR, volume: float = 1.0) -> np.ndarray:
        """渲染 FM 合成音频。

        Args:
            freq: 基频 (Hz)
            duration: 时长 (秒)
            sr: 采样率
            volume: 输出音量

        Returns:
            音频数组 (float64)
        """
        n = int(duration * sr)
        t = np.linspace(0, duration, n, dtype=np.float64)
        op_signals = []

        # 为每个算子生成信号
        for op in self.ops:
            op_freq = freq * op.freq_ratio * 2.0 ** (op.detune_cents / 1200.0)
            env = make_envelope(n, op.env_shape)
            sig = oscillator(t, op_freq, op.osc_type) * env * op.level
            op_signals.append(sig)

        # 根据算法路由调制
        if self.algorithm == FMAlgorithm.STACK:
            result = self._route_stack(t, freq, op_signals, n)
        elif self.algorithm == FMAlgorithm.PAIR:
            result = self._route_pair(t, freq, op_signals, n)
        elif self.algorithm == FMAlgorithm.BRANCH:
            result = self._route_branch(t, freq, op_signals, n)
        elif self.algorithm == FMAlgorithm.FEEDBACK:
            result = self._route_feedback(t, freq, op_signals, n)
        else:
            result = op_signals[-1]

        # 归一化
        peak = np.max(np.abs(result))
        if peak > 0:
            result = result / peak * 0.95 * volume

        return result.astype(np.float64)

    def _route_stack(self, t, freq, sigs, n):
        """串联: Op0→Op1→Op2→Op3"""
        mod = sigs[0]
        for i in range(1, len(sigs)):
            mod_freq = freq * self.ops[i].freq_ratio
            # 用前一个算子的输出调制当前算子的频率
            mod_amount = mod * freq * 2.0  # 调制深度
            # 简化: 只使用调制器的振幅信息
            phase_mod = np.cumsum(mod) / SR * 0.5
            carrier_t = t + phase_mod
            env = make_envelope(len(t), self.ops[i].env_shape)
            mod = oscillator(carrier_t, mod_freq, self.ops[i].osc_type)
            mod *= env * self.ops[i].level
        return mod

    def _route_pair(self, t, freq, sigs, n):
        """两对并行: (Op0→Op1) + (Op2→Op3)"""
        mid = len(sigs) // 2
        pair1 = sigs[0] * 0.3 + np.sin(2 * np.pi * freq * self.ops[1].freq_ratio * t)
        pair2 = sigs[mid] * 0.3
        if mid + 1 < len(sigs):
            pair2 += np.sin(2 * np.pi * freq * self.ops[mid + 1].freq_ratio * t)
        return (pair1 + pair2) * 0.7

    def _route_branch(self, t, freq, sigs, n):
        """分支: Op0→(Op1, Op2)→Op3"""
        branch1 = sigs[1] * sigs[0]
        branch2 = (sigs[2] * sigs[0] * 0.7) if len(sigs) > 2 else sigs[1]
        combined = (branch1 + branch2) * 0.7
        if len(sigs) > 3:
            result = sigs[3] * (1.0 + combined * 0.5)
        else:
            result = combined
        return result

    def _route_feedback(self, t, freq, sigs, n):
        """带反馈: Op0↻→Op1→Op2→Op3"""
        fb = self.ops[0].feedback
        mod = sigs[0]
        for i in range(1, len(sigs)):
            # 简易反馈: 将调制信号的一部分反馈给自身
            mod = mod * (1.0 - fb) + sigs[i] * fb
        return mod


# ── 预置 ──

def create_dx7_bell() -> MultiOpFM:
    """DX7 风格钟声音色"""
    fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.STACK)
    fm.set_operator(0, freq_ratio=1.0, env_shape=EnvShape.PERCUSSIVE, level=1.0)
    fm.set_operator(1, freq_ratio=3.0, env_shape=EnvShape.PERCUSSIVE, level=0.8)
    fm.set_operator(2, freq_ratio=5.5, env_shape=EnvShape.PERCUSSIVE, level=0.5)
    fm.set_operator(3, freq_ratio=1.0, env_shape=EnvShape.PLUCK, level=0.6)
    return fm


def create_dx7_epiano() -> MultiOpFM:
    """DX7 风格电钢琴"""
    fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.PAIR)
    fm.set_operator(0, freq_ratio=1.0, env_shape=EnvShape.PAD, level=1.0)
    fm.set_operator(1, freq_ratio=1.99, env_shape=EnvShape.PLUCK, level=0.7)
    fm.set_operator(2, freq_ratio=1.0, env_shape=EnvShape.PAD, level=0.5)
    fm.set_operator(3, freq_ratio=3.01, env_shape=EnvShape.PERCUSSIVE, level=0.3)
    return fm


def create_dx7_bass() -> MultiOpFM:
    """DX7 风格 FM Bass"""
    fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.FEEDBACK)
    fm.set_operator(0, freq_ratio=1.0, env_shape=EnvShape.PERCUSSIVE, level=1.0, feedback=0.3)
    fm.set_operator(1, freq_ratio=1.0, env_shape=EnvShape.PERCUSSIVE, level=0.9)
    fm.set_operator(2, freq_ratio=2.0, env_shape=EnvShape.PERCUSSIVE, level=0.5)
    fm.set_operator(3, freq_ratio=3.0, env_shape=EnvShape.PERCUSSIVE, level=0.3)
    return fm
