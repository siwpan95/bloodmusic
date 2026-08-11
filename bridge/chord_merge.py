"""
bridge/chord_merge.py —— 同时发音聚类 + 负 gap 修复（P0-3 核心）

命中需求: **P0-3**（和弦导入修复）、P1-1（力度）
关联发现:
    - **F5**：素材 PPQ = 220（不是 480），容差必须按 PPQ 比例推导（U1 已拍板）；
    - **F6**：`Chords_130406.mid` 的和弦是**严格同 tick** 的（0/880/1760/2640），
      容差取 0 都能正确聚类 → 无损判据可精确断言；
    - **F7**：`Bass/Piano_130406.mid` 未量化（onset 间隔 102–113），
      且 legato 重叠导致 `start_tick - prev_end_tick` 频繁为负 →
      `repair_negative_gaps()` 是**主路径必经步骤**，不是边界处理。

核心契约（决定 P0-3 是否无损）:
    notes[i]         = 簇内最低音（全音量，享有 octave_shifts）
    chords[i]        = 上方音列表（渲染器以 0.5 音量叠加）；单音簇 → []
    四个平行数组等长：len(notes) == len(durations) == len(chords) == len(octave_shifts)
    无损判据：sum(1 for n in notes if n) + sum(len(c) for c in chords) == 原始音符总数

约束: L2 领域层，纯函数，无 IO、无 mido → 可用构造数据单测。
"""

from __future__ import annotations

from typing import NamedTuple, Sequence

from .config import (
    CHORD_MIN_NOTES,
    CHORD_TOLERANCE_DIVISOR,
    DURATION_ROUND,
    MAX_REST_CHUNK_BEATS,
    MIN_NOTE_BEATS,
    REST_MIN_BEATS,
)
from .errors import IssueCode
from .models import BridgeIssue, NoteCluster, NoteEvent
from .note_range import fold_into_range, safe_note_and_shift

__all__ = [
    "ChordFields",
    "default_chord_tolerance",
    "cluster_simultaneous",
    "repair_negative_gaps",
    "clusters_to_pattern_fields",
    "lossless_note_count",
]


class ChordFields(NamedTuple):
    """`MusicPattern` 所需的平行数组集合。

    Attributes:
        notes: 音符名列表，None 表示休止符。
        durations: 每项时值（拍），与 notes 等长。
        chords: 每项的上方音列表，与 notes 等长；无和弦项为 []。
        octave_shifts: 每项的八度偏移，与 notes 等长。
        velocities: 每项的力度（休止符为 0），与 notes 等长。
        issues: 转换过程中累积的问题记录。
    """

    notes: list[str | None]
    durations: list[float]
    chords: list[list[str]]
    octave_shifts: list[int]
    velocities: list[int]
    issues: list[BridgeIssue]


def default_chord_tolerance(ticks_per_beat: int) -> int:
    """按 PPQ 比例推导和弦聚类容差（F5 / U1）。

    Args:
        ticks_per_beat: MIDI 文件的 PPQ。

    Returns:
        容差 tick 数 = max(1, round(ppq / 16))。
        220 → 14（=1/16 拍）；480 → 30（与 Q6 原始默认值完全吻合）。
    """
    if ticks_per_beat <= 0:
        return 1
    return max(1, round(ticks_per_beat / CHORD_TOLERANCE_DIVISOR))


def cluster_simultaneous(
    events: Sequence[NoteEvent],
    tolerance_ticks: int,
) -> list[NoteCluster]:
    """把「几乎同时」发声的音符归为一簇。

    算法（单趟扫描，复杂度取决于排序 O(n log n)）：
        1. events 按 (start_tick, midi_note) 升序；
        2. 若 `ev.start_tick - cluster.start_tick <= tolerance_ticks` → 并入当前簇；
           否则收口当前簇、开新簇；
        3. **簇锚点固定为簇内第一个音的 start_tick**（不用滑动均值）——
           否则 n 个间隔恰为 tol 的音会被链式串成一大簇（F7 的 Bass 素材就是这种形态）；
        4. 簇 end_tick = max(成员 end_tick)，保住延音踏板效果；
        5. members 按 midi_note 升序 → `root` 恒为最低音。

    Args:
        events: 已配对的音符事件序列。
        tolerance_ticks: 聚类容差（tick），< 0 时按 0 处理。

    Returns:
        按 start_tick 升序排列的簇列表。
    """
    if not events:
        return []
    tol = max(0, int(tolerance_ticks))
    ordered = sorted(events, key=lambda e: (e.start_tick, e.midi_note))

    clusters: list[NoteCluster] = []
    anchor: int = ordered[0].start_tick
    bucket: list[NoteEvent] = []

    for ev in ordered:
        if bucket and (ev.start_tick - anchor) > tol:
            clusters.append(_finalize_cluster(anchor, bucket))
            bucket = []
            anchor = ev.start_tick
        if not bucket:
            anchor = ev.start_tick
        bucket.append(ev)

    if bucket:
        clusters.append(_finalize_cluster(anchor, bucket))
    return clusters


def _finalize_cluster(anchor: int, members: list[NoteEvent]) -> NoteCluster:
    """收口一个簇：成员按音高升序，end_tick 取最长音。"""
    ordered_members = sorted(members, key=lambda e: (e.midi_note, e.start_tick))
    end_tick = max(e.end_tick for e in ordered_members)
    return NoteCluster(start_tick=anchor, end_tick=end_tick, members=ordered_members)


def repair_negative_gaps(
    clusters: list[NoteCluster],
    ticks_per_beat: int = 480,
) -> list[BridgeIssue]:
    """**原地**修复 legato 重叠导致的负 gap（F7）。

    对相邻簇 cur / nxt：
        - 若 `cur.end_tick > nxt.start_tick` → `cur.end_tick = nxt.start_tick`，
          记 `info` 级 `OVERLAP_TRUNCATED`；
        - 若截断后时值 < `MIN_NOTE_BEATS` 对应的 tick 数 → clamp 到下限，
          记 `warn` 级 `NOTE_TOO_SHORT`。

    Args:
        clusters: 待修复的簇列表（会被原地修改）。
        ticks_per_beat: PPQ，用于换算最短时值下限。

    Returns:
        issues 列表（调用方汇总，本函数**不抛异常**）。
    """
    issues: list[BridgeIssue] = []
    if len(clusters) < 1:
        return issues

    min_ticks = max(1, int(round(MIN_NOTE_BEATS * max(1, ticks_per_beat))))
    truncated = 0

    for cur, nxt in zip(clusters, clusters[1:]):
        if cur.end_tick > nxt.start_tick:
            truncated += 1
            cur.end_tick = nxt.start_tick
        if cur.duration_ticks < min_ticks:
            issues.append(
                BridgeIssue(
                    level="warn",
                    code=IssueCode.NOTE_TOO_SHORT,
                    message=(
                        f"簇时值 {cur.duration_ticks} tick 小于下限 {min_ticks} tick"
                        f"（1/64 拍），已 clamp。"
                    ),
                    context={"start_tick": cur.start_tick, "min_ticks": min_ticks},
                )
            )
            cur.end_tick = cur.start_tick + min_ticks

    # 末簇单独兜底（无后继可比对，只校验下限）
    last = clusters[-1]
    if last.duration_ticks < min_ticks:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.NOTE_TOO_SHORT,
                message=(
                    f"末簇时值 {last.duration_ticks} tick 小于下限 {min_ticks} tick，已 clamp。"
                ),
                context={"start_tick": last.start_tick, "min_ticks": min_ticks},
            )
        )
        last.end_tick = last.start_tick + min_ticks

    if truncated:
        issues.insert(
            0,
            BridgeIssue(
                level="info",
                code=IssueCode.OVERLAP_TRUNCATED,
                message=f"检出 {truncated} 处 legato 重叠（负 gap），已按后一簇起点截断。",
                context={"count": truncated},
            ),
        )
    return issues


def clusters_to_pattern_fields(
    clusters: Sequence[NoteCluster],
    ticks_per_beat: int,
    *,
    chord_min_notes: int = CHORD_MIN_NOTES,
) -> ChordFields:
    """把簇序列翻译成 `MusicPattern` 的平行数组。

    Args:
        clusters: 已修复负 gap 的簇序列（须按 start_tick 升序）。
        ticks_per_beat: PPQ，用于 tick → 拍 换算。
        chord_min_notes: 达到该规模才在报告中被称作「和弦」；
            **注意**：为保证零丢失，低于该阈值的上方音**仍然保留**在 chords 中，
            该参数只影响 issue 文案与统计，不会丢弃任何音符。

    Returns:
        ChordFields（notes / durations / chords / octave_shifts / velocities / issues）。

    Note:
        - 簇间 gap >= `REST_MIN_BEATS`（1/4 拍）→ 插入 `notes=None` 的休止，
          并拆成 <= 1.0 拍的块；更小的 gap 视为演奏释音，并入前一项时值。
        - 四个平行数组严格等长：`MusicPattern.__post_init__` 会强校验
          notes/durations，而渲染器用 `chords[idx % len(chords)]` 按下标取，
          chords 必须同步等长否则和弦会错位。
    """
    notes: list[str | None] = []
    durations: list[float] = []
    chords: list[list[str]] = []
    octave_shifts: list[int] = []
    velocities: list[int] = []
    issues: list[BridgeIssue] = []

    ppq = max(1, int(ticks_per_beat))
    folded_count = 0
    shifted_count = 0
    merged_gap_count = 0
    chord_cluster_count = 0

    prev_end_tick = 0
    for cluster in clusters:
        if not cluster.members:
            continue

        # ── 1. 休止符（簇间 gap）──
        gap_ticks = cluster.start_tick - prev_end_tick
        if gap_ticks > 0:
            gap_beats = gap_ticks / ppq
            if gap_beats < REST_MIN_BEATS and durations:
                # 释音间隙（< 1/4 拍）：并入前一项，保持时间轴总长不变，
                # 且不把「音 + 微休止」劈成两个 pattern 项。
                durations[-1] = round(durations[-1] + gap_beats, DURATION_ROUND)
                merged_gap_count += 1
            elif gap_beats >= REST_MIN_BEATS or (
                gap_beats >= MIN_NOTE_BEATS and not durations
            ):
                # 真休止；首簇之前的空拍即使很短也要保留，否则整轨会整体提前
                remaining = gap_beats
                while remaining > 1e-9:
                    chunk = min(remaining, MAX_REST_CHUNK_BEATS)
                    notes.append(None)
                    durations.append(round(chunk, DURATION_ROUND))
                    chords.append([])
                    octave_shifts.append(0)
                    velocities.append(0)
                    remaining -= chunk

        # ── 2. 根音（最低音）——享有 octave_shift，音高无损 ──
        root = cluster.root
        root_name, root_shift = safe_note_and_shift(root.midi_note)
        if root_shift != 0:
            shifted_count += 1

        # ── 3. 上方音 —— 必须折叠进 C0–C7（F10：和弦分支不施加 octave_shift）──
        upper_names: list[str] = []
        for member in cluster.upper:
            name, folded = fold_into_range(member.midi_note)
            if folded != 0:
                folded_count += 1
            upper_names.append(name)

        if cluster.size >= chord_min_notes:
            chord_cluster_count += 1

        # ── 4. 时值 ──
        dur_beats = cluster.duration_ticks / ppq
        dur_beats = max(MIN_NOTE_BEATS, round(dur_beats, DURATION_ROUND))

        notes.append(root_name)
        durations.append(dur_beats)
        chords.append(upper_names)
        octave_shifts.append(root_shift)
        velocities.append(int(round(cluster.mean_velocity)))

        prev_end_tick = cluster.end_tick

    # ── 5. 汇总 issue ──
    if shifted_count:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.PITCH_OUT_OF_RANGE,
                message=(
                    f"{shifted_count} 个根音超出 C0–C7 可渲染域，"
                    f"已转为 octave_shift 表达（音高无损）。"
                ),
                context={"count": shifted_count},
            )
        )
    if folded_count:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.CHORD_PITCH_FOLDED,
                message=(
                    f"{folded_count} 个和弦上方音超出 C0–C7，已折叠八度"
                    f"（渲染器和弦分支不支持 octave_shift，F10）。"
                ),
                context={"count": folded_count},
            )
        )
    if merged_gap_count:
        issues.append(
            BridgeIssue(
                level="info",
                code=IssueCode.TINY_GAP_MERGED,
                message=f"{merged_gap_count} 处小于 1/4 拍的释音间隙已并入前一音时值。",
                context={"count": merged_gap_count},
            )
        )

    assert len(notes) == len(durations) == len(chords) == len(octave_shifts) == len(velocities)
    return ChordFields(notes, durations, chords, octave_shifts, velocities, issues)


def lossless_note_count(fields: ChordFields) -> int:
    """按无损判据统计 pattern 中真实承载的音符总数。

    Args:
        fields: `clusters_to_pattern_fields` 的产物。

    Returns:
        `sum(1 for n in notes if n) + sum(len(c) for c in chords)`。
        该值应等于源 MIDI 轨的音符总数（P0-3 的核心验收指标）。
    """
    root_count = sum(1 for n in fields.notes if n is not None)
    upper_count = sum(len(c) for c in fields.chords)
    return root_count + upper_count
