"""
效果链 —— EffectChain 参数定义 + process_effects 管线
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List

from .filters import apply_lowpass, apply_highpass, apply_bandpass, apply_notch
from .distortion import apply_distortion, apply_bit_crush
from .spatial import apply_simple_reverb, apply_stereo, apply_schroeder_reverb
from .spatial import apply_hrtf
from .dynamics import CompressorParams, apply_compressor, apply_limiter
from .eq import ParametricEQParams, apply_parametric_eq
from .modulation import apply_chorus
from .flanger import apply_delay, apply_pingpong_delay, apply_multitap_delay, apply_flanger, apply_phaser
from ..core.constants import SR as _SR


@dataclass
class EffectChain:
    """效果链参数。所有字段为 None 表示不启用该效果。"""

    lp_filter_hz: Optional[float] = None      # 低通截止频率
    hp_filter_hz: Optional[float] = None      # 高通截止频率
    distortion: float = 0.0                   # 失真量 (0~1)
    bit_crush: Optional[int] = None           # bit depth
    reverb_mix: float = 0.0                   # 混响干湿比
    reverb_decay: float = 0.5                 # 混响衰减
    reverb_delay_ms: float = 40.0             # 混响初始延迟
    stereo_width: float = 0.0                 # 立体声展宽

    # ── 新增效果器 ──
    bp_center_hz: Optional[float] = None       # 带通中心频率
    bp_q: Optional[float] = None               # 带通 Q 值
    notch_hz: Optional[float] = None           # 陷波频率
    notch_q: Optional[float] = None            # 陷波 Q 值
    reverb_schroeder: bool = False             # 是否使用 Schroeder 混响
    compressor: Optional[CompressorParams] = None   # 压缩器参数
    eq: Optional[ParametricEQParams] = None         # EQ 参数
    chorus_mix: float = 0.0                    # Chorus 干湿比
    chorus_rate: float = 0.5                   # Chorus LFO 速率
    chorus_depth: float = 0.002                # Chorus 调制深度

    # ── Delay ──
    delay_mix: float = 0.0                     # 延迟干湿比 0~1
    delay_time: float = 0.3                    # 延迟时间 (秒)
    delay_feedback: float = 0.3                # 延迟反馈 0~0.95
    pingpong_delay: bool = False               # 是否使用乒乓立体声延迟
    delay_stereo_spread: float = 0.7           # 乒乓延迟立体声扩散
    multitap_times: Optional[List[float]] = None   # 多拍延迟时间列表
    multitap_gains: Optional[List[float]] = None   # 多拍延迟增益列表

    # ── Flanger / Phaser ──
    flanger_mix: float = 0.0                   # Flanger 干湿比
    flanger_rate: float = 0.5                  # Flanger LFO 速率
    flanger_depth: float = 0.003               # Flanger 调制深度 (秒)
    flanger_feedback: float = 0.0              # Flanger 反馈量
    phaser_mix: float = 0.0                    # Phaser 干湿比
    phaser_rate: float = 0.5                   # Phaser LFO 速率
    phaser_depth: float = 0.7                  # Phaser 调制深度
    phaser_stages: int = 6                     # Phaser 滤波器级数
    phaser_feedback: float = 0.0               # Phaser 反馈量

    # ── Spatial HRTF 双耳空间化 (P3) ──
    spatial_enabled: bool = False              # 是否启用 HRTF 双耳空间化
    spatial_azimuth: float = 0.0               # 方位角 (度) 0=前 +90=右 -90=左
    spatial_elevation: float = 0.0             # 仰角 (度) 0=水平 +90=上 -90=下
    spatial_distance: float = 1.0              # 距离 (米)


def process_effects(
    sig: np.ndarray,
    chain: EffectChain,
    sr: int = _SR,
) -> np.ndarray:
    """按顺序处理效果链。

    处理顺序: 滤波器 → EQ → 压缩器 → 失真 → Flanger/Phaser → Chorus → Delay → 混响 → 立体声

    Args:
        sig: 输入信号 (mono float64)
        chain: EffectChain 参数
        sr: 采样率
    Returns:
        处理后的信号 (mono 或 stereo)
    """
    result = sig.astype(np.float64).copy()

    # 1. 滤波器 (lowpass → highpass → bandpass → notch)
    if chain.lp_filter_hz is not None:
        result = apply_lowpass(result, chain.lp_filter_hz, sr)
    if chain.hp_filter_hz is not None:
        result = apply_highpass(result, chain.hp_filter_hz, sr)
    if chain.bp_center_hz is not None:
        bp_q = chain.bp_q if chain.bp_q is not None else 1.0
        result = apply_bandpass(result, chain.bp_center_hz, bp_q, sr)
    if chain.notch_hz is not None:
        notch_q = chain.notch_q if chain.notch_q is not None else 1.0
        result = apply_notch(result, chain.notch_hz, notch_q, sr)

    # 2. EQ
    if chain.eq is not None:
        result = apply_parametric_eq(result, chain.eq, sr)

    # 3. 压缩器
    if chain.compressor is not None:
        result = apply_compressor(result, chain.compressor, sr)

    # 4. 失真
    if chain.distortion > 0:
        result = apply_distortion(result, chain.distortion)
    if chain.bit_crush is not None:
        result = apply_bit_crush(result, chain.bit_crush)

    # 5. Flanger / Phaser (调制类，在 Chorus 前)
    if chain.flanger_mix > 0:
        result = apply_flanger(
            result, mix=chain.flanger_mix, rate=chain.flanger_rate,
            depth=chain.flanger_depth, feedback=chain.flanger_feedback, sr=sr,
        )
    if chain.phaser_mix > 0:
        result = apply_phaser(
            result, mix=chain.phaser_mix, rate=chain.phaser_rate,
            depth=chain.phaser_depth, n_stages=chain.phaser_stages,
            feedback=chain.phaser_feedback, sr=sr,
        )

    # 6. Chorus
    if chain.chorus_mix > 0:
        result = apply_chorus(
            result,
            mix=chain.chorus_mix,
            rate=chain.chorus_rate,
            depth=chain.chorus_depth,
            sr=sr,
        )

    # 7. Delay (回声在 Chorus 之后、混响之前)
    if chain.delay_mix > 0:
        if chain.multitap_times is not None:
            result = apply_multitap_delay(
                result, mix=chain.delay_mix,
                tap_times=chain.multitap_times,
                tap_gains=chain.multitap_gains, sr=sr,
            )
        elif chain.pingpong_delay:
            result = apply_pingpong_delay(
                result, mix=chain.delay_mix, delay_time=chain.delay_time,
                feedback=chain.delay_feedback,
                stereo_spread=chain.delay_stereo_spread, sr=sr,
            )
        else:
            result = apply_delay(
                result, mix=chain.delay_mix, delay_time=chain.delay_time,
                feedback=chain.delay_feedback, sr=sr,
            )

    # 8. 混响（根据 reverb_schroeder 选择）
    if chain.reverb_mix > 0:
        if chain.reverb_schroeder:
            result = apply_schroeder_reverb(
                result, mix=chain.reverb_mix, decay=chain.reverb_decay, sr=sr,
            )
        else:
            result = apply_simple_reverb(
                result, mix=chain.reverb_mix, decay=chain.reverb_decay,
                delay_ms=chain.reverb_delay_ms, sr=sr,
            )

    # 9. 立体声展宽
    if chain.stereo_width > 0:
        result = apply_stereo(result, chain.stereo_width, sr)

    # 10. HRTF 双耳空间化 (P3) —— 将单声道声源定位到三维空间
    #     若信号已是立体声（如 step 9 之后），先下混为单声道再定位
    if chain.spatial_enabled:
        if result.ndim == 2:
            result = result.mean(axis=1)
        result = apply_hrtf(
            result,
            azimuth=chain.spatial_azimuth,
            elevation=chain.spatial_elevation,
            distance=chain.spatial_distance,
            sr=sr,
        )

    return result
