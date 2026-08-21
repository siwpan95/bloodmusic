# -*- coding: utf-8 -*-
"""
cli.py —— 纯音乐制作流水线 CLI 入口（T6）

子命令：
  doctor   环境诊断（依赖隔离 / remix-bloodmusic 可用性 / ffmpeg）
  run      运行完整流水线 B→C（合成 → 混音 + 分轨保留）
  stage-b  仅阶段B：单音源导出
  stage-c  仅阶段C：混音 + 分轨保留

全局开关：--separate-mode manifest（分轨保留模式标识，默认 manifest）。
纯合成定位：无外部歌曲拆分（stage-a）与算法重分离（stage-d）。

设计依据：docs/design.md §2.6（PipelineConfig / run_pipeline）、§5（CLI 交互要点）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 扁平米模块导入：把 cli.py 自身所在目录插入 sys.path 首位
_PROJ_ROOT = Path(__file__).resolve().parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))

from config import (
    bootstrap_env,
    HONESTY_DISCLAIMER,
    REMIX_BIN,
)
from orchestrator import PipelineConfig, run_pipeline
from source_maker import TrackSpec

bootstrap_env()


# ──────────────────────────── 辅助 ────────────────────────────


def _parse_track_specs(specs_file: str | None, demo: bool) -> list[TrackSpec]:
    """从 JSON 文件或 --demo 生成 TrackSpec 列表。"""
    if demo:
        return [
            TrackSpec(name="bass_line", kind="synth", bpm=120, duration_sec=4.0),
            TrackSpec(name="pad_chord", kind="synth", bpm=120, duration_sec=4.0),
            TrackSpec(name="lead_arp", kind="synth", bpm=120, duration_sec=4.0),
        ]
    if specs_file:
        with open(specs_file, encoding="utf-8") as f:
            raw = json.load(f)
        specs: list[TrackSpec] = []
        for item in raw:
            if "pattern_source" in item and item["pattern_source"]:
                item["pattern_source"] = Path(item["pattern_source"])
            specs.append(TrackSpec(**item))
        return specs
    return []


def _parse_stages(raw: str) -> list[str]:
    """解析 --stages 参数（如 'B,C' → ['B','C']）。"""
    parts = [s.strip().upper() for s in raw.split(",") if s.strip()]
    valid = {"B", "C"}
    result = [p for p in parts if p in valid]
    return result if result else ["B", "C"]


# ──────────────────────────── 命令实现 ────────────────────────────


def cmd_doctor(_args: argparse.Namespace) -> None:
    """环境诊断：打印各依赖状态。"""
    print("═══ audio_pipeline 环境诊断 ═══")
    print(f"解释器: {sys.executable}")
    print()

    # R1: torch 不在编排进程
    torch_loaded = "torch" in sys.modules
    print(f"[{'✓' if not torch_loaded else '✗'}] torch 在编排进程: {torch_loaded}")
    if torch_loaded:
        print("  ⚠ 违反 R1 依赖隔离！torch 不应在编排层出现。")
    print()

    # remix / bloodmusic
    try:
        from core.audio_mixer import AudioMixer  # noqa: F401
        from core.audio_loader import AudioLoader  # noqa: F401
        print("[✓] remix.core (AudioMixer / AudioLoader) 可导入")
    except Exception as exc:
        print(f"[✗] remix 导入失败: {exc}")
    try:
        import bloodmusic.bridge  # noqa: F401
        print("[✓] bloodmusic.bridge 可导入")
    except Exception as exc:
        print(f"[✗] bloodmusic 导入失败: {exc}")
    print()

    # pydub / ffmpeg pin
    try:
        from pydub import AudioSegment
        conv = AudioSegment.converter
        probe = AudioSegment.ffprobe
        print(f"[✓] pydub converter: {conv}")
        print(f"[✓] pydub ffprobe  : {probe}")
        ffmpeg_ok = conv and Path(conv).is_file()
        print(f"[{'✓' if ffmpeg_ok else '✗'}] ffmpeg.exe 存在: {ffmpeg_ok}")
    except Exception as exc:
        print(f"[✗] pydub 初始化失败: {exc}")
    print()

    # 诚实性声明
    print("─── 诚实性声明 ───")
    print(HONESTY_DISCLAIMER)
    print()


def cmd_run(args: argparse.Namespace) -> None:
    """运行完整流水线 B→C。"""
    stages = _parse_stages(args.stages)
    cfg = PipelineConfig(
        workspace=Path(args.workspace),
        separate_mode=args.separate_mode,
        stages=stages,
        track_specs=_parse_track_specs(args.track_specs, args.demo),
        mix_fmt=args.mix_fmt,
    )
    print(f"启动流水线（{', '.join(stages)}），分轨保留模式: {cfg.separate_mode}")
    print(f"工作区: {cfg.workspace}")
    report = run_pipeline(cfg)
    print()
    print("═══ 流水线报告 ═══")
    for stage, status in report["stages"].items():
        print(f"  阶段 {stage}: {status}")
    if report["errors"]:
        print(f"  错误 ({len(report['errors'])}):")
        for s, msg in report["errors"]:
            print(f"    [{s}] {msg[:120]}")
    print(f"  整体 {'✓ OK' if report['ok'] else '✗ 有错误'}")
    if not report["ok"]:
        sys.exit(1)


def cmd_stage_b(args: argparse.Namespace) -> None:
    """仅阶段B。"""
    from source_maker import make_source
    ws = Path(args.workspace)
    stems_dir = ws / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    specs = _parse_track_specs(args.track_specs, args.demo)
    if not specs:
        print("[阶段B] 无 TrackSpec（请使用 --demo 或 --track-specs）。", file=sys.stderr)
        sys.exit(1)
    for spec in specs:
        out = make_source(spec, stems_dir)
        print(f"  → {out}")
    print(f"阶段B 完成：{len(specs)} 条音源。")


def cmd_stage_c(args: argparse.Namespace) -> None:
    """仅阶段C。"""
    ws = Path(args.workspace)
    stems_dir = ws / "stems"
    mixdown_dir = ws / "mixdown"
    sources = sorted(
        [p for ext in ("*.wav", "*.ogg", "*.flac") for p in stems_dir.glob(ext)]
    )
    if not sources:
        print("[阶段C] 无可用音源（请先运行阶段B）。", file=sys.stderr)
        sys.exit(1)
    from mixdown import mixdown
    from core.audio_mixer import MixConfig
    result = mixdown(
        sources, mixdown_dir, MixConfig(),
        fmt=args.mix_fmt,
        separate_mode=args.separate_mode,
    )
    print(f"阶段C 完成 → {result.song_path}")
    print(f"  _sources: {result.sources_dir}")
    print(f"  manifest: {result.manifest_path}")


# ──────────────────────────── 主入口 ────────────────────────────


def main(argv: list[str] | None = None) -> None:
    """CLI 主入口（可传 argv 用于测试注入）。"""
    parser = argparse.ArgumentParser(
        prog="audio_pipeline",
        description="纯音乐制作流水线编排工具 —— 串联合成·混音两阶段（零外部采样）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    sub.add_parser("doctor", help="环境诊断（依赖隔离 / 外部工具可用性）")

    # run
    p_run = sub.add_parser("run", help="运行完整流水线 B→C")
    p_run.add_argument("--workspace", required=True, help="工作区根目录")
    p_run.add_argument(
        "--separate-mode", choices=("manifest",), default="manifest",
        help="分轨保留模式（manifest=复用原始分轨，100% 保真）",
    )
    p_run.add_argument(
        "--stages", default="B,C",
        help="要运行的阶段（逗号分隔，如 B,C；默认全部）",
    )
    p_run.add_argument("--track-specs", default=None, help="阶段B TrackSpec JSON 文件")
    p_run.add_argument("--mix-fmt", default="wav", choices=("wav", "ogg", "flac"), help="混音格式")
    p_run.add_argument(
        "--demo", action="store_true",
        help="使用内置演示 TrackSpec（3 条 synth 分轨，4 秒）",
    )

    # stage-b
    p_b = sub.add_parser("stage-b", help="仅阶段B：单音源导出")
    p_b.add_argument("--workspace", required=True)
    p_b.add_argument("--track-specs", default=None)
    p_b.add_argument("--demo", action="store_true")

    # stage-c
    p_c = sub.add_parser("stage-c", help="仅阶段C：混音 + 分轨保留")
    p_c.add_argument("--workspace", required=True)
    p_c.add_argument("--mix-fmt", default="wav", choices=("wav", "ogg", "flac"))
    p_c.add_argument(
        "--separate-mode", choices=("manifest",), default="manifest",
        help="写入 manifest 的分轨保留模式标识（默认 manifest）",
    )

    args = parser.parse_args(argv)

    if args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "stage-b":
        cmd_stage_b(args)
    elif args.command == "stage-c":
        cmd_stage_c(args)


if __name__ == "__main__":
    main()
