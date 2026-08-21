# -*- coding: utf-8 -*-
"""
mixer_styles.py —— 24 位混音师签名链（镜像 burbidge_album/mixer_styles.py）

采样侧：numpy/scipy 实现的总线链（EQ/压缩/饱和/混响/宽度/母带），24 位签名 slug。
机生成侧：同 24 slug、同 bus_chain/master_chain 语义，DSP 全部 numpy 自实现，
         作用于机生成分轨（角色 → 总线映射同采样侧 _MIXER_ROLE_TO_BUS 语义）。

每个签名 = 总线参数（按角色微调）+ 母带参数：
    eq_low_db/eq_high_db —— 低频/高频搁架（RBJ biquad）
    comp_thr/comp_ratio —— 软拐点压缩
    sat_drive             —— tanh 饱和
    rev_wet               —— 反馈延迟混响湿度
    width                 —— 中/侧宽度
    master_gain           —— 母带增益（峰值 -1.5 dBFS 留编码余量）
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

from bloodmusic.core.constants import SR as _SR

# 角色 → 总线（镜像采样侧 _MIXER_ROLE_TO_BUS：鼓/贝斯/铺垫/主奏人声走对应总线）
ROLE_BUSES = {
    "drum": "drums",
    "bass": "bass",
    "guita": "guita",
    "pad": "pad",
    "melody": "lead",
    "vocal": "vocal",
    "fx": "fx",
}


@dataclass(frozen=True)
class BusParams:
    eq_low_db: float = 0.0      # 低频搁架增益 dB
    eq_high_db: float = 0.0     # 高频搁架增益 dB
    comp_thr: float = -18.0     # 压缩阈值 dBFS
    comp_ratio: float = 2.0
    sat_drive: float = 0.0      # tanh 驱动
    rev_wet: float = 0.0        # 混响湿度 0-1


@dataclass(frozen=True)
class MasterParams:
    eq_low_db: float = 0.0
    eq_high_db: float = 0.0
    comp_thr: float = -14.0
    comp_ratio: float = 2.0
    sat_drive: float = 0.0
    width: float = 0.0          # 中/侧宽度 -1..1
    gain_db: float = 0.0


@dataclass(frozen=True)
class MixerStyle:
    slug: str
    name: str
    buses: dict = field(default_factory=dict)   # bus 名 → BusParams
    master: MasterParams = MasterParams()

    def bus(self, role: str) -> BusParams:
        bus = ROLE_BUSES.get(role, "pad")
        return self.buses.get(bus, BusParams())


# ═══════════════════════════════════════════════════════════════
# 24 位签名（slug 与 musickit 一致）
# ═══════════════════════════════════════════════════════════════

def _mk(bass_low=0.0, bass_comp=(-18, 2.5), sat=0.0, rev=0.0,
        lead_high=0.0, vocal_high=1.0, vocal_rev=0.12,
        master=MasterParams()) -> MixerStyle:
    return MixerStyle(
        slug="", name="", master=master,
        buses={
            "drums": BusParams(eq_low_db=1.0, eq_high_db=-0.5, comp_thr=-16, comp_ratio=3.0, sat_drive=sat * 0.5, rev_wet=rev * 0.3),
            "bass": BusParams(eq_low_db=bass_low, comp_thr=bass_comp[0], comp_ratio=bass_comp[1], sat_drive=sat),
            "guita": BusParams(eq_high_db=0.5, comp_thr=-16, comp_ratio=2.5, sat_drive=sat * 1.2, rev_wet=rev * 0.5),
            "pad": BusParams(eq_low_db=-1.0, comp_thr=-20, comp_ratio=1.8, rev_wet=max(rev, 0.08)),
            "lead": BusParams(eq_high_db=lead_high, comp_thr=-16, comp_ratio=2.5, sat_drive=sat, rev_wet=rev * 0.6),
            "vocal": BusParams(eq_high_db=vocal_high, comp_thr=-18, comp_ratio=3.0, sat_drive=sat * 0.6, rev_wet=vocal_rev),
            "fx": BusParams(eq_low_db=-2.0, comp_thr=-20, comp_ratio=1.5, rev_wet=0.2),
        },
    )


_RAW = {}


def _register(slug: str, name: str, style: MixerStyle) -> None:
    _RAW[slug] = MixerStyle(slug=slug, name=name, buses=style.buses, master=style.master)


# 默认母带（峰值 -1.5 dBFS 留编码余量，镜像采样侧）
_M_DEFAULT = MasterParams(comp_thr=-14.0, comp_ratio=2.0, gain_db=0.0)

_register("burbidge", "Burbidge", _mk(
    bass_low=1.5, bass_comp=(-16, 3.0), sat=0.25, rev=0.06, lead_high=1.0,
    master=MasterParams(eq_low_db=0.5, comp_thr=-13, comp_ratio=2.2, sat_drive=0.2, width=0.15)))
_register("ghenea", "Ghenea", _mk(
    bass_low=1.0, bass_comp=(-17, 2.5), sat=0.1, rev=0.04, vocal_high=2.0, vocal_rev=0.18,
    master=MasterParams(eq_high_db=1.0, comp_thr=-12, comp_ratio=2.5, width=0.2, gain_db=-0.5)))
_register("clearmountain", "Clearmountain", _mk(
    bass_low=0.5, bass_comp=(-18, 2.0), rev=0.14, lead_high=0.5,
    master=MasterParams(eq_high_db=0.5, comp_thr=-14, comp_ratio=1.8, width=0.3)))
_register("marroquin", "Marroquin", _mk(
    bass_low=2.0, bass_comp=(-15, 3.5), sat=0.3, vocal_high=1.5, vocal_rev=0.15,
    master=MasterParams(eq_low_db=1.0, comp_thr=-12, comp_ratio=2.8, sat_drive=0.15, width=0.1)))
_register("pensado", "Pensado", _mk(
    bass_low=1.0, bass_comp=(-16, 2.8), sat=0.2, rev=0.05, lead_high=2.0,
    master=MasterParams(eq_high_db=1.5, comp_thr=-13, comp_ratio=2.2, width=0.25)))
_register("blake", "Blake", _mk(
    bass_low=1.5, bass_comp=(-15, 3.2), sat=0.35, rev=0.05, vocal_high=1.0,
    master=MasterParams(eq_low_db=0.5, comp_thr=-12, comp_ratio=3.0, sat_drive=0.25)))
_register("lordalge", "Lord-Alge", _mk(
    bass_low=0.5, bass_comp=(-17, 2.5), rev=0.08, vocal_high=1.5, vocal_rev=0.2,
    master=MasterParams(comp_thr=-11, comp_ratio=3.5, width=0.2, gain_db=-1.0)))
_register("schmitt", "Schmitt", _mk(
    bass_low=1.0, bass_comp=(-16, 3.0), sat=0.15, rev=0.03, lead_high=1.0,
    master=MasterParams(eq_high_db=0.5, comp_thr=-14, comp_ratio=2.0, width=0.1)))
_register("mikedean", "Mike Dean", _mk(
    bass_low=1.5, bass_comp=(-14, 4.0), sat=0.45, rev=0.1, lead_high=1.5, vocal_rev=0.25,
    master=MasterParams(eq_low_db=1.0, comp_thr=-12, comp_ratio=3.0, sat_drive=0.35, width=0.3)))
_register("stent", "Stent", _mk(
    bass_low=1.0, bass_comp=(-16, 2.5), rev=0.07, vocal_high=1.0,
    master=MasterParams(comp_thr=-13, comp_ratio=2.4, width=0.2)))
_register("wallace", "Wallace", _mk(
    bass_low=2.0, bass_comp=(-15, 3.5), sat=0.4, rev=0.04,
    master=MasterParams(eq_low_db=1.5, comp_thr=-12, comp_ratio=3.0, sat_drive=0.3, width=0.05)))
_register("maserati", "Maserati", _mk(
    bass_low=0.5, bass_comp=(-17, 2.2), rev=0.16, lead_high=1.5, vocal_rev=0.3,
    master=MasterParams(eq_high_db=1.0, comp_thr=-14, comp_ratio=1.8, width=0.35)))
_register("joshua", "Joshua", _mk(
    bass_low=1.0, bass_comp=(-16, 2.8), sat=0.2, rev=0.05,
    master=MasterParams(eq_high_db=1.0, comp_thr=-13, comp_ratio=2.5, width=0.15)))
_register("ali", "Ali", _mk(
    bass_low=1.5, bass_comp=(-15, 3.2), sat=0.3, rev=0.06, vocal_high=1.5,
    master=MasterParams(eq_low_db=0.5, comp_thr=-12, comp_ratio=2.8, sat_drive=0.2)))
_register("elmhirst", "Elmhirst", _mk(
    bass_low=0.5, bass_comp=(-18, 2.0), rev=0.1,
    master=MasterParams(comp_thr=-14, comp_ratio=1.8, width=0.2)))
_register("scheps", "Scheps", _mk(
    bass_low=1.0, bass_comp=(-16, 2.5), sat=0.25, rev=0.05, lead_high=1.0,
    master=MasterParams(eq_high_db=0.5, comp_thr=-13, comp_ratio=2.2, sat_drive=0.15, width=0.15)))
_register("moulder", "Moulder", _mk(
    bass_low=0.0, bass_comp=(-17, 2.0), rev=0.18, vocal_rev=0.3,
    master=MasterParams(comp_thr=-14, comp_ratio=1.6, width=0.4)))
_register("guzauski", "Guzauski", _mk(
    bass_low=1.0, bass_comp=(-16, 2.5), rev=0.06,
    master=MasterParams(eq_high_db=0.5, comp_thr=-13, comp_ratio=2.4, width=0.2)))
_register("albini", "Albini", _mk(
    bass_low=-1.0, bass_comp=(-20, 1.5), sat=0.1, rev=0.02,
    master=MasterParams(comp_thr=-16, comp_ratio=1.4, width=0.0, gain_db=0.5)))
_register("everett", "Everett", _mk(
    bass_low=1.0, bass_comp=(-16, 2.8), sat=0.2, rev=0.08, vocal_high=1.0,
    master=MasterParams(eq_high_db=0.5, comp_thr=-13, comp_ratio=2.5, width=0.1)))
_register("elevado", "Elevado", _mk(
    bass_low=1.5, bass_comp=(-15, 3.0), sat=0.3, rev=0.06, vocal_rev=0.2,
    master=MasterParams(eq_low_db=0.5, comp_thr=-12, comp_ratio=2.6, sat_drive=0.2)))
_register("shebib", "Shebib", _mk(
    bass_low=2.0, bass_comp=(-15, 3.5), sat=0.1, rev=0.1, vocal_rev=0.28,
    master=MasterParams(eq_low_db=1.0, comp_thr=-13, comp_ratio=2.2, width=0.1)))
_register("power", "Power", _mk(
    bass_low=1.0, bass_comp=(-15, 3.5), sat=0.4, rev=0.03, lead_high=2.0,
    master=MasterParams(comp_thr=-11, comp_ratio=3.5, sat_drive=0.3, width=0.1)))
_register("zhoutianche", "周天澈", _mk(
    bass_low=1.0, bass_comp=(-16, 2.8), sat=0.2, rev=0.05, vocal_high=1.5,
    master=MasterParams(eq_high_db=1.0, comp_thr=-13, comp_ratio=2.5, width=0.2)))

MIXER_STYLES: dict[str, MixerStyle] = dict(_RAW)


def resolve_style(slug: str | None) -> MixerStyle:
    """slug → 签名；None/random → 随机一位（调用方种子控制）。"""
    if slug in (None, "", "random"):
        return random.choice(list(MIXER_STYLES.values()))
    if slug not in MIXER_STYLES:
        raise KeyError(f"未知混音师 '{slug}'。可用: {list_mixers()}")
    return MIXER_STYLES[slug]


def list_mixers() -> list[str]:
    return list(MIXER_STYLES.keys())


# ═══════════════════════════════════════════════════════════════
# DSP（numpy 自实现：RBJ 搁架 EQ / 软拐点压缩 / tanh 饱和 /
#      反馈延迟混响 / 中侧宽度）
# ═══════════════════════════════════════════════════════════════

def _shelf_coeffs(f0: float, gain_db: float, sr: int, low: bool) -> tuple:
    """RBJ 低/高搁架 biquad 系数（返回 (b, a)）。"""
    if abs(gain_db) < 0.05:
        return (np.array([1.0]), np.array([1.0]))
    a_db = gain_db
    A = 10.0 ** (a_db / 40.0)
    w0 = 2 * math.pi * f0 / sr
    cosw, sinw = math.cos(w0), math.sin(w0)
    alpha = sinw / 2 * math.sqrt(2.0)
    if low:
        b = A * ((A + 1) - (A - 1) * cosw + 2 * math.sqrt(A) * alpha)
        c = 2 * A * ((A - 1) - (A + 1) * cosw)
        d = A * ((A + 1) - (A - 1) * cosw - 2 * math.sqrt(A) * alpha)
        e = (A + 1) + (A - 1) * cosw + 2 * math.sqrt(A) * alpha
        f = -2 * ((A - 1) + (A + 1) * cosw)
        g = (A + 1) + (A - 1) * cosw - 2 * math.sqrt(A) * alpha
    else:
        b = A * ((A + 1) + (A - 1) * cosw + 2 * math.sqrt(A) * alpha)
        c = -2 * A * ((A - 1) + (A + 1) * cosw)
        d = A * ((A + 1) + (A - 1) * cosw - 2 * math.sqrt(A) * alpha)
        e = (A + 1) - (A - 1) * cosw + 2 * math.sqrt(A) * alpha
        f = 2 * ((A - 1) - (A + 1) * cosw)
        g = (A + 1) - (A - 1) * cosw - 2 * math.sqrt(A) * alpha
    return (np.array([b, c, d]) / e, np.array([1.0, f / e, g / e]))


def _biquad(x: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
    from scipy.signal import lfilter
    return lfilter(b, a, x)


def _shelf_eq(x: np.ndarray, f0: float, gain_db: float, low: bool, sr: int) -> np.ndarray:
    b, a = _shelf_coeffs(f0, gain_db, sr, low)
    return _biquad(x, b, a)


def _compressor(x: np.ndarray, thr_db: float, ratio: float, sr: int) -> np.ndarray:
    """软拐点压缩（包络跟随，attack 10ms / release 120ms）。"""
    from scipy.signal import lfilter
    thr = 10.0 ** (thr_db / 20.0)
    knee = thr * 0.5
    # 过阈值量 → 增益衰减（dB）
    env = np.maximum(np.abs(x), 1e-9)
    over = np.maximum(env - (thr - knee), 0.0)
    # 软拐点：分段增益
    gain = np.ones_like(x)
    soft = (env > thr - knee) & (env <= thr + knee)
    hard = env > thr + knee
    if np.any(soft):
        g_soft = (1.0 - (1.0 / ratio)) * (thr + knee - env[soft]) ** 2 / (4 * knee)
        gain[soft] = 10.0 ** (-g_soft / 20.0)
    if np.any(hard):
        g_hard = (1.0 - (1.0 / ratio)) * (20 * np.log10(env[hard]) - thr_db)
        gain[hard] = 10.0 ** (-g_hard / 20.0)
    # 平滑（单极低通包络）
    att = 0.010
    rel = 0.120
    alpha_a = math.exp(-1.0 / (att * sr))
    alpha_r = math.exp(-1.0 / (rel * sr))
    g_smooth = np.empty_like(gain)
    g = 1.0
    for i in range(len(gain)):
        target = gain[i]
        g = g * alpha_a + target * (1 - alpha_a) if target < g else g * alpha_r + target * (1 - alpha_r)
        g_smooth[i] = g
    return x * g_smooth


def _saturate(x: np.ndarray, drive: float) -> np.ndarray:
    if drive <= 0.01:
        return x
    return np.tanh(x * (1.0 + drive * 6.0)) / math.tanh(1.0 + drive * 6.0)


def _reverb(x: np.ndarray, wet: float, sr: int) -> np.ndarray:
    """反馈延迟混响（两段延迟 + 阻尼，向量化）。"""
    if wet <= 0.01:
        return x
    d1 = int(sr * 0.037)
    d2 = int(sr * 0.053)
    out = x.copy()
    wet_gain = wet * 0.5
    # 向量化近似：两次衰减延迟叠加
    e1 = np.zeros_like(x)
    e2 = np.zeros_like(x)
    if len(x) > d1:
        e1[d1:] = out[:-d1] * 0.55
    if len(x) > d2:
        e2[d2:] = out[:-d2] * 0.45
    return out + (e1 + e2) * wet_gain


def _width(x: np.ndarray, width: float) -> np.ndarray:
    """中/侧宽度（输入单声道 → 模拟加宽：侧信号 = 高通成分 × width）。"""
    if abs(width) < 0.05:
        return x
    from scipy.signal import butter, lfilter
    b, a = butter(2, 400.0 / (_SR / 2), btype="high")
    side = lfilter(b, a, x) * width * 0.6
    return x + side


def apply_bus_chain(x: np.ndarray, role: str, style: MixerStyle, sr: int = _SR) -> np.ndarray:
    """分轨总线链（镜像采样侧 bus_chain）。"""
    p = style.bus(role)
    y = _shelf_eq(x, 120.0, p.eq_low_db, low=True, sr=sr)
    y = _shelf_eq(y, 6000.0, p.eq_high_db, low=False, sr=sr)
    y = _compressor(y, p.comp_thr, p.comp_ratio, sr)
    y = _saturate(y, p.sat_drive)
    y = _reverb(y, p.rev_wet, sr)
    return y


def apply_master_chain(x: np.ndarray, style: MixerStyle, sr: int = _SR) -> np.ndarray:
    """母带链（镜像采样侧 master_chain；峰值 -1.5 dBFS 留编码余量）。"""
    m = style.master
    y = _shelf_eq(x, 90.0, m.eq_low_db, low=True, sr=sr)
    y = _shelf_eq(y, 8000.0, m.eq_high_db, low=False, sr=sr)
    y = _compressor(y, m.comp_thr, m.comp_ratio, sr)
    y = _saturate(y, m.sat_drive)
    y = _width(y, m.width)
    y = y * (10.0 ** (m.gain_db / 20.0))
    peak = np.max(np.abs(y)) or 1.0
    target = 10.0 ** (-1.5 / 20.0)
    if peak > target:
        y = y / peak * target
    return y
