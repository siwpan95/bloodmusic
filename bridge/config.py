"""
bridge/config.py —— BridgeConfig 与全部默认常量（唯一真源）

命中需求: P0-1；覆盖 Q3（只读硬规则）、Q4（离线）、Q6（和弦容差）、Q7（鼓网格）
关联发现: F5（PPQ=220，容差改为按 PPQ 比例推导）
          F8（鼓跨 4 小节，drum_bar_policy）
          F9（渲染器 step_dur 硬编码 beat/4，本期仅支持 16 网格）

约束:
    - L1 层，零 IO（`assert_write_allowed` 只做路径判断，不落盘）；
    - 所有可配项集中此处，避免默认值在各模块间漂移（QA 只需核对本文件）。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from .errors import BridgeConfigError, BridgeWriteDenied

__all__ = [
    "BRIDGE_VERSION",
    "PACKAGE_ROOT",
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_SCAN_ROOT",
    "DEFAULT_READONLY_ROOTS",
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_MIDI_SUFFIXES",
    "CHORD_TOLERANCE_DIVISOR",
    "CHORD_MIN_NOTES",
    "DEFAULT_DRUM_GRID",
    "SUPPORTED_DRUM_GRIDS",
    "DEFAULT_DRUM_BAR_POLICY",
    "SUPPORTED_DRUM_BAR_POLICIES",
    "BEATS_PER_BAR",
    "MIN_NOTE_BEATS",
    "REST_MIN_BEATS",
    "DURATION_ROUND",
    "MAX_REST_CHUNK_BEATS",
    "DEFAULT_BPM",
    "DEFAULT_DAW_PREFIX",
    "DEFAULT_DAW_MIDI_DIRS",
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_RENDER_MODES",
    "VELOCITY_REFERENCE",
    "VELOCITY_VOLUME_MIN",
    "VELOCITY_VOLUME_MAX",
    "LOG_FORMAT",
    "DATE_FORMAT",
    "LOGGER_ROOT",
    "BridgeConfig",
    "is_under_readonly_root",
    "assert_write_allowed",
]

# ── 版本 ──
BRIDGE_VERSION: str = "1.0.0"

# ── 路径基准 ──
#: bloodmusic 包根目录（bridge/ 的上一级），即 G:\tools\audio\bloodmusic
PACKAGE_ROOT: Path = Path(__file__).resolve().parent.parent

#: R2：默认输出根 = <包根>/bridge_output/
DEFAULT_OUTPUT_ROOT: Path = PACKAGE_ROOT / "bridge_output"

#: 默认扫描根（历史素材库）
DEFAULT_SCAN_ROOT: Path = Path("G:/midi")

#: R1 / Q3：默认绝不写入这些根之下（唯一例外见 assert_write_allowed）
DEFAULT_READONLY_ROOTS: tuple[Path, ...] = (Path("G:/midi"),)

#: 扫描黑名单目录（就地剪枝整棵子树）
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        # PRD 明确要求排除的 4 个（PyInstaller 打包噪声）
        "dist",
        "_internal",
        "build",
        "site-packages",
        # 同类打包 / 环境噪声
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "venv",
        ".venv",
        "env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".idea",
        ".vscode",
    }
)

#: 识别为 MIDI 资产的扩展名（比较时统一小写）
DEFAULT_MIDI_SUFFIXES: tuple[str, ...] = (".mid", ".midi")

# ── 和弦聚类（Q6 + F5）──
#: 容差 = round(ppq / CHORD_TOLERANCE_DIVISOR)：220→14、480→30（与 Q6 原始默认一致）
CHORD_TOLERANCE_DIVISOR: int = 16
#: 达到该同时发音数即视为「和弦轨」
CHORD_MIN_NOTES: int = 2

# ── 鼓（Q7 + F8/F9）──
#: 每小节步数（十六分网格）
DEFAULT_DRUM_GRID: int = 16
#: 本期仅支持 16（F9：render_drum_pattern 的 step_dur 硬编码 beat/4）
SUPPORTED_DRUM_GRIDS: frozenset[int] = frozenset({16})
#: extend=按小节数扩展（默认，信息零丢失）| fold=按位 OR 折回 1 小节 | split=每小节一个 pattern
DEFAULT_DRUM_BAR_POLICY: str = "extend"
SUPPORTED_DRUM_BAR_POLICIES: tuple[str, ...] = ("extend", "fold", "split")
#: 无 time_signature meta 时的假设拍号分子
BEATS_PER_BAR: int = 4

# ── 时值 ──
#: 最短音符（拍），防止渲染出 0 采样
MIN_NOTE_BEATS: float = 1.0 / 64.0
#: 休止符生成阈值（拍）。小于该值的簇间空隙视为「演奏释音」而非真正的休止，
#: 并入前一音时值 —— 这既保住时间轴总长，又避免把每个音都劈成「音+微休止」两项。
#: 实测依据：Chords_130406 的簇间隙恒为 44 tick = 0.2 拍（音长 836 + 释音 44 = 880 = 4 拍），
#: 若按 MIN_NOTE_BEATS(1/64) 判定会产生 3 个伪休止，pattern 项数由 4 膨胀到 7。
REST_MIN_BEATS: float = 0.25
#: 时值统一保留的小数位，规避浮点噪声
DURATION_ROUND: int = 4
#: 长休止拆分块上限（拍），避免单个超长休止破坏节奏感知
MAX_REST_CHUNK_BEATS: float = 1.0
#: 未检出 set_tempo 时的兜底 BPM
DEFAULT_BPM: int = 120

# ── DAW 回流 ──
#: R1 例外条款要求的文件名前缀，与 DAW 原有素材物理隔离
DEFAULT_DAW_PREFIX: str = "bm_"

#: 允许 `export-to-daw --apply` 落盘的 DAW 素材目录白名单（设计文档 §3.10）。
#: 素材库里有 **两个** 独立 DAW 的 Data/MIDI，回流必须按来源归位：
#: 把 pro4 的素材写进 MusicStudio 会让 MusicStudioPro 永远看不到自己的回流文件，
#: 同时污染另一个 DAW 的工作目录（QA BUG-1）。
DEFAULT_DAW_MIDI_DIRS: tuple[Path, ...] = (
    Path(r"G:\midi\MusicStudio\Data\MIDI"),
    Path(r"G:\midi\pro4\MusicStudioPro\Data\MIDI"),
)

# ── 渲染 ──
SUPPORTED_AUDIO_FORMATS: tuple[str, ...] = ("wav", "ogg", "flac")
SUPPORTED_RENDER_MODES: tuple[str, ...] = ("mix", "stems", "both")

# ── P1-1 力度 → 音量（C4 标定：实测 velocity 域 74–108）──
VELOCITY_REFERENCE: float = 100.0
VELOCITY_VOLUME_MIN: float = 0.5
VELOCITY_VOLUME_MAX: float = 1.3

# ── 日志（§9.5）──
LOG_FORMAT: str = "[bridge] %(asctime)s %(levelname)-5s %(name)s: %(message)s"
DATE_FORMAT: str = "%H:%M:%S"
LOGGER_ROOT: str = "bloodmusic.bridge"


@dataclass
class BridgeConfig:
    """bridge 全流程配置。

    Attributes:
        output_root: 音频 / 报告输出根目录（R2）。
        chord_tolerance_ticks: 和弦聚类容差；None → 运行时按 PPQ 推导（F5/U1）。
        drum_grid: 每小节鼓步数；本期仅 16（F9/U3）。
        drum_bar_policy: extend | fold | split（F8/U2）。
        audio_format: wav | ogg | flac。
        render_mode: mix | stems | both。
        velocity_to_volume: P1-1，按轨平均力度缩放音量。
        instrument_preset: P1-3，按 GM program 套用音色预设。
        exclude_dirs: 扫描黑名单目录名（小写比较）。
        readonly_roots: 只读根，落盘前强制校验（R1）。
        allow_daw_write: 仅 `export-to-daw --apply` 置 True。
        strict: True → 首个 error 级 issue 即抛异常（供 CI 用）。
        chord_min_notes: 判定和弦轨的最小同时发音数。
        bpm_override: 强制 BPM；None → 从 set_tempo 读。
        duration_sec: 强制渲染时长；None → 由 pattern 时值精确反推（D6）。
    """

    output_root: Path = DEFAULT_OUTPUT_ROOT
    chord_tolerance_ticks: int | None = None
    drum_grid: int = DEFAULT_DRUM_GRID
    drum_bar_policy: str = DEFAULT_DRUM_BAR_POLICY
    audio_format: str = "wav"
    render_mode: str = "both"
    velocity_to_volume: bool = True
    instrument_preset: bool = True
    exclude_dirs: frozenset[str] = DEFAULT_EXCLUDE_DIRS
    readonly_roots: tuple[Path, ...] = DEFAULT_READONLY_ROOTS
    allow_daw_write: bool = False
    strict: bool = False
    chord_min_notes: int = CHORD_MIN_NOTES
    bpm_override: int | None = None
    duration_sec: float | None = None
    daw_prefix: str = DEFAULT_DAW_PREFIX
    scan_root: Path = DEFAULT_SCAN_ROOT
    suffixes: tuple[str, ...] = DEFAULT_MIDI_SUFFIXES
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """规范化路径类型并做轻量校验。"""
        self.output_root = Path(self.output_root)
        self.scan_root = Path(self.scan_root)
        self.readonly_roots = tuple(Path(p) for p in self.readonly_roots)
        self.audio_format = str(self.audio_format).lower().lstrip(".")
        self.render_mode = str(self.render_mode).lower()
        self.drum_bar_policy = str(self.drum_bar_policy).lower()

        if self.audio_format not in SUPPORTED_AUDIO_FORMATS:
            raise BridgeConfigError(
                f"不支持的音频格式: {self.audio_format}；"
                f"可选 {'/'.join(SUPPORTED_AUDIO_FORMATS)}"
            )
        if self.render_mode not in SUPPORTED_RENDER_MODES:
            raise BridgeConfigError(
                f"不支持的渲染模式: {self.render_mode}；"
                f"可选 {'/'.join(SUPPORTED_RENDER_MODES)}"
            )
        if self.drum_bar_policy not in SUPPORTED_DRUM_BAR_POLICIES:
            raise BridgeConfigError(
                f"不支持的鼓小节策略: {self.drum_bar_policy}；"
                f"可选 {'/'.join(SUPPORTED_DRUM_BAR_POLICIES)}"
            )
        if self.chord_min_notes < 2:
            raise BridgeConfigError(
                f"chord_min_notes 必须 >= 2，当前 {self.chord_min_notes}"
            )

    @classmethod
    def from_args(cls, ns: argparse.Namespace) -> "BridgeConfig":
        """从 argparse.Namespace 装配配置（缺省字段一律走默认值）。

        Args:
            ns: 已解析的命令行参数命名空间。

        Returns:
            BridgeConfig 实例。
        """
        exclude = getattr(ns, "exclude", None)
        exclude_dirs = (
            DEFAULT_EXCLUDE_DIRS | {str(d).lower() for d in exclude}
            if exclude
            else DEFAULT_EXCLUDE_DIRS
        )
        out = getattr(ns, "out", None)
        return cls(
            output_root=Path(out) if out else DEFAULT_OUTPUT_ROOT,
            chord_tolerance_ticks=getattr(ns, "chord_tolerance", None),
            drum_grid=getattr(ns, "drum_grid", DEFAULT_DRUM_GRID),
            drum_bar_policy=getattr(ns, "drum_bar_policy", DEFAULT_DRUM_BAR_POLICY),
            audio_format=getattr(ns, "format", "wav"),
            render_mode=getattr(ns, "mode", "both"),
            velocity_to_volume=not getattr(ns, "no_velocity", False),
            instrument_preset=not getattr(ns, "no_preset", False),
            exclude_dirs=frozenset(exclude_dirs),
            allow_daw_write=bool(getattr(ns, "apply", False)),
            strict=bool(getattr(ns, "strict", False)),
            chord_min_notes=getattr(ns, "chord_min_notes", CHORD_MIN_NOTES),
            bpm_override=getattr(ns, "bpm", None),
            duration_sec=getattr(ns, "duration", None),
            daw_prefix=getattr(ns, "prefix", DEFAULT_DAW_PREFIX),
            scan_root=Path(getattr(ns, "root", None) or DEFAULT_SCAN_ROOT),
        )


def is_under_readonly_root(
    path: str | Path,
    readonly_roots: tuple[Path, ...] = DEFAULT_READONLY_ROOTS,
) -> bool:
    """判断目标路径是否位于任一只读根之下。

    Args:
        path: 待检查路径（可不存在）。
        readonly_roots: 只读根元组。

    Returns:
        True 表示命中只读根。
    """
    try:
        target = Path(path).expanduser().resolve(strict=False)
    except (OSError, ValueError):  # pragma: no cover - 极端非法路径
        return False
    for root in readonly_roots:
        try:
            root_resolved = Path(root).expanduser().resolve(strict=False)
        except (OSError, ValueError):  # pragma: no cover
            continue
        if target == root_resolved:
            return True
        try:
            target.relative_to(root_resolved)
        except ValueError:
            continue
        return True
    return False


def assert_write_allowed(
    path: str | Path,
    cfg: BridgeConfig | None = None,
    *,
    prefix: str | None = None,
) -> Path:
    """落盘前的写权限鉴权（R1 / Q3 硬规则）。

    规则：
        1. 目标不在任何只读根之下 → 放行；
        2. 目标在只读根之下，必须**同时**满足
           (a) `cfg.allow_daw_write is True`（即 `export-to-daw --apply`）
           (b) 文件名以 `prefix`（默认 ``bm_``）开头
           否则一律 raise BridgeWriteDenied。

    Args:
        path: 即将写入的文件路径。
        cfg: 当前配置；None 视为「未授权」。
        prefix: 允许写入的文件名前缀；None → cfg.daw_prefix 或全局默认。

    Returns:
        规范化后的绝对路径。

    Raises:
        BridgeWriteDenied: 触碰只读根且未通过双重鉴权。
    """
    target = Path(path).expanduser()
    readonly_roots = cfg.readonly_roots if cfg is not None else DEFAULT_READONLY_ROOTS
    if not is_under_readonly_root(target, readonly_roots):
        return target

    allow = bool(cfg is not None and cfg.allow_daw_write)
    effective_prefix = prefix or (cfg.daw_prefix if cfg is not None else DEFAULT_DAW_PREFIX)
    name_ok = target.name.startswith(effective_prefix)

    if allow and name_ok:
        return target

    reason = []
    if not allow:
        reason.append("未开启 --apply（allow_daw_write=False）")
    if not name_ok:
        reason.append(f"文件名未以 '{effective_prefix}' 开头")
    raise BridgeWriteDenied(
        "拒绝写入只读根（R1/Q3 硬规则）: " + "；".join(reason),
        path=str(target),
        readonly_roots=", ".join(str(r) for r in readonly_roots),
    )
