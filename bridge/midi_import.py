"""
bridge/midi_import.py —— MIDI → BloodMusic pattern 主编排（P0-3 / P0-4）

命中需求:
    - **P0-3** 和弦导入修复（同时发音簇 → notes/chords 平行数组，零丢失）
    - **P0-4** 鼓轨识别与还原（GM 通道 10 → DrumPattern 步进矩阵）
    - P1-1 力度 → 音量、P1-3 GM program → 音色预设

关联发现:
    - **F5**：素材 PPQ = 220（非 480），一切 tick↔拍 换算都必须走 `ticks_per_beat`；
    - **F7**：legato 重叠普遍存在，`repair_negative_gaps()` 是主路径必经步骤；
    - **F8**：鼓跨 4 小节 → `drum_bar_policy="extend"` 给出 steps = 64；
    - **F10**：旋律用 octave_shift 无损，和弦只能折叠（`note_range` 已封装）；
    - **D6**：`total_beats` 必须精确反推，供 renderer 计算时长，绝不能拍脑袋。

硬约束:
    - **R5**：mido 惰性导入 —— 顶层没有 `import mido`，只在 `_read_midi_file()` 内部经
      `errors.load_mido()` 获取；
    - **R7**：只允许 bridge → bloodmusic 单向依赖；
    - §9.2：单文件解析失败降级为 `BridgeIssue`，批量流程不中断（`strict=True` 时才抛）。

判定轨类型（`_classify`）:
    max_polyphony 取「簇规模最大值」而非「同时鸣响音数」——
    Piano.mid 是 legato 演奏（前一音未松键后一音已按下），
    若按鸣响重叠统计会误判成和弦轨。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from ..music.pattern import DrumPattern, MultiTrackPattern, MusicPattern
from .chord_merge import (
    ChordFields,
    cluster_simultaneous,
    clusters_to_pattern_fields,
    default_chord_tolerance,
    lossless_note_count,
    repair_negative_gaps,
)
from .config import (
    BEATS_PER_BAR,
    CHORD_MIN_NOTES,
    DEFAULT_BPM,
    DEFAULT_DRUM_BAR_POLICY,
    DEFAULT_DRUM_GRID,
    SUPPORTED_DRUM_GRIDS,
    VELOCITY_REFERENCE,
    VELOCITY_VOLUME_MAX,
    VELOCITY_VOLUME_MIN,
    BridgeConfig,
)
from .drum_map import build_reverse_drum_map, default_drum_sounds, quantize_to_steps
from .errors import BridgeImportError, IssueCode, load_mido
from .instrument_map import DRUM_TONE_PRESET, resolve_preset
from .models import (
    GM_DRUM_CHANNEL,
    AssetProbe,
    BridgeIssue,
    ImportResult,
    NoteEvent,
    TrackAnalysis,
)

__all__ = [
    "midi_to_patterns_v2",
    "import_asset",
    "probe_midi",
    "velocity_to_volume_scale",
]


# ──────────────────────────────── 底层解析 ────────────────────────────────


def _read_midi_file(path: str | Path):
    """惰性加载 mido 并读入 MIDI 文件（R5）。

    Args:
        path: MIDI 文件路径。

    Returns:
        mido.MidiFile 实例。

    Raises:
        MidoMissingError: mido 不可用。
        BridgeImportError: 文件损坏或无法解析。
    """
    mido = load_mido()
    try:
        return mido.MidiFile(str(path))
    except Exception as exc:  # mido 会抛 OSError / EOFError / ValueError 等
        raise BridgeImportError(
            f"MIDI 文件解析失败: {Path(path).name}（{type(exc).__name__}: {exc}）",
            path=str(path),
        ) from exc


def _extract_tempo_and_meta(midi_file) -> tuple[int, int, list[BridgeIssue]]:
    """扫描全部轨的 meta 事件，取首个 set_tempo 与 time_signature。

    Args:
        midi_file: mido.MidiFile。

    Returns:
        (bpm, beats_per_bar, issues)。缺省 BPM = 120、拍号分子 = 4。
    """
    issues: list[BridgeIssue] = []
    tempos: list[int] = []
    beats_per_bar = BEATS_PER_BAR

    numerator_found = False
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                tempos.append(int(msg.tempo))
            elif msg.type == "time_signature" and not numerator_found:
                beats_per_bar = max(1, int(msg.numerator))
                numerator_found = True

    if not tempos:
        return DEFAULT_BPM, beats_per_bar, issues

    unique = sorted(set(tempos))
    if len(unique) > 1:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.MULTIPLE_TEMPO,
                message=(
                    f"检出 {len(unique)} 个不同 tempo，本期只支持恒定 BPM，"
                    f"已取首个（{round(60_000_000 / tempos[0])} BPM）。"
                ),
                context={"tempos": unique},
            )
        )
    bpm = int(round(60_000_000 / max(1, tempos[0])))
    return max(1, bpm), beats_per_bar, issues


def _collect_note_events(track, track_index: int) -> tuple[list[NoteEvent], list[BridgeIssue]]:
    """把一条 mido 轨的增量时间事件配对成绝对 tick 的 NoteEvent 列表。

    配对规则：
        - `note_on` 且 velocity > 0 → 压栈（同音高可叠多次，FIFO 出栈）；
        - `note_off` 或 `note_on` 且 velocity == 0 → 出栈成对；
        - 轨末仍未闭合的音 → 以轨末 tick 收口，记 `warn` 级 `UNCLOSED_NOTE`。

    Args:
        track: mido.MidiTrack。
        track_index: 轨序号（写入 NoteEvent.track_index）。

    Returns:
        (按 start_tick 升序的事件列表, issues)。
    """
    issues: list[BridgeIssue] = []
    pending: dict[tuple[int, int], list[tuple[int, int]]] = {}
    events: list[NoteEvent] = []
    absolute_tick = 0

    for msg in track:
        absolute_tick += int(msg.time)
        msg_type = getattr(msg, "type", "")
        if msg_type not in ("note_on", "note_off"):
            continue
        channel = int(getattr(msg, "channel", 0))
        note = int(getattr(msg, "note", 0))
        velocity = int(getattr(msg, "velocity", 0))
        key = (channel, note)

        if msg_type == "note_on" and velocity > 0:
            pending.setdefault(key, []).append((absolute_tick, velocity))
            continue

        stack = pending.get(key)
        if not stack:
            continue  # 孤立 note_off，忽略（常见于导出器的收尾冗余）
        start_tick, start_velocity = stack.pop(0)
        events.append(
            NoteEvent(
                start_tick=start_tick,
                end_tick=absolute_tick,
                midi_note=note,
                velocity=start_velocity,
                channel=channel,
                track_index=track_index,
            )
        )

    unclosed = sum(len(v) for v in pending.values())
    if unclosed:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.UNCLOSED_NOTE,
                message=f"轨 {track_index} 有 {unclosed} 个音符缺少 note_off，已按轨末收口。",
                context={"track_index": track_index, "count": unclosed},
            )
        )
        for (channel, note), stack in pending.items():
            for start_tick, velocity in stack:
                events.append(
                    NoteEvent(
                        start_tick=start_tick,
                        end_tick=max(absolute_tick, start_tick + 1),
                        midi_note=note,
                        velocity=velocity,
                        channel=channel,
                        track_index=track_index,
                    )
                )

    events.sort(key=lambda e: (e.start_tick, e.midi_note))
    return events, issues


def _track_name(track, track_index: int) -> str:
    """取轨名；无 track_name meta 时回落 "track_<i>"。"""
    for msg in track:
        if msg.type == "track_name" and str(msg.name).strip():
            return str(msg.name).strip()
    return f"track_{track_index}"


def _track_program(track) -> int | None:
    """取该轨首个 program_change 的 program 号；没有则 None。"""
    for msg in track:
        if msg.type == "program_change":
            return int(msg.program)
    return None


# ──────────────────────────────── 辅助计算 ────────────────────────────────


def velocity_to_volume_scale(mean_velocity: float) -> float:
    """力度均值 → 音量缩放系数（P1-1）。

    以 `VELOCITY_REFERENCE`(100) 为 1.0 基准线性映射，并夹在
    [`VELOCITY_VOLUME_MIN`, `VELOCITY_VOLUME_MAX`] 内，避免弱奏轨完全听不见 /
    强奏轨爆音。实测素材 velocity 域为 74–108，映射后落在 0.74–1.08。

    Args:
        mean_velocity: 该轨的平均力度（0–127）。

    Returns:
        音量缩放系数。
    """
    if mean_velocity <= 0:
        return 1.0
    scale = float(mean_velocity) / VELOCITY_REFERENCE
    return round(max(VELOCITY_VOLUME_MIN, min(VELOCITY_VOLUME_MAX, scale)), 6)


def _classify(
    events: Sequence[NoteEvent],
    max_cluster_size: int,
    chord_min_notes: int,
) -> str:
    """判定轨类型：drum / chord / melody / empty。

    Args:
        events: 该轨的音符事件。
        max_cluster_size: 最大同时发音簇规模（不是鸣响重叠数，见模块 docstring）。
        chord_min_notes: 和弦判定阈值。

    Returns:
        "drum" | "chord" | "melody" | "empty"。
    """
    if not events:
        return "empty"
    if any(e.channel == GM_DRUM_CHANNEL for e in events):
        return "drum"
    if max_cluster_size >= chord_min_notes:
        return "chord"
    return "melody"


def _mean_velocity(events: Iterable[NoteEvent]) -> float:
    """事件序列的平均力度；空序列返回 0.0。"""
    values = [e.velocity for e in events]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _build_music_pattern(
    name: str,
    fields: ChordFields,
    bpm: int,
    analysis: TrackAnalysis,
    *,
    velocity_to_volume: bool,
    instrument_preset: bool,
) -> MusicPattern:
    """把平行数组 + 轨分析装配成 MusicPattern（含音色与力度）。

    Args:
        name: pattern 名。
        fields: `clusters_to_pattern_fields` 的产物。
        bpm: 曲速。
        analysis: 轨分析（决定音色预设）。
        velocity_to_volume: 是否按平均力度缩放音量（P1-1）。
        instrument_preset: 是否套用 GM 音色预设（P1-3）。

    Returns:
        MusicPattern（loop=False，避免渲染器意外重复乐句）。
    """
    mean_velocity = (
        sum(v for v in fields.velocities if v > 0) / max(1, sum(1 for v in fields.velocities if v > 0))
        if any(v > 0 for v in fields.velocities)
        else 0.0
    )
    volume_scale = velocity_to_volume_scale(mean_velocity) if velocity_to_volume else 1.0

    pattern = MusicPattern(
        name=name,
        notes=list(fields.notes),
        durations=list(fields.durations),
        octave_shifts=list(fields.octave_shifts),
        bpm=bpm,
        loop=False,
        chords=[list(c) for c in fields.chords],
    )
    if instrument_preset:
        preset = resolve_preset(analysis)
        return preset.apply_to(pattern, volume_scale=volume_scale)

    # 不套预设时也要让力度生效，否则 P1-1 在 --no-preset 下失效
    pattern.volume = round(float(pattern.volume) * volume_scale, 6)
    return pattern


# ──────────────────────────────── 主入口 ────────────────────────────────


def midi_to_patterns_v2(
    path: str | Path,
    *,
    bpm: int | None = None,
    chord_tolerance_ticks: int | None = None,
    drum_steps: int = DEFAULT_DRUM_GRID,
    drum_bar_policy: str = DEFAULT_DRUM_BAR_POLICY,
    chord_min_notes: int = CHORD_MIN_NOTES,
    velocity_to_volume: bool = True,
    instrument_preset: bool = True,
    strict: bool = False,
) -> ImportResult:
    """把一个 MIDI 文件转换为 BloodMusic 的 pattern 集合。

    这是 bridge 的核心函数，取代 `music/midi_io.py::midi_to_patterns`，
    修复了「和弦被拆成连续单音」「鼓轨被整体丢弃」两个 P0 缺陷。

    流程：
        1. 惰性加载 mido 并读文件（R5）；
        2. 扫 meta 取 BPM / 拍号（多 tempo 记 warn）；
        3. 逐轨配对 note_on/note_off → NoteEvent（绝对 tick）；
        4. 鼓轨（channel 9）走 `quantize_to_steps` → DrumPattern；
        5. 音高轨走 `cluster_simultaneous` → `repair_negative_gaps`
           → `clusters_to_pattern_fields` → MusicPattern；
        6. 套用 GM 音色预设与力度缩放，装配 MultiTrackPattern；
        7. 汇总 `total_beats`（D6，供 renderer 精确计算时长）。

    Args:
        path: MIDI 文件路径。
        bpm: 强制曲速；None → 从 set_tempo 读取，缺省 120。
        chord_tolerance_ticks: 和弦聚类容差（tick）；
            None → `round(ppq / 16)`（220 → 14、480 → 30，U1）。
        drum_steps: 每小节鼓步数；本期仅 16，其它值记 error 并回退（U3）。
        drum_bar_policy: extend | fold | split（U2，默认 extend）。
        chord_min_notes: 判定和弦轨的最小同时发音数。
        velocity_to_volume: P1-1，按平均力度缩放音量。
        instrument_preset: P1-3，按 GM program 套用音色。
        strict: True → 出现 error 级 issue 时抛 `BridgeImportError`（供 CI）。

    Returns:
        ImportResult。

    Raises:
        MidoMissingError: mido 未安装。
        BridgeImportError: 文件无法解析，或 strict=True 且存在 error 级 issue。

    Example:
        >>> r = midi_to_patterns_v2("<MIDI_ROOT>/MusicStudio/Data/MIDI/Chords.mid")   # doctest: +SKIP
        >>> len(r.chord_patterns[0].notes)                                              # doctest: +SKIP
        4
    """
    source = Path(path)
    midi_file = _read_midi_file(source)

    ticks_per_beat = int(getattr(midi_file, "ticks_per_beat", 480) or 480)
    detected_bpm, beats_per_bar, issues = _extract_tempo_and_meta(midi_file)
    effective_bpm = int(bpm) if bpm else detected_bpm
    tolerance = (
        int(chord_tolerance_ticks)
        if chord_tolerance_ticks is not None
        else default_chord_tolerance(ticks_per_beat)
    )

    result = ImportResult(
        source=source,
        bpm=effective_bpm,
        ticks_per_beat=ticks_per_beat,
        beats_per_bar=beats_per_bar,
        issues=list(issues),
    )

    reverse_drum_map = build_reverse_drum_map()
    total_beats = 0.0
    drum_track_count = 0

    for track_index, track in enumerate(midi_file.tracks):
        events, track_issues = _collect_note_events(track, track_index)
        result.issues.extend(track_issues)

        name = _track_name(track, track_index)
        program = _track_program(track)
        channels = sorted({e.channel for e in events})
        is_drum = any(e.channel == GM_DRUM_CHANNEL for e in events)

        analysis = TrackAnalysis(
            track_index=track_index,
            name=name,
            channel=channels[0] if channels else None,
            program=program,
            is_drum=is_drum,
            kind="empty",
            note_count=len(events),
            pitch_min=min((e.midi_note for e in events), default=None),
            pitch_max=max((e.midi_note for e in events), default=None),
            span_ticks=max((e.end_tick for e in events), default=0),
        )

        if not events:
            result.analyses.append(analysis)
            continue

        # ── 鼓轨（P0-4）──
        if is_drum:
            drum_track_count += 1
            analysis.kind = "drum"
            analysis.max_polyphony = 1
            # U3：不支持的网格在 quantize_to_steps 内部回退 16，此处同步取回退后的值，
            # 否则 total_beats 会按错误的网格反推出错误时长。
            effective_grid = (
                int(drum_steps) if int(drum_steps) in SUPPORTED_DRUM_GRIDS else DEFAULT_DRUM_GRID
            )
            grid = quantize_to_steps(
                events,
                ticks_per_beat,
                grid=drum_steps,
                beats_per_bar=beats_per_bar,
                policy=drum_bar_policy,  # type: ignore[arg-type]
                reverse_map=reverse_drum_map,
            )
            result.issues.extend(grid.issues)

            for group_index, group_tracks in enumerate(grid.groups):
                if not group_tracks:
                    continue
                suffix = f"_bar{group_index + 1}" if len(grid.groups) > 1 else ""
                pattern_name = f"{source.stem}_{_slug(name)}{suffix}"
                steps = len(next(iter(group_tracks.values())))
                drum_pattern = DrumPattern(
                    name=pattern_name,
                    steps=steps,
                    bpm=effective_bpm,
                    tracks={k: list(v) for k, v in group_tracks.items()},
                    sounds=default_drum_sounds(group_tracks.keys()),
                    loop=False,
                )
                result.drum_patterns.append(drum_pattern)
                analysis.pattern_names.append(pattern_name)
                result.pattern_meta[pattern_name] = {
                    "track_index": track_index,
                    "kind": "drum",
                    "channel": GM_DRUM_CHANNEL,
                    "program": program,
                    "preset": DRUM_TONE_PRESET.name,
                    "mean_velocity": round(_mean_velocity(events), 2),
                    "bars": grid.bars,
                    "steps": steps,
                    "source_notes": len(events),
                }
                # D6：鼓 pattern 的自然时长 = 步数 / 每小节步数 × 每小节拍数
                total_beats = max(total_beats, steps / effective_grid * beats_per_bar)

            result.analyses.append(analysis)
            continue

        # ── 音高轨（P0-3）──
        clusters = cluster_simultaneous(events, tolerance)
        result.issues.extend(repair_negative_gaps(clusters, ticks_per_beat))
        max_cluster_size = max((c.size for c in clusters), default=0)
        analysis.max_polyphony = max_cluster_size
        analysis.kind = _classify(events, max_cluster_size, chord_min_notes)

        fields = clusters_to_pattern_fields(
            clusters, ticks_per_beat, chord_min_notes=chord_min_notes
        )
        result.issues.extend(fields.issues)

        if not fields.notes:
            result.issues.append(
                BridgeIssue(
                    level="info",
                    code=IssueCode.EMPTY_TRACK_SKIPPED,
                    message=f"轨 {track_index}（{name}）未产出任何音符项，已跳过。",
                    context={"track_index": track_index},
                )
            )
            result.analyses.append(analysis)
            continue

        # 无损自检：任何丢失都是 P0-3 的红线
        produced = lossless_note_count(fields)
        if produced != len(events):
            result.issues.append(
                BridgeIssue(
                    level="error",
                    code=IssueCode.IMPORT_FAILED,
                    message=(
                        f"轨 {track_index}（{name}）音符数不守恒: "
                        f"源 {len(events)} → 产出 {produced}。"
                    ),
                    context={"track_index": track_index, "src": len(events), "dst": produced},
                )
            )

        pattern_name = f"{source.stem}_{_slug(name)}"
        pattern = _build_music_pattern(
            pattern_name,
            fields,
            effective_bpm,
            analysis,
            velocity_to_volume=velocity_to_volume,
            instrument_preset=instrument_preset,
        )
        if analysis.kind == "chord":
            result.chord_patterns.append(pattern)
        else:
            result.melody_patterns.append(pattern)

        analysis.pattern_names.append(pattern_name)
        result.pattern_meta[pattern_name] = {
            "track_index": track_index,
            "kind": analysis.kind,
            "channel": analysis.channel,
            "program": program,
            "preset": resolve_preset(analysis).name,
            "mean_velocity": round(_mean_velocity(events), 2),
            "velocities": list(fields.velocities),
            "source_notes": len(events),
            "produced_notes": produced,
        }
        total_beats = max(total_beats, float(sum(fields.durations)))
        result.analyses.append(analysis)

    # ── 多轨装配 ──
    if drum_track_count > 1 or len(result.drum_patterns) > 1:
        result.issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.MULTI_DRUM_TRACK_TRUNCATED,
                message=(
                    f"检出 {len(result.drum_patterns)} 个鼓 pattern，"
                    f"MultiTrackPattern 只能挂 1 个鼓轨，混音时只用第 1 个"
                    f"（其余仍会作为独立 stem 渲染，不丢失）。"
                ),
                context={"count": len(result.drum_patterns)},
            )
        )

    music_tracks = result.all_music_patterns
    if music_tracks or result.drum_patterns:
        result.multi_track = MultiTrackPattern(
            name=f"{source.stem}_full",
            bpm=effective_bpm,
            loop=False,
            music_tracks=list(music_tracks),
            drum_track=result.drum_patterns[0] if result.drum_patterns else None,
        )
    else:
        result.issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.NO_PATTERN_PRODUCED,
                message=f"{source.name} 未产出任何 pattern（可能是空 MIDI）。",
                context={"path": str(source)},
            )
        )

    result.total_beats = round(total_beats, 6)

    if strict and not result.ok:
        first = next(i for i in result.issues if i.is_error)
        raise BridgeImportError(
            f"strict 模式下导入失败: {first.code} - {first.message}", path=str(source)
        )
    return result


def import_asset(
    path: str | Path,
    cfg: BridgeConfig | None = None,
) -> ImportResult:
    """按 `BridgeConfig` 导入单个 MIDI 文件（CLI / 批量层的便捷封装）。

    Args:
        path: MIDI 文件路径。
        cfg: 配置；None → 使用全默认配置。

    Returns:
        ImportResult。
    """
    config = cfg if cfg is not None else BridgeConfig()
    return midi_to_patterns_v2(
        path,
        bpm=config.bpm_override,
        chord_tolerance_ticks=config.chord_tolerance_ticks,
        drum_steps=config.drum_grid,
        drum_bar_policy=config.drum_bar_policy,
        chord_min_notes=config.chord_min_notes,
        velocity_to_volume=config.velocity_to_volume,
        instrument_preset=config.instrument_preset,
        strict=config.strict,
    )


def probe_midi(path: str | Path, cfg: BridgeConfig | None = None) -> AssetProbe:
    """轻量探测（`scan` 子命令表格用），失败不抛异常。

    Args:
        path: MIDI 文件路径。
        cfg: 配置；用于取 chord_min_notes 等阈值。

    Returns:
        AssetProbe；解析失败时 `error` 字段非空，其余字段为 0。
    """
    config = cfg if cfg is not None else BridgeConfig()
    probe = AssetProbe(path=Path(path))
    try:
        result = import_asset(path, config)
    except Exception as exc:  # 探测绝不能中断表格输出（§9.2）
        probe.error = f"{type(exc).__name__}: {exc}"
        return probe

    probe.track_count = sum(1 for a in result.analyses if a.note_count > 0)
    probe.bpm = result.bpm
    probe.ticks_per_beat = result.ticks_per_beat
    probe.duration_sec = result.duration_sec
    probe.note_count = sum(a.note_count for a in result.analyses)
    probe.has_drum = any(a.kind == "drum" for a in result.analyses)
    probe.has_chord = any(a.kind == "chord" for a in result.analyses)
    return probe


def _slug(text: str) -> str:
    """把轨名规范成可用于文件名的片段（空格 → 下划线，去掉非法字符）。

    Args:
        text: 原始轨名。

    Returns:
        安全片段；全部字符非法时返回 "track"。
    """
    safe: list[str] = []
    for ch in str(text).strip():
        if ch.isalnum() or ch in ("_", "-"):
            safe.append(ch)
        elif ch in (" ", ".", "/", "\\"):
            safe.append("_")
    cleaned = "".join(safe).strip("_")
    return cleaned or "track"
