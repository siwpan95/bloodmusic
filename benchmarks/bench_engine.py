#!/usr/bin/env python3
"""RealtimeMusicEngine 实时性能基准。

测量 process_frame() 在不同层密度 × buffer_size 下的单帧耗时，
对照 60fps 预算 (16.6ms/帧)，给出实时可行的配置建议。

用法:
    python benchmarks/bench_engine.py
输出:
    benchmarks/report.md — 表格 + 结论
"""

from __future__ import annotations

import copy
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from bloodmusic.interactive.engine import (
    RealtimeMusicEngine, EngineConfig, DEFAULT_LAYER_TEMPLATES,
)
from bloodmusic.interactive.state_machine import MusicState

#: 60fps 单帧预算 (ms)
FRAME_BUDGET_MS = 16.6

BUFFER_SIZES = [128, 256, 512]
LAYER_COUNTS = [2, 4, 6, 8]
WARMUP_FRAMES = 10
MEASURE_FRAMES = 200

_GAME_STATE = {"hp_ratio": 0.8, "enemy_count": 2, "intensity": 0.4}


def _engine_with_n_layers(n_layers: int, buffer_size: int) -> RealtimeMusicEngine:
    """构建带 n 层模板的引擎。"""
    engine = RealtimeMusicEngine(EngineConfig(
        sample_rate=44100, buffer_size=buffer_size, master_volume=0.7,
    ))
    names = list(DEFAULT_LAYER_TEMPLATES)
    templates = {}
    for i in range(min(n_layers, len(names))):
        layer = copy.deepcopy(DEFAULT_LAYER_TEMPLATES[names[i]])
        layer.name = f"layer_{i}"
        templates[layer.name] = layer
    # 层数超过默认模板时复制最后一层补齐
    while len(templates) < n_layers:
        layer = copy.deepcopy(DEFAULT_LAYER_TEMPLATES[names[-1]])
        layer.name = f"layer_{len(templates)}"
        templates[layer.name] = layer
    engine.setup_layers_from_templates(templates)
    engine.start(MusicState.EXPLORE)
    return engine


def _measure(engine: RealtimeMusicEngine, n_frames: int) -> list[float]:
    """返回每帧耗时 (ms)。"""
    times = []
    for _ in range(n_frames):
        engine.update(_GAME_STATE, dt=0.016)
        t0 = time.perf_counter()
        engine.process_frame()
        times.append((time.perf_counter() - t0) * 1000.0)
    return times


def _row(label: str, times: list[float]) -> dict:
    return {
        "label": label,
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95) - 1],
        "worst_ms": max(times),
    }


def main() -> int:
    results = []
    for buffer_size in BUFFER_SIZES:
        for n_layers in LAYER_COUNTS:
            engine = _engine_with_n_layers(n_layers, buffer_size)
            _measure(engine, WARMUP_FRAMES)  # 预热
            times = _measure(engine, MEASURE_FRAMES)
            results.append(_row(
                f"{n_layers} 层 / buffer {buffer_size}", times,
            ))

    # ── 报告 ──
    lines = [
        "# RealtimeMusicEngine 性能基准",
        "",
        f"- 环境: Python {sys.version.split()[0]} / numpy {np.__version__}",
        f"- 测量: {MEASURE_FRAMES} 帧/配置（预热 {WARMUP_FRAMES} 帧）",
        f"- 60fps 单帧预算: **{FRAME_BUDGET_MS} ms**",
        "",
        "| 配置 | 均值 | 中位数 | P95 | 最坏 | 60fps 可行 |",
        "|------|------|--------|-----|------|-----------|",
    ]
    for r in results:
        ok = r["p95_ms"] <= FRAME_BUDGET_MS
        lines.append(
            f"| {r['label']} | {r['mean_ms']:.2f} ms | {r['median_ms']:.2f} ms "
            f"| {r['p95_ms']:.2f} ms | {r['worst_ms']:.2f} ms "
            f"| {'**是**' if ok else '否'} |"
        )

    feasible = [r for r in results if r["p95_ms"] <= FRAME_BUDGET_MS]
    lines += [
        "",
        "## 结论",
        "",
    ]
    if feasible:
        best = max(feasible, key=lambda r: int(r["label"].split()[0]))
        lines.append(
            f"- 实时可行（P95 ≤ {FRAME_BUDGET_MS} ms）的配置共 {len(feasible)} 个，"
            f"最大可行层密度: **{best['label']}**"
            f"（P95 {best['p95_ms']:.2f} ms）"
        )
        lines.append(
            "- 建议: 游戏实时使用时优先选择可行配置中 buffer 较小者，"
            "兼顾延迟与算力余量；超出上限的密度应改为预渲染/离线模式"
        )
    else:
        lines.append("- **无配置满足 60fps 实时预算** — 当前实现仅适合离线生成，"
                     "实时使用需优化 _synthesize_layer 或降层密度")
    lines.append("")
    lines.append(
        "> 注: 单次 process_frame 不含音频设备 I/O 延迟；"
        "实际游戏集成需额外预留 sounddevice/游戏引擎缓冲时间。"
    )
    lines.append("")

    report = Path(__file__).resolve().parent / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    # 控制台输出
    print("\n".join(lines))
    print(f"\n报告已写入: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
