"""
bridge/daw_export.py —— pattern 回流 DAW（P1-2）

命中需求: **P1-2**（导出回 DAW 素材库）

关联发现:
    - **F11**：`export/midi_export.py::export_music_to_midi` 的和弦分支存在量纲 bug
      （和弦音的 note_on/note_off 时间记账把「拍」与「tick」混用），
      直接复用会写出错位的 MIDI。本模块**自带一个正确的写出器**绕开它；
      R4 要求那个文件 git diff 为空，所以不去修它。
    - 鼓部分复用 `export/midi_export.py::MIDI_DRUM_MAP` **常量**（只读引用，不修改）。

写盘鉴权（R1 例外条款，三重条件缺一不可）:
    a. 目标目录必须落在 `DAW_MIDI_DIRS` 白名单（两个 DAW 各自的 `Data/MIDI`）之下；
    b. 文件名必须以 `bm_` 前缀开头（与 DAW 原有素材物理隔离）；
    c. 必须显式 `--apply`（即 `cfg.allow_daw_write is True`）。
    任一不满足 → 抛 `BridgeWriteDenied`，**永不降级为 warning**。

目录归属（QA BUG-1 修复）:
    素材库里有 **两个** 独立 DAW（MusicStudio 与 pro4/MusicStudioPro），
    回流目标必须按 `ImportResult.source` 归位到它自己的 `Data/MIDI`；
    旧实现写死单目录，导致 4/6 素材（pro4 来源）被误路由到另一个 DAW 目录。
    解析优先级: 显式 out_dir > 由 source 推导 > 白名单首项（并记 warn）。

约束: R5 —— mido 仍是惰性导入。
"""

from __future__ import annotations

from pathlib import Path

from ..export.midi_export import MIDI_DRUM_MAP
from ..music.pattern import DrumPattern, MusicPattern
from .config import DEFAULT_DAW_MIDI_DIRS, BridgeConfig, is_under_readonly_root
from .errors import BridgeWriteDenied, IssueCode, load_mido
from .models import BridgeIssue, ImportResult
from .note_range import note_name_to_midi

__all__ = [
    "DAW_MIDI_DIRS",
    "DAW_MIDI_DIR",
    "DEFAULT_VELOCITY",
    "assert_daw_write_allowed",
    "resolve_daw_dir_for_source",
    "write_music_pattern_midi",
    "write_drum_pattern_midi",
    "export_import_result_to_daw",
]

#: R1 例外条款允许写入的目录白名单（两个 DAW 各一个 Data/MIDI）
DAW_MIDI_DIRS: tuple[Path, ...] = tuple(DEFAULT_DAW_MIDI_DIRS)

#: 兼容别名：白名单首项。**新代码请用 `DAW_MIDI_DIRS`**，
#: 单目录常量正是 QA BUG-1（4/6 素材误路由）的根因。
DAW_MIDI_DIR: Path = DAW_MIDI_DIRS[0]

#: pattern_meta 中没有逐音力度时使用的默认力度
DEFAULT_VELOCITY: int = 96

#: 未知鼓件回落的 GM 音符号（GM 打击乐区间内的中性音）
FALLBACK_DRUM_NOTE: int = 60


def assert_daw_write_allowed(
    path: str | Path,
    cfg: BridgeConfig,
    *,
    daw_dirs: tuple[Path, ...] | list[Path] | None = None,
    daw_dir: Path | None = None,
) -> Path:
    """DAW 回流专用的三重鉴权。

    Args:
        path: 目标 MIDI 文件路径。
        cfg: 配置（提供 allow_daw_write 与 daw_prefix）。
        daw_dirs: 允许写入的 DAW 素材目录白名单；None → `DAW_MIDI_DIRS`。
        daw_dir: 单目录写法（向后兼容）；给出时覆盖 `daw_dirs`。

    Returns:
        规范化后的绝对路径。

    Raises:
        BridgeWriteDenied: 任一条件不满足。
    """
    target = Path(path).expanduser().resolve(strict=False)
    if daw_dir is not None:
        candidates: tuple[Path, ...] = (Path(daw_dir),)
    else:
        candidates = tuple(daw_dirs) if daw_dirs else DAW_MIDI_DIRS
    daw_roots = [Path(d).expanduser().resolve(strict=False) for d in candidates]
    prefix = cfg.daw_prefix or "bm_"

    reasons: list[str] = []
    if not cfg.allow_daw_write:
        reasons.append("未显式传入 --apply（allow_daw_write=False）")
    if not target.name.startswith(prefix):
        reasons.append(f"文件名 '{target.name}' 未以 '{prefix}' 开头")

    inside_daw = any(target == root or _is_relative_to(target, root) for root in daw_roots)
    if not inside_daw:
        # 目标不在任何 DAW 目录内：若它也不在只读根内，说明是普通输出目录，放行
        if not is_under_readonly_root(target, cfg.readonly_roots):
            return target
        allowed = " | ".join(str(r) for r in daw_roots)
        reasons.append(f"目标不在允许的 DAW 目录 [{allowed}] 之下")

    if reasons:
        raise BridgeWriteDenied(
            "拒绝写入 DAW 素材库（R1 硬规则）: " + "；".join(reasons),
            path=str(target),
            daw_dir=" | ".join(str(r) for r in daw_roots),
        )
    return target


def resolve_daw_dir_for_source(
    source: str | Path | None,
    *,
    daw_dirs: tuple[Path, ...] | list[Path] | None = None,
) -> tuple[Path, bool]:
    """按素材来源反查它自己的 DAW `Data/MIDI` 目录（QA BUG-1）。

    判定顺序:
        1. source 落在白名单某个目录之下 → 直接用那个目录（最常见）；
        2. source 的祖先里存在 `.../Data/MIDI` → 用该祖先（兼容白名单未登记的第三个 DAW）；
        3. 都不匹配 → 回落白名单首项，并把 `matched` 置 False 交由调用方记 warn。

    Args:
        source: 素材源文件路径（`ImportResult.source`）。
        daw_dirs: 目录白名单；None → `DAW_MIDI_DIRS`。

    Returns:
        (目标目录, 是否命中来源)。`matched=False` 表示这是兜底值，不可信。
    """
    candidates = tuple(Path(d) for d in (daw_dirs or DAW_MIDI_DIRS))
    fallback = candidates[0] if candidates else DAW_MIDI_DIRS[0]
    if not source:
        return fallback, False

    src = Path(source).expanduser().resolve(strict=False)
    for root in candidates:
        resolved = Path(root).expanduser().resolve(strict=False)
        if src == resolved or _is_relative_to(src, resolved):
            return Path(root), True

    # 白名单未登记：尝试从路径里认出 `<...>/Data/MIDI` 结构
    for parent in src.parents:
        if parent.name.lower() == "midi" and parent.parent.name.lower() == "data":
            return parent, True
    return fallback, False


def _is_relative_to(target: Path, root: Path) -> bool:
    """`Path.is_relative_to` 的兼容实现（不依赖 3.9+ 行为差异）。"""
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _beats_to_ticks(beats: float, ticks_per_beat: int) -> int:
    """拍 → tick（四舍五入，最小 0）。"""
    return max(0, int(round(float(beats) * int(ticks_per_beat))))


def write_music_pattern_midi(
    pattern: MusicPattern,
    out_path: str | Path,
    cfg: BridgeConfig,
    *,
    ticks_per_beat: int = 480,
    velocities: list[int] | None = None,
    program: int | None = None,
    channel: int = 0,
) -> Path:
    """把 `MusicPattern`（含和弦）写成标准 MIDI 文件。

    与 `export/midi_export.py::export_music_to_midi` 的区别（F11）：
        本实现把所有事件先算成**绝对 tick**，最后统一转成增量时间，
        因此根音与和弦上方音的时值不会互相污染；
        原实现在和弦分支里用拍数直接当 delta time，导致时间轴被拉长数倍。

    Args:
        pattern: 待导出的 pattern。
        out_path: 输出 .mid 路径。
        cfg: 配置（写盘鉴权）。
        ticks_per_beat: 输出文件的 PPQ。
        velocities: 逐项力度；None 或长度不足时用 `DEFAULT_VELOCITY` 补齐。
        program: GM program 号；None 则不写 program_change。
        channel: MIDI 通道（0-based）。

    Returns:
        实际写入的路径。

    Raises:
        BridgeWriteDenied: 鉴权失败。
        MidoMissingError: mido 未安装。
    """
    mido = load_mido()
    target = assert_daw_write_allowed(out_path, cfg)

    midi_file = mido.MidiFile(type=1, ticks_per_beat=int(ticks_per_beat))
    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage("track_name", name=str(pattern.name), time=0))
    meta_track.append(
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(max(1, int(pattern.bpm))), time=0)
    )
    midi_file.tracks.append(meta_track)

    note_track = mido.MidiTrack()
    if program is not None:
        note_track.append(
            mido.Message("program_change", channel=channel, program=int(program), time=0)
        )

    octaves = list(pattern.octave_shifts or [0] * len(pattern.notes))
    chords = list(pattern.chords or [])
    vel_list = list(velocities or [])

    # ── 1. 先算绝对 tick 事件表 ──
    events: list[tuple[int, int, int, int]] = []  # (tick, priority, note, velocity)
    cursor = 0
    for index, note_name in enumerate(pattern.notes):
        duration_beats = float(pattern.durations[index])
        length_ticks = max(1, _beats_to_ticks(duration_beats, ticks_per_beat))
        velocity = int(vel_list[index]) if index < len(vel_list) and vel_list[index] > 0 else DEFAULT_VELOCITY
        velocity = max(1, min(127, velocity))

        if note_name is not None:
            shift = int(octaves[index]) if index < len(octaves) else 0
            root_note = max(0, min(127, note_name_to_midi(note_name) + shift * 12))
            events.append((cursor, 1, root_note, velocity))
            events.append((cursor + length_ticks, 0, root_note, 0))

            if index < len(chords):
                for chord_name in chords[index]:
                    chord_note = max(0, min(127, note_name_to_midi(chord_name)))
                    events.append((cursor, 1, chord_note, max(1, velocity - 12)))
                    events.append((cursor + length_ticks, 0, chord_note, 0))

        cursor += length_ticks

    # ── 2. 绝对 tick → 增量时间（note_off 排在同 tick 的 note_on 之前）──
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    last_tick = 0
    for tick, priority, note, velocity in events:
        delta = max(0, tick - last_tick)
        last_tick = tick
        msg_type = "note_on" if priority == 1 else "note_off"
        note_track.append(
            mido.Message(msg_type, channel=channel, note=note, velocity=velocity, time=delta)
        )

    note_track.append(mido.MetaMessage("end_of_track", time=0))
    midi_file.tracks.append(note_track)

    target.parent.mkdir(parents=True, exist_ok=True)
    midi_file.save(str(target))
    return target


def write_drum_pattern_midi(
    pattern: DrumPattern,
    out_path: str | Path,
    cfg: BridgeConfig,
    *,
    ticks_per_beat: int = 480,
    velocity: int = 100,
) -> Path:
    """把 `DrumPattern` 写成 GM 通道 10 的 MIDI 文件。

    鼓件名 → 音符号复用 `export/midi_export.py::MIDI_DRUM_MAP`（只读引用）；
    `perc_<n>` 形式的未知鼓件直接解析出数字 n 作为音符号，保证往返无损。

    Args:
        pattern: 鼓 pattern。
        out_path: 输出 .mid 路径。
        cfg: 配置（写盘鉴权）。
        ticks_per_beat: 输出文件的 PPQ。
        velocity: 打击力度。

    Returns:
        实际写入的路径。

    Raises:
        BridgeWriteDenied: 鉴权失败。
        MidoMissingError: mido 未安装。
    """
    mido = load_mido()
    target = assert_daw_write_allowed(out_path, cfg)

    midi_file = mido.MidiFile(type=1, ticks_per_beat=int(ticks_per_beat))
    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage("track_name", name=str(pattern.name), time=0))
    meta_track.append(
        mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(max(1, int(pattern.bpm))), time=0)
    )
    midi_file.tracks.append(meta_track)

    step_ticks = max(1, int(round(int(ticks_per_beat) / 4)))  # 十六分音符
    hit_ticks = max(1, step_ticks // 2)

    events: list[tuple[int, int, int, int]] = []
    for track_name, steps in pattern.tracks.items():
        drum_note = _drum_note_for(track_name)
        for step_index, is_hit in enumerate(steps):
            if not is_hit:
                continue
            start = step_index * step_ticks
            events.append((start, 1, drum_note, max(1, min(127, int(velocity)))))
            events.append((start + hit_ticks, 0, drum_note, 0))

    events.sort(key=lambda e: (e[0], e[1], e[2]))
    drum_track = mido.MidiTrack()
    last_tick = 0
    for tick, priority, note, vel in events:
        delta = max(0, tick - last_tick)
        last_tick = tick
        msg_type = "note_on" if priority == 1 else "note_off"
        drum_track.append(
            mido.Message(msg_type, channel=9, note=note, velocity=vel, time=delta)
        )
    drum_track.append(mido.MetaMessage("end_of_track", time=0))
    midi_file.tracks.append(drum_track)

    target.parent.mkdir(parents=True, exist_ok=True)
    midi_file.save(str(target))
    return target


def _drum_note_for(track_name: str) -> int:
    """鼓件名 → GM 音符号。

    Args:
        track_name: 鼓件名，如 "kick" / "perc_60"。

    Returns:
        GM 音符号；未知名回落 `FALLBACK_DRUM_NOTE`。
    """
    lowered = str(track_name).lower()
    if lowered in MIDI_DRUM_MAP:
        return int(MIDI_DRUM_MAP[lowered])
    if lowered.startswith("perc_"):
        try:
            return max(0, min(127, int(lowered.split("_", 1)[1])))
        except (ValueError, IndexError):
            return FALLBACK_DRUM_NOTE
    return FALLBACK_DRUM_NOTE


def export_import_result_to_daw(
    result: ImportResult,
    cfg: BridgeConfig,
    *,
    out_dir: str | Path | None = None,
    ticks_per_beat: int | None = None,
) -> tuple[list[Path], list[BridgeIssue]]:
    """把一个 `ImportResult` 的全部 pattern 回流成 `bm_*.mid`。

    未开启 `--apply` 时执行 **dry-run**：只列出「将要写入」的路径并记
    `info` 级 `DRY_RUN` issue，一个字节都不落盘。

    目录归属（QA BUG-1）:
        `out_dir=None` 时**不再**写死单目录，而是按 `result.source` 归位到
        素材自己所属 DAW 的 `Data/MIDI`；来源无法判定时回落白名单首项并记 warn，
        且此种情况下即便带了 `--apply` 也拒绝落盘（OBS-1：目标必须可确证）。

    Args:
        result: 导入产物。
        cfg: 配置（allow_daw_write 决定 dry-run / 实写）。
        out_dir: 输出目录；None → 由 `result.source` 推导。
        ticks_per_beat: 输出 PPQ；None → 沿用源文件 PPQ（默认 220）。

    Returns:
        (写入或计划写入的路径列表, issues)。

    Raises:
        BridgeWriteDenied: 开启了 --apply 但路径 / 前缀不合规，或目标目录无法确证。
    """
    issues: list[BridgeIssue] = []
    written: list[Path] = []

    if out_dir is not None:
        base_dir = Path(out_dir)
        routed_by_source = False
    else:
        base_dir, routed_by_source = resolve_daw_dir_for_source(result.source)
        if not routed_by_source:
            issues.append(
                BridgeIssue(
                    level="warn",
                    code=IssueCode.WRITE_DENIED if cfg.allow_daw_write else IssueCode.DRY_RUN,
                    message=(
                        f"无法从来源 '{result.source}' 判定所属 DAW 目录，"
                        f"回落 '{base_dir}'。请用 --daw-dir 显式指定。"
                    ),
                    context={"source": str(result.source), "fallback_dir": str(base_dir)},
                )
            )
            if cfg.allow_daw_write:
                # OBS-1：--apply 下目标目录必须可确证，绝不猜着往 DAW 素材库里写
                raise BridgeWriteDenied(
                    "拒绝写入 DAW 素材库（R1 硬规则）: "
                    f"无法由来源 '{result.source}' 确定目标 DAW 目录，"
                    "请显式传入 --daw-dir。",
                    path=str(result.source),
                    daw_dir=" | ".join(str(d) for d in DAW_MIDI_DIRS),
                )

    ppq = int(ticks_per_beat or result.ticks_per_beat or 480)
    prefix = cfg.daw_prefix or "bm_"

    for pattern in result.all_music_patterns:
        target = base_dir / f"{prefix}{_safe_name(pattern.name)}.mid"
        meta = result.pattern_meta.get(pattern.name, {})
        if not cfg.allow_daw_write:
            issues.append(_dry_run_issue(target))
            written.append(target)
            continue
        written.append(
            write_music_pattern_midi(
                pattern,
                target,
                cfg,
                ticks_per_beat=ppq,
                velocities=list(meta.get("velocities") or []),
                program=meta.get("program"),
                channel=int(meta.get("channel") or 0),
            )
        )

    for drum in result.drum_patterns:
        target = base_dir / f"{prefix}{_safe_name(drum.name)}.mid"
        if not cfg.allow_daw_write:
            issues.append(_dry_run_issue(target))
            written.append(target)
            continue
        written.append(write_drum_pattern_midi(drum, target, cfg, ticks_per_beat=ppq))

    if not cfg.allow_daw_write:
        issues.append(
            BridgeIssue(
                level="info",
                code=IssueCode.DRY_RUN,
                message=(
                    f"dry-run：共 {len(written)} 个文件待写入 {base_dir}，"
                    f"未落盘。确认无误后追加 --apply 执行。"
                ),
                context={"count": len(written), "out_dir": str(base_dir)},
            )
        )
    return written, issues


def _dry_run_issue(target: Path) -> BridgeIssue:
    """构造一条 dry-run 记录。"""
    return BridgeIssue(
        level="info",
        code=IssueCode.DRY_RUN,
        message=f"[dry-run] 将写入: {target}",
        context={"path": str(target)},
    )


def _safe_name(name: str) -> str:
    """把 pattern 名规范成安全文件名片段。"""
    safe = [c if (c.isalnum() or c in ("_", "-")) else "_" for c in str(name)]
    return "".join(safe).strip("_") or "pattern"
