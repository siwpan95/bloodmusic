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


# ═══════════════════════════════════════════════════════════════════════
# HRTF 双耳空间化 (P3)
# ═══════════════════════════════════════════════════════════════════════
#
# 头相关传输函数 (HRTF) 让单声道声源被"定位"到三维空间中的某一点，
# 输出 (n, 2) 双耳信号。真实 HRTF 依赖测量得到的 HRIR 数据库（与本项目
# 「零外部采样」理念冲突），因此这里用参数化合成模型逼近三大核心线索：
#   - ITD  (Interaural Time Difference)   双耳时差    → 方位角（左右）
#   - ILD  (Interaural Level Difference)  双耳级差    → 高频头部阴影（左右）
#   - 耳廓陷波 (Pinna notch)              频谱线索    → 仰角（上下）
# 以及距离衰减 + 空气吸收低通。完全程序化，无需任何采样。

_HEAD_RADIUS = 0.09          # 头部半径 (m)
_SPEED_OF_SOUND = 343.0       # 声速 (m/s)
_ITD_PEAK = 0.00035           # 单耳峰值 ITD (s)，双耳总差 ≈ 0.7 ms（真人 ~0.6–0.8ms）


def _fractional_delay(sig: np.ndarray, delay_samples: float) -> np.ndarray:
    """分数样本延迟（线性插值，可正可负）。

    delay>0 → 信号滞后（右移）；delay<0 → 提前（左移）。
    """
    n = len(sig)
    if abs(delay_samples) < 1e-6:
        return sig.astype(np.float64)
    x = np.clip(np.arange(n) - float(delay_samples), 0, n - 1)
    return np.interp(x, np.arange(n), sig)


def _lowpass(sig: np.ndarray, cutoff_hz: float, sr: int) -> np.ndarray:
    """一阶低通（ILD 高频阴影 / 距离空气吸收）。"""
    nyq = sr / 2.0
    if cutoff_hz >= nyq:
        return sig.astype(np.float64)
    wc = 2.0 * np.pi * cutoff_hz / sr
    alpha = wc / (wc + 1.0)
    from scipy.signal import lfilter
    return lfilter([alpha], [1.0 - alpha], sig)


def _pinna_notch(sig: np.ndarray, freq_hz: float, q: float, sr: int) -> np.ndarray:
    """耳廓陷波（仰角线索），用二阶陷波实现。"""
    if freq_hz <= 0 or freq_hz >= sr / 2.0:
        return sig.astype(np.float64)
    from scipy.signal import iirnotch, lfilter
    b, a = iirnotch(freq_hz, q, sr)
    return lfilter(b, a, sig)


def apply_hrtf(
    sig: np.ndarray,
    azimuth: float = 0.0,
    elevation: float = 0.0,
    distance: float = 1.0,
    sr: int = 44100,
    max_ild_db: float = 8.0,
    apply_pinna: bool = True,
) -> np.ndarray:
    """HRTF 双耳空间化（合成模型，零采样）。

    将单声道信号定位到 (azimuth 方位角, elevation 仰角, distance 距离)
    的虚拟声源位置，输出 (n, 2) 双耳信号。

    Args:
        sig: 输入信号 (mono float64)；若为 (n,2) 则先下混为单声道
        azimuth:   方位角 (度)，0=正前，+90=正右，-90=正左，±180=正后
        elevation: 仰角 (度)，0=水平面，+90=正上，-90=正下
        distance:  距离 (米)，1.0=参考距离
        sr:        采样率
        max_ild_db:最大双耳级差 (默认 8 dB)
        apply_pinna:是否施加耳廓陷波（仰角频谱线索）
    Returns:
        (n, 2) float64 双耳信号
    """
    sig = np.asarray(sig, dtype=np.float64)
    if sig.ndim == 2:
        sig = sig.mean(axis=1)
    n = len(sig)
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)

    az = np.radians(float(azimuth))
    el = np.radians(float(elevation))
    sin_az = np.sin(az)
    abs_az = abs(sin_az)                       # 0(前/后) → 1(侧)
    nyq = sr / 2.0

    # ── ITD：双耳时差（Woodworth 近似）──
    # 声源在右(az>0) → 左耳(远)滞后(+)，右耳(近)提前(-)
    left_delay = _ITD_PEAK * sin_az * sr        # 样本
    right_delay = -_ITD_PEAK * sin_az * sr
    left = _fractional_delay(sig, left_delay)
    right = _fractional_delay(sig, right_delay)

    # ── ILD：高频头部阴影 → 远侧耳低通 + 整体衰减 ──
    far_cutoff = max(1500.0, nyq * (1.0 - 0.85 * abs_az))
    ild_gain = 10.0 ** (-(max_ild_db * abs_az) / 20.0)   # 远侧耳整体衰减
    if sin_az >= 0:                          # 声源在右 → 左(远)耳压暗
        left = _lowpass(left, far_cutoff, sr) * ild_gain
    else:                                    # 声源在左 → 右(远)耳压暗
        right = _lowpass(right, far_cutoff, sr) * ild_gain

    # ── 耳廓陷波：仰角线索（上仰→陷波上移）──
    if apply_pinna and abs(el) > 1e-3:
        base = max(1500.0, min(8000.0, 2000.0 + 3000.0 * np.sin(el)))
        left = _pinna_notch(left, base * 1.05, q=6.0, sr=sr)
        right = _pinna_notch(right, base * 0.95, q=6.0, sr=sr)

    # ── 距离：1/r 衰减 + 空气吸收低通 ──
    dist = max(0.1, float(distance))
    dist_gain = 1.0 / dist
    air_cutoff = max(2000.0, 20000.0 * (1.0 - min(1.0, (dist - 1.0) / 9.0)))
    left = _lowpass(left, air_cutoff, sr) * dist_gain
    right = _lowpass(right, air_cutoff, sr) * dist_gain

    out = np.column_stack([left, right])
    peak = np.max(np.abs(out))
    if peak > 1.0:
        out = out / peak * 0.98
    return out


def synthesize_hrir(
    azimuth: float = 0.0,
    elevation: float = 0.0,
    sr: int = 44100,
    length: int = 512,
) -> tuple:
    """合成一对 HRIR（左/右耳），用于真卷积路径。

    由"延迟直达脉冲 + 耳廓 ring（频率随仰角）"构成，长度 length 样本。
    返回 (hrir_l, hrir_r)，均为 float64 并已归一化。
    """
    az = np.radians(float(azimuth))
    el = np.radians(float(elevation))
    sin_az = np.sin(az)

    l_shift = int(round(_ITD_PEAK * sin_az * sr))
    r_shift = -int(round(_ITD_PEAK * sin_az * sr))

    hrir_l = np.zeros(length)
    hrir_r = np.zeros(length)
    # 直达脉冲
    lp = -l_shift
    if 0 <= lp < length:
        hrir_l[lp] = 1.0
    else:
        hrir_l[0] = 1.0
    rp = -r_shift
    if 0 <= rp < length:
        hrir_r[rp] = 1.0
    else:
        hrir_r[0] = 1.0

    # 耳廓 ring：短衰减正弦，频率随仰角上移，侧向时更强
    f = max(1500.0, min(8000.0, 2000.0 + 3000.0 * np.sin(el)))
    t = np.arange(length) / sr
    ring = 0.3 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.002)
    ring *= (0.5 + 0.5 * abs(sin_az))
    hrir_l += ring
    hrir_r += ring * 0.9

    for h in (hrir_l, hrir_r):
        p = np.max(np.abs(h))
        if p > 0:
            h /= p
    return hrir_l, hrir_r


def apply_hrtf_convolution(
    sig: np.ndarray,
    azimuth: float = 0.0,
    elevation: float = 0.0,
    sr: int = 44100,
    ir_length: int = 512,
) -> np.ndarray:
    """HRTF 真卷积变体：用合成 HRIR 与输入做 FFT 卷积。

    与 apply_hrtf 的分析模型相比，卷积路径更贴近"真实 HRIR 卷积"管线，
    便于未来替换为测量 HRIR 数据集。
    """
    sig = np.asarray(sig, dtype=np.float64)
    if sig.ndim == 2:
        sig = sig.mean(axis=1)
    n = len(sig)
    if n == 0:
        return np.zeros((0, 2), dtype=np.float64)

    hrir_l, hrir_r = synthesize_hrir(azimuth, elevation, sr, ir_length)
    n_fft = 1
    while n_fft < n + ir_length - 1:
        n_fft *= 2

    sig_fft = np.fft.rfft(sig, n=n_fft)
    out = np.zeros((n, 2), dtype=np.float64)
    for ch, hrir in enumerate((hrir_l, hrir_r)):
        h_fft = np.fft.rfft(hrir, n=n_fft)
        conv = np.fft.irfft(sig_fft * h_fft, n=n_fft)[:n]
        peak = np.max(np.abs(conv))
        if peak > 0:
            conv = conv / peak * 0.9
        out[:, ch] = conv
    peak = np.max(np.abs(out))
    if peak > 1.0:
        out = out / peak * 0.98
    return out

