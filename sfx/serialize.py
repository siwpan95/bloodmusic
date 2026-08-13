"""SFX 参数序列化 — SynthVoice ↔ JSON / 紧凑字符串。

仿 jsfxr 的 base58 短 URL 理念：整个音效的参数可压缩成一段短字符串，
便于分享、版本控制与存储。支持嵌套的 EffectChain / ADSRParams /
CompressorParams / ParametricEQParams / LFOParams 全量往返。

用法:
    >>> from bloodmusic.sfx.serialize import voice_to_json, voice_from_json
    >>> s = voice_to_json(voice)
    >>> voice2 = voice_from_json(s)
    >>> compact = voice_to_compact(voice)   # 短字符串 (<300 字符)
    >>> voice3 = voice_from_compact(compact)
"""

import base64
import json
import zlib
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints

from ..core.oscillator import OscType
from ..core.envelope import EnvShape, ADSRParams
from ..core.voice import SynthVoice, LFOParams, LFOTarget
from ..effects.chain import EffectChain
from ..effects.dynamics import CompressorParams
from ..effects.eq import ParametricEQParams

__all__ = [
    "voice_to_dict", "voice_from_dict",
    "voice_to_json", "voice_from_json",
    "voice_to_compact", "voice_from_compact",
]

#: compact 串版本前缀（格式变更时递增）
_COMPACT_PREFIX = "bm1:"

#: 已知枚举类型（按 value 字符串还原）
_ENUM_TYPES = (OscType, EnvShape, LFOTarget)

#: 类型注解缓存（解析 forward ref，如 Optional["EffectChain"]）
#: core/voice.py 对 EffectChain 是延迟导入（字符串注解），其模块 globals
#: 不含该名字，需显式提供 globalns 才能解析。
_HINT_GLOBALS: dict = {
    "EffectChain": EffectChain,
    "CompressorParams": CompressorParams,
    "ParametricEQParams": ParametricEQParams,
    "ADSRParams": ADSRParams,
    "LFOParams": LFOParams,
    "LFOTarget": LFOTarget,
    "OscType": OscType,
    "EnvShape": EnvShape,
}

_HINTS: dict = {
    SynthVoice: get_type_hints(SynthVoice, globalns=_HINT_GLOBALS),
    EffectChain: get_type_hints(EffectChain, globalns=_HINT_GLOBALS),
    ADSRParams: get_type_hints(ADSRParams, globalns=_HINT_GLOBALS),
    CompressorParams: get_type_hints(CompressorParams, globalns=_HINT_GLOBALS),
    ParametricEQParams: get_type_hints(ParametricEQParams, globalns=_HINT_GLOBALS),
    LFOParams: get_type_hints(LFOParams, globalns=_HINT_GLOBALS),
}


# ═══════════════════════════════════════════════════════════════════
# 序列化（对象 → 可 JSON 化结构）
# ═══════════════════════════════════════════════════════════════════

def _to_data(obj: Any) -> Any:
    """递归转换为 JSON 可序列化结构（枚举→字符串、dataclass→dict、tuple→list）。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_to_data(x) for x in obj]
    if is_dataclass(obj):
        return {f.name: _to_data(getattr(obj, f.name)) for f in fields(obj)}
    raise TypeError(f"unsupported type for serialization: {type(obj)!r}")


def voice_to_dict(voice: SynthVoice) -> dict:
    """SynthVoice → 可 JSON 化字典（含嵌套 EffectChain/ADSR/LFO 等）。"""
    return _to_data(voice)


# ═══════════════════════════════════════════════════════════════════
# 反序列化（JSON 结构 → 对象）
# ═══════════════════════════════════════════════════════════════════

def _from_data(value: Any, target_type: Any, owner: type = None) -> Any:
    """按目标类型注解递归还原值。owner 提供 forward-ref 解析上下文。"""
    if value is None:
        return None
    if isinstance(target_type, str):
        if owner is not None and target_type in _HINTS.get(owner, {}):
            target_type = _HINTS[owner][target_type]
        elif target_type == "EffectChain":
            target_type = EffectChain
        else:
            return value
    if isinstance(target_type, type) and issubclass(target_type, Enum):
        return target_type(value)
    if is_dataclass(target_type):
        if not isinstance(value, dict):
            raise TypeError(f"expected dict for {target_type}, got {type(value)!r}")
        hints = _HINTS.get(target_type, {})
        kwargs = {}
        for f in fields(target_type):
            if f.name in value:
                kwargs[f.name] = _from_data(
                    value[f.name],
                    hints.get(f.name, f.type),
                    owner=target_type,
                )
        return target_type(**kwargs)
    origin = get_origin(target_type)
    if origin in (list,):
        (inner,) = get_args(target_type) or (Any,)
        return [_from_data(x, inner, owner=owner) for x in value]
    if origin in (tuple,):
        args = get_args(target_type)
        return tuple(
            _from_data(x, args[i] if i < len(args) else Any, owner=owner)
            for i, x in enumerate(value)
        )
    if origin is Union:  # Optional[X] → Union[X, None]
        args = [a for a in get_args(target_type) if a is not type(None)]
        return _from_data(value, args[0] if args else Any, owner=owner)
    return value


def voice_from_dict(data: dict) -> SynthVoice:
    """可 JSON 化字典 → SynthVoice（枚举/嵌套 dataclass 自动还原）。"""
    if not isinstance(data, dict):
        raise TypeError(f"expected dict, got {type(data)!r}")
    return _from_data(data, SynthVoice, owner=SynthVoice)


# ═══════════════════════════════════════════════════════════════════
# JSON 往返
# ═══════════════════════════════════════════════════════════════════

def voice_to_json(voice: SynthVoice) -> str:
    """SynthVoice → JSON 字符串。"""
    return json.dumps(voice_to_dict(voice), ensure_ascii=False)


def voice_from_json(text: str) -> SynthVoice:
    """JSON 字符串 → SynthVoice。"""
    return voice_from_dict(json.loads(text))


# ═══════════════════════════════════════════════════════════════════
# 紧凑字符串（仿 jsfxr base58 短 URL）
# ═══════════════════════════════════════════════════════════════════

def _compact_data(obj: Any) -> Any:
    """delta 编码：{字段索引: 非默认值}。

    只保留与默认实例不同的字段（大幅缩减字段数），键用 dataclass
    字段顺序的数字索引代替字段名（键长从 10+ 字符降到 1-2 字符）。
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [_compact_data(x) for x in obj]
    if is_dataclass(obj):
        default = type(obj)()
        out: dict = {}
        for i, f in enumerate(fields(obj)):
            v = getattr(obj, f.name)
            if v != getattr(default, f.name):
                out[i] = _compact_data(v)
        return out
    raise TypeError(f"unsupported type for compact encoding: {type(obj)!r}")


def _from_compact_data(value: Any, target_type: Any, owner: type = None) -> Any:
    """compact delta 结构 → 对象（与 _from_data 对应，键为数字索引）。"""
    if value is None:
        return None
    if isinstance(target_type, str):
        if owner is not None and target_type in _HINTS.get(owner, {}):
            target_type = _HINTS[owner][target_type]
        elif target_type == "EffectChain":
            target_type = EffectChain
        else:
            return value
    if isinstance(target_type, type) and issubclass(target_type, Enum):
        return target_type(value)
    if is_dataclass(target_type):
        if not isinstance(value, dict):
            raise TypeError(f"expected dict for {target_type}, got {type(value)!r}")
        hints = _HINTS.get(target_type, {})
        flds = list(fields(target_type))
        kwargs = {}
        for idx_str, v in value.items():
            i = int(idx_str)
            f = flds[i]
            kwargs[f.name] = _from_compact_data(
                v, hints.get(f.name, f.type), owner=target_type,
            )
        return target_type(**kwargs)
    origin = get_origin(target_type)
    if origin in (list,):
        (inner,) = get_args(target_type) or (Any,)
        return [_from_compact_data(x, inner, owner=owner) for x in value]
    if origin in (tuple,):
        args = get_args(target_type)
        return tuple(
            _from_compact_data(x, args[i] if i < len(args) else Any, owner=owner)
            for i, x in enumerate(value)
        )
    if origin is Union:
        args = [a for a in get_args(target_type) if a is not type(None)]
        return _from_compact_data(value, args[0] if args else Any, owner=owner)
    return value


def voice_to_compact(voice: SynthVoice) -> str:
    """SynthVoice → 紧凑短字符串（delta 编码 + zlib + base64url）。

    长度远小于 JSON（真实预设通常 <300 字符），适合分享/日志/版本记录。
    压缩后若反而变大则直接使用未压缩载荷。
    """
    payload = json.dumps(
        _compact_data(voice), ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")
    compressed = zlib.compress(payload, level=9)
    body = compressed if len(compressed) < len(payload) else payload
    return _COMPACT_PREFIX + base64.urlsafe_b64encode(body).decode("ascii")


def voice_from_compact(text: str) -> SynthVoice:
    """紧凑短字符串 → SynthVoice。"""
    if not isinstance(text, str) or not text.startswith(_COMPACT_PREFIX):
        raise ValueError(
            f"invalid compact string (expected prefix '{_COMPACT_PREFIX}')"
        )
    body = base64.urlsafe_b64decode(text[len(_COMPACT_PREFIX):].encode("ascii"))
    try:
        payload = zlib.decompress(body)
    except zlib.error:
        payload = body  # 未压缩载荷
    return _from_compact_data(
        json.loads(payload.decode("utf-8")), SynthVoice, owner=SynthVoice,
    )
