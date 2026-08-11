"""
album_maker/demo_config.py — 内置 demo 专辑配置

提供 make_demo_config() 函数，返回 3 首曲目的内置 AlbumConfig。
风格覆盖：exploration / battle / town，各 16 小节，零外部文件依赖。
"""

from __future__ import annotations

from .config import AlbumConfig, TrackSpec


def make_demo_config() -> AlbumConfig:
    """返回内置 3 曲 demo 专辑配置。

    Returns:
        AlbumConfig: 包含 exploration(100BPM/16bars) +
                     battle(140BPM/16bars) +
                     town(90BPM/16bars) 的 demo 配置
    """
    pool_raw: dict = {
        "name": "Demo 电子氛围乐池",
        "bpm": 120,
        "key": "Am",
        "scale": "minor",
        "global_volume": 0.9,
        "generation": {
            "diversity": 0.4,
            "humanize": True,
            "seed": 42,
            "chord_progression": "dreamy",
        },
        "instruments": [
            {
                "name": "主旋律合成器",
                "role": "melody",
                "engine": "wavetable",
                "preset": "synth_lead",
                "volume": 0.9,
                "pan": 0.1,
            },
            {
                "name": "和弦铺底",
                "role": "chord",
                "engine": "fm_advanced",
                "preset": "warm_pad",
                "volume": 0.7,
                "pan": -0.3,
            },
            {
                "name": "贝斯线",
                "role": "bass",
                "engine": "subtractive",
                "preset": "deep_bass",
                "volume": 1.0,
                "pan": 0.0,
            },
            {
                "name": "电子鼓",
                "role": "drum",
                "engine": "noise",
                "volume": 0.85,
                "pan": 0.0,
            },
            {
                "name": "氛围铺底",
                "role": "pad",
                "engine": "granular",
                "preset": "bright_pad",
                "volume": 0.5,
                "pan": 0.4,
            },
        ],
    }

    mix_config_raw: dict = {
        "clip_mode": "soft",
        "normalize_mode": "rms",
        "rms_target_db": -3.0,
        "fade_in_ms": 50,
        "fade_out_ms": 200,
        "compress": True,
        "compress_threshold": -20.0,
        "compress_ratio": 4.0,
    }

    tracks: list[TrackSpec] = [
        TrackSpec(
            title="探索曲 — 漫游",
            bpm=100,
            bars=16,
            key="Am",
            style="exploration",
            seed=42,
        ),
        TrackSpec(
            title="战斗曲 — 脉冲",
            bpm=140,
            bars=16,
            key="Em",
            style="battle",
            seed=777,
        ),
        TrackSpec(
            title="城镇曲 — 暖阳",
            bpm=90,
            bars=16,
            key="C",
            style="town",
            seed=1234,
        ),
    ]

    return AlbumConfig(
        title="Demo 专辑 — 三界",
        artist="BloodMusic Engine (Demo)",
        genre="game",
        year=2026,
        cover=None,
        pool_raw=pool_raw,
        mix_config_raw=mix_config_raw,
        separate_mode="manifest",
        tracks=tracks,
    )


# 模块级常量，方便直接引用
DEMO_ALBUM_CONFIG: AlbumConfig = make_demo_config()
