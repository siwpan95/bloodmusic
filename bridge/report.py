"""
bridge/report.py —— 统一日志 + 批量编排 + 结构化报告（P1-4）

命中需求: **P1-4**（批量转换报告）
关联设计: §9.2「批量不中断」、§9.5「日志规范」

职责:
    1. `get_logger()` —— 全 bridge 唯一的 logger 工厂（不污染 root logger）；
    2. `run_batch()` —— 扫描 → 导入 → 渲染的批量编排，
       **单个文件失败只降级为 BridgeIssue，绝不中断整批**；
    3. `write_report()` —— 落 `report.json` + `report.md`（R2：写默认输出根）。

约束:
    - `BridgeWriteDenied` 是唯一**不降级**的异常：它代表触碰只读根（R1），
      必须原样向上抛，让整批立即停下。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import (
    DATE_FORMAT,
    LOG_FORMAT,
    LOGGER_ROOT,
    BridgeConfig,
    assert_write_allowed,
)
from .errors import BridgeError, BridgeWriteDenied, IssueCode
from .midi_import import import_asset
from .models import BridgeIssue, BridgeReport, ImportResult, MidiAsset, RenderResult
from .renderer import render_import_result
from .scanner import scan_midi_assets

__all__ = [
    "get_logger",
    "configure_logging",
    "run_batch",
    "write_report",
    "format_summary",
]


def get_logger(name: str = "") -> logging.Logger:
    """获取 bridge 命名空间下的 logger。

    Args:
        name: 子模块名；空字符串表示根 logger。

    Returns:
        `bloodmusic.bridge[.name]` logger。
    """
    return logging.getLogger(f"{LOGGER_ROOT}.{name}" if name else LOGGER_ROOT)


def configure_logging(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """配置 bridge 日志输出（只挂自己的 handler，不动 root logger）。

    Args:
        verbose: True → DEBUG 级。
        quiet: True → 仅 ERROR 级（优先级高于 verbose）。

    Returns:
        已配置好的 bridge 根 logger。
    """
    logger = get_logger()
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)

    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logger.setLevel(level)
    handler.setLevel(level)
    return logger


def _issue_from_exception(exc: Exception, asset: MidiAsset) -> BridgeIssue:
    """把单文件异常降级成 error 级 issue（§9.2 批量不中断）。

    Args:
        exc: 捕获到的异常。
        asset: 出错的资产。

    Returns:
        BridgeIssue。
    """
    code = exc.code if isinstance(exc, BridgeError) else IssueCode.IMPORT_FAILED
    message = exc.message if isinstance(exc, BridgeError) else f"{type(exc).__name__}: {exc}"
    return BridgeIssue(
        level="error",
        code=code,
        message=f"{asset.rel_path}: {message}",
        context={"path": str(asset.path)},
    )


def run_batch(
    root: str | Path,
    cfg: BridgeConfig | None = None,
    *,
    do_render: bool = False,
    command: str = "import",
) -> BridgeReport:
    """批量扫描 → 导入（可选渲染），单文件失败不中断。

    Args:
        root: 扫描根目录或单个 MIDI 文件。
        cfg: 配置；None → 全默认。
        do_render: True → 导入后立即渲染音频。
        command: 写入报告的命令名（仅用于展示）。

    Returns:
        BridgeReport。

    Raises:
        BridgeScanError: 扫描根不存在。
        BridgeWriteDenied: 触碰只读根（R1，唯一不降级的异常）。
    """
    config = cfg if cfg is not None else BridgeConfig()
    logger = get_logger("batch")
    started = time.perf_counter()

    assets = scan_midi_assets(root, exclude_dirs=config.exclude_dirs, suffixes=config.suffixes)
    logger.info("扫描 %s → %d 个 MIDI 资产", root, len(assets))

    report = BridgeReport(root=Path(root), scanned=assets, command=command)

    for index, asset in enumerate(assets, start=1):
        logger.info("[%d/%d] 导入 %s", index, len(assets), asset.rel_path)
        try:
            result: ImportResult = import_asset(asset.path, config)
        except BridgeWriteDenied:
            raise  # R1：只读根被触碰，必须立即停止整批
        except Exception as exc:
            report.issues.append(_issue_from_exception(exc, asset))
            logger.error("导入失败: %s（%s）", asset.rel_path, exc)
            continue

        report.imported.append(result)
        logger.debug(
            "  → BPM=%s PPQ=%s 拍数=%.3f 旋律=%d 和弦=%d 鼓=%d",
            result.bpm,
            result.ticks_per_beat,
            result.total_beats,
            len(result.melody_patterns),
            len(result.chord_patterns),
            len(result.drum_patterns),
        )

        if not do_render:
            continue

        try:
            render: RenderResult = render_import_result(result, config)
        except BridgeWriteDenied:
            raise
        except Exception as exc:
            report.issues.append(_issue_from_exception(exc, asset))
            logger.error("渲染失败: %s（%s）", asset.rel_path, exc)
            continue

        report.rendered.append(render)
        logger.info("  → 产出 %d 个音频（%.3f s）", len(render.audio_files), render.duration_sec)

    report.elapsed_sec = time.perf_counter() - started
    logger.info("批量完成: %s", format_summary(report))
    return report


def format_summary(report: BridgeReport) -> str:
    """把报告汇总成单行人读文本（CLI 收尾用）。

    Args:
        report: 批量报告。

    Returns:
        形如 "扫描 6 / 成功 6 / 失败 0 / 音频 12 / error 0 warn 3 / 1.234s"。
    """
    s = report.summary()
    return (
        f"扫描 {s['scanned']} / 成功 {s['ok']} / 失败 {s['failed']} / "
        f"音频 {s['audio_files']} / error {s['error']} warn {s['warn']} info {s['info']} / "
        f"{s['elapsed_sec']}s"
    )


def write_report(
    report: BridgeReport,
    cfg: BridgeConfig | None = None,
    *,
    out_dir: str | Path | None = None,
    basename: str = "report",
) -> list[Path]:
    """把报告写成 `report.json` + `report.md`。

    Args:
        report: 批量报告。
        cfg: 配置（提供 output_root 与写盘鉴权）。
        out_dir: 覆盖输出目录；None → `cfg.output_root`。
        basename: 文件名主干。

    Returns:
        写入的文件路径列表。

    Raises:
        BridgeWriteDenied: 输出目录落在只读根内（R1）。
    """
    config = cfg if cfg is not None else BridgeConfig()
    base = Path(out_dir) if out_dir is not None else Path(config.output_root)

    json_path = assert_write_allowed(base / f"{basename}.json", config)
    md_path = assert_write_allowed(base / f"{basename}.md", config)

    base.mkdir(parents=True, exist_ok=True)
    json_path.write_text(report.to_json(), encoding="utf-8")
    md_path.write_text(report.to_markdown(), encoding="utf-8")

    get_logger("report").info("报告已写入 %s / %s", json_path.name, md_path.name)
    return [json_path, md_path]
