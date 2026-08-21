# -*- coding: utf-8 -*-
"""
config.py —— 编排工具配置与环境解析（T1）

职责（仅依赖 os / sys / pathlib 标准库，零重包）：
  - 项目根路径与内置 ffmpeg 常量
  - bootstrap_env()：在 import pydub / remix / bloodmusic 之前调用一次，
    负责 PATH 注入 + pydub pin + sys.path 注入（依赖隔离落地）。
  - HONESTY_DISCLAIMER：诚实性文案，CLI / 日志 / manifest 三处统一引用。

纯合成定位：本流水线仅合成与混音 BloodMusic 自生成音频，
不涉及外部歌曲拆分（audio_separator/demucs）或算法重分离。

设计依据：docs/design.md §2.1、§4（依赖隔离）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ───────────────────────── 项目路径常量 ─────────────────────────
# 内部自包含：remix/ 已迁入 bloodmusic 内部

_THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # bloodmusic root

# remix 已内置于 bloodmusic/remix
REMIX_ROOT = os.path.join(_THIS_DIR, "remix")
# bloodmusic 自身
BLOODMUSIC_ROOT = _THIS_DIR
# remix 自带的 ffmpeg / ffprobe（仅用这一份，不污染系统 PATH）
REMIX_BIN = os.path.join(REMIX_ROOT, "bin")

# ───────────────────────── 默认输出参数 ─────────────────────────

DEFAULT_OUTPUT_FMT = "wav"          # 阶段B/C 可 wav/ogg/flac

# ───────────────────────── 诚实性声明（三处统一引用） ─────────────────────────

HONESTY_DISCLAIMER = (
    "⚠ 混音不可逆；全部音源均为 BloodMusic 程序化合成（零外部采样），"
    "分轨=复用混音时保留的原始分轨（100% 保真）。"
)

# 分轨保留说明（manifest note 细分）
HONESTY_MODE_A = (
    "模式A：复用混音时保留的原始分轨（逐字节一致），100% 保真。"
)

# 受支持的音频格式（与 bloodmusic / remix 对齐）
SUPPORTED_AUDIO_FORMATS = ("wav", "ogg", "flac")

_BOOTSTRAPPED = False


def bootstrap_env() -> None:
    """在 import pydub / remix / bloodmusic 之前调用一次（幂等）。

    1) 把 REMIX_BIN 注入 os.environ["PATH"]；
    2) pin pydub.AudioSegment.converter / ffprobe 到 REMIX_BIN 的 ffmpeg / ffprobe；
    3) sys.path.insert(0, REMIX_ROOT)，使 `from core.audio_mixer import AudioMixer` 可用；
    4) import bloodmusic / bloodmusic.bridge（验证可用）。
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    # 1) PATH 注入（remix 自带 ffmpeg）
    old_path = os.environ.get("PATH", "")
    if REMIX_BIN not in old_path.split(os.pathsep):
        os.environ["PATH"] = REMIX_BIN + os.pathsep + old_path

    # 2) pydub pin（仅 PATH 不够稳，pin 路径最可靠）
    try:
        from pydub import AudioSegment  # 仅依赖 audioop（已装 audioop-lts），无 torch
        AudioSegment.converter = os.path.join(REMIX_BIN, "ffmpeg.exe")
        AudioSegment.ffprobe = os.path.join(REMIX_BIN, "ffprobe.exe")
    except Exception as exc:  # pragma: no cover - 环境异常时给出明确提示
        sys.stderr.write(
            f"[audio_pipeline] 警告：pin pydub 失败（{exc}）。"
            "请确认 audioop-lts 已安装且 remix/bin 含 ffmpeg。\n"
        )

    # 3) remix 根注入 sys.path
    if REMIX_ROOT not in sys.path:
        sys.path.insert(0, REMIX_ROOT)

    # 4) 验证 bloodmusic 可用（editable 已装，无需 path 注入）
    try:
        import bloodmusic  # noqa: F401
        import bloodmusic.bridge  # noqa: F401
    except Exception as exc:  # pragma: no cover
        sys.stderr.write(
            f"[audio_pipeline] 警告：import bloodmusic 失败（{exc}）。"
            "请确认 bloodmusic 已 editable 安装。\n"
        )

    _BOOTSTRAPPED = True
