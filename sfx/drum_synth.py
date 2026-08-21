"""
模拟鼓合成器 — 808 风格底鼓 / 军鼓 / 踩镲 + 鼓层叠
=====================================================

实现经典 Roland TR-808 风格的模拟鼓合成算法，全部通过纯合成
（无采样）生成专业级电子鼓音色。

808 Kick 原理:
    1. 正弦波振荡器 → 频率从高到低快速扫频
    2. 扫频速度控制"冲击感"
    3. 可叠加谐波失真增加"咬合感"

使用方式:
    >>> from bloodmusic.sfx.drum_synth import synthesize_808_kick
    >>> kick = synthesize_808_kick(freq_start=150, freq_end=40, duration=0.4)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

from ..core.constants import SR


# ══════════════════════════════════════════════════════════════
# 808 底鼓合成
# ══════════════════════════════════════════════════════════════

@dataclass
class Kick808Params:
    """808 底鼓合成参数"""
    freq_start: float = 150.0          # 起始频率 (Hz)
    freq_end: float = 40.0             # 结束频率 (Hz)
    duration: float = 0.4              # 总时长 (秒)
    freq_decay: float = 0.06           # 频率衰减时间 (秒)
    amp_decay: float = 0.25            # 振幅衰减时间 (秒)
    click_level: float = 0.3           # 起始 click/attack 量
    distortion: float = 0.0            # 软削波失真 0~1
    volume: float = 0.8               # 总音量


def synthesize_808_kick(
    params: Optional[Kick808Params] = None,
) -> np.ndarray:
    """合成 808 风格底鼓。

    原理:
        1. 频率指数衰减: f(t) = f_end + (f_start - f_end) * exp(-t / freq_decay)
        2. 相位积分 + sin 生成波形
        3. 振幅指数衰减
        4. 可选 soft clipping 失真

    Args:
        params: 合成参数，None 为默认

    Returns:
        底鼓音频 (float64, 归一化 -1~1)

    Examples:
        >>> # 短促有力
        >>> kick = synthesize_808_kick(Kick808Params(duration=0.3, freq_decay=0.04))
        >>> # 深沉长冲
        >>> kick = synthesize_808_kick(Kick808Params(freq_start=120, freq_end=30, duration=0.6))
    """
    if params is None:
        params = Kick808Params()

    n = int(params.duration * SR)
    if n < 1:
        n = 1

    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 频率扫频曲线 (指数衰减)
    freq = params.freq_end + (params.freq_start - params.freq_end) * np.exp(
        -t / max(params.freq_decay, 0.001)
    )

    # 振幅包络 (指数衰减)
    amp_env = np.exp(-t / max(params.amp_decay, 0.001))

    # 通过积分频率生成相位，再取 sin
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    sig = np.sin(phase)

    # 添加 click (白噪声短暂的冲击)
    if params.click_level > 0:
        click_dur = int(0.005 * SR)  # 5ms
        click_dur = min(click_dur, n)
        click = np.random.uniform(-1, 1, n)
        click_env = np.exp(-np.arange(n) / max(click_dur * 0.3, 1))
        sig += click * click_env * params.click_level

    # 应用振幅包络
    sig = sig * amp_env * params.volume

    # 可选失真 (tanh 软削波)
    if params.distortion > 0:
        drive = 1.0 + params.distortion * 8.0
        sig = np.tanh(sig * drive) / np.tanh(drive)

    # 归一化
    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak

    return sig


# ══════════════════════════════════════════════════════════════
# 808 军鼓合成
# ══════════════════════════════════════════════════════════════

@dataclass
class Snare808Params:
    """808 军鼓合成参数"""
    tone_freq: float = 180.0      # 色调频率 (Hz)
    tone_decay: float = 0.1       # 色调衰减 (秒)
    noise_decay: float = 0.15     # 噪声衰减 (秒)
    tone_level: float = 0.5       # 色调分量音量
    noise_level: float = 0.7      # 噪声分量音量
    duration: float = 0.25        # 总时长
    volume: float = 0.8


def synthesize_808_snare(
    params: Optional[Snare808Params] = None,
) -> np.ndarray:
    """合成 808 风格军鼓。

    两层混合:
        1. Tone 层: 正弦波扫频 (模拟鼓腔共振)
        2. Noise 层: 白噪声滤除低频 (模拟沙锤声)

    Args:
        params: 合成参数

    Returns:
        军鼓音频
    """
    if params is None:
        params = Snare808Params()

    n = int(params.duration * SR)
    if n < 1:
        n = 1

    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # Tone 层 - 正弦扫频
    freq = params.tone_freq * np.exp(-t / max(params.tone_decay, 0.001))
    phase = 2.0 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase)
    tone_env = np.exp(-t / max(params.tone_decay * 2, 0.001))
    tone = tone * tone_env * params.tone_level

    # Noise 层 - 白噪声 + 高频衰减
    noise = np.random.uniform(-1, 1, n)
    noise_env = np.exp(-t / max(params.noise_decay, 0.001))
    noise = noise * noise_env * params.noise_level

    # 对 noise 做简单的高通 (去掉过多低频)
    from ..effects.filters import apply_highpass
    noise = apply_highpass(noise, 500.0)

    # 混合
    sig = tone + noise
    sig *= params.volume

    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak

    return sig.astype(np.float64)


# ══════════════════════════════════════════════════════════════
# 808 踩镲合成
# ══════════════════════════════════════════════════════════════

@dataclass
class Hihat808Params:
    """808 踩镲合成参数"""
    osc_freq: float = 8000.0        # 振荡器频率 (Hz) — 决定音高
    decay: float = 0.05             # 衰减时间 (秒)
    hp_freq: float = 2000.0         # 高通截止
    noise_mix: float = 0.8          # 噪声混合比
    duration: float = 0.1           # 总时长
    volume: float = 0.6


def synthesize_808_hihat(
    params: Optional[Hihat808Params] = None,
) -> np.ndarray:
    """合成 808 风格踩镲。

    原理:
        6个方波振荡器 (非谐波关系) + 白噪声 → 高通滤波 → 快速衰减

    Args:
        params: 合成参数

    Returns:
        踩镲音频
    """
    if params is None:
        params = Hihat808Params()

    n = int(params.duration * SR)
    if n < 1:
        n = 1

    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 多个非谐波方波产生金属质感
    ratios = [1.0, 1.342, 1.782, 2.243, 2.895, 3.471]
    metallic = np.zeros(n, dtype=np.float64)
    for ratio in ratios:
        metallic += np.sign(np.sin(2.0 * np.pi * params.osc_freq * ratio * t)) * 0.15

    # 白噪声
    noise = np.random.uniform(-1, 1, n) * params.noise_mix

    # 混合
    sig = metallic + noise

    # 高通滤波器
    from ..effects.filters import apply_highpass
    sig = apply_highpass(sig, params.hp_freq)

    # 快速衰减包络
    env = np.exp(-t / max(params.decay, 0.001))
    sig = sig * env * params.volume

    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak

    return sig.astype(np.float64)


# ══════════════════════════════════════════════════════════════
# Open Hihat (开镲)
# ══════════════════════════════════════════════════════════════

def synthesize_808_open_hihat(
    freq: float = 8000.0,
    decay: float = 0.4,
    volume: float = 0.5,
) -> np.ndarray:
    """合成 808 风格开镲 (比闭镲衰减更长)。"""
    params = Hihat808Params(
        osc_freq=freq,
        decay=decay,
        duration=decay * 1.2,
        volume=volume,
        noise_mix=0.6,
    )
    return synthesize_808_hihat(params)


# ══════════════════════════════════════════════════════════════
# 808 Clap 合成
# ══════════════════════════════════════════════════════════════

def synthesize_808_clap(
    duration: float = 0.2,
    volume: float = 0.7,
) -> np.ndarray:
    """合成 808 风格拍手声。

    原理:
        多层噪声 + 延迟线模拟多人拍手的时间散布

    Returns:
        拍手声音频
    """
    n = int(duration * SR)
    if n < 1:
        n = 1

    t = np.linspace(0, duration, n, dtype=np.float64)

    # 3 层噪声模拟多次拍手
    sig = np.zeros(n, dtype=np.float64)

    # 密集的短噪声 burst
    bursts = [0, 8, 16, 24]  # 延迟 (ms)
    for delay_ms in bursts:
        delay_samp = int(delay_ms / 1000.0 * SR)
        if delay_samp >= n:
            continue
        noise_burst = np.random.uniform(-1, 1, n - delay_samp)
        env = np.exp(-np.arange(len(noise_burst)) / max(0.01 * SR, 1))
        noise_burst = noise_burst * env
        sig[delay_samp:delay_samp + len(noise_burst)] += noise_burst

    # 高通滤波
    from ..effects.filters import apply_highpass
    sig = apply_highpass(sig, 1000.0)

    sig = sig * volume

    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig / peak

    return sig.astype(np.float64)


# ══════════════════════════════════════════════════════════════
# 鼓层叠系统
# ══════════════════════════════════════════════════════════════

@dataclass
class DrumLayer:
    """单个鼓层"""
    audio: np.ndarray
    gain: float = 1.0
    delay_ms: float = 0.0    # 微延迟 (ms)，用于 flam 效果
    pitch_shift: float = 0.0  # 音高偏移 (半音)


def layer_drums(layers: List[DrumLayer], sr: int = SR) -> np.ndarray:
    """多层鼓叠加，支持微延迟和增益调节。

    用于创造更丰富的鼓音色:
        - 底鼓 = 低频 punch 层 + 高频 click 层
        - 军鼓 = 低频 body 层 + 高频 snappy 层 + 噪声层
        - 踩镲 = 紧致闭镲 + 松散开镲

    Args:
        layers: 鼓层列表
        sr: 采样率

    Returns:
        叠加后的鼓 sound

    Example:
        >>> # 双层底鼓: punchy low + clicky high
        >>> kick_low = synthesize_808_kick(Kick808Params(freq_start=100, freq_end=35))
        >>> kick_click = synthesize_808_kick(Kick808Params(freq_start=300, freq_end=180, duration=0.08))
        >>> layered_kick = layer_drums([
        ...     DrumLayer(kick_low, gain=0.8),
        ...     DrumLayer(kick_click, gain=0.3, delay_ms=2),
        ... ])
    """
    if not layers:
        return np.array([], dtype=np.float64)

    # 计算最大长度
    max_len = 0
    delayed_layers = []
    for layer in layers:
        delay_samp = int(layer.delay_ms / 1000.0 * sr)
        padded = np.pad(layer.audio, (delay_samp, 0))
        if layer.pitch_shift != 0:
            # 简单的重采样实现音高偏移
            ratio = 2.0 ** (-layer.pitch_shift / 12.0)
            old_len = len(padded)
            new_len = int(old_len * ratio)
            if new_len > 0:
                x_old = np.linspace(0, 1, old_len)
                x_new = np.linspace(0, 1, new_len)
                padded = np.interp(x_new, x_old, padded)
                # 补齐到原始长度
                if len(padded) < old_len:
                    padded = np.pad(padded, (0, old_len - len(padded)))

        delayed_layers.append((padded[:max(old_len := max(max_len, len(padded)), max_len)], layer.gain))

    # 混合
    result = np.zeros(max_len, dtype=np.float64)
    for audio, gain in delayed_layers:
        audio_padded = np.pad(audio, (0, max_len - len(audio)))
        result += audio_padded * gain

    # 归一化
    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak

    return result


# ══════════════════════════════════════════════════════════════
# 808 全套鼓组
# ══════════════════════════════════════════════════════════════

@dataclass
class DrumKit808:
    """完整的 808 鼓组"""
    kick: np.ndarray
    snare: np.ndarray
    hihat_closed: np.ndarray
    hihat_open: np.ndarray
    clap: np.ndarray
    sr: int = SR


def create_808_kit() -> DrumKit808:
    """创建一套完整的 808 鼓组。

    Returns:
        DrumKit808 包含所有核心鼓音色
    """
    return DrumKit808(
        kick=synthesize_808_kick(),
        snare=synthesize_808_snare(),
        hihat_closed=synthesize_808_hihat(),
        hihat_open=synthesize_808_open_hihat(),
        clap=synthesize_808_clap(),
    )


# ══════════════════════════════════════════════════════════════
# 预置库
# ══════════════════════════════════════════════════════════════

KICK_808_PRESETS: Dict[str, Kick808Params] = {
    "standard": Kick808Params(),
    "punchy": Kick808Params(
        freq_start=200, freq_end=45, duration=0.3,
        freq_decay=0.04, amp_decay=0.15, click_level=0.4, distortion=0.15,
    ),
    "deep": Kick808Params(
        freq_start=120, freq_end=30, duration=0.6,
        freq_decay=0.1, amp_decay=0.3, click_level=0.1,
    ),
    "short": Kick808Params(
        freq_start=180, freq_end=60, duration=0.15,
        freq_decay=0.03, amp_decay=0.1, click_level=0.5,
    ),
    "distorted": Kick808Params(
        freq_start=150, freq_end=40, duration=0.4,
        freq_decay=0.05, amp_decay=0.2, click_level=0.3, distortion=0.5,
    ),
    "trap_808": Kick808Params(
        freq_start=100, freq_end=35, duration=0.6,
        freq_decay=0.08, amp_decay=0.3, click_level=0.15, distortion=0.3,
    ),
    "soft": Kick808Params(
        freq_start=130, freq_end=50, duration=0.5,
        freq_decay=0.08, amp_decay=0.25, click_level=0.05,
    ),
}

SNARE_808_PRESETS: Dict[str, Snare808Params] = {
    "standard": Snare808Params(),
    "tight": Snare808Params(
        tone_freq=200, tone_decay=0.06, noise_decay=0.08, duration=0.15,
    ),
    "heavy": Snare808Params(
        tone_freq=150, tone_decay=0.12, noise_decay=0.2,
        tone_level=0.6, noise_level=0.8, duration=0.3,
    ),
    "rim": Snare808Params(
        tone_freq=500, tone_decay=0.03, noise_decay=0.05,
        tone_level=0.7, noise_level=0.3, duration=0.1,
    ),
}


# ══════════════════════════════════════════════════════════════
# 原声鼓合成 (Acoustic Drum Synthesis) — P1 增强
# ══════════════════════════════════════════════════════════════

from dataclasses import dataclass as _dataclass_std

@_dataclass_std
class TomParams:
    """通鼓合成参数 (膜振动 + 腔体共振模型)"""
    freq_hz: float = 150.0      # 基频 (hi=300, mid=200, lo=120, floor=80)
    duration: float = 0.4
    bend_depth: float = 0.15    # 音高下沉量 (0-1)
    tone_mix: float = 0.6       # 音调 vs 噪声
    volume: float = 0.8


def synthesize_tom(params: TomParams = None, sr: int = SR) -> np.ndarray:
    """合成通鼓音色。

    膜振动模型：快速频率扫掠 + 谐波 + 噪声冲击。
    """
    if params is None:
        params = TomParams()
    n = int(params.duration * sr)
    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 频率扫掠 (打击瞬间频率最高，然后快速下降)
    freq_env = np.exp(-t / (params.duration * 0.15))
    freq = params.freq_hz * (1.0 + params.bend_depth * freq_env)

    # 相位累积
    phase = 2.0 * np.pi * np.cumsum(freq) / sr

    # 音调层 (正弦 + 谐波)
    tone = np.sin(phase) * 0.6 + np.sin(phase * 2) * 0.25 + np.sin(phase * 3) * 0.1

    # 噪声冲击层
    noise = np.random.randn(n) * 0.4
    noise_env = np.exp(-t / (params.duration * 0.08))
    noise *= noise_env

    # 混合
    result = tone * params.tone_mix + noise * (1.0 - params.tone_mix)

    # 振幅包络
    amp_env = np.exp(-t / (params.duration * 0.2))
    result *= amp_env * params.volume

    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95

    return result


@_dataclass_std
class CrashParams:
    """镲片合成参数"""
    duration: float = 1.5
    brightness: float = 0.7    # 亮度 (0=暗, 1=亮)
    volume: float = 0.7


def synthesize_crash(params: CrashParams = None, sr: int = SR) -> np.ndarray:
    """合成镲片/吊镲音色。

    多层金属噪声模型。
    """
    if params is None:
        params = CrashParams()
    n = int(params.duration * sr)
    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 多层带通噪声模拟金属共振
    result = np.zeros(n, dtype=np.float64)
    noise = np.random.randn(n)

    # 多个共振频率带
    freqs = [3000, 5000, 8000, 12000]
    for f in freqs:
        # 简易带通: sin 调制噪声
        band = noise * np.sin(2 * np.pi * f * t) * params.brightness * 0.3
        result += band

    # 振幅包络 (长衰减)
    amp_env = np.exp(-t / (params.duration * 0.3))
    result *= amp_env * params.volume

    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95

    return result


@_dataclass_std
class ShakerParams:
    """沙锤/摇铃合成参数"""
    duration: float = 0.15
    density: float = 0.8      # 颗粒密度
    brightness: float = 0.6   # 亮度
    volume: float = 0.5


def synthesize_shaker(params: ShakerParams = None, sr: int = SR) -> np.ndarray:
    """合成沙锤/摇铃音色。

    高频噪声脉冲串模拟颗粒碰撞。
    """
    if params is None:
        params = ShakerParams()
    n = int(params.duration * sr)
    result = np.zeros(n, dtype=np.float64)

    # 脉冲密度
    n_pulses = int(params.duration * sr * params.density / 2000)
    for _ in range(n_pulses):
        pos = np.random.randint(0, n - 50)
        pulse = np.random.randn(50) * np.exp(-np.arange(50) / 10)
        result[pos:pos + 50] += pulse * params.brightness

    # 高通滤波 (简易: 差分)
    result = np.diff(np.pad(result, (1, 0)))
    result *= params.volume

    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95

    return result


@_dataclass_std
class AcousticSnareParams:
    """原声军鼓合成参数 (比 808 snare 更丰富的腔体共鸣)"""
    body_freq: float = 180.0
    duration: float = 0.3
    body_mix: float = 0.5
    ring_mix: float = 0.3
    noise_mix: float = 0.4
    volume: float = 0.8


def synthesize_acoustic_snare(params: AcousticSnareParams = None,
                              sr: int = SR) -> np.ndarray:
    """合成原声军鼓。

    三层模型：膜振动主体 + 弹簧响弦 + 噪声冲击。
    """
    if params is None:
        params = AcousticSnareParams()
    n = int(params.duration * sr)
    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 主体 (膜振动)
    body = np.sin(2 * np.pi * params.body_freq * t) * np.exp(-t / 0.08)

    # 响弦 (高频金属共振)
    ring_freqs = [1200, 2500, 4000]
    ring = np.zeros(n)
    for f in ring_freqs:
        ring += np.sin(2 * np.pi * f * t) * 0.15 * np.exp(-t / 0.12)

    # 噪声冲击
    noise = np.random.randn(n) * np.exp(-t / 0.06)

    result = (body * params.body_mix +
              ring * params.ring_mix +
              noise * params.noise_mix)
    result *= params.volume

    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95

    return result


@_dataclass_std
class AcousticKickParams:
    """原声底鼓合成参数 (boomier 质感)"""
    freq_start: float = 120.0
    freq_end: float = 40.0
    duration: float = 0.5
    punch: float = 0.4       # 打击感
    boom: float = 0.6        # 低频共鸣
    volume: float = 0.85


def synthesize_acoustic_kick(params: AcousticKickParams = None,
                             sr: int = SR) -> np.ndarray:
    """合成原声底鼓。"""
    if params is None:
        params = AcousticKickParams()
    n = int(params.duration * sr)
    t = np.linspace(0, params.duration, n, dtype=np.float64)

    # 频率扫掠
    freq = params.freq_start + (params.freq_end - params.freq_start) * (1 - np.exp(-t / 0.04))

    # 相位累积
    phase = 2.0 * np.pi * np.cumsum(freq) / sr
    tone = np.sin(phase)

    # 冲击 click
    click = np.random.randn(int(n * 0.02)) * np.exp(-np.arange(int(n * 0.02)) / 100)
    click_padded = np.zeros(n); click_padded[:len(click)] = click

    # 低频共鸣
    boom = np.sin(phase * 0.5) * np.exp(-t / 0.3)

    result = (tone * 0.3 + click_padded * params.punch +
              boom * params.boom) * params.volume

    peak = np.max(np.abs(result))
    if peak > 0:
        result = result / peak * 0.95

    return result


# ── Tom 预设 ──
TOM_PRESETS: Dict[str, TomParams] = {
    "hi": TomParams(freq_hz=300, duration=0.25, bend_depth=0.2, volume=0.7),
    "mid": TomParams(freq_hz=200, duration=0.3, bend_depth=0.18, volume=0.75),
    "lo": TomParams(freq_hz=120, duration=0.4, bend_depth=0.15, volume=0.8),
    "floor": TomParams(freq_hz=80, duration=0.5, bend_depth=0.12, volume=0.85),
}
