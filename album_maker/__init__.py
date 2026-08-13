"""
BloodMusic Album Maker — 程序化专辑制作器 + 快速单曲生成器
============================================================

整合 album_generator.py (旧版硬编码专辑) + skill/make_beats.py (节拍工具)，
提供统一的专辑/单曲生成接口。

架构分层：
  config.py      — AlbumConfig / TrackSpec 数据模型
  demo_config.py — 内置 demo 配置（零配置体验）
  track.py       — TrackHandler：单曲目全流程处理器
  album.py       — AlbumMaker：专辑级编排器
  report.py      — AlbumReport：报告生成
  quick.py       — QuickMaker：随机风格快速单曲生成器（新增）
  cli.py         — CLI 入口

用法：
  >>> from bloodmusic.album_maker import QuickMaker
  >>> QuickMaker.random()           # 随机风格单曲
  >>> QuickMaker.style("jazz")      # 指定风格单曲
  >>> QuickMaker.jam(5)             # 连续即兴 5 首

CLI：
  $ python -m bloodmusic.album_maker.cli quick          # 随机单曲
  $ python -m bloodmusic.album_maker.cli style jazz     # 爵士单曲
  $ python -m bloodmusic.album_maker.cli jam --count 3  # 即兴 3 首
  $ python -m bloodmusic.album_maker.cli make --demo    # 完整专辑
"""

__all__ = [
    "AlbumConfig",
    "AlbumMaker",
    "AlbumReport",
    "AlbumResult",
    "DEMO_ALBUM_CONFIG",
    "QuickMaker",
    "QuickResult",
    "TrackHandler",
    "TrackResult",
    "TrackSpec",
    "make_demo_config",
]

from .config import AlbumConfig, TrackSpec
from .demo_config import DEMO_ALBUM_CONFIG, make_demo_config
from .track import TrackHandler, TrackResult
from .album import AlbumMaker, AlbumResult
from .quick import QuickMaker, QuickResult
from .report import AlbumReport
