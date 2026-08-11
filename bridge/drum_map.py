"""
bridge/drum_map.py —— GM 鼓映射反转 + 十六分网格量化（P0-4 核心）

命中需求: **P0-4**（鼓轨识别与还原）
关联发现:
    - **F8**：两个鼓素材跨度都是 ~15.7 拍 ≈ 4 小节 = 64 个十六分步；
      若把 `DrumPattern.steps` 写死 16 会直接丢弃 3/4 的鼓点 →
      `drum_bar_policy="extend"`（默认）让 steps = 网格 × 小节数（U2 已拍板）；
    - **F9**：`render_drum_pattern()` 的 `step_dur` 硬编码为 `beat/4`，与 steps 无关，
      因此 extend 策略下渲染侧**零改造**；但 32 网格本期不支持，
      传入即报 `DRUM_GRID_UNSUPPORTED` 并回退 16（U3 已拍板）。

复用（R4 只读，不得修改）:
    - `export/midi_export.py::MIDI_DRUM_MAP`（一对多别名，反转需消歧）
    - `music/presets.py` 第 255–257 行的鼓音色基线数值

约束: L2 领域层，纯函数，无 IO、无 mido。
"""

from __future__ import annotations

import math
from typing import Iterable, Literal, NamedTuple, Sequence

from ..core.oscillator import OscType
from ..export.midi_export import MIDI_DRUM_MAP
from ..music.pattern import DrumSoundParams
from .config import BEATS_PER_BAR, DEFAULT_DRUM_GRID, SUPPORTED_DRUM_GRIDS
from .errors import IssueCode
from .models import BridgeIssue, NoteEvent

__all__ = [
    "CANONICAL_DRUM_NOTES",
    "DRUM_SOUND_BASELINE",
    "DrumGrid",
    "build_reverse_drum_map",
    "midi_note_to_drum_track",
    "quantize_to_steps",
    "default_drum_sounds",
]

#: 由 MIDI_DRUM_MAP 反转而来的**规范名**优先表（消歧用）。
#: MIDI_DRUM_MAP 中 36 同时对应 kick/bass_drum/bd，反转时以本表为准。
CANONICAL_DRUM_NOTES: dict[int, str] = {
    36: "kick",
    37: "rimshot",
    38: "snare",
    39: "clap",
    41: "low_tom",
    42: "hihat",
    44: "hihat_pedal",
    45: "mid_tom",
    46: "hihat_open",
    48: "high_tom",
    49: "crash",
    51: "ride",
    54: "tambourine",
    56: "cowbell",
    70: "shaker",
}

#: 鼓音色基线（数值直接沿用 music/presets.py:255-257 的 `_mk_drum` 默认值）
DRUM_SOUND_BASELINE: dict[str, DrumSoundParams] = {
    "kick": DrumSoundParams(osc_type=OscType.SINE, pitch_hz=55, decay=0.22, volume=0.8),
    "snare": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=180, decay=0.15, hp_hz=250, volume=0.65
    ),
    "hihat": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=8000, decay=0.06, hp_hz=1500, volume=0.35
    ),
    # ── 以下为基于上述三条基线的合理外推 ──
    "hihat_open": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=7000, decay=0.22, hp_hz=1200, volume=0.32
    ),
    "hihat_pedal": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=6000, decay=0.05, hp_hz=1000, volume=0.28
    ),
    "clap": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=1200, decay=0.12, hp_hz=600, volume=0.55
    ),
    "rimshot": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=2000, decay=0.05, hp_hz=800, volume=0.45
    ),
    "low_tom": DrumSoundParams(osc_type=OscType.SINE, pitch_hz=100, decay=0.28, volume=0.6),
    "mid_tom": DrumSoundParams(osc_type=OscType.SINE, pitch_hz=150, decay=0.24, volume=0.6),
    "high_tom": DrumSoundParams(osc_type=OscType.SINE, pitch_hz=220, decay=0.2, volume=0.6),
    "crash": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=9000, decay=0.9, hp_hz=2500, volume=0.34
    ),
    "ride": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=7500, decay=0.55, hp_hz=2000, volume=0.3
    ),
    "cowbell": DrumSoundParams(osc_type=OscType.SQUARE, pitch_hz=540, decay=0.12, volume=0.4),
    "tambourine": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=6500, decay=0.14, hp_hz=3000, volume=0.3
    ),
    "shaker": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=8500, decay=0.07, hp_hz=4000, volume=0.26
    ),
}

#: 未知鼓件的通用兜底音色
_FALLBACK_DRUM_SOUND = DrumSoundParams(
    osc_type=OscType.NOISE_WHITE, pitch_hz=1500, decay=0.1, hp_hz=400, volume=0.4
)


class DrumGrid(NamedTuple):
    """鼓量化产物。

    Attributes:
        tracks: 步进矩阵 {鼓件名: [bool] * steps}（extend/fold 策略）。
        steps: 每个 DrumPattern 的步数。
        bars: 小节数。
        groups: 分组步进矩阵；extend/fold 为单元素列表，
            split 策略下每小节一组（调用方据此生成多个 DrumPattern）。
        issues: 量化过程中累积的问题记录。
    """

    tracks: dict[str, list[bool]]
    steps: int
    bars: int
    groups: list[dict[str, list[bool]]]
    issues: list[BridgeIssue]


def build_reverse_drum_map(extra: dict[str, int] | None = None) -> dict[int, str]:
    """反转 `MIDI_DRUM_MAP`（一对多别名 → 单一规范名）。

    消歧策略：先用 `CANONICAL_DRUM_NOTES` 覆盖，再补 `MIDI_DRUM_MAP`
    中尚未覆盖的音符号（同一音符号有多个别名时取字典序最短者，结果确定）。

    Args:
        extra: 额外的 {别名: 音符号} 映射，会一并参与反转。

    Returns:
        {MIDI 音符号: 规范鼓件名}。
    """
    forward: dict[str, int] = dict(MIDI_DRUM_MAP)
    if extra:
        forward.update(extra)

    reverse: dict[int, str] = {}
    for alias, note in sorted(forward.items(), key=lambda kv: (kv[1], len(kv[0]), kv[0])):
        reverse.setdefault(int(note), str(alias))

    # 规范名优先覆盖（保证 36 → "kick" 而不是 "bd"）
    reverse.update(CANONICAL_DRUM_NOTES)
    return reverse


def midi_note_to_drum_track(
    midi_note: int,
    reverse_map: dict[int, str] | None = None,
) -> str:
    """MIDI 鼓音符号 → 鼓轨名。

    未知音符号返回 `perc_<n>`（**不丢弃**，保证鼓点零丢失），
    调用方应记 `BridgeIssue('info', 'UNMAPPED_DRUM_NOTE')`。

    Args:
        midi_note: MIDI 音符号。
        reverse_map: 反转映射；None → 现场构建。

    Returns:
        规范鼓件名，如 "kick" / "snare" / "perc_60"。
    """
    table = reverse_map if reverse_map is not None else build_reverse_drum_map()
    return table.get(int(midi_note), f"perc_{int(midi_note)}")


def quantize_to_steps(
    events: Sequence[NoteEvent],
    ticks_per_beat: int,
    *,
    grid: int = DEFAULT_DRUM_GRID,
    beats_per_bar: int = BEATS_PER_BAR,
    policy: Literal["extend", "fold", "split"] = "extend",
    reverse_map: dict[int, str] | None = None,
) -> DrumGrid:
    """MIDI 鼓事件 → `DrumPattern.tracks` 步进矩阵。

    要点：
        - `step_ticks = ticks_per_beat * beats_per_bar / grid`（220*4/16 = 55）；
        - `step_index = round(start_tick / step_ticks)`（四舍五入，非截断）；
        - 量化误差 > 25% 步长 → `warn` 级 `DRUM_QUANTIZE_DRIFT`
          （实测 6 素材 onset 全为 55 的整数倍，误差恒为 0）；
        - policy="extend"（默认）：`bars = ceil((max_step+1)/grid)`，`steps = bars*grid`
          → 两个鼓素材均得 steps = 64，信息零丢失（F8）；
        - policy="fold"：steps = grid，各小节按位 OR；
        - policy="split"：返回 bars 组，每组 steps = grid；
        - `grid not in SUPPORTED_DRUM_GRIDS` → `error` 级 `DRUM_GRID_UNSUPPORTED`
          并回退 16（F9 / U3）。

    Args:
        events: 鼓轨的音符事件序列。
        ticks_per_beat: PPQ。
        grid: 每小节步数。
        beats_per_bar: 每小节拍数。
        policy: 小节策略。
        reverse_map: 鼓音符反转映射；None → 现场构建。

    Returns:
        DrumGrid。
    """
    issues: list[BridgeIssue] = []

    # ── 网格校验（F9 / U3：32 步本期必须报错并回退 16）──
    effective_grid = int(grid)
    if effective_grid not in SUPPORTED_DRUM_GRIDS:
        issues.append(
            BridgeIssue(
                level="error",
                code=IssueCode.DRUM_GRID_UNSUPPORTED,
                message=(
                    f"鼓网格 {effective_grid} 本期不支持"
                    f"（render_drum_pattern 的 step_dur 硬编码为 beat/4，F9），"
                    f"已回退到 {DEFAULT_DRUM_GRID}。"
                ),
                context={"requested": effective_grid, "fallback": DEFAULT_DRUM_GRID},
            )
        )
        effective_grid = DEFAULT_DRUM_GRID

    policy_name = str(policy).lower()
    if policy_name not in ("extend", "fold", "split"):
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.DRUM_BAR_POLICY_UNSUPPORTED,
                message=f"未知的 drum_bar_policy '{policy}'，已回退 'extend'。",
                context={"requested": str(policy)},
            )
        )
        policy_name = "extend"

    bpb = max(1, int(beats_per_bar))
    ppq = max(1, int(ticks_per_beat))
    step_ticks = ppq * bpb / float(effective_grid)

    if not events:
        return DrumGrid(tracks={}, steps=effective_grid, bars=1, groups=[{}], issues=issues)

    table = reverse_map if reverse_map is not None else build_reverse_drum_map()

    # ── 逐事件量化 ──
    hits: dict[str, set[int]] = {}
    unmapped: set[int] = set()
    drift_max = 0.0
    collapsed = 0
    raw_hit_count = 0

    for ev in events:
        track_name = table.get(int(ev.midi_note))
        if track_name is None:
            track_name = f"perc_{int(ev.midi_note)}"
            unmapped.add(int(ev.midi_note))

        step_index = int(round(ev.start_tick / step_ticks))
        drift = abs(ev.start_tick - step_index * step_ticks)
        drift_max = max(drift_max, drift)

        bucket = hits.setdefault(track_name, set())
        raw_hit_count += 1
        if step_index in bucket:
            collapsed += 1
        bucket.add(step_index)

    max_step = max(max(v) for v in hits.values()) if hits else 0
    bars = max(1, math.ceil((max_step + 1) / effective_grid))

    if drift_max > step_ticks * 0.25:
        issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.DRUM_QUANTIZE_DRIFT,
                message=(
                    f"鼓量化最大误差 {drift_max:.1f} tick 超过 25% 步长"
                    f"（步长 {step_ticks:.1f} tick），节奏可能被拉直。"
                ),
                context={"drift_ticks": round(drift_max, 2), "step_ticks": round(step_ticks, 2)},
            )
        )
    if collapsed:
        issues.append(
            BridgeIssue(
                level="info",
                code=IssueCode.DRUM_STEP_COLLAPSED,
                message=f"{collapsed} 次同步同鼓件的重复触发被合并（步进矩阵是布尔量）。",
                context={"count": collapsed},
            )
        )
    if unmapped:
        issues.append(
            BridgeIssue(
                level="info",
                code=IssueCode.UNMAPPED_DRUM_NOTE,
                message=(
                    f"未知鼓音符号 {sorted(unmapped)} 已映射为 perc_<n> 轨（不丢弃）。"
                ),
                context={"notes": sorted(unmapped)},
            )
        )

    # ── 按策略装配步进矩阵 ──
    if policy_name == "fold":
        steps = effective_grid
        tracks = {
            name: _to_bool_row({s % effective_grid for s in idxs}, steps)
            for name, idxs in sorted(hits.items())
        }
        return DrumGrid(tracks=tracks, steps=steps, bars=bars, groups=[tracks], issues=issues)

    if policy_name == "split":
        groups: list[dict[str, list[bool]]] = []
        for bar in range(bars):
            lo = bar * effective_grid
            hi = lo + effective_grid
            bar_tracks = {
                name: _to_bool_row({s - lo for s in idxs if lo <= s < hi}, effective_grid)
                for name, idxs in sorted(hits.items())
            }
            groups.append(bar_tracks)
        first = groups[0] if groups else {}
        return DrumGrid(
            tracks=first, steps=effective_grid, bars=bars, groups=groups, issues=issues
        )

    # extend（默认）
    steps = bars * effective_grid
    tracks = {name: _to_bool_row(idxs, steps) for name, idxs in sorted(hits.items())}
    return DrumGrid(tracks=tracks, steps=steps, bars=bars, groups=[tracks], issues=issues)


def _to_bool_row(step_indices: Iterable[int], steps: int) -> list[bool]:
    """把步索引集合展开为定长布尔数组。"""
    row = [False] * steps
    for idx in step_indices:
        if 0 <= idx < steps:
            row[idx] = True
    return row


def default_drum_sounds(track_names: Iterable[str]) -> dict[str, DrumSoundParams]:
    """为每个鼓轨提供合成参数。

    必须为 tracks 中**每一个** key 都提供 sounds，
    否则 `DrumPattern.__post_init__`（pattern.py:118）会发出 warnings.warn。

    Args:
        track_names: 鼓轨名集合。

    Returns:
        {鼓件名: DrumSoundParams}。未知 perc_* 使用通用兜底音色。
    """
    sounds: dict[str, DrumSoundParams] = {}
    for name in track_names:
        baseline = DRUM_SOUND_BASELINE.get(name)
        if baseline is None:
            sounds[name] = DrumSoundParams(
                osc_type=_FALLBACK_DRUM_SOUND.osc_type,
                pitch_hz=_FALLBACK_DRUM_SOUND.pitch_hz,
                decay=_FALLBACK_DRUM_SOUND.decay,
                volume=_FALLBACK_DRUM_SOUND.volume,
                hp_hz=_FALLBACK_DRUM_SOUND.hp_hz,
                lp_hz=_FALLBACK_DRUM_SOUND.lp_hz,
            )
        else:
            # 复制一份，避免多个 pattern 共享同一实例后被意外改写
            sounds[name] = DrumSoundParams(
                osc_type=baseline.osc_type,
                pitch_hz=baseline.pitch_hz,
                decay=baseline.decay,
                volume=baseline.volume,
                hp_hz=baseline.hp_hz,
                lp_hz=baseline.lp_hz,
            )
    return sounds
