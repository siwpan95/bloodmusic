"""
album_maker/config.py — 专辑配置数据模型

定义 AlbumConfig 和 TrackSpec dataclass，支持从 album.yaml 加载。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class TrackSpec:
    """单曲目配置。

    Args:
        title: 曲目标题
        bpm: BPM（覆盖 pool 默认）
        bars: target_bars（小节数）
        key: 调性（如 "Am", "C"）
        style: 风格预设名（12 选 1），None=用 pool 默认
        seed: 随机种子
        extra_instruments: 额外/覆盖乐器（raw dict 列表）
        mix_config_override: 曲目级 mix_config 覆盖
        midi_path: MIDI 文件路径，非空时优先走 MIDI 导入路径（跳过 PoolGenerator 合成）
    """
    title: str
    bpm: int = 120
    bars: int = 32
    key: str = "C"
    style: Optional[str] = None
    seed: Optional[int] = None
    extra_instruments: Optional[list[dict]] = None
    mix_config_override: Optional[dict] = None
    midi_path: str = ""

    def to_pool_overrides(self) -> dict:
        """生成传给 InstrumentPool 构造的覆盖参数字典。"""
        overrides: dict = {"bpm": self.bpm, "key": self.key}
        if self.seed is not None:
            overrides["seed"] = self.seed
        return overrides


@dataclass
class AlbumConfig:
    """专辑配置，从 album.yaml 解析。

    Args:
        title: 专辑标题
        artist: 艺术家
        genre: 流派
        year: 年份
        cover: 封面路径，None=无封面
        pool_raw: 乐器池 raw YAML dict
        mix_config_raw: 专辑级混音 raw dict
        separate_mode: "manifest" | "algo"
        tracks: 曲目列表
    """
    title: str
    artist: str = "BloodMusic Engine"
    genre: str = "electronic"
    year: int = 2026
    cover: Optional[str] = None
    pool_raw: dict = field(default_factory=dict)
    mix_config_raw: dict = field(default_factory=dict)
    separate_mode: str = "manifest"
    tracks: list[TrackSpec] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AlbumConfig":
        """从 album.yaml 加载并校验。

        Args:
            path: YAML 文件路径

        Returns:
            AlbumConfig 实例

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 校验失败
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"配置文件为空: {filepath}")

        if not isinstance(data, dict):
            raise ValueError(
                f"配置文件格式错误: 期望 dict，实际 {type(data).__name__}"
            )

        return cls._from_dict(data, source_path=filepath)

    @classmethod
    def _from_dict(cls, data: dict, source_path: Optional[Path] = None) -> "AlbumConfig":
        """从解析后的 dict 构造 AlbumConfig。"""
        # 解析 album 元数据
        album_data = data.get("album", {})
        if not isinstance(album_data, dict):
            album_data = {}

        # 解析 tracks
        tracks: list[TrackSpec] = []
        for i, track_data in enumerate(data.get("tracks", [])):
            if not isinstance(track_data, dict):
                logger.warning(f"曲目 #{i + 1} 格式错误，已跳过")
                continue
            try:
                tracks.append(cls._parse_track(track_data))
            except Exception as exc:
                logger.warning(f"曲目 #{i + 1} 解析失败: {exc}，已跳过")

        if not tracks:
            raise ValueError("配置文件中没有有效的曲目定义")

        # 解析 instrument_pool（内联定义）
        pool_raw = data.get("instrument_pool", {})
        if not isinstance(pool_raw, dict):
            pool_raw = {}

        # 解析 mix_config
        mix_config_raw = data.get("mix_config", {})
        if not isinstance(mix_config_raw, dict):
            mix_config_raw = {}

        return cls(
            title=album_data.get("title", "Untitled Album"),
            artist=album_data.get("artist", "BloodMusic Engine"),
            genre=album_data.get("genre", "electronic"),
            year=album_data.get("year", 2026),
            cover=album_data.get("cover"),
            pool_raw=pool_raw,
            mix_config_raw=mix_config_raw,
            separate_mode=data.get("separate_mode", "manifest"),
            tracks=tracks,
        )

    @staticmethod
    def _parse_track(data: dict) -> TrackSpec:
        """从 dict 解析单首曲目配置。"""
        return TrackSpec(
            title=data.get("title", "Untitled Track"),
            bpm=int(data.get("bpm", 120)),
            bars=int(data.get("bars", 32)),
            key=str(data.get("key", "C")),
            style=data.get("style"),
            seed=data.get("seed"),
            extra_instruments=data.get("extra_instruments"),
            mix_config_override=data.get("mix_config"),
            midi_path=str(data.get("midi_path", "")),
        )
