"""
Loop 无缝拼接 — 游戏音频循环点检测与无缝拼接
===============================================

针对游戏配乐的核心需求：任意音频片段可无缝循环播放，
循环点不产生爆音或相位跳变。

核心功能:
  - zero_crossing_detect: 在指定区域搜索最近的零交叉点
  - find_loop_points:     自动搜索最佳循环起止点
  - seamless_splice:      等功率交叉淡化拼接
  - make_loopable:        一键将音频变成可循环版本
  - loop_game_bgm:        针对游戏场景的优化封装

用法:
    >>> from bloodmusic.music.loop_utils import make_loopable, seamless_splice
    >>> audio = make_loopable(bgm_audio, target_duration=8.0, bpm=120)
    >>> # 或手动指定循环点
    >>> looped = seamless_splice(audio, loop_start_s, loop_end_s, crossfade_ms=20)
"""

from __future__ import annotations
from typing import Tuple, Optional
import numpy as np

from ..core.constants import SR


# ═══════════════════════════════════════════════════════════════════════
# 零交叉点检测
# ═══════════════════════════════════════════════════════════════════════

def zero_crossing_detect(
    audio: np.ndarray,
    region_start: int,
    region_end: int,
    direction: str = "either",
) -> int:
    """在指定区域搜索最近的零交叉点。

    Args:
        audio: 音频数组
        region_start: 搜索起始采样索引
        region_end: 搜索结束采样索引
        direction: "either" | "positive" | "negative"
                    either=任意方向, positive=负→正, negative=正→负

    Returns:
        零交叉点的采样索引，若未找到则返回 region_start
    """
    region_start = max(0, region_start)
    region_end = min(len(audio) - 1, region_end)

    if region_start >= region_end:
        return region_start

    segment = audio[region_start:region_end + 1]
    signs = np.sign(segment)

    if direction == "positive":
        crossings = np.where((signs[:-1] < 0) & (signs[1:] > 0))[0]
    elif direction == "negative":
        crossings = np.where((signs[:-1] > 0) & (signs[1:] < 0))[0]
    else:  # either
        crossings = np.where(signs[:-1] != signs[1:])[0]
        # 过滤掉涉及零值的情况
        crossings = crossings[(signs[crossings] != 0) | (signs[crossings + 1] != 0)]

    if len(crossings) > 0:
        return region_start + crossings[0]
    return region_start


# ═══════════════════════════════════════════════════════════════════════
# 循环点搜索
# ═══════════════════════════════════════════════════════════════════════

def find_loop_points(
    audio: np.ndarray,
    target_loop_sec: float,
    search_tail_range: Tuple[float, float] = (0.8, 1.0),
    sr: int = SR,
) -> Tuple[int, int]:
    """自动搜索最佳循环起止点。

    算法:
      1. 在音频尾部 search_tail_range 区间搜索零交叉点作为 loop_end
      2. 从 loop_end 向前倒退 target_loop_sec 找 loop_start
      3. 在 loop_start 附近搜索最近的零交叉点
      4. 返回修正后的 (loop_start, loop_end) 采样索引

    Args:
        audio: 音频数组
        target_loop_sec: 目标循环时长（秒）
        search_tail_range: 在音频尾部的搜索区间比例 (start_ratio, end_ratio)
        sr: 采样率

    Returns:
        (loop_start_sample, loop_end_sample) 采样索引
    """
    n = len(audio)
    target_samples = int(target_loop_sec * sr)

    if target_samples >= n:
        # 音频太短，从头到尾循环
        return 0, n

    # 搜索尾部零交叉点作为 loop_end
    tail_start = int(n * search_tail_range[0])
    tail_end = int(n * search_tail_range[1])

    # 在尾部区域搜索零交叉点
    loop_end = zero_crossing_detect(audio, tail_start, tail_end, "either")

    # 反向计算 loop_start
    loop_start = max(0, loop_end - target_samples)

    # 在 loop_start 附近搜索零交叉点（微调）
    search_radius = int(sr * 0.02)  # ±20ms
    start_search = max(0, loop_start - search_radius)
    end_search = min(n - 1, loop_start + search_radius)
    loop_start = zero_crossing_detect(audio, start_search, end_search, "either")

    return loop_start, loop_end


# ═══════════════════════════════════════════════════════════════════════
# 无缝拼接
# ═══════════════════════════════════════════════════════════════════════

def seamless_splice(
    audio: np.ndarray,
    loop_start: int,
    loop_end: int,
    crossfade_ms: float = 20.0,
    sr: int = SR,
) -> np.ndarray:
    """在循环点做等功率交叉淡化，实现无缝循环。

    将 loop_end 处的尾部和 loop_start 处的首部做等功率交叉淡化，
    然后拼接为: [0:loop_start] + [crossfade_region] + [loop_end+crossfade:]

    Args:
        audio: 音频数组
        loop_start: 循环起始采样索引
        loop_end: 循环结束采样索引
        crossfade_ms: 交叉淡化时长 (毫秒)
        sr: 采样率

    Returns:
        可无缝循环的音频数组
    """
    n = len(audio)
    crossfade_samples = int(crossfade_ms / 1000.0 * sr)

    if crossfade_samples <= 0:
        return audio

    # 确保不越界
    crossfade_samples = min(crossfade_samples, loop_end - loop_start,
                            n - loop_end, loop_start)

    if crossfade_samples <= 1:
        return audio

    # 从 loop_end 尾部取 fade_out 区域
    fade_out_start = loop_end - crossfade_samples
    if fade_out_start < 0:
        return audio
    fade_out_region = audio[fade_out_start:loop_end].copy()

    # 从 loop_start 首部取 fade_in 区域
    fade_in_region = audio[loop_start:loop_start + crossfade_samples].copy()
    # 检查相似度（避免循环点差异巨大导致相位问题）
    correlation = np.corrcoef(fade_out_region, fade_in_region)[0, 1]
    if correlation < -0.3:
        # 极性相反 → 翻转 fade_in 减少相位抵消
        fade_in_region = -fade_in_region

    # 等功率交叉淡化曲线: cos² 用于 fade_out, sin² 用于 fade_in
    t = np.linspace(0, np.pi / 2, crossfade_samples)
    fade_out_env = np.cos(t) ** 2
    fade_in_env = np.sin(t) ** 2

    # 混合
    mixed = fade_out_region * fade_out_env + fade_in_region * fade_in_env

    # 拼接待循环的版本
    # 结果大小: 移除 loop_start~loop_end 区间, 加入 crossfade_samples
    result_n = n - (loop_end - loop_start) + crossfade_samples
    result = np.zeros(result_n, dtype=audio.dtype)

    # [0 : loop_start] 保持不变
    result[:loop_start] = audio[:loop_start]
    # [loop_start : loop_start + crossfade_samples] = 混合区域
    result[loop_start:loop_start + crossfade_samples] = mixed
    # [loop_start + crossfade_samples :] = 循环结束后的部分
    remaining = audio[loop_end:]
    copy_len = min(len(remaining), result_n - (loop_start + crossfade_samples))
    result[loop_start + crossfade_samples:loop_start + crossfade_samples + copy_len] = remaining[:copy_len]

    return result


# ═══════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════

def make_loopable(
    audio: np.ndarray,
    target_duration: Optional[float] = None,
    bpm: Optional[int] = None,
    bars: Optional[int] = None,
    crossfade_ms: float = 20.0,
    sr: int = SR,
) -> np.ndarray:
    """一键将任意音频变成可无缝循环版本。

    会根据 BPM+小节数 或直接指定时长来计算目标循环长度。

    Args:
        audio: 输入音频
        target_duration: 目标循环时长（秒），优先级高于 bpm+bars
        bpm: BPM（与 bars 配合使用）
        bars: 小节数（与 bpm 配合使用）
        crossfade_ms: 交叉淡化时长 (毫秒)
        sr: 采样率

    Returns:
        可无缝循环的音频
    """
    # 计算目标循环时长
    if target_duration is not None:
        loop_sec = target_duration
    elif bpm is not None and bars is not None:
        loop_sec = bars * 4.0 * (60.0 / bpm)
    else:
        # 默认：取音频长度
        loop_sec = len(audio) / sr

    loop_start, loop_end = find_loop_points(audio, loop_sec, sr=sr)
    return seamless_splice(audio, loop_start, loop_end, crossfade_ms, sr)


def loop_game_bgm(
    audio: np.ndarray,
    loop_bars: int,
    bpm: int,
    crossfade_ms: float = 15.0,
    sr: int = SR,
) -> np.ndarray:
    """针对游戏 BGM 的优化循环处理。

    比 make_loopable 更激进：使用更短的交叉淡化 + 自动极性对齐。

    Args:
        audio: BGM 音频
        loop_bars: 循环小节数
        bpm: BPM
        crossfade_ms: 交叉淡化时长 (毫秒)，游戏 BGM 推荐短值 (10-20ms)
        sr: 采样率

    Returns:
        可无缝循环的 BGM
    """
    loop_sec = loop_bars * 4.0 * (60.0 / bpm)
    return make_loopable(audio, target_duration=loop_sec,
                         crossfade_ms=crossfade_ms, sr=sr)


def auto_loop(
    audio: np.ndarray,
    crossfade_ms: float = 15.0,
    sr: int = SR,
) -> np.ndarray:
    """全自动循环处理：使用最佳猜测拼接。

    Args:
        audio: 音频数组
        crossfade_ms: 交叉淡化时长 (毫秒)
        sr: 采样率

    Returns:
        可循环音频
    """
    return make_loopable(audio, crossfade_ms=crossfade_ms, sr=sr)


# ═══════════════════════════════════════════════════════════════════════
# 循环测试工具
# ═══════════════════════════════════════════════════════════════════════

def check_loop_quality(
    audio: np.ndarray,
    loop_start: int,
    loop_end: int,
    sr: int = SR,
) -> dict:
    """检查循环点质量，返回诊断信息。

    Returns:
        dict with:
          - correlation: 循环首尾相关度 (-1~1, 越高越好)
          - rms_ratio:   尾/首 RMS 比 (接近 1 为好)
          - peak_diff_db: 峰值差异 (dB, 越小越好)
          - is_good:      是否适合循环
    """
    check_len = int(0.05 * sr)  # 50ms
    check_len = min(check_len, loop_end - loop_start)

    if check_len <= 0:
        return {"correlation": 0, "rms_ratio": 0,
                "peak_diff_db": 999, "is_good": False}

    tail = audio[loop_end - check_len:loop_end]
    head = audio[loop_start:loop_start + check_len]

    # 相关度
    corr = np.corrcoef(tail, head)[0, 1]

    # RMS 比
    tail_rms = np.sqrt(np.mean(tail ** 2) + 1e-10)
    head_rms = np.sqrt(np.mean(head ** 2) + 1e-10)
    rms_ratio = tail_rms / head_rms

    # 峰值差异
    tail_peak = np.max(np.abs(tail)) + 1e-10
    head_peak = np.max(np.abs(head)) + 1e-10
    peak_diff_db = 20 * np.log10(tail_peak / head_peak)

    is_good = abs(corr) > 0.5 and 0.3 < rms_ratio < 3.0

    return {
        "correlation": float(corr),
        "rms_ratio": float(rms_ratio),
        "peak_diff_db": float(peak_diff_db),
        "is_good": is_good,
    }
