# -*- coding: utf-8 -*-
"""
album.py —— 固定风格专辑镜像（镜像 musickit burbidge_album/build_album.py）

采样侧：同一 stems × 24 位混音师签名链 → album/<slug>/<同曲名>.wav + 索引。
机生成侧：同一「干声」生成 stems（render_full_tracks(bus=False)，种子固定可复现）
         × 24 位混音师（mirror/mixer_styles.py）各自总线着色 + 母带 → 同结构输出。

用法:
    python -m bloodmusic.mirror.album --style phonk --seed 42 --bars 16
    python -m bloodmusic.mirror.album --styles wallace,ghenea,mikedean --out mirror_album
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.export.batch import export_audio

from .styles import generate_prompt, list_styles
from .selection import SourceSpec
from .mixer_styles import (
    MIXER_STYLES,
    resolve_style,
    apply_bus_chain,
    apply_master_chain,
    list_mixers,
)
from .renderer import render_full_tracks, _ROLE_GAIN


@dataclass
class AlbumResult:
    out_dir: Path
    prompt: dict
    stems: list = field(default_factory=list)      # SourceSpec.as_dict()
    mixer_styles: list = field(default_factory=list)
    tracks: list = field(default_factory=list)     # [{mixer, song_path}]
    album_manifest_path: Path | None = None


def build_album(
    out_dir: str | Path = "mirror_album",
    style: str | None = None,
    seed: int = 42,
    bars: int = 16,
    bpm: int | None = None,
    mixer_slugs: list[str] | None = None,
    fmt: str = "wav",
) -> AlbumResult:
    """固定 stems × N 位混音师生成专辑。

    Args:
        out_dir: 输出根目录。
        style: 风格 slug（None=随机，但 seed 固定保证可复现）。
        seed: 固定种子（同一 stems 跨混音师、跨运行一致）。
        bars: 小节数。
        bpm: 速度（None=由风格决定）。
        mixer_slugs: 混音师列表（None=全部 24 位）。
        fmt: wav/ogg/flac。

    Returns:
        AlbumResult。
    """
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    prompt = generate_prompt(style, seed=seed)
    track_bpm = bpm or prompt.bpm
    slugs = list(mixer_slugs) if mixer_slugs else list_mixers()
    for s in slugs:
        if s not in MIXER_STYLES:
            raise KeyError(f"未知混音师 '{s}'。可用: {list_mixers()}")

    # ── 1. 固定干声 stems（一次渲染，全专辑共用）──
    specs, raw_tracks, _ = render_full_tracks(
        prompt, bars, track_bpm, None, seed, bus=False,
    )

    # ── 2. 每混音师：总线着色 → 求和 → 母带 → 落盘 ──
    song_name = f"01_{prompt.style}.{fmt}"
    tracks_out: list[dict] = []
    for slug in slugs:
        mstyle = resolve_style(slug)
        bussed = [apply_bus_chain(tr, sp.role, mstyle) for sp, tr in zip(specs, raw_tracks)]
        total_n = min(len(t) for t in bussed)
        mixed = np.zeros(total_n, dtype=np.float64)
        for sp, tr in zip(specs, bussed):
            g = _ROLE_GAIN.get(sp.role, 0.5)
            mixed += tr[:total_n] * g
        mixed = apply_master_chain(mixed, mstyle)

        track_dir = root / slug
        track_dir.mkdir(parents=True, exist_ok=True)
        song_path = track_dir / song_name
        export_audio(mixed, str(song_path), format=fmt)
        tracks_out.append({"mixer": slug, "song": song_name, "path": str(song_path)})
        print(f"  [{slug}] → {song_path}")

    # ── 3. 专辑清单 + 索引页 ──
    manifest = {
        "title": f"{prompt.style} × {len(slugs)} 混音师",
        "prompt": prompt.as_dict(),
        "bpm": track_bpm,
        "bars": bars,
        "seed": seed,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "license_tier": "selfgen",
        "stems": [s.as_dict() for s in specs],
        "mixer_styles": slugs,
        "tracks": tracks_out,
    }
    import json
    manifest_path = root / "album_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "".join(
        f"<tr><td>{t['mixer']}</td>"
        f"<td><a href='{t['mixer']}/{t['song']}'>{t['song']}</a></td></tr>"
        for t in tracks_out
    )
    (root / "index.html").write_text(
        "<html><head><meta charset='utf-8'><title>mirror album</title></head><body>"
        f"<h1>{prompt.style} × {len(slugs)} 混音师（机生成镜像）</h1>"
        f"<p>固定 stems（seed={seed}, {bars} 小节, {track_bpm}BPM）经 {len(slugs)} 位签名链混音</p>"
        f"<table border='1' cellpadding='6'>{rows}</table></body></html>",
        encoding="utf-8",
    )

    return AlbumResult(
        out_dir=root,
        prompt=prompt.as_dict(),
        stems=[s.as_dict() for s in specs],
        mixer_styles=slugs,
        tracks=tracks_out,
        album_manifest_path=manifest_path,
    )


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="bloodmusic-mirror-album",
        description="固定风格专辑镜像：同一生成 stems × 24 混音师签名链（镜像 burbidge_album）",
    )
    p.add_argument("--style", help=f"风格 slug（默认随机，seed 固定可复现；可用: {list_styles()}）")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--bars", type=int, default=16)
    p.add_argument("--bpm", type=int, default=None)
    p.add_argument("--styles", dest="mixers", default=None,
                   help="混音师列表：all 或逗号分隔 slug（默认 all=24 位）")
    p.add_argument("--out", default="mirror_album")
    p.add_argument("--format", default="wav", choices=("wav", "ogg", "flac"))
    args = p.parse_args(argv)

    slugs = None
    if args.mixers and args.mixers != "all":
        slugs = [s.strip() for s in args.mixers.split(",") if s.strip()]

    result = build_album(
        out_dir=args.out, style=args.style, seed=args.seed, bars=args.bars,
        bpm=args.bpm, mixer_slugs=slugs, fmt=args.format,
    )
    print(f"\n专辑完成: {result.out_dir}")
    print(f"  {len(result.tracks)} 位混音师 × 1 首固定 stems 曲目")
    print(f"  清单: {result.album_manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
