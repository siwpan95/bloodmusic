"""
bridge/scanner.py —— MIDI 资产扫描器（P0-2）

命中需求: **P0-2**（资产扫描器，对 G:\\midi 恰好返回 6）
关联发现: **D2** —— 素材树里混有 PyInstaller 打包噪声
          （`pro4/.../dist/.../_internal/pygame/examples/data/MIDI_sample.mid`），
          必须用 `os.walk` **就地剪枝** 整棵子树。

硬约束:
    - 纯只读，**不创建任何目录、不写任何文件**（R1/R2）；
    - 返回值按 `rel_path` 升序 → 结果确定性，测试可稳定断言。
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Collection, Sequence

from .config import DEFAULT_EXCLUDE_DIRS, DEFAULT_MIDI_SUFFIXES
from .errors import BridgeScanError
from .models import MidiAsset

__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_MIDI_SUFFIXES",
    "is_excluded",
    "scan_midi_assets",
    "snapshot_tree",
]


def _is_excluded_dir(dir_name: str, exclude_dirs: Collection[str]) -> bool:
    """单个目录名是否命中黑名单。"""
    lowered = dir_name.lower()
    if lowered in exclude_dirs:
        return True
    return lowered.endswith(".egg-info")


def is_excluded(rel_parts: Sequence[str], exclude_dirs: Collection[str]) -> bool:
    """路径任一级目录名（小写）命中黑名单，或以 `.egg-info` 结尾 → True。

    Args:
        rel_parts: 相对扫描根的路径分段（可含文件名末段）。
        exclude_dirs: 黑名单目录名集合（应为小写）。

    Returns:
        True 表示该路径应被排除。
    """
    normalized = {str(d).lower() for d in exclude_dirs}
    return any(_is_excluded_dir(str(part), normalized) for part in rel_parts)


def _make_asset(path: Path, root: Path) -> MidiAsset:
    """构造 MidiAsset（读取 stat 信息，只读操作）。"""
    stat = path.stat()
    try:
        rel = path.relative_to(root)
        rel_path = PurePosixPath(*rel.parts).as_posix()
        source_group = rel.parts[0] if len(rel.parts) > 1 else ""
    except ValueError:  # pragma: no cover - root 与 path 不同盘时的兜底
        rel_path = path.name
        source_group = path.parent.name
    return MidiAsset(
        path=path,
        name=path.stem,
        rel_path=rel_path,
        source_group=source_group,
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
    )


def scan_midi_assets(
    root: str | Path,
    *,
    exclude_dirs: Collection[str] = DEFAULT_EXCLUDE_DIRS,
    suffixes: Sequence[str] = DEFAULT_MIDI_SUFFIXES,
    min_size_bytes: int = 1,
    follow_symlinks: bool = False,
) -> list[MidiAsset]:
    """递归扫描 root 下的 MIDI 资产。

    实现要点：
        1. `os.walk(topdown=True)` 并**就地**修改 dirnames（切片赋值）——
           剪枝整棵子树，比「先收集后过滤」快且不会漏；
        2. 扩展名比较统一 `.lower()`，兼容 `.MID`；
        3. 返回值按 `rel_path` 升序，重复调用完全一致；
        4. root 不存在 → 抛 `BridgeScanError`；
           root 是单个 MIDI 文件 → 返回单元素列表（便于 `--file` 复用）；
        5. **只读操作，不创建任何目录**。

    Args:
        root: 扫描根目录或单个 MIDI 文件。
        exclude_dirs: 黑名单目录名（小写比较）。
        suffixes: 视为 MIDI 的扩展名。
        min_size_bytes: 小于该字节数的文件被忽略（默认过滤 0 字节空文件）。
        follow_symlinks: 是否跟随目录软链接（默认 False，防环）。

    Returns:
        按 rel_path 升序的 MidiAsset 列表。

    Raises:
        BridgeScanError: root 不存在或不可读。

    Example:
        >>> assets = scan_midi_assets("<MIDI_ROOT>")   # doctest: +SKIP
        >>> len(assets)                            # doctest: +SKIP
        6
    """
    root_path = Path(root).expanduser()
    if not root_path.exists():
        raise BridgeScanError(f"扫描根不存在: {root_path}", path=str(root_path))

    normalized_suffixes = tuple(s.lower() if s.startswith(".") else f".{s.lower()}" for s in suffixes)
    normalized_excludes = {str(d).lower() for d in exclude_dirs}

    # ── root 直接是一个 MIDI 文件 ──
    if root_path.is_file():
        if root_path.suffix.lower() not in normalized_suffixes:
            raise BridgeScanError(
                f"目标文件不是 MIDI: {root_path}（支持 {'/'.join(normalized_suffixes)}）",
                path=str(root_path),
            )
        return [_make_asset(root_path.resolve(), root_path.resolve().parent)]

    if not root_path.is_dir():  # pragma: no cover - 特殊设备文件
        raise BridgeScanError(f"扫描根不是目录也不是文件: {root_path}", path=str(root_path))

    root_resolved = root_path.resolve()
    assets: list[MidiAsset] = []

    for dirpath, dirnames, filenames in os.walk(
        root_resolved, topdown=True, followlinks=follow_symlinks
    ):
        # ★ 必须用切片赋值就地修改，否则剪枝失效（会多扫出 dist 里的打包噪声）
        dirnames[:] = [d for d in dirnames if not _is_excluded_dir(d, normalized_excludes)]
        dirnames.sort()

        current_dir = Path(dirpath)
        for filename in sorted(filenames):
            if Path(filename).suffix.lower() not in normalized_suffixes:
                continue
            file_path = current_dir / filename
            try:
                if not follow_symlinks and file_path.is_symlink():
                    continue
                if file_path.stat().st_size < min_size_bytes:
                    continue
                assets.append(_make_asset(file_path, root_resolved))
            except OSError:
                # 单个文件不可读不应中断整次扫描（§9.2 批量不中断）
                continue

    assets.sort(key=lambda a: a.rel_path)
    return assets


def snapshot_tree(
    root: str | Path,
    *,
    exclude_dirs: Collection[str] = frozenset(),
) -> dict[str, tuple[int, int]]:
    """对目录树做 (size, mtime_ns) 快照，用于 Q3 只读性校验。

    Args:
        root: 目标根目录；不存在时返回空字典。
        exclude_dirs: 需要跳过的目录名。

    Returns:
        {相对 POSIX 路径: (字节数, mtime_ns)}。
    """
    root_path = Path(root).expanduser()
    if not root_path.exists():
        return {}
    root_resolved = root_path.resolve()
    normalized_excludes = {str(d).lower() for d in exclude_dirs}

    snapshot: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root_resolved, topdown=True):
        if normalized_excludes:
            dirnames[:] = [d for d in dirnames if d.lower() not in normalized_excludes]
        current_dir = Path(dirpath)
        for filename in filenames:
            file_path = current_dir / filename
            try:
                stat = file_path.stat()
                rel = file_path.relative_to(root_resolved)
                snapshot[PurePosixPath(*rel.parts).as_posix()] = (stat.st_size, stat.st_mtime_ns)
            except (OSError, ValueError):  # pragma: no cover
                continue
    return snapshot
