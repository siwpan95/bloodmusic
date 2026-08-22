"""
album_maker/cli.py — CLI 入口

子命令: make / doctor / list-styles / list-pools / quick / style / jam
用法:
  python -m bloodmusic.album_maker.cli make --demo --out ./album_output
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# ── sys.path 注入（内部自包含） ──
# pipeline/ 和 remix/ 已迁移到 bloodmusic 内部
_AUDIO_PIPELINE_ROOT = Path(__file__).resolve().parents[1] / "pipeline"
_REMIX_ROOT = Path(__file__).resolve().parents[1] / "remix"
for _root in (_REMIX_ROOT, _AUDIO_PIPELINE_ROOT):
    _root_str = str(_root)
    while _root_str in sys.path:
        sys.path.remove(_root_str)
    sys.path.insert(0, _root_str)

# ── PATH 注入 (remix 内置 ffmpeg) ──
_REMIX_BIN = str(_REMIX_ROOT / "bin")
if _REMIX_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _REMIX_BIN + os.pathsep + os.environ.get("PATH", "")

# 默认输出根（绝对路径，固定到 bloodmusic 项目内）
_BLOODMUSIC_ROOT = Path(__file__).resolve().parents[1]
_QUICK_DEFAULT_OUT = str(_BLOODMUSIC_ROOT / "album_maker_quick")
_JAM_DEFAULT_OUT = str(_BLOODMUSIC_ROOT / "album_maker_jam")
_MAKE_DEFAULT_OUT = str(_BLOODMUSIC_ROOT / "album_output")

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    """配置日志级别。"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ═══════════════════════════════════════════════════════════════════════
# 子命令: make
# ═══════════════════════════════════════════════════════════════════════

def _cmd_make(args: argparse.Namespace) -> int:
    """执行 make 子命令。"""
    from .album import AlbumMaker
    from .config import AlbumConfig
    from .demo_config import make_demo_config
    from .report import AlbumReport

    # 加载配置
    if args.demo:
        config = make_demo_config()
        logger.info("使用 --demo 内置配置（3 首曲目）")
    elif args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return 1
        config = AlbumConfig.from_yaml(config_path)
        logger.info(f"已加载配置: {config_path}")
    else:
        logger.error("请指定 --config <album.yaml> 或 --demo")
        return 1

    # 执行
    out_dir = Path(args.out) if args.out else Path(_MAKE_DEFAULT_OUT)
    maker = AlbumMaker(config)
    result = maker.make(out_dir, parallel=args.parallel, video_path=args.video)

    # 报告
    report = AlbumReport.generate(result)
    print(report)

    # 写入 JSON 报告
    report_path = out_dir / "album_report.json"
    AlbumReport.to_json(result, report_path)

    return 0 if result.all_success else 1



# 子命令: doctor
# ═══════════════════════════════════════════════════════════════════════

def _cmd_doctor(args: argparse.Namespace) -> int:
    """环境诊断。"""
    issues: list[str] = []

    # 检查 Python 版本
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"  Python: {py_version}")
    if sys.version_info < (3, 11):
        issues.append(f"Python 版本过低 ({py_version})，需要 3.11+")

    # 检查 bloodmusic
    try:
        import bloodmusic
        print(f"  BloodMusic: v{bloodmusic.__version__}")
    except ImportError as exc:
        issues.append(f"bloodmusic 导入失败: {exc}")

    # 检查 audio_pipeline
    try:
        from mixdown import mixdown
        print(f"  audio_pipeline (mixdown): OK")
    except ImportError as exc:
        issues.append(f"audio_pipeline 不可用: {exc}")

    try:
        from manifest import read_manifest
        print(f"  audio_pipeline (manifest): OK")
    except ImportError as exc:
        issues.append(f"audio_pipeline manifest 不可用: {exc}")

    # 检查 remix (MixConfig)
    try:
        from core.audio_mixer import MixConfig
        print(f"  remix (audio_mixer): OK")
    except ImportError as exc:
        issues.append(f"remix 不可用: {exc}")

    # 检查 PyYAML
    try:
        import yaml
        print(f"  PyYAML: {yaml.__version__}")
    except ImportError as exc:
        issues.append(f"PyYAML 不可用: {exc}")

    # 检查 numpy
    try:
        import numpy
        print(f"  numpy: {numpy.__version__}")
    except ImportError as exc:
        issues.append(f"numpy 不可用: {exc}")

    # 流水线路径检查（内置 pipeline/）
    ap_root = _BLOODMUSIC_ROOT / "pipeline"
    if ap_root.exists():
        print(f"  audio_pipeline 路径: OK ({ap_root})")
    else:
        issues.append(f"audio_pipeline 路径不存在: {ap_root}")

    print()
    if issues:
        print(f"  ⚠ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"    - {issue}")
        return 1
    else:
        print("  ✅ 环境诊断通过，所有依赖就绪")
        return 0


# ═══════════════════════════════════════════════════════════════════════
# 子命令: list-styles
# ═══════════════════════════════════════════════════════════════════════

def _cmd_list_styles(args: argparse.Namespace) -> int:
    """列出所有可用风格预设（含编配策略）。"""
    from .style_db import STYLE_DB

    print("风格编配策略（quick/style/jam/make/beat 共用）:")
    print("-" * 60)
    for name, s in sorted(STYLE_DB.items()):
        bpm = f"{s['bpm_range'][0]}-{s['bpm_range'][1]}"
        keys = "/".join(s["keys"][:4])
        scales = "/".join(s["scales"][:2])
        progs = ", ".join(s["progressions"][:3])
        print(f"  {name:14s} BPM {bpm:>8s}")
        print(f"  {'':14s} 调: {keys}  调式: {scales}")
        print(f"  {'':14s} 和声: {progs}")
        print(f"  {'':14s} 乐器: {', '.join(s['instruments'][:3])}  节奏: {s['drum_style']}")
        print()
    return 0


# ═══════════════════════════════════════════════════════════════════════
# 子命令: list-pools
# ═══════════════════════════════════════════════════════════════════════

def _cmd_list_pools(args: argparse.Namespace) -> int:
    """列出内置乐器池预设。"""
    try:
        from bloodmusic.music.pool_serializer import PoolSerializer
    except ImportError as exc:
        print(f"错误: 无法加载 bloodmusic — {exc}")
        return 1

    presets = PoolSerializer.list_presets()
    if presets:
        print(f"内置乐器池预设 ({len(presets)} 个):")
        for name in presets:
            print(f"  - {name}")
    else:
        print("未找到内置乐器池预设")
    return 0


# ── 快速单曲命令 ────────────────────────────────────────────

def _cmd_quick(args: argparse.Namespace) -> int:
    """随机风格快速单曲"""
    from .quick import QuickMaker
    import random
    if args.seed is not None:
        random.seed(args.seed)
    result = QuickMaker.random(out_dir=args.out, seed=args.seed)
    print(f"\n🎲 {result.title}")
    print(f"   风格={result.style}  BPM={result.bpm}  Key={result.key}  Bars={result.bars}")
    if result.wave_path:
        print(f"   📁 {result.wave_path}  ({result.duration_sec:.1f}s)")
    return 0


def _cmd_style(args: argparse.Namespace) -> int:
    """指定风格快速单曲"""
    from .quick import QuickMaker, STYLE_DB
    if args.style_name not in STYLE_DB:
        print(f"未知风格: {args.style_name}")
        print(f"可用: {', '.join(STYLE_DB.keys())}")
        return 1
    result = QuickMaker.style(args.style_name, out_dir=args.out,
                               bpm=args.bpm, bars=args.bars, seed=args.seed)
    print(f"\n🎵 {result.title}")
    print(f"   风格={result.style}  BPM={result.bpm}  Key={result.key}  Bars={result.bars}")
    if result.wave_path:
        print(f"   📁 {result.wave_path}  ({result.duration_sec:.1f}s)")
    return 0


def _cmd_jam(args: argparse.Namespace) -> int:
    """即兴连续生成"""
    from .quick import QuickMaker
    results = QuickMaker.jam(count=args.count, out_dir=args.out)
    ok = sum(1 for r in results if r.wave_path)
    print(f"\n🎸 {ok}/{args.count} 成功 → {args.out}")
    return 0 if ok == args.count else 1

# ═══════════════════════════════════════════════════════════════════════
# 命令行解析器
# main
# ═══════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        prog="bloodmusic-album",
        description="BloodMusic Album Maker — 程序化专辑制作器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  bloodmusic-album make --demo --out ./album_output
  bloodmusic-album make --config album.yaml --out ./album_output --parallel
  bloodmusic-album make --demo --out ./album_output --video ./input.mp4
  bloodmusic-album doctor
  bloodmusic-album list-styles
  bloodmusic-album list-pools
        """,
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    # make
    p_make = sub.add_parser("make", help="完整专辑生成")
    p_make.add_argument(
        "--config", type=str, help="album.yaml 路径"
    )
    p_make.add_argument(
        "--demo", action="store_true", help="使用内置 demo 配置（零配置体验）"
    )
    p_make.add_argument(
        "--out", type=str, default=_MAKE_DEFAULT_OUT, help="输出目录（默认 bloodmusic/album_output）"
    )
    p_make.add_argument(
        "--parallel", action="store_true", help="并行生成曲目（P1）"
    )
    p_make.add_argument(
        "-v", "--verbose", action="store_true", help="详细日志输出"
    )
    p_make.add_argument(
        "--video", type=str, default=None, help="视频文件路径（可选），将专辑首支曲目作为 BGM 嵌入视频"
    )


    # doctor
    p_doctor = sub.add_parser("doctor", help="环境诊断")
    p_doctor.add_argument(
        "-v", "--verbose", action="store_true", help="详细日志输出"
    )

    # list-styles
    sub.add_parser("list-styles", help="列出可用风格")

    # list-pools
    sub.add_parser("list-pools", help="列出内置乐器池模板")

    # ── 快速单曲 (style_db 风格知识 + skill/make_beats.py) ──
    p_quick = sub.add_parser("quick", help="🎲 随机风格快速单曲（零配置）")
    p_quick.add_argument("--out", default=_QUICK_DEFAULT_OUT, help="输出目录")
    p_quick.add_argument("--seed", type=int, default=None, help="随机种子")

    p_style = sub.add_parser("style", help="🎵 指定风格快速单曲")
    p_style.add_argument("style_name", help="风格名（classical/jazz/electronic/...）")
    p_style.add_argument("--bpm", type=int, default=None)
    p_style.add_argument("--bars", type=int, default=None)
    p_style.add_argument("--out", default=_QUICK_DEFAULT_OUT)
    p_style.add_argument("--seed", type=int, default=None)

    p_jam = sub.add_parser("jam", help="🎸 即兴模式 — 连续生成 N 首随机曲")
    p_jam.add_argument("--count", type=int, default=5, help="生成数量（默认 5）")
    p_jam.add_argument("--out", default=_JAM_DEFAULT_OUT)
    p_jam.add_argument("--seed", type=int, default=None)


    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。

    Args:
        argv: 命令行参数列表，None=使用 sys.argv

    Returns:
        退出码（0=全部成功，1=有失败）
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    _setup_logging(verbose=getattr(args, "verbose", False))

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "make": _cmd_make,
        "doctor": _cmd_doctor,
        "list-styles": _cmd_list_styles,
        "list-pools": _cmd_list_pools,
        "quick": _cmd_quick,
        "style": _cmd_style,
        "jam": _cmd_jam,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except Exception as exc:
        logger.error(f"命令执行异常: {type(exc).__name__}: {exc}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
