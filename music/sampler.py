"""
基础采样器 —— 加载 WAV 文件并回放
==================================

[兼容层] 2026-08-23 恢复：v2.0 镜像架构重构（commit 7af5092）时本模块被删除，
但 audio_pipeline（tools/audio/audio_pipeline）仍依赖本 API
（Sample/SamplePad/load_sample/render_sampler_pattern）。
恢复自 git 7af5092^，仅依赖 core/note_utils 与 core/constants（均健在）。
待 audio_pipeline 迁移到 PoolRenderer/InstrumentPool 新 API 后可再次删除。

提供从 WAV 文件加载音频并带音高/速度控制的回放功能。

核心能力:
  - load_sample:  加载 WAV 文件到内存
  - play_sample:  按指定频率/速度回放 (支持变调不变速)
  - SamplePad:    鼓垫式触发 (一次加载，多次触发)
  - render_sampler_pattern: 从 MusicPattern 批量触发采样

用法:
    >>> from bloodmusic.music.sampler import load_sample, play_sample, SamplePad
    >>> sample = load_sample("kick.wav")
    >>> audio = play_sample(sample, duration=0.5)
    >>> pad = SamplePad()
    >>> pad.add("kick", "kick.wav")
    >>> pad.add("snare", "snare.wav")
    >>> hit = pad.trigger("kick", volume=0.8)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import struct
import wave

from ..core.note_utils import note_to_freq
from ..core.constants import SR as _SR


# ═══════════════════════════════════════════════════════════════════════
# 采样数据结构
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Sample:
    """加载后的采样数据。

    Args:
        data: 音频数据 (float64, 归一化到 -1~1)
        sr: 原始采样率
        name: 采样名称
        root_note: 原始音高 (用于重采样变调)
    """
    data: np.ndarray
    sr: int
    name: str = "sample"
    root_note: str = "C4"  # 原始录制音高

    @property
    def duration(self) -> float:
        """采样时长 (秒)"""
        return len(self.data) / self.sr

    @property
    def root_freq(self) -> float:
        """原始频率"""
        return note_to_freq(self.root_note)


# ═══════════════════════════════════════════════════════════════════════
# WAV 加载
# ═══════════════════════════════════════════════════════════════════════

def load_sample(
    path: str,
    name: Optional[str] = None,
    root_note: str = "C4",
) -> Sample:
    """从 WAV 文件加载采样。

    Args:
        path: .wav 文件路径
        name: 采样名称 (默认取文件名)
        root_note: 原始音高

    Returns:
        Sample 对象

    支持:
        - 8-bit (无符号), 16-bit, 24-bit, 32-bit (有符号整数/float)
        - mono 和 stereo (自动转换为 mono)
    """
    import os

    if name is None:
        name = os.path.splitext(os.path.basename(path))[0]

    with wave.open(path, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()  # bytes per sample
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)

    # 解析字节为数值
    if sample_width == 1:
        # 8-bit unsigned
        fmt = f"{n_frames * n_channels}B"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        data = (data - 128.0) / 128.0  # 转有符号
    elif sample_width == 2:
        # 16-bit signed
        fmt = f"{n_frames * n_channels}h"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        data = data / 32768.0
    elif sample_width == 3:
        # 24-bit signed
        data = _parse_24bit(raw_data, n_frames, n_channels)
    elif sample_width == 4:
        # 32-bit (可能是 int 或 float)
        fmt = f"{n_frames * n_channels}i"
        data = np.array(struct.unpack(fmt, raw_data), dtype=np.float64)
        if np.max(np.abs(data)) > 10.0:
            data = data / 2147483648.0  # 32-bit int
        else:
            pass  # 已经是 float
    else:
        raise ValueError(f"不支持的采样位深度: {sample_width * 8} bit")

    # 多声道 → mono
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)

    return Sample(data=data, sr=sr, name=name, root_note=root_note)


def _parse_24bit(raw_data: bytes, n_frames: int, n_channels: int) -> np.ndarray:
    """解析 24-bit PCM 为 float64"""
    total_samples = n_frames * n_channels
    result = np.zeros(total_samples, dtype=np.float64)
    for i in range(total_samples):
        b3 = i * 3
        # 小端序
        sample = raw_data[b3] | (raw_data[b3 + 1] << 8) | (raw_data[b3 + 2] << 16)
        # 符号扩展
        if sample & 0x800000:
            sample -= 0x1000000
        result[i] = sample / 8388608.0  # 2^23
    return result


# ═══════════════════════════════════════════════════════════════════════
# 回放
# ═══════════════════════════════════════════════════════════════════════

def play_sample(
    sample: Sample,
    target_note: Optional[str] = None,
    target_freq: Optional[float] = None,
    duration: Optional[float] = None,
    volume: float = 1.0,
    start_offset: float = 0.0,
    target_sr: int = _SR,
) -> np.ndarray:
    """回放采样，支持变调。

    通过重采样实现变调：播放速度改变 → 音高改变。

    Args:
        sample: 采样数据
        target_note: 目标音符 (如 "C3", None = 原音高)
        target_freq: 目标频率 (Hz), 与 target_note 二选一
        duration: 目标时长 (秒), None = 自动
        volume: 音量 0~1
        start_offset: 起始偏移 (秒)
        target_sr: 目标采样率

    Returns:
        回放音频 (float64)
    """
    # 计算音高比
    if target_freq is not None:
        pitch_ratio = target_freq / sample.root_freq
    elif target_note is not None:
        target_f = note_to_freq(target_note)
        pitch_ratio = target_f / sample.root_freq
    else:
        pitch_ratio = 1.0

    # 抽出对应片段
    start_sample = int(start_offset * sample.sr)
    src = sample.data[start_sample:]
    if len(src) < 1:
        return np.zeros(1, dtype=np.float64)

    # 重采样到目标采样率 + 变调
    # 变调 ratio = 播放速度。ratio > 1 → 更快 → 更高
    effective_ratio = pitch_ratio * (sample.sr / target_sr)

    # 目标长度
    if duration is not None:
        target_len = int(duration * target_sr)
    else:
        target_len = int(len(src) / effective_ratio)

    if target_len < 1:
        return np.zeros(1, dtype=np.float64)

    # 线性插值重采样
    src_indices = np.arange(target_len) * effective_ratio
    src_indices = np.clip(src_indices, 0, len(src) - 2)

    i0 = np.floor(src_indices).astype(int)
    frac = src_indices - i0
    result = src[i0] * (1.0 - frac) + src[i0 + 1] * frac

    # 防止截断噪声：淡出尾部
    fade_len = min(int(0.01 * target_sr), target_len)
    if fade_len > 0:
        fade = np.linspace(1.0, 0.0, fade_len)
        result[-fade_len:] *= fade

    result = result * volume
    result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)
    return result


# ═══════════════════════════════════════════════════════════════════════
# 鼓垫式 SamplePad
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PadSlot:
    """鼓垫上的一个槽位"""
    sample: Sample
    volume: float = 1.0
    pitch: float = 0.0  # 半音偏移


@dataclass
class SamplePad:
    """鼓垫/采样触发器 —— 类似 MPC 的 Pad。

    用法:
        >>> pad = SamplePad()
        >>> pad.add("kick", load_sample("kick.wav"), volume=0.8)
        >>> pad.add("snare", load_sample("snare.wav"), volume=0.7, pitch=-2)
        >>> kick_audio = pad.trigger("kick")
    """
    slots: Dict[str, PadSlot] = field(default_factory=dict)

    def add(
        self,
        key: str,
        sample: Sample,
        volume: float = 1.0,
        pitch: float = 0.0,  # 半音偏移
    ):
        """添加/覆盖一个 Pad 槽位"""
        self.slots[key] = PadSlot(
            sample=sample,
            volume=volume,
            pitch=pitch,
        )
        return self

    def remove(self, key: str):
        """移除一个 Pad 槽位"""
        self.slots.pop(key, None)
        return self

    def trigger(
        self,
        key: str,
        volume: float = 1.0,
        pitch: float = 0.0,
        duration: Optional[float] = None,
    ) -> np.ndarray:
        """触发一个 Pad。

        Args:
            key: Pad 键名
            volume: 覆盖音量 (1.0 = 使用槽位默认音量)
            pitch: 额外半音偏移 (叠加槽位默认 pitch)
            duration: 回放时长 (None=自动)

        Returns:
            音频数组

        Raises:
            KeyError: key 不存在
        """
        if key not in self.slots:
            raise KeyError(f"Pad '{key}' 不存在。可用的: {list(self.slots.keys())}")

        slot = self.slots[key]
        total_pitch = slot.pitch + pitch
        target_freq = slot.sample.root_freq * (2 ** (total_pitch / 12.0))
        total_vol = slot.volume * volume

        return play_sample(
            slot.sample,
            target_freq=target_freq,
            duration=duration,
            volume=total_vol,
        )

    @property
    def keys(self) -> List[str]:
        return list(self.slots.keys())


# ═══════════════════════════════════════════════════════════════════════
# 序列播放
# ═══════════════════════════════════════════════════════════════════════

def render_pad_sequence(
    pad: SamplePad,
    sequence: List[Tuple[float, str, float]],  # [(时间秒, key, volume), ...]
    total_duration: float,
    sr: int = _SR,
) -> np.ndarray:
    """按时间序列触发 Pad, 渲染为完整音频。

    Args:
        pad: SamplePad 实例
        sequence: [(触发时间秒, key, volume), ...] 按时间排序
        total_duration: 总时长 (秒)
        sr: 采样率

    Returns:
        混合音频 (float64)
    """
    n_samples = int(total_duration * sr)
    result = np.zeros(n_samples, dtype=np.float64)

    for time_sec, key, vol in sequence:
        sample_pos = int(time_sec * sr)
        if sample_pos >= n_samples:
            break

        audio = pad.trigger(key, volume=vol)
        end_pos = min(sample_pos + len(audio), n_samples)
        result[sample_pos:end_pos] += audio[:end_pos - sample_pos]

    # 限幅
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95

    return result


def render_sampler_pattern(
    pad: SamplePad,
    pattern,  # MusicPattern
    duration_sec: float,
    sample_map: Optional[Dict[str, str]] = None,
    sr: int = _SR,
) -> np.ndarray:
    """从 MusicPattern 渲染采样器轨道。

    将 MusicPattern 中的音符名映射到 SamplePad 的 Pad key，
    按时序触发采样。

    Args:
        pad: SamplePad 实例
        pattern: MusicPattern (notes → pad keys)
        duration_sec: 总时长 (秒)
        sample_map: {音符名: pad_key} 映射 (None = 音符名即 key)
        sr: 采样率

    Returns:
        混合音频 (float64)
    """
    beat_dur = 60.0 / pattern.bpm
    total_beats = sum(pattern.durations)
    loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

    # 构建时间序列
    sequence: List[Tuple[float, str, float]] = []
    current_time = 0.0

    for _ in range(loops):
        for i, note in enumerate(pattern.notes):
            dur = pattern.durations[i] * beat_dur
            if note is not None:
                key = sample_map.get(note, note) if sample_map else note
                if key in pad.slots:
                    sequence.append((current_time, key, pattern.volume))
            current_time += dur  # 更新: 不管是不是休止符都前进时间
            if current_time >= duration_sec:
                break

        if current_time >= duration_sec:
            break

    return render_pad_sequence(pad, sequence, duration_sec, sr)
