# -*- coding: utf-8 -*-
"""
source_maker.py —— 阶段 B：单音源导出（T3）

职责：
  - TrackSpec：单条音源规格（纯合成）
  - make_source()：导出单条音源分轨到 stems/，返回产物路径
      * bridge 振荡器合成（纯自生成，零外部采样）

零改造：仅调用 bloodmusic.bridge / export.batch，不修改其源码（R4）。
设计依据：docs/design.md §2.3、§6.2、§7。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import bootstrap_env
from bloodmusic.bridge import (
    midi_to_patterns_v2,
    render_pattern_file,
    BridgeConfig,
)
from bloodmusic.bridge.models import ImportResult
from bloodmusic.music.pattern import MusicPattern

bootstrap_env()


@dataclass
class TrackSpec:
    """单条音源规格。"""

    name: str                          # 音源名（用于产物文件名）
    kind: str = "synth"                # 固定 "synth"（纯合成路径）
    pattern_source: Optional[Path] = None   # MIDI 资产（midi_to_patterns_v2 输入）
    pattern_name: Optional[str] = None      # 从 ImportResult 选单个 pattern 的名称
    fmt: str = "wav"                  # wav|ogg|flac（P0-2）
    duration_sec: Optional[float] = None
    bpm: Optional[int] = None


def _programmatic_pattern(spec: TrackSpec) -> MusicPattern:
    """无 MIDI 时的内置程序化 pattern（决策：允许无 MIDI 程序化 pattern）。"""
    bpm = int(spec.bpm) if spec.bpm else 120
    return MusicPattern(
        name=spec.name,
        notes=["C4", "E4", "G4", "C5"],
        durations=[1.0, 1.0, 1.0, 1.0],
        bpm=bpm,
        loop=False,
        volume=0.6,
    )


def _resolve_pattern(spec: TrackSpec) -> object:
    """解析出要渲染的 pattern。

    Args:
        spec: 音源规格。

    Returns:
        MusicPattern 或 DrumPattern。

    Raises:
        ValueError: 无法解析出可用 pattern。
    """
    pat = None
    src = Path(spec.pattern_source) if spec.pattern_source else None
    if src is not None and src.is_file():
        result: ImportResult = midi_to_patterns_v2(str(src), bpm=spec.bpm)
        candidates = result.all_patterns  # 旋律 + 和弦 + 鼓
        if spec.pattern_name:
            pat = next((p for p in candidates if p.name == spec.pattern_name), None)
        else:
            pat = candidates[0] if candidates else None

    if pat is None:
        # 退化为程序化 pattern（始终为 MusicPattern）
        pat = _programmatic_pattern(spec)
    return pat


def _natural_duration(pat: object) -> float:
    """按 pattern 自然时长反推秒数（D6：不用拍脑袋时长）。"""
    bpm = getattr(pat, "bpm", 120) or 120
    durations = getattr(pat, "durations", []) or []
    total_beats = sum(float(d) for d in durations)
    if total_beats <= 0:
        return 2.0
    return max(0.05, total_beats * 60.0 / float(bpm))


def _output_path(out_dir: Path, spec: TrackSpec) -> Path:
    """按 §6.2 命名：stems/synth__<track_name>.<fmt>。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"synth__{spec.name}.{spec.fmt}"


def make_source(track_spec: TrackSpec, out_dir: Path) -> Path:
    """阶段B 主入口：导出单条合成音源分轨。

    Args:
        track_spec: 音源规格。
        out_dir: 输出目录（如 stems/）。

    Returns:
        产物文件路径。

    Raises:
        ValueError: 规格非法。
        BridgeRenderError: bridge 渲染失败（透传）。
    """
    if track_spec.kind != "synth":
        raise ValueError(f"未知 kind: {track_spec.kind}（纯合成流水线仅支持 synth）")

    out_path = _output_path(out_dir, track_spec)
    fmt = track_spec.fmt.lower()
    if fmt not in ("wav", "ogg", "flac"):
        raise ValueError(f"不支持的输出格式: {fmt}（应为 wav|ogg|flac）")

    # ── 解析 pattern ──
    pat = _resolve_pattern(track_spec)

    # ── 时长 ──
    duration = float(track_spec.duration_sec) if track_spec.duration_sec else _natural_duration(pat)

    # bridge 振荡器合成（纯自生成，零外部采样）
    cfg = BridgeConfig(audio_format=fmt, readonly_roots=())
    render_pattern_file(pat, out_path, duration, cfg=cfg)
    return out_path
