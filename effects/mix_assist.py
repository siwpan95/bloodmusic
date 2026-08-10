"""
智能混音助手 — 自动频率冲突检测 / 电平平衡 / 侧链闪避
======================================================

为多轨混音提供轻量级分析和辅助工具：
  - analyze_mix:          全面混音诊断
  - auto_level:           自动平衡各轨音量
  - ducking_sidechain:    侧链闪避（如 kick→bass）
  - freq_slot_allocator:  EQ 避让建议
  - mix_suggestion:       基于风格参考的混音建议

所有功能以"诊断+可选修正"模式工作，不强制修改音频。

用法:
    >>> from bloodmusic.effects.mix_assist import analyze_mix, auto_level
    >>> diagnosis = analyze_mix({"kick": kick_audio, "bass": bass_audio})
    >>> balanced = auto_level(tracks, target_rms=-18)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..core.constants import SR


# ═══════════════════════════════════════════════════════════════════════
# 诊断数据结构
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class FrequencyConflict:
    """频率冲突报告"""
    track_a: str
    track_b: str
    freq_range: Tuple[float, float]  # 冲突频率范围 (Hz)
    severity: float                   # 严重度 0~1
    recommendation: str = ""


@dataclass
class LevelImbalance:
    """电平不平衡报告"""
    track: str
    rms_db: float
    peak_db: float
    recommendation: str = ""


@dataclass
class MixDiagnosis:
    """全面混音诊断结果"""
    frequency_conflicts: List[FrequencyConflict] = field(default_factory=list)
    level_imbalances: List[LevelImbalance] = field(default_factory=list)
    phase_issues: List[Tuple[str, str, float]] = field(default_factory=list)
    headroom_db: float = 0.0
    overall_rms_db: float = 0.0
    track_count: int = 0
    warnings: List[str] = field(default_factory=list)

    def has_issues(self) -> bool:
        return bool(self.frequency_conflicts or self.level_imbalances or self.warnings)

    def summary(self) -> str:
        lines = [f"=== Mix Diagnosis ==="]
        lines.append(f"Tracks: {self.track_count}, Headroom: {self.headroom_db:.1f} dB, Overall RMS: {self.overall_rms_db:.1f} dB")
        if self.frequency_conflicts:
            lines.append(f"\nFrequency Conflicts ({len(self.frequency_conflicts)}):")
            for c in self.frequency_conflicts:
                lines.append(f"  {c.track_a} vs {c.track_b}: {c.freq_range[0]:.0f}-{c.freq_range[1]:.0f} Hz [severity:{c.severity:.2f}]")
        if self.level_imbalances:
            lines.append(f"\nLevel Imbalances ({len(self.level_imbalances)}):")
            for i in self.level_imbalances:
                lines.append(f"  {i.track}: RMS {i.rms_db:.1f} dB, Peak {i.peak_db:.1f} dB: {i.recommendation}")
        if self.warnings:
            lines.append(f"\nWarnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# 音频分析工具
# ═══════════════════════════════════════════════════════════════════════

def _compute_rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2) + 1e-10))

def _compute_peak(audio: np.ndarray) -> float:
    return float(np.max(np.abs(audio)))

def _rms_to_db(rms: float) -> float:
    return float(20 * np.log10(rms + 1e-10))

def _db_to_linear(db: float) -> float:
    return float(10 ** (db / 20.0))

def _compute_spectrum(audio: np.ndarray, fft_size: int = 4096) -> Tuple[np.ndarray, np.ndarray]:
    """计算音频的幅度谱"""
    if len(audio) < fft_size:
        fft_size = len(audio)
    spec = np.abs(np.fft.rfft(audio, n=fft_size))
    freqs = np.fft.rfftfreq(fft_size, 1.0 / SR)
    return freqs, spec


# ═══════════════════════════════════════════════════════════════════════
# 混音分析
# ═══════════════════════════════════════════════════════════════════════

def analyze_mix(tracks: Dict[str, np.ndarray]) -> MixDiagnosis:
    """分析多轨音频，检测潜在混音问题。

    Args:
        tracks: {轨道名: 音频数组} 字典

    Returns:
        MixDiagnosis 检测结果
    """
    diag = MixDiagnosis(track_count=len(tracks))

    if not tracks:
        return diag

    # ── 计算每轨频谱和电平 ──
    track_info = {}
    for name, audio in tracks.items():
        audio = audio.astype(np.float64)
        rms = _compute_rms(audio)
        peak = _compute_peak(audio)
        freqs, spec = _compute_spectrum(audio)
        track_info[name] = {
            "audio": audio, "rms": rms, "peak": peak,
            "freqs": freqs, "spec": spec,
        }

    # ── 整体电平 ──
    all_audio = np.sum([t["audio"] for t in track_info.values()], axis=0)
    peak_total = np.max(np.abs(all_audio))
    rms_total = _compute_rms(all_audio)
    diag.headroom_db = _rms_to_db(1.0) - _rms_to_db(peak_total)
    diag.overall_rms_db = _rms_to_db(rms_total)

    # ── 频率冲突检测 ──
    freq_bands = [
        ("sub_bass", 20, 80),
        ("bass", 80, 250),
        ("low_mid", 250, 500),
        ("mid", 500, 2000),
        ("high_mid", 2000, 5000),
        ("high", 5000, 12000),
    ]

    names = list(track_info.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_a, name_b = names[i], names[j]
            info_a, info_b = track_info[name_a], track_info[name_b]

            for band_name, f_low, f_high in freq_bands:
                mask = (info_a["freqs"] >= f_low) & (info_a["freqs"] <= f_high)
                if not np.any(mask):
                    continue

                energy_a = np.sum(info_a["spec"][mask])
                energy_b = np.sum(info_b["spec"][mask])
                total_energy = energy_a + energy_b + 1e-10

                # 两者都在该频段有显著能量 → 冲突
                overlap = 1.0 - abs(energy_a - energy_b) / total_energy
                # 提高能量阈值，减少纯正弦波的误报
                min_energy = max(energy_a, energy_b) * 0.1
                if overlap > 0.5 and energy_a > min_energy and energy_b > min_energy:
                    diag.frequency_conflicts.append(FrequencyConflict(
                        track_a=name_a, track_b=name_b,
                        freq_range=(f_low, f_high),
                        severity=min(1.0, overlap),
                        recommendation=f"建议对 {name_b} 在 {f_low}-{f_high}Hz 做 -3dB 衰减，或调整编排",
                    ))

    # ── 电平不平衡 ──
    rms_values = {n: _rms_to_db(t["rms"]) for n, t in track_info.items()}
    if rms_values:
        avg_rms = np.mean(list(rms_values.values()))
        for name, rms_db in rms_values.items():
            diff = rms_db - avg_rms
            if abs(diff) > 6:  # 超过 6dB 差
                rec = f"建议{'提升' if diff < 0 else '降低'} {abs(diff):.1f} dB"
                diag.level_imbalances.append(LevelImbalance(
                    track=name,
                    rms_db=rms_db,
                    peak_db=_rms_to_db(track_info[name]["peak"]),
                    recommendation=rec,
                ))

    # ── 警告 ──
    if diag.headroom_db < 3:
        diag.warnings.append(f"Headroom 仅 {diag.headroom_db:.1f} dB，建议降低整体电平")
    if diag.headroom_db < 0.5:
        diag.warnings.append("⚠ 接近削波！需要立即降低电平")

    return diag


# ═══════════════════════════════════════════════════════════════════════
# 自动电平平衡
# ═══════════════════════════════════════════════════════════════════════

def auto_level(
    tracks: Dict[str, np.ndarray],
    target_rms_db: float = -18.0,
) -> Dict[str, np.ndarray]:
    """自动平衡各轨音量到目标 RMS 电平。

    Args:
        tracks: {轨道名: 音频数组}
        target_rms_db: 目标 RMS 电平 (dB)，默认 -18dB

    Returns:
        电平平衡后的 {轨道名: 音频数组}
    """
    result = {}
    target_linear = _db_to_linear(target_rms_db)

    for name, audio in tracks.items():
        audio = audio.astype(np.float64)
        rms = _compute_rms(audio)
        if rms < 1e-10:
            result[name] = audio
            continue

        gain = target_linear / rms
        # 限制最大增益，避免噪声过大
        gain = min(gain, 4.0)
        result[name] = audio * gain

    return result


# ═══════════════════════════════════════════════════════════════════════
# 侧链闪避
# ═══════════════════════════════════════════════════════════════════════

def ducking_sidechain(
    source: np.ndarray,
    target: np.ndarray,
    threshold_db: float = -20.0,
    ratio: float = 4.0,
    attack_ms: float = 5.0,
    release_ms: float = 100.0,
    depth_db: float = 6.0,
    sr: int = SR,
) -> np.ndarray:
    """自动侧链闪避 — 当 source 有信号时降低 target 音量。

    典型应用: kick 触发 bass 音量降低，避免低频冲突。

    Args:
        source: 触发信号（如 kick 鼓）
        target: 被闪避信号（如 bass）
        threshold_db: 触发阈值 (dB)
        ratio: 压缩比
        attack_ms: 起音时间 (ms)
        release_ms: 释放时间 (ms)
        depth_db: 最大衰减量 (dB)
        sr: 采样率

    Returns:
        闪避处理后的 target 信号
    """
    n = min(len(source), len(target))
    if n == 0:
        return target

    source = source[:n].astype(np.float64)
    target = target[:n].astype(np.float64).copy()

    # 将 source 转为 envelope
    source_abs = np.abs(source)
    attack_coeff = np.exp(-1.0 / (attack_ms / 1000.0 * sr)) if attack_ms > 0 else 0.0
    release_coeff = np.exp(-1.0 / (release_ms / 1000.0 * sr)) if release_ms > 0 else 0.0

    envelope = np.zeros(n, dtype=np.float64)
    envelope[0] = source_abs[0]
    for i in range(1, n):
        coeff = attack_coeff if source_abs[i] > envelope[i - 1] else release_coeff
        envelope[i] = coeff * envelope[i - 1] + (1 - coeff) * source_abs[i]

    # 阈值检测
    threshold_linear = _db_to_linear(threshold_db)
    depth_linear = _db_to_linear(-depth_db)  # 衰减因子

    gain = np.ones(n, dtype=np.float64)
    above = envelope > threshold_linear
    if np.any(above):
        # 压缩: above_threshold 部分按 ratio 压缩
        over_db = 20 * np.log10(np.maximum(envelope, 1e-10) / threshold_linear + 1e-10)
        gain_db = -np.maximum(0, over_db) * (1 - 1.0 / ratio)
        gain[above] = 10.0 ** (gain_db[above] / 20.0)
        # 限制最大衰减
        gain = np.maximum(gain, depth_linear)

    # 平滑增益变化
    smoothed_gain = np.ones(n, dtype=np.float64)
    smooth_coeff = np.exp(-1.0 / (release_ms / 1000.0 * sr * 0.5))
    smoothed_gain[0] = gain[0]
    for i in range(1, n):
        smoothed_gain[i] = smooth_coeff * smoothed_gain[i - 1] + (1 - smooth_coeff) * gain[i]

    return target * smoothed_gain


# ═══════════════════════════════════════════════════════════════════════
# EQ 避让建议
# ═══════════════════════════════════════════════════════════════════════

def freq_slot_allocator(
    tracks: Dict[str, np.ndarray],
) -> Dict[str, List[Tuple[float, float, float]]]:
    """为每个轨道建议 EQ 调整以避免频率冲突。

    Returns:
        {track_name: [(freq_hz, gain_db, q), ...]}
    """
    suggestions = {}
    diag = analyze_mix(tracks)

    for conflict in diag.frequency_conflicts:
        # 对 track_b 建议在冲突频段做衰减
        f_low, f_high = conflict.freq_range
        center_freq = np.sqrt(f_low * f_high)
        bw_octaves = np.log2(f_high / f_low)
        q = 1.0 / bw_octaves if bw_octaves > 0 else 1.0

        gain_db = -3.0 * conflict.severity  # 严重度越高衰减越多

        if conflict.track_b not in suggestions:
            suggestions[conflict.track_b] = []
        suggestions[conflict.track_b].append(
            (center_freq, gain_db, max(0.5, min(5.0, q)))
        )

    return suggestions


# ═══════════════════════════════════════════════════════════════════════
# 风格参考混音建议
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MixStyleGuide:
    """混音风格参考参数"""
    target_rms_db: float = -14.0
    target_headroom_db: float = 3.0
    kick_peak_db: float = -6.0
    snare_peak_db: float = -8.0
    bass_rms_db: float = -18.0
    melody_rms_db: float = -20.0
    pad_rms_db: float = -24.0
    reverb_mix: float = 0.2
    compression_ratio: float = 2.0
    notes: str = ""


STYLE_GUIDES = {
    "edm": MixStyleGuide(
        target_rms_db=-10, target_headroom_db=2,
        kick_peak_db=-3, snare_peak_db=-6,
        bass_rms_db=-14, melody_rms_db=-16,
        reverb_mix=0.15, compression_ratio=4.0,
        notes="EDM: 高响度、紧实压缩、kick 突出",
    ),
    "orchestral": MixStyleGuide(
        target_rms_db=-18, target_headroom_db=6,
        kick_peak_db=-12, snare_peak_db=-14,
        bass_rms_db=-22, melody_rms_db=-20,
        reverb_mix=0.35, compression_ratio=1.5,
        notes="管弦乐: 保留动态、大混响、自然衰减",
    ),
    "lofi": MixStyleGuide(
        target_rms_db=-16, target_headroom_db=4,
        kick_peak_db=-8, snare_peak_db=-10,
        bass_rms_db=-16, melody_rms_db=-18,
        reverb_mix=0.1, compression_ratio=2.5,
        notes="Lo-Fi: 温暖、轻微饱和、少量混响",
    ),
    "rock": MixStyleGuide(
        target_rms_db=-12, target_headroom_db=3,
        kick_peak_db=-5, snare_peak_db=-5,
        bass_rms_db=-16, melody_rms_db=-14,
        reverb_mix=0.15, compression_ratio=3.0,
        notes="摇滚: 能量感、鼓和贝斯扎实",
    ),
    "jazz": MixStyleGuide(
        target_rms_db=-18, target_headroom_db=6,
        kick_peak_db=-10, snare_peak_db=-12,
        bass_rms_db=-18, melody_rms_db=-16,
        reverb_mix=0.2, compression_ratio=1.5,
        notes="爵士: 自然动态、宽松压缩、温暖氛围",
    ),
}


def mix_suggestion(
    diagnosis: MixDiagnosis,
    style: str = "edm",
) -> str:
    """基于风格参考给出整体混音建议。

    Args:
        diagnosis: analyze_mix 的诊断结果
        style: 风格参考 ("edm" | "orchestral" | "lofi" | "rock" | "jazz")

    Returns:
        可读的混音建议文本
    """
    guide = STYLE_GUIDES.get(style, STYLE_GUIDES["edm"])
    lines = [f"=== Mix Suggestion ({style}) ==="]
    lines.append(guide.notes)
    lines.append("")

    # 响度建议
    if diagnosis.overall_rms_db < guide.target_rms_db - 3:
        lines.append(f"[响度] 当前 RMS {diagnosis.overall_rms_db:.1f} dB < 目标 {guide.target_rms_db} dB")
        lines.append(f"  → 建议整体提升 {guide.target_rms_db - diagnosis.overall_rms_db:.1f} dB")
    elif diagnosis.overall_rms_db > guide.target_rms_db + 2:
        lines.append(f"[响度] 当前 RMS {diagnosis.overall_rms_db:.1f} dB > 目标 {guide.target_rms_db} dB")
        lines.append("  → 建议降低整体电平以避免失真")

    # Headroom 建议
    if diagnosis.headroom_db < guide.target_headroom_db:
        lines.append(f"[Headroom] 当前 {diagnosis.headroom_db:.1f} dB < 目标 {guide.target_headroom_db} dB")
        lines.append("  → 建议降低峰值电平")

    # 冲突处理
    if diagnosis.frequency_conflicts:
        lines.append(f"[冲突] 检测到 {len(diagnosis.frequency_conflicts)} 处频率冲突")
        for c in diagnosis.frequency_conflicts[:3]:
            lines.append(f"  → {c.recommendation}")

    if not lines[2:]:
        lines.append("混音状况良好，无需调整。")

    return "\n".join(lines)
