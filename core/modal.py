"""模态合成引擎 (Modal Synthesis)
================================

将谐振体 (棒 / 板 / 膜 / 钟 / 钵) 建模为一组衰减正弦模态 (mode)。
每个 mode 有独立频率比 (ratio)、幅度 (amp)、衰减速率 (decay_scale)。
低阶 mode 衰减慢 (sustain)，高阶 mode 衰减快 (敲击瞬态) —— 这正是
marimba / xylophone / tubular bells / singing bowl 的物理本质。

单音渲染函数 modal_synth() 供 music/pattern.py 的渲染调度调用。
"""
import numpy as np
from .oscillator import oscillator, OscType
from .envelope import make_envelope, EnvShape
from .constants import SR


# 模态预设：[(ratio, amp, decay_scale), ...]
# decay_scale 越大，该 mode 衰减越快 (通常在 1~16 之间)
MODAL_PRESETS = {
    # 悬臂梁 (marimba / xylophone)：模态比 1 : 2.76 : 5.40 : 8.93
    "bar":       [(1.0, 1.0, 1.0), (2.76, 0.6, 4.0), (5.40, 0.35, 9.0), (8.93, 0.2, 16.0)],
    # 圆膜 (timpani / 鼓面近似)：1 : 1.59 : 2.14 : 2.30 : 2.65
    "membrane":  [(1.0, 1.0, 1.0), (1.59, 0.7, 3.0), (2.14, 0.5, 5.0),
                  (2.30, 0.4, 6.0), (2.65, 0.3, 7.0)],
    # 管钟 (tubular bell)：非谐金属
    "tubular":   [(1.0, 1.0, 1.0), (2.0, 0.5, 2.0), (2.4, 0.4, 2.5),
                  (2.9, 0.3, 3.0), (3.6, 0.2, 4.0)],
    # 颂钵 (singing bowl)：基频 + 多个非谐泛音，长衰减
    "bowl":      [(1.0, 1.0, 0.8), (2.1, 0.5, 2.0), (3.3, 0.35, 3.0),
                  (4.7, 0.25, 4.0), (6.2, 0.15, 5.0)],
    # 锣 / 镲 (gong)：密集高频，快速瞬态 + 长基频
    "gong":      [(1.0, 1.0, 0.6), (1.5, 0.6, 2.0), (2.3, 0.5, 3.0), (3.1, 0.4, 4.0),
                  (4.0, 0.3, 5.0), (5.2, 0.2, 6.0), (6.5, 0.15, 7.0)],
}


def modal_synth(freq, t, env_shape=EnvShape.PAD, volume=1.0, engine_params=None,
                vibrato_rate=0.0, vibrato_depth=0.0):
    """渲染单个模态合成音符 (已含包络与音量)。

    Args:
        freq: 基频 (Hz)
        t: 时间数组 (秒)
        env_shape: 包络形状 (模态合成以物理指数衰减为主包络，此参数仅作占位/兼容)
        volume: 音量 (0~1)
        engine_params: 引擎参数，可含：
            modes: [(ratio, amp, decay_scale), ...] 自定义模态 (覆盖 preset)
            preset: 预设名 ("bar"/"membrane"/"tubular"/"bowl"/"gong")
            base_decay: 基础衰减速率 (默认 3.0，越大整体越短)
            attack: 起音斜坡秒数 (默认 0.002，避免 click)
        vibrato_rate / vibrato_depth: 颤音
    Returns:
        音频数组 (float64)，长度 = len(t)
    """
    engine_params = engine_params or {}
    n_samp = len(t)

    modes = engine_params.get("modes")
    if modes is None:
        preset_name = engine_params.get("preset", "bar")
        modes = MODAL_PRESETS.get(preset_name, MODAL_PRESETS["bar"])
    if not modes:
        modes = [(1.0, 1.0, 1.0)]

    base_decay = float(engine_params.get("base_decay", 3.0))

    if vibrato_depth > 0:
        vib_env = make_envelope(n_samp, EnvShape.PAD)
        vib = 1.0 + (vibrato_depth / 12.0) * np.sin(2 * np.pi * vibrato_rate * t) * vib_env
    else:
        vib = 1.0

    sig = np.zeros(n_samp, dtype=np.float64)
    for ratio, amp, decay_scale in modes:
        decay_rate = base_decay * decay_scale
        mode_env = np.exp(-decay_rate * t)
        sig += oscillator(t, freq * ratio * vib, OscType.SINE) * amp * mode_env

    # 起音斜坡防 click
    attack = float(engine_params.get("attack", 0.002))
    atk_n = max(1, int(attack * len(t)))
    if atk_n < n_samp:
        sig[:atk_n] *= np.linspace(0.0, 1.0, atk_n)

    # 模态合成以物理指数衰减为主包络，不再叠加 ADSR，避免双重衰减
    return sig * volume
