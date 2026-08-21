# -*- coding: utf-8 -*-
"""
renderer.py —— 机生成混音主流程（镜像 musickit remix/main.py::run_remix）

流程（与采样侧同构）：
    提示词(styles.generate_prompt) → 选源(selection.select_sources)
    → 逐源合成(pools.render_source) → 曲式编排(structure，段落强度/层进出)
    → 分轨总线链(mixer_styles.apply_bus_chain) → 求和混音
    → 母带链(apply_master_chain，峰值 -1.5 dBFS) → 导出成品 + stems + manifest + report
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

from .styles import generate_prompt, get_style, list_styles
from .structure import resolve_structure, list_structures
from .selection import select_sources, SourceSpec
from .mixer_styles import resolve_style, apply_bus_chain, apply_master_chain, MIXER_STYLES
from .manifest import SourceManifestEntry, write_pool_manifest, PoolManifest, sha256_file
from .report import RemixReport
from .pools import render_source

# 角色基础电平（镜像采样侧分轨增益约定）
_ROLE_GAIN = {"drum": 0.9, "bass": 0.8, "guita": 0.65, "pad": 0.5,
              "melody": 0.6, "vocal": 0.7, "fx": 0.4}


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
        slug = style or (rng.choice(list_styles()) if style is None else style)
        prompt = generate_prompt(slug if style else None, seed=track_seed)
        if style:
            prompt = generate_prompt(style, seed=track_seed)
        track_bpm = bpm or prompt.bpm
        structure_name = structure or trng.choice(list_structures())
        sections = resolve_structure(structure_name, bars)

        # ── 2. 选源 ──
        specs = select_sources(prompt, bars, seed=track_seed)

        # ── 3. 逐源合成 + 曲式编排 ──
        total_sec = sum(s.bars for s in sections) * 4 * 60.0 / max(1, track_bpm)
        total_n = int(total_sec * SR)
        beat = 60.0 / max(1, track_bpm)
        stems_dir = out_root / f"track_{i + 1:02d}_{slug}_{_safe_stem(structure_name)}" / "stems"
        stems_dir.mkdir(parents=True, exist_ok=True)

        mixed = np.zeros(total_n, dtype=np.float64)
        stem_files: list[str] = []
        manifest_entries: list[SourceManifestEntry] = []

        bar_pos = 0
        for sec in sections:
            sec_start = bar_pos * 4 * beat
            sec_n = int(sec.bars * 4 * beat * SR)
            for spec in specs:
                # 每源按段落渲染（loop 素材天然支持任意小节数）
                seg = render_source(
                    spec, bpm=track_bpm, key=prompt.key, bars=sec.bars,
                    intensity=sec.intensity, seed=spec.seed + bar_pos,
                    volume=spec.volume,
                )
                gain = _section_gain(sec.intensity, spec.role, sec.skeleton_only)
                if gain <= 0.0:
                    continue
                g = gain * _ROLE_GAIN.get(spec.role, 0.5)
                i0 = int(sec_start * SR)
                end = min(i0 + len(seg), total_n)
                mixed[i0:end] += seg[:end - i0] * g
            bar_pos += sec.bars

        # ── 4. 分轨导出（整曲重渲染一遍，便于 stems/ 留档） ──
        #     （骨架+点缀全层、强度 0.8，作为"源分轨"保留）
        mstyle = resolve_style(mixer_style)  # 整曲一位混音师（random 时按种子复现）
        for spec in specs:
            seg_full = render_source(spec, bpm=track_bpm, key=prompt.key, bars=sum(s.bars for s in sections),
                                     intensity=0.8, seed=spec.seed, volume=spec.volume)
            # 总线链
            seg_full = apply_bus_chain(seg_full, spec.role, mstyle)
            name = _safe_stem(f"{spec.pool}__{spec.name}")
            stem_path = stems_dir / f"{name}.wav"
            export_audio(seg_full, str(stem_path), format="wav")
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

        # ── 5. 母带 ──
        mixed = apply_master_chain(mixed, mstyle)

        # ── 6. 导出成品 ──
        track_dir = stems_dir.parent
        song_name = f"song_final.{fmt}"
        song_path = track_dir / song_name
        export_audio(mixed, str(song_path), format=fmt)

        # ── 7. manifest + report ──
        pool_manifest = PoolManifest(
            pool=slug,
            generated=datetime.now().isoformat(timespec="seconds"),
            entries=manifest_entries,
        )
        write_pool_manifest(track_dir / "manifest.json", pool_manifest)

        report = RemixReport(
            title=f"{slug} · {track_seed}",
            prompt=prompt.as_dict(),
            seed=track_seed,
            bpm=track_bpm,
            bars=sum(s.bars for s in sections),
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
