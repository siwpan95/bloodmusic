"""
album_maker/cli.py — CLI 入口

子命令: make / restore / doctor / list-styles / list-pools
用法:
  python -m bloodmusic.album_maker.cli make --demo --out ./album_output
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# ── sys.path 注入 audio_pipeline + remix ──
# CRITICAL: remix 必须在 bloodmusic 之前，因为 bloodmusic 也有 core/ 子包
_AUDIO_PIPELINE_ROOT = Path(r"G:\tools\audio_pipeline")
_REMIX_ROOT = Path(r"G:\tools\remix")
for _root in (_REMIX_ROOT, _AUDIO_PIPELINE_ROOT):
    _root_str = str(_root)
    while _root_str in sys.path:
        sys.path.remove(_root_str)
    sys.path.insert(0, _root_str)

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
    out_dir = Path(args.out) if args.out else Path("./album_output")
    maker = AlbumMaker(config)
    result = maker.make(out_dir, parallel=args.parallel, video_path=args.video)

    # 报告
    report = AlbumReport.generate(result)
    print(report)

    # 写入 JSON 报告
    report_path = out_dir / "album_report.json"
    AlbumReport.to_json(result, report_path)

    return 0 if result.all_success else 1


# ═══════════════════════════════════════════════════════════════════════
# 子命令: restore
# ═══════════════════════════════════════════════════════════════════════

def _cmd_restore(args: argparse.Namespace) -> int:
    """执行 restore 子命令。"""
    try:
        from separate_back import separate_back
    except ImportError as exc:
        logger.error(f"无法加载 audio_pipeline: {exc}")
        return 1

    album_dir = Path(args.album)
    if not album_dir.is_dir():
        logger.error(f"专辑目录不存在: {album_dir}")
        return 1

    # 定位曲目
    if args.track is not None:
        track_idx = int(args.track)
        # 查找 track_XX_* 目录
        track_dirs = sorted(album_dir.glob(f"track_{track_idx:02d}_*"))
        if not track_dirs:
            logger.error(f"未找到曲目 #{track_idx} 的目录")
            return 1
        track_dir = track_dirs[0]
    else:
        logger.error("请指定 --track <编号>")
        return 1

    # 定位 manifest
    manifest_path = track_dir / "manifest.json"
    if not manifest_path.is_file():
        logger.error(f"未找到 manifest: {manifest_path}")
        return 1

    song_path = track_dir / "song_final.wav"
    if not song_path.is_file():
        logger.error(f"未找到成品: {song_path}")
        return 1

    out_dir = track_dir / "separated"
    mode = args.mode or "manifest"

    logger.info(f"还原分轨: {track_dir.name} (mode={mode})")
    result = separate_back(
        song=song_path,
        out_dir=out_dir,
        mode=mode,
        manifest=manifest_path if mode == "manifest" else None,
    )

    print(f"✓ 分轨已还原到: {out_dir}")
    print(f"  模式: {result.get('mode', mode)}")
    print(f"  保真度: {result.get('fidelity', 'N/A')}")
    files = result.get("files", [])
    if files:
        print(f"  文件数: {len(files)}")
        for f in files[:5]:
            print(f"    - {f}")

    return 0


# ═══════════════════════════════════════════════════════════════════════
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

    # 系统路径检查
    ap_root = Path(r"G:\tools\audio_pipeline")
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
    """列出所有可用风格预设。"""
    try:
        from bloodmusic.music.pool_styles import STYLES
    except ImportError as exc:
        print(f"错误: 无法加载 bloodmusic — {exc}")
        return 1

    print("可用风格预设 (12 种):")
    print("-" * 60)
    for name, style in STYLES.items():
        print(f"  {name:16s} — {style.description}")
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


# ═══════════════════════════════════════════════════════════════════════
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
  bloodmusic-album restore --album ./album_output --track 1
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
        "--out", type=str, default="./album_output", help="输出目录（默认 ./album_output）"
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

    # restore
    p_restore = sub.add_parser("restore", help="按需还原分轨")
    p_restore.add_argument(
        "--album", type=str, required=True, help="专辑输出目录"
    )
    p_restore.add_argument(
        "--track", type=int, required=True, help="曲目编号（从 1 开始）"
    )
    p_restore.add_argument(
        "--mode", type=str, choices=["manifest", "algo"],
        default="manifest", help="还原模式（默认 manifest）"
    )
    p_restore.add_argument(
        "-v", "--verbose", action="store_true", help="详细日志输出"
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
        "restore": _cmd_restore,
        "doctor": _cmd_doctor,
        "list-styles": _cmd_list_styles,
        "list-pools": _cmd_list_pools,
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
