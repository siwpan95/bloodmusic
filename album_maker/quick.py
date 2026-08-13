"""album_maker/quick.py — 随机风格单曲快速生成器
================================================
整合 album_generator.py 的风格知识 + album_maker YAML 引擎，
一条命令出单曲，零配置。

用法:
    from bloodmusic.album_maker.quick import QuickMaker
    result = QuickMaker.random()       # 随机风格
    result = QuickMaker.style("jazz")  # 指定风格
    result = QuickMaker.jam(5)         # 连续生成 5 首随机曲
"""

from __future__ import annotations
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import TrackSpec, AlbumConfig
from .album import AlbumMaker
from .track import TrackHandler

# 默认输出根（绝对路径，固定到 bloodmusic 项目内）
_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "album_maker_quick"
_JAM_DEFAULT_OUT = Path(__file__).resolve().parents[1] / "album_maker_jam"

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 风格数据库（已提取到公共模块 style_db.py，含随机候选 key/scale/progression）
# ═══════════════════════════════════════════════════════════════════════
from .style_db import STYLE_DB, get_style

BARS_OPTIONS = [8, 12, 16, 24, 32]
MIX_CONFIG_DEFAULTS = {
    "clip_mode": "soft", "normalize_mode": "rms", "rms_target_db": -2.0,
    "fade_in_ms": 50, "fade_out_ms": 200, "compress": True,
    "compress_threshold": -18.0, "compress_ratio": 3.0,
}

# 采样池逻辑已提取到公共模块 sample_pool.py（quick/make/beat 共享）
from .sample_pool import (
    SAMPLE_SCAN_DIRS,
    DEFAULT_SYNTH_POOL,
    wav_to_instrument_name,
    assign_sample_role,
    auto_build_pool,
)

# 向后兼容别名
_SAMPLE_SCAN_DIRS = SAMPLE_SCAN_DIRS
_DEFAULT_SYNTH_POOL = DEFAULT_SYNTH_POOL
_wav_to_instrument_name = wav_to_instrument_name
_assign_sample_role = assign_sample_role
_auto_build_pool = auto_build_pool


# ═══════════════════════════════════════════════════════════════════════
# 曲目标题生成器（来自 album_generator.py TRACKLIST 灵感）
# ═══════════════════════════════════════════════════════════════════════

TITLE_TEMPLATES = [
    "晨曦 · {mood}", "星海 · {mood}", "深海 · {mood}", "午夜 · {mood}",
    "脉冲 · {mood}", "远征 · {mood}", "旧日 · {mood}", "空山 · {mood}",
    "田园 · {mood}", "终章 · {mood}", "漫步 · {mood}", "迷雾 · {mood}",
    "极光 · {mood}", "裂谷 · {mood}", "回响 · {mood}", "幻境 · {mood}",
]


@dataclass
class QuickResult:
    """单曲生成结果"""
    title: str
    style: str
    bpm: int
    key: str
    bars: int
    output_dir: Path
    wave_path: Optional[Path] = None
    duration_sec: float = 0.0
    seed: int = 0


class QuickMaker:
    """快速单曲生成器 — 零配置立即产出"""

    @classmethod
    def random(cls, out_dir: str | None = None, seed: int | None = None) -> QuickResult:
        """随机风格、BPM、小节数，一键生成单曲。

        Args:
            out_dir: 输出目录，默认 bloodmusic/album_maker_quick/
            seed: 随机种子（可复现），None=真随机
        """
        style_name = random.choice(list(STYLE_DB.keys()))
        return cls.style(style_name, out_dir, seed)

    @classmethod
    def style(cls, style_name: str, out_dir: str | None = None,
              bpm: int | None = None, bars: int | None = None,
              seed: int | None = None) -> QuickResult:
        """指定风格生成单曲。

        Args:
            style_name: 风格名（classical/jazz/electronic/...）
            out_dir: 输出目录
            bpm: 指定 BPM，None=随机取风格范围
            bars: 小节数，None=随机
            seed: 随机种子
        """
        if seed is not None:
            random.seed(seed)

        style = STYLE_DB.get(style_name)
        if not style:
            available = ", ".join(STYLE_DB.keys())
            raise ValueError(f"未知风格 '{style_name}'。可用: {available}")

        # 随机参数（key/scale/progression 从候选列表随机选，保证随机性）
        bpm = bpm or random.randint(*style["bpm_range"])
        bars = bars or random.choice(BARS_OPTIONS)
        key = random.choice(style["keys"])
        scale = random.choice(style["scales"])
        progression = random.choice(style["progressions"])
        seed_val = seed if seed is not None else random.randint(0, 9999)
        title_template = random.choice(TITLE_TEMPLATES)
        title = title_template.format(mood=style["mood"])

        base_dir = Path(out_dir) if out_dir else _DEFAULT_OUT
        base_dir.mkdir(parents=True, exist_ok=True)

        # 构造 TrackSpec（key/scale 随机）
        spec = TrackSpec(
            title=title, bpm=bpm, bars=bars,
            key=key, style=style_name, seed=seed_val,
        )

        # 构造 pool（注入随机 progression）
        pool = _auto_build_pool()
        pool["key"] = key
        pool["scale"] = scale
        pool.setdefault("generation", {})["chord_progression"] = progression
        pool["generation"]["seed"] = seed_val

        # 构造最小 AlbumConfig（单曲专辑）
        config = AlbumConfig(
            title=title, artist="BloodMusic Quick", genre=style_name, year=2026,
            pool_raw=pool,
            mix_config_raw=MIX_CONFIG_DEFAULTS,
            separate_mode="manifest",
            tracks=[spec],
        )

        # 调用 album_maker 引擎
        result = AlbumMaker(config).make(str(base_dir))

        qr = QuickResult(
            title=title, style=style_name, bpm=bpm,
            key=key, bars=bars, output_dir=base_dir, seed=seed_val,
        )

        if result.tracks and result.tracks[0].song_path:
            qr.wave_path = result.tracks[0].song_path
            qr.duration_sec = result.tracks[0].duration_sec

        return qr

    @classmethod
    def jam(cls, count: int = 5, out_dir: str | None = None) -> list[QuickResult]:
        """连续随机生成 N 首曲目（即兴模式）。

        Args:
            count: 生成数量
            out_dir: 输出目录
        """
        results = []
        for i in range(count):
            # 避开重复风格
            used = {r.style for r in results}
            available = [s for s in STYLE_DB if s not in used]
            if not available:
                available = list(STYLE_DB.keys())

            style_name = random.choice(available)
            seed = random.randint(0, 9999)
            logger.info(f"[jam {i+1}/{count}] 风格={style_name} seed={seed}")

            result = cls.style(style_name, out_dir, seed=seed)
            results.append(result)

            if result.wave_path:
                print(f"  ✅ {result.title} ({style_name}, {result.bpm}BPM, "
                      f"{result.duration_sec:.1f}s)")

        print(f"\n🎵 Jam 完成: {count} 首 → {out_dir or str(_JAM_DEFAULT_OUT)}")
        return results

    @classmethod
    def list_styles(cls) -> dict:
        """列出所有可用风格（含编配策略）"""
        return STYLE_DB
