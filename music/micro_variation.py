"""
循环微变化系统 — 防止长时间循环听觉疲劳
========================================

基于指导第 5.2.4 节：为 MusicPattern 循环播放增加微变化：
- 装饰音概率触发
- 滤波器 LFO 缓慢调制
- 动态范围随机浮动
- 层次激活时间表
- 微妙的时值随机化
- 合成参数 drift

用法:
    from bloodmusic.music import MicroVariation, MicroVariationProcessor
    mv = MicroVariation(ornament_probability=0.2, filter_lfo_rate=0.1)
    proc = MicroVariationProcessor(pattern, mv)
    audio = proc.render_varied(30.0)  # 30秒带微变化的循环
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Callable
import numpy as np
import random

from ..core.constants import SR
from ..core.note_utils import note_to_freq
from ..core.oscillator import oscillator, OscType
from ..core.envelope import make_envelope, EnvShape


@dataclass
class MicroVariation:
    """微变化参数"""

    # ── 装饰音 ──
    ornament_probability: float = 0.15      # 每音符触发装饰音的概率
    ornament_types: List[str] = field(default_factory=lambda: [
        "grace_note",      # 短倚音（半音上方）
        "slide_in",        # 滑入（微音高弯曲）
        "trill",           # 快速交替（与上方邻音）
        "mordent",         # 波音（本音-上方-本音）
        "turn",            # 回音（上方-本音-下方-本音）
    ])
    ornament_max_duration: float = 0.08     # 装饰音最大时长 (秒)

    # ── 滤波器 LFO ──
    filter_lfo_enabled: bool = True
    filter_lfo_rate: float = 0.05           # LFO 频率 (Hz) — 非常慢的调制
    filter_lfo_depth: float = 0.3           # LFO 深度 (cutoff 范围比例)
    filter_lfo_phase: float = 0.0           # 初始相位

    # ── 动态范围微调 ──
    dynamic_variation: float = 2.0          # 音量 ±dB 范围
    dynamic_correlation: float = 0.7        # 0=完全随机, 1=慢速渐变

    # ── 时值微调 ──
    timing_humanize: float = 0.015          # 时值随机化 (秒), 模拟人类演奏的不精确
    timing_swing: float = 0.0               # Swing 量 (0=均匀, 0.5=强Swing)

    # ── 音高微调 ──
    pitch_drift_range: float = 3.0          # 音高漂移范围 (cents)
    pitch_drift_rate: float = 0.02          # 音高漂移速率 (Hz)

    # ── 层次激活 ──
    layer_activation: Optional[List[Tuple[float, str]]] = None  # [(时间, 层名)]
    layer_schedule_period: float = 30.0      # 层次循环周期 (秒)

    # ── 合成参数漂移 ──
    osc_drift: bool = True                  # 振荡器参数漂移
    env_drift: bool = True                  # 包络参数漂移
    drift_amount: float = 0.05              # 漂移量 (0-1)

    # ── 种子 ──
    seed: Optional[int] = None              # 可重现随机


class MicroVariationProcessor:
    """
    微变化处理器 — 对 MusicPattern 循环渲染施加微妙变化

    用法:
        from bloodmusic.music import MusicPattern, MicroVariation, MicroVariationProcessor

        pattern = MusicPattern(name="my_track", notes=[...], durations=[...], bpm=120)
        mv = MicroVariation(ornament_probability=0.2, filter_lfo_rate=0.05)
        proc = MicroVariationProcessor(pattern, mv)
        audio = proc.render_varied(60.0)  # 60秒带变化的循环
    """

    def __init__(self, pattern, variation: Optional[MicroVariation] = None):
        """
        pattern: MusicPattern 对象
        variation: 微变化参数 (默认使用基础参数)
        """
        self.pattern = pattern
        self.variation = variation or MicroVariation()
        self._rng = random.Random(self.variation.seed)

    def render_varied(self, duration_sec: float) -> np.ndarray:
        """
        渲染带微变化的音频。

        duration_sec: 总时长 (秒)
        """
        mv = self.variation
        rng = self._rng

        beat_dur = 60.0 / self.pattern.bpm
        total_beats = sum(self.pattern.durations)
        loop_duration = total_beats * beat_dur

        if not self.pattern.loop:
            loop_duration = min(loop_duration, duration_sec)

        octaves = self.pattern.octave_shifts or [0] * len(self.pattern.notes)
        notes = self.pattern.notes
        durations = self.pattern.durations

        # 收集所有音符事件（含循环）
        all_events = []
        elapsed = 0.0
        loop_count = 0
        while elapsed < duration_sec:
            for i, note in enumerate(notes):
                dur = durations[i] * beat_dur
                oct_v = octaves[i] if i < len(octaves) else 0
                all_events.append((elapsed, note, dur, oct_v, loop_count, i))
                elapsed += dur
            loop_count += 1
            if not self.pattern.loop:
                break

        # 音频缓冲区
        n_total = int(duration_sec * SR)
        audio = np.zeros(n_total, dtype=np.float64)

        # 噪声种子（连续噪声生成）
        noise_state = rng.getstate()

        # 缓慢变化的全局参数
        for idx, (event_time, note, dur, oct_v, loop_idx, note_idx) in enumerate(all_events):
            # 跳过超出范围的
            if event_time >= duration_sec:
                continue

            sample_start = int(event_time * SR)
            if sample_start >= n_total:
                continue

            # ── 时值 humanize ──
            if mv.timing_humanize > 0:
                dur += rng.uniform(-mv.timing_humanize, mv.timing_humanize)
                dur = max(0.02, dur)

            # ── Swing ──
            if mv.timing_swing > 0 and note_idx % 2 == 1:
                dur *= (1.0 + mv.timing_swing * 0.3)

            n_samp = int(dur * SR)
            if n_samp < 1:
                n_samp = 1

            sample_end = min(sample_start + n_samp, n_total)
            actual_n = sample_end - sample_start
            if actual_n <= 0:
                continue

            t = np.linspace(0, dur, actual_n, dtype=np.float64)

            # ── 休止符 ──
            if note is None:
                continue

            # ── 核心合成 ──
            f_base = note_to_freq(note) * (2 ** oct_v)

            # 音高漂移
            if mv.pitch_drift_range > 0:
                drift_phase = event_time * mv.pitch_drift_rate
                drift_cents = np.sin(2 * np.pi * drift_phase) * mv.pitch_drift_range
                # 添加一些随机抖动
                drift_cents += rng.uniform(-2, 2)
                f = f_base * (2 ** (drift_cents / 1200.0))
            else:
                f = f_base

            # 振荡器
            osc_type = self.pattern.osc_type
            sig = oscillator(t, f, osc_type)

            for h_mult, h_amp in self.pattern.harmonics:
                sig += oscillator(t, f * h_mult, osc_type) * h_amp

            # 颤音
            if self.pattern.vibrato_depth > 0:
                vib_env = make_envelope(actual_n, EnvShape.PAD)
                vib_rate = self.pattern.vibrato_rate * (1.0 + rng.uniform(-0.1, 0.1) * mv.drift_amount)
                vib_depth = self.pattern.vibrato_depth * (1.0 + rng.uniform(-0.05, 0.05) * mv.drift_amount)
                vib = 1.0 + (vib_depth / 12) * np.sin(2 * np.pi * vib_rate * t) * vib_env
                sig_mod = oscillator(t, f * vib, osc_type)
                for h_mult, h_amp in self.pattern.harmonics:
                    sig_mod += oscillator(t, f * vib * h_mult, osc_type) * h_amp
                sig = sig_mod

            # 包络 (带漂移)
            env = make_envelope(actual_n, self.pattern.env_shape)

            # ── 动态范围浮动 ──
            if mv.dynamic_variation > 0:
                # 使用事件时间做慢速渐变
                dyn_phase = event_time * mv.dynamic_correlation * 0.1
                dyn_db = np.sin(2 * np.pi * dyn_phase) * mv.dynamic_variation
                dyn_db += rng.uniform(-mv.dynamic_variation * 0.3, mv.dynamic_variation * 0.3)
                dyn_linear = 10 ** (dyn_db / 20.0)
                vol = self.pattern.volume * dyn_linear
            else:
                vol = self.pattern.volume

            sig = sig * env * vol

            # ── 装饰音 ──
            if mv.ornament_probability > 0 and rng.random() < mv.ornament_probability:
                ornament_type = rng.choice(mv.ornament_types)
                max_orn_samp = min(int(mv.ornament_max_duration * SR), actual_n // 4)
                if max_orn_samp > 4:
                    orn_sig = self._render_ornament(
                        ornament_type, f, t, actual_n, rng, mv,
                    )
                    sig[:len(orn_sig)] += orn_sig[:len(sig[:len(orn_sig)])]

            # ── 层次激活 ──
            layer_mult = 1.0
            if mv.layer_activation:
                for (layer_time, layer_name) in mv.layer_activation:
                    # 检查事件时间是否在这个层激活窗口内
                    relative_time = event_time % mv.layer_schedule_period
                    if abs(relative_time - layer_time) < mv.layer_schedule_period * 0.1:
                        if layer_name == "muted":
                            layer_mult = 0.0
                        elif layer_name == "soft":
                            layer_mult = 0.3
                        elif layer_name == "full":
                            layer_mult = 1.0
                        elif layer_name == "accent":
                            layer_mult = 1.3

            sig *= layer_mult

            # 写入音频缓冲区
            audio[sample_start:sample_end] += sig[:actual_n]

        # ── 全局滤波器 LFO ──
        if mv.filter_lfo_enabled and mv.filter_lfo_depth > 0:
            audio = self._apply_filter_lfo(audio, mv)

        # ── 归一化 ──
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak * 0.9

        return audio

    def _render_ornament(
        self,
        orn_type: str,
        base_freq: float,
        t: np.ndarray,
        n_samp: int,
        rng: random.Random,
        mv: MicroVariation,
    ) -> np.ndarray:
        """渲染装饰音"""
        max_orn = min(int(mv.ornament_max_duration * SR), n_samp // 4)
        if max_orn < 4:
            return np.zeros(n_samp, dtype=np.float64)

        orn_sig = np.zeros(n_samp, dtype=np.float64)
        orn_vol = self.pattern.volume * 0.35

        if orn_type == "grace_note":
            # 半音上方短倚音
            grace_freq = base_freq * (2 ** (1 / 12))  # 半音上
            grace_len = min(max_orn, int(0.04 * SR))
            grace_env = np.exp(-np.linspace(0, 3, grace_len))
            orn_sig[:grace_len] = np.sin(2 * np.pi * grace_freq * t[:grace_len]) * grace_env * orn_vol

        elif orn_type == "slide_in":
            # 频率滑入
            slide_len = min(max_orn, int(0.06 * SR))
            slide_freqs = np.linspace(base_freq * 0.85, base_freq, slide_len)
            phase = np.cumsum(2 * np.pi * slide_freqs / SR)
            orn_sig[:slide_len] = np.sin(phase) * orn_vol

        elif orn_type == "trill":
            # 快速交替
            trill_len = min(max_orn, int(0.08 * SR))
            trill_rate = base_freq * 0.12  # trill rate
            trill_mod = 1.0 + 0.08 * np.sin(2 * np.pi * trill_rate * t[:trill_len])
            phase = np.cumsum(2 * np.pi * base_freq * trill_mod / SR)
            orn_sig[:trill_len] = np.sin(phase) * orn_vol

        elif orn_type == "mordent":
            # 波音：本音→上方邻音→本音
            orn_len = int(max_orn * 0.5)
            up_freq = base_freq * (2 ** (2 / 12))
            seg1 = int(orn_len * 0.3)
            seg2 = int(orn_len * 0.4)
            seg3 = orn_len - seg1 - seg2
            orn_sig[:seg1] = np.sin(2 * np.pi * base_freq * t[:seg1]) * orn_vol
            orn_sig[seg1:seg1 + seg2] = np.sin(2 * np.pi * up_freq * t[:seg2]) * orn_vol * 0.7
            if seg1 + seg2 + seg3 <= n_samp:
                orn_sig[seg1 + seg2:seg1 + seg2 + seg3] = np.sin(2 * np.pi * base_freq * t[:seg3]) * orn_vol * 0.5

        elif orn_type == "turn":
            # 回音
            orn_len = min(max_orn, int(0.07 * SR))
            up = base_freq * (2 ** (2 / 12))
            down = base_freq * (2 ** (-2 / 12))
            step = orn_len // 4
            offsets = [0, step, step * 2, step * 3]
            freqs = [base_freq, up, base_freq, down]
            for j, (off, freq) in enumerate(zip(offsets, freqs)):
                end = min(off + step, n_samp)
                if off < n_samp:
                    seg_len = end - off
                    orn_sig[off:end] = np.sin(2 * np.pi * freq * t[:seg_len]) * orn_vol * (0.8 - j * 0.15)

        return orn_sig

    def _apply_filter_lfo(self, audio: np.ndarray, mv: MicroVariation) -> np.ndarray:
        """
        全局滤波器 LFO — 缓慢调制低通截止频率，
        模拟模拟合成器的漂移感。
        """
        from ..effects.filters import apply_lowpass

        n = len(audio)
        t = np.linspace(0, n / SR, n)

        # LFO 信号 (0.3 ~ 1.0)
        lfo = 0.65 + mv.filter_lfo_depth * np.sin(2 * np.pi * mv.filter_lfo_rate * t)

        # 分块处理（高效）
        block_size = 4096
        result = np.zeros_like(audio)

        for i in range(0, n, block_size):
            end = min(i + block_size, n)
            block = audio[i:end]
            cutoff = 1500.0 + 8000.0 * lfo[i]  # cutoff 1500-9500 Hz
            result[i:end] = apply_lowpass(block, cutoff)

        return result
