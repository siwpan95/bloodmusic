"""
人性化引擎 —— 为程序化音乐添加"人情味"
============================================

消除完美量化的机械感，模拟人类演奏的微妙不精确性。

核心能力:
  - velocity_jitter:   力度随机波动 (0-1, 默认 0.03)
  - timing_jitter_ms:  微时序偏移 (ms, 默认 2.0)
  - pitch_drift_cents: 音高微漂移 (音分, 默认 2.0)
  - ghost_notes:       随机幽灵音概率 (0-1, 默认 0.0)
  - swing_amount:      摇摆感 (三连音偏移, 0-1, 默认 0.0)
  - seed:              随机种子 (可复现)

用法:
    >>> from bloodmusic.music.humanize import HumanizeParams, apply_humanize
    >>> hp = HumanizeParams(velocity_jitter=0.05, timing_jitter_ms=3.0)
    >>> humanized = apply_humanize(audio_notes, durations_sec, hp)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from ..core.constants import SR


@dataclass
class HumanizeParams:
    """人性化参数。

    所有参数为 0 时不产生任何效果（即完全量化）。
    建议值：velocity_jitter=0.03~0.08, timing_jitter_ms=1~5, pitch_drift=1~3
    """
    velocity_jitter: float = 0.03     # 力度随机波动 (0=无, 0.1=明显)
    timing_jitter_ms: float = 2.0     # 微时序偏移 (ms)
    pitch_drift_cents: float = 2.0    # 音高微漂移 (音分, 100音分=1半音)
    ghost_notes: float = 0.0          # 幽灵音概率 (0=无, 0.02=偶尔)
    swing_amount: float = 0.0         # 摇摆量 (0=直, 0.3=轻摆, 0.6=爵士)
    seed: Optional[int] = None        # 随机种子

    def __post_init__(self):
        """参数范围校验"""
        for name, val, rng in [
            ("velocity_jitter", self.velocity_jitter, (0, 0.5)),
            ("timing_jitter_ms", self.timing_jitter_ms, (0, 30)),
            ("pitch_drift_cents", self.pitch_drift_cents, (0, 50)),
            ("ghost_notes", self.ghost_notes, (0, 0.2)),
            ("swing_amount", self.swing_amount, (0, 0.7)),
        ]:
            lo, hi = rng
            if not (lo <= val <= hi):
                raise ValueError(
                    f"HumanizeParams.{name} = {val} 超出合理范围 [{lo}, {hi}]，"
                    f"请检查是否误填。"
                )

    @property
    def is_active(self) -> bool:
        """是否启用了任何人性化效果"""
        return any([
            self.velocity_jitter > 0,
            self.timing_jitter_ms > 0,
            self.pitch_drift_cents > 0,
            self.ghost_notes > 0,
            self.swing_amount > 0,
        ])

    @classmethod
    def none(cls) -> "HumanizeParams":
        """完全量化（无效果）"""
        return cls(0, 0, 0, 0, 0)

    @classmethod
    def subtle(cls) -> "HumanizeParams":
        """微人性化（适合古典/钢琴）"""
        return cls(velocity_jitter=0.03, timing_jitter_ms=2.0,
                   pitch_drift_cents=2.0, swing_amount=0.0)

    @classmethod
    def natural(cls) -> "HumanizeParams":
        """自然演奏（适合民谣/世界音乐）"""
        return cls(velocity_jitter=0.05, timing_jitter_ms=4.0,
                   pitch_drift_cents=3.0, swing_amount=0.0)

    @classmethod
    def groovy(cls) -> "HumanizeParams":
        """摇摆律动（适合爵士/Funk）"""
        return cls(velocity_jitter=0.06, timing_jitter_ms=3.0,
                   pitch_drift_cents=1.5, swing_amount=0.35)

    @classmethod
    def human(cls) -> "HumanizeParams":
        """高度人性化（适合独奏乐器）"""
        return cls(velocity_jitter=0.08, timing_jitter_ms=5.0,
                   pitch_drift_cents=5.0, ghost_notes=0.02, swing_amount=0.15)


def apply_humanize_to_note(
    note_audio: np.ndarray,
    params: HumanizeParams,
    rng: np.random.RandomState,
    note_index: int,
) -> np.ndarray:
    """对单个音符的音频应用人性化效果。

    Args:
        note_audio: 单个音符的音频片段
        params: 人性化参数
        rng: numpy 随机状态
        note_index: 当前音符在序列中的位置 (用于种子一致性)

    Returns:
        处理后的音频片段
    """
    if not params.is_active:
        return note_audio

    result = note_audio.copy().astype(np.float64)

    # 1. 力度抖动 (volume micro-variation)
    if params.velocity_jitter > 0:
        vel_scale = 1.0 + rng.uniform(
            -params.velocity_jitter, params.velocity_jitter
        )
        result *= vel_scale

    # 2. 音高微漂移 (pitch drift via resampling)
    #    通过轻微的时间拉伸/压缩模拟音高变化
    if params.pitch_drift_cents > 0:
        drift_cents = rng.uniform(
            -params.pitch_drift_cents, params.pitch_drift_cents
        )
        # 1 cent = 2^(1/1200), 拉伸因子 = 2^(-drift/1200)
        stretch = 2.0 ** (-drift_cents / 1200.0)
        n_orig = len(result)
        n_new = max(1, int(n_orig * stretch))
        indices = np.linspace(0, n_orig - 1, n_new)
        result = np.interp(indices, np.arange(n_orig), result)
        # 如果变短了，补零或截断到原长
        if len(result) < n_orig:
            padded = np.zeros(n_orig, dtype=np.float64)
            padded[:len(result)] = result
            result = padded
        else:
            result = result[:n_orig]

    # 3. 权重衰减 (模拟渐弱的尾部)
    if params.velocity_jitter > 0 and len(result) > 10:
        # 对尾部做轻微额外衰减
        tail_start = int(len(result) * 0.85)
        if tail_start > 0 and tail_start < len(result):
            tail_len = len(result) - tail_start
            tail_extra = 1.0 - rng.uniform(0, params.velocity_jitter * 0.5)
            result[tail_start:] *= np.linspace(1.0, tail_extra, tail_len)

    return result


def apply_humanize_to_sequence(
    audio: np.ndarray,
    note_durations_sec: list,
    params: HumanizeParams,
    sr: int = SR,
) -> np.ndarray:
    """对整个音符序列应用人性化效果（包含时序偏移）。

    在渲染完成的音频上，按音符边界进行：
      - 微时序偏移（前移/后移音符起点）
      - 逐音符力度抖动
      - 音高微漂移

    Args:
        audio: 原始渲染音频
        note_durations_sec: 每个音符的时长（秒）
        params: 人性化参数
        sr: 采样率

    Returns:
        人性化处理后的音频
    """
    if not params.is_active or len(note_durations_sec) == 0:
        return audio

    rng = np.random.RandomState(params.seed)
    n_samples = len(audio)
    result = np.zeros(n_samples, dtype=np.float64)

    # 计算每个音符在音频中的位置
    positions = np.cumsum([0] + list(note_durations_sec))
    positions_samples = (positions * sr).astype(int)

    swing_active = params.swing_amount > 0

    for i in range(len(note_durations_sec)):
        start_samp = positions_samples[i]
        end_samp = min(positions_samples[i + 1], n_samples)

        if start_samp >= n_samples:
            break
        if end_samp <= start_samp:
            continue

        # 微时序偏移
        timing_offset = 0
        if params.timing_jitter_ms > 0:
            timing_offset = int(rng.uniform(
                -params.timing_jitter_ms, params.timing_jitter_ms
            ) * sr / 1000.0)

        # Swing (仅对偶数/奇数位置做偏移)
        if swing_active and i % 2 == 1:
            # 奇数位后移（典型摇摆感）
            note_len_samples = end_samp - start_samp
            swing_offset = int(note_len_samples * params.swing_amount * 0.3)
            timing_offset += swing_offset

        new_start = max(0, min(n_samples - 1, start_samp + timing_offset))
        new_end = min(n_samples, new_start + (end_samp - start_samp))

        # 提取原始音符片段
        note_segment = audio[start_samp:end_samp].copy()

        # 应用力度/音高人性化
        note_segment = apply_humanize_to_note(note_segment, params, rng, i)

        # 放入结果数组
        seg_len = min(len(note_segment), new_end - new_start)
        result[new_start:new_start + seg_len] += note_segment[:seg_len]

    # 幽灵音 (偶尔插入极轻的随机音)
    if params.ghost_notes > 0:
        for i in range(len(note_durations_sec)):
            if rng.random() < params.ghost_notes:
                ghost_pos = positions_samples[i] + int(
                    rng.uniform(0, 0.5) * sr
                )
                ghost_len = int(rng.uniform(0.02, 0.08) * sr)
                ghost_end = min(ghost_pos + ghost_len, n_samples)
                if ghost_pos < n_samples:
                    ghost = (rng.randn(ghost_end - ghost_pos) *
                             rng.uniform(0.005, 0.015))
                    result[ghost_pos:ghost_end] += ghost

    return result


# ── 预设快捷方式 ──
HUMANIZE_NONE = HumanizeParams.none()
HUMANIZE_SUBTLE = HumanizeParams.subtle()
HUMANIZE_NATURAL = HumanizeParams.natural()
HUMANIZE_GROOVY = HumanizeParams.groovy()
HUMANIZE_HUMAN = HumanizeParams.human()
