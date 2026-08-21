# -*- coding: utf-8 -*-
"""
cli.py —— 机生成混音 CLI（镜像 musickit remix/main.py 参数）

用法（与采样侧同名参数）：
    python -m bloodmusic.mirror --remix --count 1 --bars 16 --bpm 140 --seed 42
    python -m bloodmusic.mirror --remix --structure classic_drop --mixer-style wallace
    python -m bloodmusic.mirror --list-styles
    python -m bloodmusic.mirror --list-mixers
"""

from __future__ import annotations

import argparse
import sys

from .renderer import run_remix
from .styles import list_styles
from .structure import list_structures
from .mixer_styles import list_mixers


def _cmd_remix(args: argparse.Namespace) -> int:
    results = run_remix(
        count=args.count,
        seed=args.seed,
        bars=args.bars,
        bpm=args.bpm,
        structure=args.structure,
        style=args.style,
        mixer_style=args.mixer_style,
        out_dir=args.out,
        fmt=args.format,
        release_safe=args.release_safe,
    )
    print(f"═══ 机生成混音完成（{len(results)} 曲，license_tier=selfgen）═══")
    for r in results:
        rep = r.report
        print(f"  {rep.title}  style={rep.prompt['style']}  bpm={rep.bpm}  "
              f"bars={rep.bars}  mixer={rep.mixer_style}  dur={rep.duration_sec}s  "
              f"elapsed={r.elapsed_sec}s")
        print(f"    → {r.song_path}")
        print(f"    stems: {len(r.stems)}   report: {r.report_path}")
    return 0


def _cmd_build_pools(args: argparse.Namespace) -> int:
    """生成 13 池索引（镜像采样侧 manifest 构建；生成物清单，不落音频文件）。"""
    import json
    from .pools import list_pool_instruments
    from .taxonomy import as_dict
    out = {
        "taxonomy": as_dict(),
        "pools": list_pool_instruments(),
        "license_tier": "selfgen",
        "note": "机生成声池：素材由合成引擎实时渲染（无采样文件），池清单即生成乐器注册表",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"池索引已写入: {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bloodmusic-mirror",
        description="bloodmusic 镜像层 —— 纯机生成混音（musickit 纯采样混音的镜像）",
    )

    # 镜像 musickit remix/main.py 的开关
    parser.add_argument("--remix", action="store_true", help="生成机生成混音曲目")
    parser.add_argument("--count", type=int, default=1, help="曲目数（默认 1）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（默认随机）")
    parser.add_argument("--bars", type=int, default=16, help="每曲小节数（默认 16）")
    parser.add_argument("--bpm", type=int, default=None, help="BPM（默认由风格决定）")
    parser.add_argument("--structure", type=str, default=None, help=f"曲式模板: {list_structures()}")
    parser.add_argument("--style", type=str, default=None, help="风格 slug（默认随机）")
    parser.add_argument("--out", type=str, default="mirror_output", help="输出目录")
    parser.add_argument("--format", type=str, default="wav", choices=("wav", "ogg", "flac"),
                        help="输出格式（默认 wav）")
    parser.add_argument("--release-safe", action="store_true",
                        help="发布安全模式（机生成恒 selfgen，保留镜像语义）")
    parser.add_argument("--mixer-style", type=str, default=None,
                        help=f"混音师 slug（{'/'.join(list_mixers())} | random）")
    parser.add_argument("--list-styles", action="store_true", help="列出 65 风格")
    parser.add_argument("--list-mixers", action="store_true", help="列出 24 混音师")
    parser.add_argument("--list-structures", action="store_true", help="列出曲式模板")
    parser.add_argument("--build-pools", action="store_true", help="生成 13 池索引 JSON（--out 指定路径）")

    args = parser.parse_args(argv)

    if args.list_styles:
        print("风格（" + str(len(list_styles())) + "）: " + ", ".join(list_styles()))
        return 0
    if args.list_mixers:
        print("混音师（" + str(len(list_mixers())) + "）: " + ", ".join(list_mixers()))
        return 0
    if args.list_structures:
        print("曲式模板: " + ", ".join(list_structures()))
        return 0
    if args.build_pools:
        return _cmd_build_pools(args)
    return _cmd_remix(args)


if __name__ == "__main__":
    sys.exit(main())
