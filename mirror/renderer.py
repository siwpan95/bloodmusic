# -*- coding: utf-8 -*-
"""
renderer.py —— 机生成混音主流程（镜像 musickit remix/main.py::run_remix）

流程（与采样侧同构）：
    提示词(styles.generate_prompt) → 选源(selection.select_sources)
    → 逐源合成(pools.render_source，全长一次渲染) → 曲式编排
    （structure 分段增益曲线：段落强度/层进出，段界 1024 点平滑防咔哒）
    → 分轨总线链(mixer_styles.apply_bus_chain) → 求和混音
    → 母带链(apply_master_chain，峰值 -1.5 dBFS) → 导出成品 + stems + manifest + report

render_full_tracks() 为共用核心：固定 stems（源分轨 + 总线链），
供 run_remix 与 mirror/album.py（固定风格专辑镜像）复用。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.export.batch import export_audio

from .styles import generate_prompt, list_styles
from .structure import resolve_structure, list_structures
from .selection import select_sources, SourceSpec
from .mixer_styles import resolve_style, apply_bus_chain, apply_master_chain, MixerStyle
from .manifest import SourceManifestEntry, write_pool_manifest, PoolManifest, sha256_file
from .report import RemixReport
from .pools import render_source

# 角色基础电平（镜像采样侧分轨增益约定）
_ROLE_GAIN = {"drum": 0.9, "bass": 0.8, "guita": 0.65, "pad": 0.5,
              "melody": 0.6, "vocal": 0.7, "fx": 0.4}

# 段界平滑宽度（样本），避免分段增益切换产生咔哒
_RAMP = 1024


@dataclass
class RemixResult:
    song_path: Path | None = None
    stems: list = field(default_factory=list)
    report_path: Path | None = None
    report: RemixReport | None = None
    elapsed_sec: float = 0.0


def _section_gain(section_intensity: float, role: str, skeleton_only: bool) -> float:
    """段落 → 分轨增益：骨架层恒开，点缀层仅在强度≥0.5 时开。"""
    if role in ("drum", "bass", "guita"):
        return section_intensity
    if skeleton_only or section_intensity < 0.5:
        return 0.0
    return section_intensity


def _safe_stem(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "_-") else "_" for c in name).strip("_") or "stem"


def render_full_tracks(
    prompt,
    bars: int,
    bpm: int,
    mixer_style_slug: str | None,
    seed: int,
    bus: bool = True,
) -> tuple[list[SourceSpec], list[np.ndarray], MixerStyle]:
    """渲染固定 stems：按提示词选源 → 全长合成 → （可选）逐源总线链。

    Args:
        prompt: styles.Prompt。
        bars: 全长小节数。
        bpm: 速度。
        mixer_style_slug: 混音师 slug（random 时按种子复现）。
        seed: 选源/合成种子（同 seed 得同 stems，可复现）。
        bus: True=应用总线链（run_remix 用）；False=原始干声
             （album 镜像用：同一干声 stems 供 24 位混音师各自着色）。

    Returns:
        (specs, tracks, style)：源规格、全长分轨、混音师签名。
    """
    specs = select_sources(prompt, bars, seed=seed)
    mstyle = resolve_style(mixer_style_slug)

    tracks: list[np.ndarray] = []
    for spec in specs:
        seg = render_source(
            spec, bpm=bpm, key=prompt.key, bars=bars,
            intensity=0.8, seed=spec.seed, volume=spec.volume,
        )
        tracks.append(apply_bus_chain(seg, spec.role, mstyle) if bus else seg)
    return specs, tracks, mstyle


def _arrangement_curve(
    spec: SourceSpec,
    sections,
    bpm: int,
    total_n: int,
) -> np.ndarray:
    """构建某源的全长增益曲线：段落强度 × 层进出，段界平滑。"""
    beat = 60.0 / max(1, bpm)
    curve = np.zeros(total_n, dtype=np.float64)
    bar_pos = 0
    for sec in sections:
        g = _section_gain(sec.intensity, spec.role, sec.skeleton_only)
        if g > 0.0:
            g *= _ROLE_GAIN.get(spec.role, 0.5)
            i0 = int(bar_pos * 4 * beat * SR)
            i1 = int((bar_pos + sec.bars) * 4 * beat * SR)
            i0 = max(0, min(i0, total_n))
            i1 = max(i0, min(i1, total_n))
            curve[i0:i1] = g
        bar_pos += sec.bars
    if np.any(curve):
        kernel = np.ones(_RAMP, dtype=np.float64) / _RAMP
        curve = np.convolve(curve, kernel, mode="same")
    return curve


def run_remix(
    count: int = 1,
    seed: int | None = None,
    bars: int = 16,
    bpm: int | None = None,
    structure: str | None = None,
    style: str | None = None,
    mixer_style: str | None = None,
    out_dir: str | Path = "mirror_output",
    fmt: str = "wav",
    release_safe: bool = True,
) -> list[RemixResult]:
    """镜像 --remix 主入口：生成 N 首纯机生成混音。

    Args:
        count: 曲目数。
        seed: 基础种子（None=随机）；第 i 首用 seed+i，可复现。
        bars: 每曲小节数。
        bpm: 速度（None=由风格决定）。
        structure: 曲式模板名（None=随机）。
        style: 风格 slug（None=随机）。
        mixer_style: 混音师 slug（None=随机一位）。
        out_dir: 输出目录。
        fmt: wav/ogg/flac。
        release_safe: 镜像开关（机生成恒安全，保留语义）。

    Returns:
        RemixResult 列表。
    """
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    results: list[RemixResult] = []

    base_seed = seed if seed is not None else random.randint(0, 999_999)
    rng = random.Random(base_seed)

    for i in range(count):
        t0 = time.time()
        track_seed = base_seed + i
        trng = random.Random(track_seed)

        # ── 1. 提示词 ──
        prompt = generate_prompt(style, seed=track_seed)
        track_bpm = bpm or prompt.bpm
        structure_name = structure or trng.choice(list_structures())
        sections = resolve_structure(structure_name, bars)
        total_bars = sum(s.bars for s in sections)
        total_sec = total_bars * 4 * 60.0 / max(1, track_bpm)
        total_n = int(total_sec * SR)

        # ── 2+3. 选源 + 全长合成（单遍渲染，含总线链）──
        specs, tracks, mstyle = render_full_tracks(
            prompt, total_bars, track_bpm, mixer_style, track_seed,
        )

        # ── 4. 曲式编排：分段增益曲线加权求和 ──
        mixed = np.zeros(total_n, dtype=np.float64)
        for spec, tr in zip(specs, tracks):
            curve = _arrangement_curve(spec, sections, track_bpm, total_n)
            n = min(len(tr), total_n)
            mixed[:n] += tr[:n] * curve[:n]

        # ── 5. 母带 ──
        mixed = apply_master_chain(mixed, mstyle)

        # ── 6. 导出成品 + 分轨 + manifest + report ──
        track_dir = out_root / f"track_{i + 1:02d}_{prompt.style}_{_safe_stem(structure_name)}"
        stems_dir = track_dir / "stems"
        stems_dir.mkdir(parents=True, exist_ok=True)
        song_name = f"song_final.{fmt}"
        song_path = track_dir / song_name
        export_audio(mixed, str(song_path), format=fmt)

        stem_files: list[str] = []
        manifest_entries: list[SourceManifestEntry] = []
        for spec, tr in zip(specs, tracks):
            name = _safe_stem(f"{spec.pool}__{spec.name}")
            stem_path = stems_dir / f"{name}.wav"
            export_audio(tr, str(stem_path), format="wav")
            stem_files.append(stem_path.name)
            manifest_entries.append(SourceManifestEntry(
                file=f"stems/{stem_path.name}",
                subcategory=spec.subcategory,
                content_kind=spec.kind,
                duration_s=round(total_sec, 3),
                sha256=sha256_file(stem_path),
                synth_engine=spec.engine,
                synth_preset=spec.preset,
                bpm=track_bpm,
                key=prompt.key,
                role=spec.role,
                seed=spec.seed,
            ))

        write_pool_manifest(track_dir / "manifest.json", PoolManifest(
            pool=prompt.style,
            generated=datetime.now().isoformat(timespec="seconds"),
            entries=manifest_entries,
        ))

        report = RemixReport(
            title=f"{prompt.style} · {track_seed}",
            prompt=prompt.as_dict(),
            seed=track_seed,
            bpm=track_bpm,
            bars=total_bars,
            structure=structure_name,
            mixer_style=mstyle.slug,
            release_safe=bool(release_safe),
            license_tier="selfgen",
            sources=[s.as_dict() for s in specs],
            stems=stem_files,
            song=song_name,
            duration_sec=round(total_sec, 3),
            out_dir=str(track_dir),
        )
        report_path = report.to_json(track_dir / "report.json")

        results.append(RemixResult(
            song_path=song_path,
            stems=[stems_dir / f for f in stem_files],
            report_path=report_path,
            report=report,
            elapsed_sec=round(time.time() - t0, 2),
        ))

    return results
