"""混合声部合成引擎 (Hybrid Voice Synthesis)
=============================================

单个声部内融合多种合成技术——additive（分音）+ modal（谐振体）
+ tone（减法式谐波）+ noise（瞬态噪声）+ fm（2 算子）——组合成
一个有机的 Hybrid 音色。这正是 Serum / Vital / Arturia 式
"同一声部内多层合成" 的程序化落地。

单音渲染函数 hybrid_synth() 供 music/pattern.py 与 music/pool_renderer.py
的引擎分派调用，签名与其余引擎（additive_synth / modal_synth）一致。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .oscillator import oscillator, OscType
from .envelope import make_envelope, EnvShape
from .constants import SR
from . import additive as _additive
from . import modal as _modal


# 单层定义：{type, gain, ...}
# type ∈ "additive" | "modal" | "tone" | "noise" | "fm"
# 公共键：gain(0~1) / detune(半音) / env_scale(包络时长缩放)
# additive: preset / partials
# modal:    preset / modes / base_decay
# tone:     harmonics=[(mult,amp)] / osc="sine"
# noise:    amount / decay / hp / lp / bp / bp_q
# fm:       ratio / depth


@dataclass
class HybridLayer:
    """Hybrid 声部的一个子层。"""
    type: str = "tone"
    gain: float = 1.0
    detune: float = 0.0          # 半音偏移
    env_scale: float = 1.0       # 包络时长缩放 (越大越短)
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HybridLayer":
        d = dict(d)
        t = d.pop("type", "tone")
        gain = float(d.pop("gain", 1.0))
        detune = float(d.pop("detune", 0.0))
        env_scale = float(d.pop("env_scale", 1.0))
        return cls(type=t, gain=gain, detune=detune, env_scale=env_scale, params=d)


# 预设：每个预设是若干 HybridLayer 的组合
HYBRID_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    # 金属钟：加法玻璃体 + 模态管钟长鸣 + 噪声瞬态 click
    "bell_metal": [
        {"type": "additive", "gain": 0.5, "preset": "glass"},
        {"type": "modal", "gain": 0.6, "preset": "tubular", "base_decay": 1.6},
        {"type": "noise", "gain": 0.35, "amount": 0.5, "decay": 0.02, "hp": 3000},
    ],
    # 玻璃击打：加法玻璃 + 模态颂钵微光 + 高频 click
    "glass_strike": [
        {"type": "additive", "gain": 0.6, "preset": "glass"},
        {"type": "modal", "gain": 0.3, "preset": "bowl", "base_decay": 3.0},
        {"type": "noise", "gain": 0.25, "amount": 0.4, "decay": 0.015, "hp": 5000},
    ],
    # 微光 pad：加法玻璃 pad + 减法锯齿谐波衬底
    "hybrid_pad": [
        {"type": "additive", "gain": 0.5, "preset": "glass_pad"},
        {"type": "tone", "gain": 0.35, "osc": "saw",
         "harmonics": [(1.0, 1.0), (2.0, 0.4), (3.0, 0.2), (4.0, 0.1)]},
        {"type": "modal", "gain": 0.2, "preset": "bowl", "base_decay": 2.0},
    ],
    # 金属打击（镲感）：加法金属 + 模态锣 + 密集噪声
    "metal_strike": [
        {"type": "additive", "gain": 0.45, "preset": "metal"},
        {"type": "modal", "gain": 0.4, "preset": "gong", "base_decay": 1.0},
        {"type": "noise", "gain": 0.4, "amount": 0.6, "decay": 0.08, "hp": 4000},
    ],
    # 木质混合：模态 bar（木质共鸣）+ 减法三角 + 短噪声
    "wood_hybrid": [
        {"type": "modal", "gain": 0.6, "preset": "bar", "base_decay": 3.0},
        {"type": "tone", "gain": 0.3, "osc": "triangle",
         "harmonics": [(1.0, 1.0), (2.0, 0.3), (3.0, 0.15)]},
        {"type": "noise", "gain": 0.2, "amount": 0.4, "decay": 0.02, "hp": 1500, "lp": 6000},
    ],
}


def _render_layer(
    layer: HybridLayer,
    freq: float,
    t: np.ndarray,
    n_samp: int,
    env_shape: EnvShape,
    vibrato_rate: float,
    vibrato_depth: float,
) -> np.ndarray:
    """渲染单个 Hybrid 子层。"""
    f = freq * (2.0 ** (layer.detune / 12.0))

    # 颤音调制
    if vibrato_depth > 0:
        vib_env = make_envelope(n_samp, EnvShape.PAD)
        vib = 1.0 + (vibrato_depth / 12.0) * np.sin(2 * np.pi * vibrato_rate * t) * vib_env
    else:
        vib = 1.0

    sig = np.zeros(n_samp, dtype=np.float64)

    if layer.type == "additive":
        ep = dict(layer.params)
        sig = _additive.additive_synth(
            f * vib, t, env_shape, 1.0,
            ep or {}, vibrato_rate, 0.0,  # 颤音已在父层处理
        )

    elif layer.type == "modal":
        ep = dict(layer.params)
        # modal 内部以物理衰减为主包络，env_shape 仅作兼容占位
        sig = _modal.modal_synth(
            f * vib, t, env_shape, 1.0,
            ep or {}, vibrato_rate, 0.0,
        )

    elif layer.type == "tone":
        osc_name = layer.params.get("osc", "sine")
        try:
            osc_type = OscType(osc_name)
        except ValueError:
            osc_type = OscType.SINE
        harmonics = layer.params.get(
            "harmonics", [(1.0, 1.0)]
        )
        s = oscillator(t, f * vib, osc_type)
        for h_mult, h_amp in harmonics:
            s += oscillator(t, f * vib * h_mult, osc_type) * h_amp
        env = make_envelope(n_samp, env_shape)
        sig = s * env

    elif layer.type == "noise":
        amount = float(layer.params.get("amount", 0.5))
        decay = float(layer.params.get("decay", 0.03))
        noise = np.random.uniform(-1, 1, n_samp)
        n_env = np.exp(-t / max(decay, 1e-3))
        noise = noise * n_env * amount
        from ..effects.filters import apply_highpass, apply_lowpass
        hp = layer.params.get("hp")
        lp = layer.params.get("lp")
        if hp:
            noise = apply_highpass(noise, float(hp))
        if lp:
            noise = apply_lowpass(noise, float(lp))
        sig = noise

    elif layer.type == "fm":
        ratio = float(layer.params.get("ratio", 2.0))
        depth = float(layer.params.get("depth", 100.0))
        mod = np.sin(2 * np.pi * f * ratio * vib * t) * depth
        carrier = np.sin(2 * np.pi * (f * vib + mod) * t)
        env = make_envelope(n_samp, env_shape)
        sig = carrier * env

    else:
        # 未知层类型：回退为纯正弦
        sig = oscillator(t, f * vib, OscType.SINE) * make_envelope(n_samp, env_shape)

    # env_scale：整体时长缩放（仅对非 noise 的包络化层有意义）
    return sig * layer.gain


def hybrid_synth(
    freq,
    t,
    env_shape=EnvShape.PAD,
    volume=1.0,
    engine_params=None,
    vibrato_rate=0.0,
    vibrato_depth=0.0,
):
    """渲染单个 Hybrid 合成音符（已含音量与子层合成）。

    Args:
        freq: 基频 (Hz)
        t: 时间数组 (秒)
        env_shape: 包络形状（透传给子层）
        volume: 总音量 (0~1)
        engine_params: 可含：
            layers: [HybridLayer dict, ...] 自定义层组合（覆盖 preset）
            preset: 预设名（"bell_metal"/"glass_strike"/"hybrid_pad"/
                             "metal_strike"/"wood_hybrid"）
        vibrato_rate / vibrato_depth: 颤音（应用到所有旋律型子层）
    Returns:
        音频数组 (float64)，长度 = len(t)
    """
    engine_params = engine_params or {}
    n_samp = len(t)

    raw_layers = engine_params.get("layers")
    if raw_layers is None:
        preset_name = engine_params.get("preset", "bell_metal")
        raw_layers = HYBRID_PRESETS.get(preset_name, HYBRID_PRESETS["bell_metal"])

    layers = [HybridLayer.from_dict(d) for d in raw_layers]
    if not layers:
        layers = [HybridLayer(type="tone", gain=1.0)]

    sig = np.zeros(n_samp, dtype=np.float64)
    for layer in layers:
        sig += _render_layer(
            layer, freq, t, n_samp, env_shape,
            vibrato_rate, vibrato_depth,
        )

    # 软限幅防叠加爆音
    peak = np.max(np.abs(sig))
    if peak > 1.0:
        sig = sig / peak

    return sig * volume
