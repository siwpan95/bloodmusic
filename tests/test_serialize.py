"""SFX 参数序列化测试 — SynthVoice ↔ JSON / 紧凑字符串往返。"""

import numpy as np
import pytest

from bloodmusic.core.voice import SynthVoice, LFOParams, LFOTarget
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape, ADSRParams
from bloodmusic.core import synthesize_voice
from bloodmusic.effects.chain import EffectChain
from bloodmusic.effects.dynamics import CompressorParams
from bloodmusic.effects.eq import ParametricEQParams
from bloodmusic.sfx.presets import UI_FX_PRESETS
from bloodmusic.sfx.serialize import (
    voice_to_dict, voice_from_dict,
    voice_to_json, voice_from_json,
    voice_to_compact, voice_from_compact,
)


def _sample_voice() -> SynthVoice:
    """含全部嵌套结构的复杂 SynthVoice。"""
    return SynthVoice(
        freq=440.0,
        osc_type=OscType.SQUARE,
        duration=0.25,
        volume=0.6,
        env_shape=EnvShape.PLUCK,
        adsr=ADSRParams(attack=0.02, decay=0.15, sustain=0.5, release=0.1),
        pitch_mod=-3,
        vibrato_rate=5.0,
        vibrato_depth=1.5,
        detune=4.0,
        harmonics=[(2.0, 0.3), (3.0, 0.1)],
        lfo=LFOParams(rate=4.0, depth=0.2, target=LFOTarget.AMPLITUDE),
        effect_chain=EffectChain(
            lp_filter_hz=4000.0,
            distortion=0.2,
            bit_crush=8,
            reverb_mix=0.15,
            reverb_schroeder=True,
            compressor=CompressorParams(threshold_db=-15.0, ratio=3.0),
            eq=ParametricEQParams(mid_gain_db=2.0),
            chorus_mix=0.1,
            multitap_times=[0.2, 0.35],
            phaser_stages=8,
        ),
    )


# ═══════════════════════════════════════════════════════════════════
# dict / JSON 往返
# ═══════════════════════════════════════════════════════════════════

def test_dict_roundtrip_fields():
    voice = _sample_voice()
    data = voice_to_dict(voice)
    restored = voice_from_dict(data)
    assert restored.freq == 440.0
    assert restored.osc_type is OscType.SQUARE
    assert restored.env_shape is EnvShape.PLUCK
    assert restored.adsr.attack == 0.02
    assert restored.harmonics == [(2.0, 0.3), (3.0, 0.1)]
    assert restored.lfo.target is LFOTarget.AMPLITUDE
    assert restored.effect_chain.lp_filter_hz == 4000.0
    assert restored.effect_chain.compressor.threshold_db == -15.0
    assert restored.effect_chain.eq.mid_gain_db == 2.0
    assert restored.effect_chain.multitap_times == [0.2, 0.35]
    assert restored.effect_chain.phaser_stages == 8


def test_audio_bit_exact_after_roundtrip():
    """序列化→反序列化→合成，音频必须逐位一致。"""
    voice = _sample_voice()
    restored = voice_from_dict(voice_to_dict(voice))
    a = synthesize_voice(voice)
    b = synthesize_voice(restored)
    assert np.array_equal(a, b), "audio differs after dict roundtrip"


def test_json_roundtrip():
    voice = _sample_voice()
    restored = voice_from_json(voice_to_json(voice))
    a = synthesize_voice(voice)
    b = synthesize_voice(restored)
    assert np.array_equal(a, b), "audio differs after JSON roundtrip"


# ═══════════════════════════════════════════════════════════════════
# compact 紧凑串
# ═══════════════════════════════════════════════════════════════════

def test_compact_roundtrip_audio_identical():
    voice = _sample_voice()
    compact = voice_to_compact(voice)
    restored = voice_from_compact(compact)
    a = synthesize_voice(voice)
    b = synthesize_voice(restored)
    assert np.array_equal(a, b), "audio differs after compact roundtrip"


def test_compact_is_short():
    """紧凑串应远小于 JSON（典型 <300 字符）。"""
    voice = _sample_voice()
    compact = voice_to_compact(voice)
    assert len(compact) < 300, f"compact too long: {len(compact)} chars"
    assert len(compact) < len(voice_to_json(voice)), (
        "compact should be shorter than plain JSON"
    )


def test_compact_invalid_input():
    with pytest.raises(ValueError):
        voice_from_compact("not-a-valid-compact")
    with pytest.raises(ValueError):
        voice_from_compact(12345)


# ═══════════════════════════════════════════════════════════════════
# 全预设往返
# ═══════════════════════════════════════════════════════════════════

def test_all_ui_presets_roundtrip():
    """UI_FX_PRESETS 全部预设可往返且音频一致。"""
    for name, voice in UI_FX_PRESETS.items():
        restored = voice_from_dict(voice_to_dict(voice))
        a = synthesize_voice(voice)
        b = synthesize_voice(restored)
        assert np.array_equal(a, b), f"preset '{name}' differs after roundtrip"


def test_minimal_voice_roundtrip():
    """最小字段 SynthVoice（全默认）往返。"""
    voice = SynthVoice()
    restored = voice_from_dict(voice_to_dict(voice))
    assert np.array_equal(synthesize_voice(voice), synthesize_voice(restored))


def test_dict_is_json_serializable():
    import json
    data = voice_to_dict(_sample_voice())
    json.dumps(data)  # 不抛异常即可


def test_compact_tampered_index_raises_friendly_error():
    """篡改字段索引（越界）应抛出友好 ValueError 而非 IndexError。"""
    import json
    import zlib
    import base64
    from bloodmusic.core.voice import SynthVoice
    from bloodmusic.sfx.serialize import _COMPACT_PREFIX, voice_to_compact, voice_from_compact

    # 解码合法 compact（兼容"压缩更短才压缩"的编码策略）
    body = base64.urlsafe_b64decode(
        voice_to_compact(SynthVoice(freq=880.0, volume=0.5))[len(_COMPACT_PREFIX):].encode("ascii")
    )
    try:
        raw = zlib.decompress(body)
    except zlib.error:
        raw = body
    decoded = json.loads(raw.decode())
    assert decoded, "非默认 voice 的 compact 载荷不应为空"
    # 篡改：把某个字段索引替换为越界索引 999
    decoded["999"] = decoded.pop(next(iter(decoded)))
    payload = json.dumps(decoded, separators=(",", ":")).encode()
    compressed = zlib.compress(payload)
    tampered_body = compressed if len(compressed) < len(payload) else payload
    tampered = _COMPACT_PREFIX + base64.urlsafe_b64encode(tampered_body).decode("ascii")
    with pytest.raises(ValueError, match="越界|非法"):
        voice_from_compact(tampered)
