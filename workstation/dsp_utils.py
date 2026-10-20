"""DSP 工具函数：混音、增益、重采样等基本操作"""

import math


def mix_buffers(buffers: list[list[list[float]]],
                out: list[list[float]], n_samples: int) -> None:
    """多轨混音到输出。

    Args:
        buffers: [track][channel][sample]
        out: [channel][sample]
        n_samples: 样本数
    """
    if not buffers:
        for ch_out in out:
            ch_out[:n_samples] = [0.0] * n_samples
        return

    n_channels = len(out)
    for ch in range(n_channels):
        ch_out = out[ch]
        for samp in range(n_samples):
            total = 0.0
            for buf in buffers:
                if ch < len(buf):
                    total += buf[ch][samp]
            ch_out[samp] = max(-1.0, min(1.0, total))


def apply_gain_ramp(buffer: list[list[float]], n_samples: int,
                    start_gain: float, end_gain: float) -> None:
    """对缓冲区应用线性增益渐变。

    Args:
        buffer: [channel][sample]
        start_gain: 起始增益 (0.0 ~ 1.0)
        end_gain: 结束增益 (0.0 ~ 1.0)
    """
    if n_samples <= 1:
        for ch in buffer:
            ch[:n_samples] = [s * start_gain for s in ch[:n_samples]]
        return

    for ch in buffer:
        for i in range(n_samples):
            t = i / (n_samples - 1)
            gain = start_gain + (end_gain - start_gain) * t
            ch[i] *= gain


def db_to_linear(db: float) -> float:
    """dB 转线性增益"""
    return 10.0 ** (db / 20.0)


def linear_to_db(linear: float) -> float:
    """线性增益转 dB"""
    if linear <= 0.0:
        return -float("inf")
    return 20.0 * math.log10(linear)


def pan_law(pan: float, law: float = -3.0) -> tuple[float, float]:
    """声像定位，返回 (left_gain, right_gain)。

    Args:
        pan: -1.0 (极左) ~ 1.0 (极右)
        law: 声像法则 dB，-3.0=恒定功率, -4.5=传统, -6.0=线性

    Returns:
        (left_gain, right_gain) 线性增益
    """
    pan = max(-1.0, min(1.0, pan))
    law_linear = db_to_linear(law)

    if pan <= 0:
        right_gain = law_linear + (1.0 - law_linear) * (pan + 1.0)
        left_gain = 1.0
    else:
        left_gain = law_linear + (1.0 - law_linear) * (1.0 - pan)
        right_gain = 1.0
    return left_gain, right_gain


def resample_mono(src: list[float], src_rate: int,
                  dst_rate: int) -> list[float]:
    """简单线性插值重采样 (单声道)"""
    if src_rate == dst_rate:
        return src.copy()
    ratio = src_rate / dst_rate
    dst_len = int(len(src) / ratio)
    result = [0.0] * dst_len
    for i in range(dst_len):
        pos = i * ratio
        idx = int(pos)
        frac = pos - idx
        if idx + 1 < len(src):
            result[i] = src[idx] * (1 - frac) + src[idx + 1] * frac
        else:
            result[i] = src[idx]
    return result


def sine_wave(freq: float, sample_rate: int, duration: float,
              amplitude: float = 0.5, phase: float = 0.0) -> list[float]:
    """生成正弦波"""
    n = int(sample_rate * duration)
    result = [0.0] * n
    for i in range(n):
        t = i / sample_rate
        result[i] = amplitude * math.sin(2 * math.pi * freq * t + phase)
    return result


def saw_wave(freq: float, sample_rate: int, duration: float,
             amplitude: float = 0.5) -> list[float]:
    """生成锯齿波"""
    n = int(sample_rate * duration)
    period = sample_rate / freq
    result = [0.0] * n
    for i in range(n):
        result[i] = amplitude * (2.0 * ((i % period) / period) - 1.0)
    return result


def square_wave(freq: float, sample_rate: int, duration: float,
                amplitude: float = 0.5, duty: float = 0.5) -> list[float]:
    """生成方波"""
    n = int(sample_rate * duration)
    period = sample_rate / freq
    result = [0.0] * n
    for i in range(n):
        phase = (i % period) / period
        result[i] = amplitude if phase < duty else -amplitude
    return result


def triangle_wave(freq: float, sample_rate: int, duration: float,
                  amplitude: float = 0.5) -> list[float]:
    """生成三角波"""
    n = int(sample_rate * duration)
    period = sample_rate / freq
    result = [0.0] * n
    for i in range(n):
        phase = (i % period) / period
        result[i] = amplitude * (4.0 * abs(phase - 0.5) - 1.0)
    return result


def normalize(buffer: list[list[float]], n_samples: int,
              target_peak: float = 0.95) -> float:
    """归一化到目标峰值，返回应用的增益"""
    peak = 0.0
    for ch in buffer:
        for s in ch[:n_samples]:
            peak = max(peak, abs(s))
    if peak < 1e-9:
        return 1.0
    gain = target_peak / peak
    for ch in buffer:
        ch[:n_samples] = [s * gain for s in ch[:n_samples]]
    return gain
