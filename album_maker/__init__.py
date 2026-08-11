"""
BloodMusic Album Maker — 程序化专辑制作器
==========================================

从乐器池 YAML 到完整专辑目录，一键生成。

架构分层：
  config.py      — AlbumConfig / TrackSpec 数据模型
  demo_config.py — 内置 demo 配置（零配置体验）
  track.py       — TrackHandler：单曲目全流程处理器
  album.py       — AlbumMaker：专辑级编排器
  report.py      — AlbumReport：报告生成
  cli.py         — CLI 入口

用法：
  >>> from bloodmusic.album_maker import AlbumConfig, make_demo_config
  >>> from bloodmusic.album_maker import AlbumMaker
  >>> config = make_demo_config()
  >>> maker = AlbumMaker(config)
  >>> result = maker.make("./demo_output")
  >>> print(f"成功 {result.success_count}/{len(result.tracks)} 首")

CLI：
  $ python -m bloodmusic.album_maker.cli make --demo --out ./album_output
"""

__all__ = [
    "AlbumConfig",
    "AlbumMaker",
    "AlbumReport",
    "AlbumResult",
    "DEMO_ALBUM_CONFIG",
    "TrackHandler",
    "TrackResult",
    "TrackSpec",
    "make_demo_config",
]

from .config import AlbumConfig, TrackSpec
from .demo_config import DEMO_ALBUM_CONFIG, make_demo_config
from .track import TrackHandler, TrackResult
from .album import AlbumMaker, AlbumResult
from .report import AlbumReport
