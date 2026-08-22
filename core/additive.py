"""加法合成引擎 (Additive Synthesis)
===================================

通过叠加多个正弦分音 (partial) 构造任意音色，支持非整数 (inharmonic) 分音比，
用于 glass、bell、metal 等谐振质感。每个分音可有独立衰减，模拟真实共鸣体瞬态。

单音渲染函数 additive_synth() 供 music/pattern.py 的渲染调度调用。
"""
import numpy as np
from .oscillator import oscillator, OscType
from .envelope import make_envelope, EnvShape
from .constants import SR


# 分音预设：[(ratio, amp), ...]  ratio 为相对基频的倍频比
ADDITIVE_PRESETS = {
    # 玻璃 / 板状：非整数倍频，明亮金属感
    "glass":     [(1.0, 1.0), (2.76, 0.5), (5.40, 0.25), (8.93, 0.12)],
    # 钟：非谐，低频比 <1
    "bell":      [(0.56, 0.6), (0.92, 0.4), (1.19, 1.0), (1.71, 0.5), (2.0, 0.3), (2.74, 0.15)],
    # 金属：密集非谐
    "metal":     [(1.0, 1.0), (1.74, 0.6), (2.55, 0.4), (3.42, 0.25), (4.3, 0.15)],
    # 弱音玻璃质感 pad
    "glass_pad": [(1.0, 1.0), (2.0, 0.2), (3.0, 0.1), (4.76, 0.05)],
    # 风琴（谐波堆叠）
    "organ":     [(1.0, 1.0), (2.0, 0.5), (3.0, 0.3), (4.0, 0.2), (6.0, 0.1)],
    # 锯齿谐波堆（合成器）
    "saw":       [(1.0, 1.0)] + [(i, 1.0 / i) for i in range(2, 13)],
    # 三角波谐波堆
    "triangle":  [(1.0, 1.0)] + [(i, 1.0 / (i * i)) for i in range(3, 14, 2)],
}


def additive_synth(freq, t, env_shape=EnvShape.PAD, volume=1.0, engine_params=None,
                   vibrato_rate=0.0, vibrato_depth=0.0):
    """渲染单个加法合成音符 (已含包络与音量)。

    Args:
        freq: 基频 (Hz)
        t: 时间数组 (秒)，由调用方生成 (np.linspace)
        env_shape: 包络形状
        volume: 音量 (0~1)
        engine_params: 引擎专属参数，可含：
            partials: [(ratio, amp), ...] 自定义分音 (覆盖 preset)
            preset: 预设名 ("glass"/"bell"/"metal"/"glass_pad"/"organ"/"saw"/"triangle")
            inharmonicity: 非谐系数 (>0 时高次分音按 i^2 偏离)
            partial_decay: 每分音衰减速率 (>0 时高阶分音衰减更快，营造瞬态)
        vibrato_rate / vibrato_depth: 颤音
    Returns:
        音频数组 (float64)，长度 = len(t)
    """
    engine_params = engine_params or {}
    n_samp = len(t)

    partials = engine_params.get("partials")
    if partials is None:
        preset_name = engine_params.get("preset", "glass")
        partials = ADDITIVE_PRESETS.get(preset_name, ADDITIVE_PRESETS["glass"])
    if not partials:
        partials = [(1.0, 1.0)]

    inharm = float(engine_params.get("inharmonicity", 0.0))
    p_decay = float(engine_params.get("partial_decay", 0.0))

    # 颤音频率调制
    if vibrato_depth > 0:
        vib_env = make_envelope(n_samp, EnvShape.PAD)
        vib = 1.0 + (vibrato_depth / 12.0) * np.sin(2 * np.pi * vibrato_rate * t) * vib_env
    else:
        vib = 1.0

    sig = np.zeros(n_samp, dtype=np.float64)
    for i, (ratio, amp) in enumerate(partials):
        # 非谐拉伸：高阶分音按 i^2 偏离 (类似钢琴/钟的拉伸)
        ratio_eff = ratio * (1.0 + inharm * (i + 1) * (i + 1))
        partial = oscillator(t, freq * ratio_eff * vib, OscType.SINE) * amp
        # 每分音独立衰减 (高阶更快，营造敲击瞬态)
        if p_decay > 0:
            partial = partial * np.exp(-p_decay * (i + 1) * t)
        sig += partial

    env = make_envelope(n_samp, env_shape)
    return sig * env * volume
