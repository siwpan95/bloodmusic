"""空间效果 —— 简易混响 / 立体声展宽 / Schroeder 混响"""

import numpy as np


def apply_simple_reverb(
    sig: np.ndarray,
    mix: float = 0.2,
    decay: float = 0.5,
    delay_ms: float = 40.0,
    sr: int = 44100,
) -> np.ndarray:
    """简易 comb-filter 混响。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 (0.0=全干, 1.0=全湿)
        decay: 衰减系数
        delay_ms: 初始延迟 (ms)
        sr: 采样率
    """
    if mix <= 0.001:
        return sig
    delay_samples = int(delay_ms / 1000.0 * sr)
    wet = np.zeros(len(sig) + delay_samples)
    wet[delay_samples:delay_samples + len(sig)] = sig * mix

    # 简单衰减反馈（clamp 保证稳定性，避免极长音频下溢出）
    feedback_coeff = min(decay * 0.7, 0.999)
    for i in range(delay_samples, len(wet)):
        wet[i] += wet[i - delay_samples] * feedback_coeff

    # 截断 + 混合
    result = sig * (1 - mix) + wet[:len(sig)] * mix
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95
    return result


def apply_stereo(sig: np.ndarray, width: float = 0.5, sr: int = 44100) -> np.ndarray:
    """单声道 → 立体声展宽。

    Args:
        sig: 输入信号 (mono)
        width: 展宽度 (0.0=mono, 1.0=最大宽度)
        sr: 采样率
    Returns:
        (n, 2) stereo 数组
    """
    if width <= 0.01:
        return np.column_stack([sig, sig])

    delay_samples = int(15 * width)
    left = np.zeros(len(sig) + delay_samples)
    left[:len(sig)] = sig
    right = np.zeros(len(sig) + delay_samples)
    right[delay_samples:delay_samples + len(sig)] = sig

    # Haas 效应：左右各展宽方向
    return np.column_stack([
        left[:len(sig)] * 0.7 + sig * 0.3,
        right[:len(sig)] * 0.7 + sig * 0.3,
    ])


def apply_schroeder_reverb(
    sig: np.ndarray,
    mix: float = 0.3,
    decay: float = 0.5,
    sr: int = 44100,
) -> np.ndarray:
    """Schroeder 混响 (4×并行 comb + 2×串联 allpass)。

    Args:
        sig: 输入信号 (mono float64)
        mix: 干湿比 (0.0=全干, 1.0=全湿)
        decay: 衰减系数 (0~1)
        sr: 采样率
    """
    if mix <= 0.001:
        return sig

    # 保护：feedback >= 1 时 comb 滤波器会发散
    decay = min(decay, 0.999)

    # Comb 滤波器延迟（Schroeder 经典值，单位：样本）
    comb_delays = [1557, 1617, 1491, 1422]  # 基于 44100Hz
    # 按采样率缩放
    comb_delays = [int(d * sr / 44100) for d in comb_delays]
    # Allpass 延迟
    allpass_delays = [225, 556]
    allpass_delays = [int(d * sr / 44100) for d in allpass_delays]

    def _comb(sig_in, delay, feedback):
        """单个 comb 滤波器"""
        out = np.zeros(len(sig_in))
        buffer = np.zeros(delay)
        buf_idx = 0
        for i in range(len(sig_in)):
            out[i] = sig_in[i] + buffer[buf_idx] * feedback
            buffer[buf_idx] = out[i]
            buf_idx = (buf_idx + 1) % delay
        return out

    def _allpass(sig_in, delay, feedback=0.5):
        """单个 allpass 滤波器（Schroeder 经典公式）"""
        out = np.zeros(len(sig_in))
        buffer = np.zeros(delay)
        buf_idx = 0
        for i in range(len(sig_in)):
            w = buffer[buf_idx]
            out[i] = -feedback * sig_in[i] + w
            buffer[buf_idx] = sig_in[i] + feedback * out[i]
            buf_idx = (buf_idx + 1) % delay
        return out

    # 4× 并行 comb
    wet = np.zeros_like(sig)
    for delay in comb_delays:
        wet += _comb(sig, delay, decay)

    # 2× 串联 allpass
    for delay in allpass_delays:
        wet = _allpass(wet, delay, 0.5)

    # 归一化 wet 信号
    wet_peak = np.max(np.abs(wet))
    if wet_peak > 0:
        wet = wet / wet_peak

    # 混合干湿信号
    result = sig * (1 - mix) + wet * mix
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95
    return result


# ═══════════════════════════════════════════════════════════════════════
# 卷积混响 (P2)
# ═══════════════════════════════════════════════════════════════════════

def apply_convolution_reverb(
    sig: np.ndarray,
    mix: float = 0.3,
    ir_type: str = "hall",
    sr: int = 44100,
) -> np.ndarray:
    """卷积混响 — 通过脉冲响应 (IR) 与输入卷积产生真实空间感。

    支持合成 IR: "hall", "room", "plate", "cathedral"
    也可传入 np.ndarray 作为自定义 IR。
    """
    if mix <= 0:
        return sig

    if isinstance(ir_type, np.ndarray):
        ir = ir_type.astype(np.float64)
    else:
        ir = _synthesize_ir(ir_type, sr)

    if len(ir) == 0:
        return sig

    sig64 = sig.astype(np.float64)
    # FFT 卷积
    n_fft = 1
    while n_fft < len(sig64) + len(ir) - 1:
        n_fft *= 2

    sig_fft = np.fft.rfft(sig64, n=n_fft)
    ir_fft = np.fft.rfft(ir, n=n_fft)
    wet = np.fft.irfft(sig_fft * ir_fft, n=n_fft)[:len(sig64)]

    peak = np.max(np.abs(wet))
    if peak > 0:
        wet = wet / peak * 0.8

    result = sig64 * (1.0 - mix) + wet * mix
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.95
    return result


def _synthesize_ir(ir_type: str, sr: int) -> np.ndarray:
    """合成脉冲响应"""
    import numpy as np

    configs = {
        "hall":       (2.0, 0.8,  [0.02, 0.035, 0.055, 0.08, 0.12]),
        "room":       (1.0, 0.25, [0.005, 0.012, 0.02, 0.03, 0.045, 0.06]),
        "plate":      (1.5, 1.0,  [0.01, 0.025, 0.04]),
        "cathedral":  (4.0, 2.0,  [0.1, 0.25, 0.4, 0.6, 0.85, 1.1]),
    }
    dur, decay, ref_delays = configs.get(ir_type, (1.0, 0.3, []))

    n = int(dur * sr)
    t = np.linspace(0, dur, n)
    ir = np.random.randn(n) * np.exp(-t / decay)

    for d in ref_delays:
        pos = int(d * sr)
        a = 0.4 * np.exp(-d * (2 if ir_type != "room" else 8))
        if pos < n:
            ir[pos] += a * (1.0 if np.random.random() > 0.5 else -1.0)

    if ir_type == "plate":
        mod = 0.5 * np.sin(2 * np.pi * 0.7 * t) + 0.5
        ir *= mod

    peak = np.max(np.abs(ir))
    if peak > 0:
        ir = ir / peak
    return ir


def load_ir_wav(filepath: str) -> np.ndarray:
    """从 WAV 文件加载脉冲响应 (IR)"""
    try:
        import soundfile as sf
        data, _ = sf.read(filepath)
    except ImportError:
        from scipy.io import wavfile
        _, data = wavfile.read(filepath)
        data = data.astype(np.float64) / 32768.0
    if data.ndim == 2:
        data = data.mean(axis=1)
    return data.astype(np.float64)
