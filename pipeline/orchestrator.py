# -*- coding: utf-8 -*-
"""
orchestrator.py —— 两阶段全链路编排（T6）

职责：
  - PipelineConfig：流水线全局配置数据类
  - run_pipeline(cfg)：串联阶段 B→C
      * 基于 manifest / 产物文件判定完成度实现断点续跑（P1-4）
      * 任意阶段失败记录异常但不破坏已产物（错误追加至 report.errors，继续后续阶段）
      * 工作区目录自动创建

纯合成定位：阶段B 由 bloodmusic.bridge 合成音源，阶段C 混音 + 分轨保留。
无外部歌曲拆分（audio_separator/demucs），无算法重分离。

设计依据：docs/design.md §2.6、§6.1、§7（决策① 独立编排工具）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from config import bootstrap_env
from source_maker import TrackSpec, make_source
from mixdown import mixdown, MixResult
from manifest import read_manifest
from core.audio_mixer import MixConfig

bootstrap_env()


@dataclass
class PipelineConfig:
    """流水线全局配置。"""

    workspace: Path                              # audio_pipeline_workspace
    mix_config: MixConfig = field(default_factory=MixConfig)   # 透传增益/归一化/削波/淡变/压缩/滤波
    separate_mode: str = "manifest"              # 写入 manifest 的分轨保留模式标识
    stages: list[str] = field(default_factory=lambda: ["B", "C"])
    track_specs: list[TrackSpec] = field(default_factory=list)  # 阶段B 规格
    mix_fmt: str = "wav"                         # 混音成品格式


def _stems_from_spec(out_dir: Path, spec: TrackSpec) -> Path:
    """按 §6.2 推断阶段B 预期产物文件名（不创建目录，用于断点续跑判定）。"""
    return out_dir / f"synth__{spec.name}.{spec.fmt}"


def _gather_stems(stems_dir: Path) -> list[Path]:
    """收集 stems 目录下已存在的音源文件。"""
    stems: list[Path] = []
    if stems_dir.is_dir():
        for ext in ("*.wav", "*.ogg", "*.flac"):
            stems.extend(stems_dir.glob(ext))
    return sorted(stems)


def run_pipeline(cfg: PipelineConfig) -> dict:
    """串联阶段 B→C，返回结构化报告。

    断点续跑（P1-4）：
      - 阶段B：按 TrackSpec 推断预期文件名，已存在则跳过单条渲染；
      - 阶段C：若 manifest.json 与 song_final 均存在，跳过混音。

    异常处理：每阶段 try/except，失败记录到 report.errors，
             不中断后续阶段（不破坏已产物）。

    Args:
        cfg: PipelineConfig。

    Returns:
        dict: {"stages": {...}, "ok": bool, "errors": [...]}
    """
    ws = Path(cfg.workspace)
    stems_dir = ws / "stems"
    mixdown_dir = ws / "mixdown"

    # 创建工作区子目录（设计 §6.1）
    for d in (stems_dir, mixdown_dir, mixdown_dir / "_sources"):
        d.mkdir(parents=True, exist_ok=True)

    report: dict = {"stages": {}, "ok": True, "errors": []}
    stems: list[Path] = []
    mix_result: MixResult | None = None

    # ═══════════════════════ 阶段 B — 单音源导出 ═══════════════════════
    if "B" in cfg.stages:
        try:
            new_count = 0
            skip_count = 0
            for spec in cfg.track_specs:
                expected = _stems_from_spec(stems_dir, spec)
                if expected.is_file():
                    # 断点续跑：单条音源已产出
                    stems.append(expected)
                    skip_count += 1
                    continue
                out = make_source(spec, stems_dir)
                stems.append(out)
                new_count += 1
            if new_count == 0 and skip_count > 0:
                report["stages"]["B"] = f"skipped ({skip_count} stems already exist)"
            else:
                report["stages"]["B"] = (
                    f"produced {new_count} new, {skip_count} existing → {len(stems)} stems"
                )
        except Exception as exc:
            report["ok"] = False
            report["errors"].append(("B", str(exc)))
            print(f"[阶段B 失败] {exc}")
    else:
        stems = _gather_stems(stems_dir)

    # ═══════════════════════ 阶段 C — 混音 + 分轨保留 ═══════════════════════
    if "C" in cfg.stages:
        try:
            manifest_path = mixdown_dir / "manifest.json"
            if manifest_path.is_file():
                mani = read_manifest(manifest_path)
                song_path = mixdown_dir / mani.song
                if song_path.is_file():
                    mix_result = MixResult(
                        song_path=song_path,
                        sources_dir=mixdown_dir / "_sources",
                        manifest_path=manifest_path,
                    )
                    report["stages"]["C"] = "skipped (manifest + song_final exist)"
                else:
                    # manifest 有但缺成品歌 → 重新混
                    mix_result = _do_mixdown(stems_dir, mixdown_dir, cfg, stems)
                    report["stages"]["C"] = f"mixed → {mix_result.song_path.name}"
            else:
                mix_result = _do_mixdown(stems_dir, mixdown_dir, cfg, stems)
                report["stages"]["C"] = f"mixed → {mix_result.song_path.name}"
        except Exception as exc:
            report["ok"] = False
            report["errors"].append(("C", str(exc)))
            print(f"[阶段C 失败] {exc}")

    return report


def _do_mixdown(
    stems_dir: Path,
    mixdown_dir: Path,
    cfg: PipelineConfig,
    stems_pre: list[Path] | None = None,
) -> MixResult:
    """混音内部实现：收集 stems → mixdown。"""
    sources = stems_pre if stems_pre else _gather_stems(stems_dir)
    if not sources:
        raise ValueError("阶段C 无可用音源（请先运行阶段B）。")
    return mixdown(
        sources, mixdown_dir, cfg.mix_config,
        fmt=cfg.mix_fmt,
        separate_mode=cfg.separate_mode,
    )
