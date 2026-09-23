"""
bridge/cli.py —— 命令行入口（P0-6）

命中需求: **P0-6**（CLI 工具）

子命令:
    scan            扫描素材树，输出表格（# / 文件 / 轨数 / BPM / 时长 / 鼓轨 / 和弦）
    import          解析 MIDI → pattern，写 import.json（不渲染音频）
    render          解析 + 渲染音频到 bridge_output/
    export-to-daw   把 pattern 回流成 bm_*.mid（默认 dry-run，需 --apply 才落盘）
    doctor          环境自检（mido / 输出根 / 只读根）

硬规则:
    - **U3**：`--drum-grid 32` 必须报错（退出码 2）并提示回退 16；
    - **R2**：默认输出根 `<包根>/bridge_output/`；
    - **R1**：除 `export-to-daw --apply` + `bm_` 前缀外，绝不写 MIDI 素材根。

退出码:
    0 = 全部成功；1 = 有 error 级 issue；2 = 参数非法 / 环境缺失。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .config import (
    BRIDGE_VERSION,
    DEFAULT_DAW_PREFIX,
    DEFAULT_DRUM_BAR_POLICY,
    DEFAULT_DRUM_GRID,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SCAN_ROOT,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_DRUM_BAR_POLICIES,
    SUPPORTED_DRUM_GRIDS,
    SUPPORTED_RENDER_MODES,
    BridgeConfig,
    assert_write_allowed,
)
from .daw_export import DAW_MIDI_DIRS, export_import_result_to_daw
from .errors import BridgeError, BridgeWriteDenied, MidoMissingError, mido_available
from .midi_import import import_asset, probe_midi
from .report import configure_logging, format_summary, get_logger, run_batch, write_report
from .scanner import scan_midi_assets

__all__ = ["build_parser", "main", "render_scan_table"]

EXIT_OK: int = 0
EXIT_ISSUE: int = 1
EXIT_USAGE: int = 2


# ──────────────────────────────── 参数解析 ────────────────────────────────


def _add_common(parser: argparse.ArgumentParser) -> None:
    """挂载所有子命令共用的参数。"""
    parser.add_argument(
        "--root",
        default=str(DEFAULT_SCAN_ROOT),
        help=f"扫描根目录或单个 MIDI 文件（默认 {DEFAULT_SCAN_ROOT}）",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=None,
        help="额外排除的目录名（默认已排除 dist/_internal/build/site-packages 等）",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="输出 DEBUG 级日志")
    parser.add_argument("-q", "--quiet", action="store_true", help="仅输出 ERROR 级日志")


def _add_import_options(parser: argparse.ArgumentParser) -> None:
    """挂载解析相关参数。"""
    parser.add_argument("--bpm", type=int, default=None, help="强制曲速（默认读 set_tempo）")
    parser.add_argument(
        "--chord-tolerance",
        type=int,
        default=None,
        help="和弦聚类容差（tick）；默认按 PPQ 推导 round(ppq/16)，220 → 14",
    )
    parser.add_argument(
        "--drum-grid",
        type=int,
        default=DEFAULT_DRUM_GRID,
        help=f"每小节鼓步数（本期仅支持 {sorted(SUPPORTED_DRUM_GRIDS)}）",
    )
    parser.add_argument(
        "--drum-bar-policy",
        choices=SUPPORTED_DRUM_BAR_POLICIES,
        default=DEFAULT_DRUM_BAR_POLICY,
        help="鼓跨小节策略: extend=按小节扩展步数(默认) | fold=折回1小节 | split=每小节一个 pattern",
    )
    parser.add_argument(
        "--chord-min-notes", type=int, default=2, help="判定和弦轨的最小同时发音数（默认 2）"
    )
    parser.add_argument("--no-velocity", action="store_true", help="关闭力度 → 音量映射")
    parser.add_argument("--no-preset", action="store_true", help="关闭 GM program → 音色预设")
    parser.add_argument("--strict", action="store_true", help="出现 error 级问题立即失败")
    parser.add_argument(
        "--out", default=str(DEFAULT_OUTPUT_ROOT), help=f"输出根目录（默认 {DEFAULT_OUTPUT_ROOT}）"
    )


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。

    Returns:
        已挂载全部子命令的 ArgumentParser。
    """
    parser = argparse.ArgumentParser(
        prog="python -m bloodmusic.bridge",
        description="BloodMusic ×  MIDI 素材库桥接工具（bridge）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python -m bloodmusic.bridge scan\n"
            "  python -m bloodmusic.bridge import --root <MIDI_ROOT>\n"
            "  python -m bloodmusic.bridge render --root <MIDI_ROOT> --format wav\n"
            "  python -m bloodmusic.bridge export-to-daw --root <MIDI_ROOT>          # dry-run\n"
            "  python -m bloodmusic.bridge export-to-daw --root <MIDI_ROOT> --apply  # 真写盘\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"bridge {BRIDGE_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="扫描素材树并输出表格")
    _add_common(scan_parser)
    scan_parser.add_argument(
        "--probe", action="store_true", default=True, help="读文件头补全轨数/BPM/时长列（默认开启）"
    )
    scan_parser.add_argument(
        "--no-probe", dest="probe", action="store_false", help="只列文件，不读文件头（最快）"
    )

    import_parser = subparsers.add_parser("import", help="解析 MIDI → pattern，写 import.json")
    _add_common(import_parser)
    _add_import_options(import_parser)

    render_parser = subparsers.add_parser("render", help="解析并渲染音频")
    _add_common(render_parser)
    _add_import_options(render_parser)
    render_parser.add_argument(
        "--format", choices=SUPPORTED_AUDIO_FORMATS, default="wav", help="音频格式（默认 wav）"
    )
    render_parser.add_argument(
        "--mode", choices=SUPPORTED_RENDER_MODES, default="both", help="mix | stems | both（默认 both）"
    )
    render_parser.add_argument(
        "--duration", type=float, default=None, help="强制时长（秒）；默认由 pattern 时值精确反推"
    )

    daw_parser = subparsers.add_parser("export-to-daw", help="把 pattern 回流成 bm_*.mid")
    _add_common(daw_parser)
    _add_import_options(daw_parser)
    daw_parser.add_argument(
        "--apply", action="store_true", help="真正写盘（缺省为 dry-run，一个字节都不写）"
    )
    daw_parser.add_argument(
        "--prefix", default=DEFAULT_DAW_PREFIX, help=f"输出文件名前缀（默认 {DEFAULT_DAW_PREFIX}）"
    )
    daw_parser.add_argument(
        "--daw-dir",
        default=None,
        help=(
            "强制指定 DAW 素材目录；缺省按素材来源自动归位到它自己的 Data/MIDI"
            f"（白名单: {' | '.join(str(d) for d in DAW_MIDI_DIRS)}）"
        ),
    )

    doctor_parser = subparsers.add_parser("doctor", help="环境自检")
    _add_common(doctor_parser)

    return parser


# ──────────────────────────────── 表格渲染 ────────────────────────────────


def render_scan_table(rows: list[list[str]], headers: Sequence[str]) -> str:
    """把二维字符串表渲染成等宽终端表格。

    Args:
        rows: 数据行（每行元素个数须与 headers 一致）。
        headers: 表头。

    Returns:
        多行字符串（含分隔线）。
    """
    widths = [_display_width(h) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], _display_width(cell))

    def _line(cells: Sequence[str]) -> str:
        parts = []
        for index, cell in enumerate(cells):
            pad = widths[index] - _display_width(cell)
            parts.append(str(cell) + " " * max(0, pad))
        return "  ".join(parts).rstrip()

    separator = "  ".join("-" * w for w in widths)
    lines = [_line(headers), separator]
    lines.extend(_line(row) for row in rows)
    return "\n".join(lines)


def _display_width(text: str) -> int:
    """估算终端显示宽度（CJK 字符按 2 列计）。"""
    width = 0
    for ch in str(text):
        width += 2 if _is_wide(ch) else 1
    return width


def _is_wide(ch: str) -> bool:
    """判断字符是否为全角（简化版，覆盖常用 CJK 区段）。"""
    code = ord(ch)
    return (
        0x1100 <= code <= 0x115F
        or 0x2E80 <= code <= 0xA4CF
        or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF
        or 0xFE30 <= code <= 0xFE6F
        or 0xFF00 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6
    )


# ──────────────────────────────── 子命令实现 ────────────────────────────────


def _validate_drum_grid(ns: argparse.Namespace) -> None:
    """U3：不支持的鼓网格必须报错，不允许静默回退。

    Args:
        ns: 已解析参数。

    Raises:
        SystemExit: 网格不受支持时以退出码 2 终止。
    """
    grid = getattr(ns, "drum_grid", DEFAULT_DRUM_GRID)
    if grid is None or int(grid) in SUPPORTED_DRUM_GRIDS:
        return
    print(
        f"错误: --drum-grid {grid} 本期不支持。\n"
        f"      原因: music/pattern.py::render_drum_pattern 的步长硬编码为 beat/4，\n"
        f"            非 16 网格会导致鼓点时间轴错位（F9）。\n"
        f"      支持: {sorted(SUPPORTED_DRUM_GRIDS)}；请改用 --drum-grid {DEFAULT_DRUM_GRID}。",
        file=sys.stderr,
    )
    raise SystemExit(EXIT_USAGE)


def cmd_scan(ns: argparse.Namespace) -> int:
    """`scan` 子命令：输出素材表格。

    Args:
        ns: 已解析参数。

    Returns:
        退出码。
    """
    cfg = BridgeConfig.from_args(ns)
    assets = scan_midi_assets(ns.root, exclude_dirs=cfg.exclude_dirs, suffixes=cfg.suffixes)

    headers = ["#", "文件", "轨数", "BPM", "时长", "鼓轨", "和弦"]
    rows: list[list[str]] = []
    error_count = 0

    for index, asset in enumerate(assets, start=1):
        if not getattr(ns, "probe", True):
            rows.append([str(index), asset.rel_path, "-", "-", "-", "-", "-"])
            continue
        probe = probe_midi(asset.path, cfg)
        if probe.error:
            error_count += 1
            rows.append([str(index), asset.rel_path, "!", "-", "-", "-", probe.error[:40]])
            continue
        rows.append(
            [
                str(index),
                asset.rel_path,
                str(probe.track_count),
                str(probe.bpm),
                f"{probe.duration_sec:.2f}s",
                "是" if probe.has_drum else "否",
                "是" if probe.has_chord else "否",
            ]
        )

    print(render_scan_table(rows, headers))
    print(f"\n共 {len(assets)} 个 MIDI 资产（扫描根: {ns.root}）")
    return EXIT_ISSUE if error_count else EXIT_OK


def cmd_import(ns: argparse.Namespace) -> int:
    """`import` 子命令：批量解析并写报告。"""
    _validate_drum_grid(ns)
    cfg = BridgeConfig.from_args(ns)
    report = run_batch(ns.root, cfg, do_render=False, command="import")
    write_report(report, cfg)
    print(format_summary(report))
    return EXIT_ISSUE if report.summary()["error"] else EXIT_OK


def cmd_render(ns: argparse.Namespace) -> int:
    """`render` 子命令：批量解析并渲染音频。"""
    _validate_drum_grid(ns)
    cfg = BridgeConfig.from_args(ns)
    report = run_batch(ns.root, cfg, do_render=True, command="render")
    write_report(report, cfg)
    print(format_summary(report))
    for rendered in report.rendered:
        for path in rendered.audio_files:
            print(f"  ♪ {path}")
    return EXIT_ISSUE if report.summary()["error"] else EXIT_OK


def cmd_export_to_daw(ns: argparse.Namespace) -> int:
    """`export-to-daw` 子命令：pattern 回流 DAW（默认 dry-run）。"""
    _validate_drum_grid(ns)
    cfg = BridgeConfig.from_args(ns)
    logger = get_logger("daw")
    assets = scan_midi_assets(ns.root, exclude_dirs=cfg.exclude_dirs, suffixes=cfg.suffixes)

    # --daw-dir 缺省为 None：由 export_import_result_to_daw 按素材来源归位（QA BUG-1）
    forced_dir_arg = getattr(ns, "daw_dir", None)
    forced_dir = Path(forced_dir_arg) if forced_dir_arg else None

    total_written = 0
    error_count = 0
    used_dirs: list[str] = []
    for asset in assets:
        try:
            result = import_asset(asset.path, cfg)
            paths, issues = export_import_result_to_daw(result, cfg, out_dir=forced_dir)
        except BridgeWriteDenied:
            raise
        except BridgeError as exc:
            error_count += 1
            logger.error("回流失败 %s: %s", asset.rel_path, exc)
            continue

        for issue in issues:
            logger.info("%s", issue)
        for path in paths:
            print(f"  {'✓' if cfg.allow_daw_write else '·'} {path}")
            parent = str(path.parent)
            if parent not in used_dirs:
                used_dirs.append(parent)
        total_written += len(paths)

    action = "已写入" if cfg.allow_daw_write else "待写入（dry-run，追加 --apply 执行）"
    destination = " | ".join(used_dirs) if used_dirs else str(forced_dir or "（无产物）")
    print(f"\n{action} {total_written} 个 MIDI 文件 → {destination}")
    return EXIT_ISSUE if error_count else EXIT_OK


def cmd_doctor(ns: argparse.Namespace) -> int:
    """`doctor` 子命令：环境自检。"""
    cfg = BridgeConfig.from_args(ns)
    ok = True

    print(f"bridge 版本      : {BRIDGE_VERSION}")
    print(f"Python           : {sys.version.split()[0]}")

    if mido_available():
        print("mido             : 可用")
    else:
        ok = False
        print(f"mido             : 不可用 —— {MidoMissingError().message}")

    root = Path(ns.root)
    print(f"扫描根           : {root}（{'存在' if root.exists() else '不存在'}）")
    if not root.exists():
        ok = False

    print(f"输出根           : {cfg.output_root}")
    print(f"只读根           : {', '.join(str(p) for p in cfg.readonly_roots)}")

    probe_path = Path(cfg.output_root) / "__doctor_probe__.tmp"
    try:
        assert_write_allowed(probe_path, cfg)
        print("输出根写权限     : 允许（R1 鉴权通过，未实际写入）")
    except BridgeWriteDenied as exc:
        ok = False
        print(f"输出根写权限     : 拒绝 —— {exc.message}")

    return EXIT_OK if ok else EXIT_ISSUE


_HANDLERS = {
    "scan": cmd_scan,
    "import": cmd_import,
    "render": cmd_render,
    "export-to-daw": cmd_export_to_daw,
    "doctor": cmd_doctor,
}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI 主入口。

    Args:
        argv: 参数列表；None → 取 `sys.argv[1:]`。

    Returns:
        退出码（0 成功 / 1 有 error / 2 参数或环境问题）。
    """
    parser = build_parser()
    ns = parser.parse_args(list(argv) if argv is not None else None)
    configure_logging(verbose=ns.verbose, quiet=ns.quiet)

    handler = _HANDLERS.get(ns.command)
    if handler is None:  # pragma: no cover - argparse 已用 required=True 拦截
        parser.error(f"未知子命令: {ns.command}")
        return EXIT_USAGE

    try:
        return handler(ns)
    except SystemExit as exc:
        return int(exc.code or EXIT_OK)
    except BridgeWriteDenied as exc:
        print(f"[R1 违规] {exc}", file=sys.stderr)
        return EXIT_USAGE
    except MidoMissingError as exc:
        print(f"[环境缺失] {exc.message}", file=sys.stderr)
        return EXIT_USAGE
    except BridgeError as exc:
        print(f"[{exc.code}] {exc}", file=sys.stderr)
        return EXIT_ISSUE
    except KeyboardInterrupt:  # pragma: no cover - 交互式中断
        print("\n已取消。", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
