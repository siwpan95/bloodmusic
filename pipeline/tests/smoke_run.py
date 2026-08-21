#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_run.py —— 独立冒烟测试（无需 pytest，用合成小样本跑两阶段 B→C）。

用法：
    python pipeline/tests/smoke_run.py

流程：
    1) 在临时目录建工作区
    2) run_pipeline(B→C) 全链路（纯合成音源）
    3) 逐项断言产物存在 / manifest 完整 / _sources 保留
    4) 打印摘要，exit 0（成功）或 1（失败）

零外部采样 / 零联网 / 不依赖 demucs。
"""

from __future__ import annotations

import math
import shutil
import struct
import sys
import tempfile
import wave
from pathlib import Path

# 确保项目根在 sys.path
_HERE = Path(__file__).resolve().parent
_PROJ_ROOT = _HERE.parent
sys.path.insert(0, str(_PROJ_ROOT))

from config import bootstrap_env
bootstrap_env()

from config import HONESTY_DISCLAIMER
from source_maker import TrackSpec
from orchestrator import PipelineConfig, run_pipeline
from manifest import read_manifest, sha256_file


def main() -> int:
    """冒烟测试主入口，返回 0（成功）或 1（失败）。"""
    ws_parent = Path(tempfile.mkdtemp(prefix="smoke_audio_pipeline_"))
    ws = ws_parent / "workspace"
    ws.mkdir(parents=True)

    try:
        # ── 0. 基础检查 ──
        print("═══ audio_pipeline 冒烟测试 ═══")
        print(HONESTY_DISCLAIMER)
        print()

        assert "torch" not in sys.modules, "R1 违反：torch 在编排进程！"
        print("[✓] R1 依赖隔离：torch ∉ sys.modules")

        # ── 1. B→C ──
        cfg = PipelineConfig(
            workspace=ws,
            stages=["B", "C"],
            separate_mode="manifest",
            track_specs=[
                TrackSpec(name="bass", kind="synth", bpm=120, duration_sec=2.0, fmt="wav"),
                TrackSpec(name="pad", kind="synth", bpm=120, duration_sec=2.0, fmt="wav"),
            ],
            mix_fmt="wav",
        )
        print(f"启动流水线 B→C，工作区: {ws}")
        report = run_pipeline(cfg)

        assert report["ok"], f"流水线失败: {report['errors']}"
        print(f"  B: {report['stages'].get('B', '-')}")
        print(f"  C: {report['stages'].get('C', '-')}")

        # ── 2. 产物校验 ──
        stems_dir = ws / "stems"
        stems = sorted(stems_dir.glob("*.wav"))
        assert len(stems) == 2, f"阶段B 应为 2 条 stems，实际 {len(stems)}"
        print(f"[✓] 阶段B：{len(stems)} 条 stems")

        song = ws / "mixdown" / "song_final.wav"
        assert song.is_file(), "阶段C 缺 song_final.wav"
        print(f"[✓] 阶段C：{song.name}")

        manifest_path = ws / "mixdown" / "manifest.json"
        assert manifest_path.is_file()
        mani = read_manifest(manifest_path)
        assert len(mani.sources) == 2
        print(f"[✓] manifest：{len(mani.sources)} 条 source")

        sources_dir = ws / "mixdown" / "_sources"
        for e in mani.sources:
            orig = sources_dir / e.output_name
            assert orig.is_file(), f"_sources 缺 {e.output_name}"
            h = sha256_file(orig)
            assert h == e.sha256, f"sha256 不一致：{e.output_name}"
        print("[✓] _sources 保留：逐字节 sha256 与 manifest 一致（100% 保真）")

        # ── 3. 断点续跑 ──
        report2 = run_pipeline(cfg)
        assert report2["ok"]
        for stage in ("B", "C"):
            status = report2["stages"].get(stage, "")
            assert "skip" in status.lower() or "already" in status.lower(), (
                f"断点续跑失败：阶段 {stage} 未跳过 — '{status}'"
            )
        print("[✓] 断点续跑：全部阶段正确跳过")

        print()
        print("═══ 冒烟测试通过 ✓ ═══")
        return 0

    except Exception as exc:
        print(f"\n✗ 冒烟测试失败: {exc}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 清理临时目录
        shutil.rmtree(ws_parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
