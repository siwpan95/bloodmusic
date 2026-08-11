"""
bridge/models.py —— 跨模块数据契约（全部 dataclass）

命中需求: P0-2 / P0-3 / P0-4 / P0-5 / P1-4
关联发现: F5（ticks_per_beat 是 220 不是 480）、F8（鼓 steps 可 > 16）

约束:
    - L1 层，零 IO、零 mido；
    - `ImportResult` 是 scanner / midi_import / renderer / report 四方共用的契约，
      必须独立成文件以免循环 import。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ..music.pattern import DrumPattern, MultiTrackPattern, MusicPattern

__all__ = [
    "MidiAsset",
    "NoteEvent",
    "NoteCluster",
    "TrackAnalysis",
    "BridgeIssue",
    "ImportResult",
    "RenderResult",
    "BridgeReport",
    "AssetProbe",
]

#: GM 鼓通道（MIDI 通道 10，0-based 为 9）
GM_DRUM_CHANNEL: int = 9


@dataclass(frozen=True, slots=True)
class MidiAsset:
    """一个被扫描到的 MIDI 资产（只读元信息，不含音符）。

    Attributes:
        path: 绝对路径。
        name: 文件名（不含扩展名），如 "Drum Kit_130406"。
        rel_path: 相对扫描根的 POSIX 风格路径，用于稳定排序与报告。
        source_group: 相对根的首级目录名，如 "MusicStudio" / "pro4"。
        size_bytes: 文件字节数。
        mtime_ns: 最后修改时间（纳秒），用于只读性快照比对。
    """

    path: Path
    name: str
    rel_path: str
    source_group: str
    size_bytes: int
    mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "path": str(self.path),
            "name": self.name,
            "rel_path": self.rel_path,
            "source_group": self.source_group,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
        }


@dataclass(slots=True)
class NoteEvent:
    """一个已配对（note_on/note_off）的音符事件，时间单位为绝对 tick。"""

    start_tick: int
    end_tick: int
    midi_note: int
    velocity: int
    channel: int
    track_index: int

    @property
    def duration_ticks(self) -> int:
        """时值（tick）；负值被夹为 0。"""
        return max(0, self.end_tick - self.start_tick)

    @property
    def is_drum(self) -> bool:
        """是否位于 GM 鼓通道（channel == 9）。"""
        return self.channel == GM_DRUM_CHANNEL


@dataclass(slots=True)
class NoteCluster:
    """一个「同时发音簇」：单音时 size == 1，和弦时 size >= 2。

    Attributes:
        start_tick: 簇锚点（簇内第一个音的 start_tick，避免容差链式漂移）。
        end_tick: 修复负 gap 后的最终收口 tick。
        members: 簇成员，按 midi_note 升序，故 members[0] 恒为最低音。
    """

    start_tick: int
    end_tick: int
    members: list[NoteEvent] = field(default_factory=list)

    @property
    def root(self) -> NoteEvent:
        """簇内最低音（根音）。"""
        return self.members[0]

    @property
    def upper(self) -> list[NoteEvent]:
        """根音之上的所有音（和弦上方音）。"""
        return self.members[1:]

    @property
    def size(self) -> int:
        """簇内音符数。"""
        return len(self.members)

    @property
    def duration_ticks(self) -> int:
        """簇时值（tick）。"""
        return max(0, self.end_tick - self.start_tick)

    @property
    def mean_velocity(self) -> float:
        """簇内平均力度；空簇返回 0.0。"""
        if not self.members:
            return 0.0
        return sum(m.velocity for m in self.members) / len(self.members)


@dataclass(slots=True)
class TrackAnalysis:
    """单条 MIDI 轨的静态分析结果。"""

    track_index: int
    name: str
    channel: int | None = None
    program: int | None = None
    is_drum: bool = False
    kind: Literal["melody", "chord", "drum", "empty"] = "empty"
    note_count: int = 0
    max_polyphony: int = 0
    pitch_min: int | None = None
    pitch_max: int | None = None
    span_ticks: int = 0
    pattern_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "track_index": self.track_index,
            "name": self.name,
            "channel": self.channel,
            "program": self.program,
            "is_drum": self.is_drum,
            "kind": self.kind,
            "note_count": self.note_count,
            "max_polyphony": self.max_polyphony,
            "pitch_min": self.pitch_min,
            "pitch_max": self.pitch_max,
            "span_ticks": self.span_ticks,
            "pattern_names": list(self.pattern_names),
        }


@dataclass(slots=True)
class BridgeIssue:
    """一条分级问题记录（批量流程不抛异常，统一汇总为 issue）。"""

    level: Literal["info", "warn", "error"]
    code: str
    message: str
    context: dict = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        """是否为 error 级。"""
        return self.level == "error"

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "context": {k: _jsonable(v) for k, v in self.context.items()},
        }

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}: {self.message}"


@dataclass(slots=True)
class ImportResult:
    """一个 MIDI 文件的完整导入产物。"""

    source: Path
    bpm: int = 120
    ticks_per_beat: int = 480
    total_beats: float = 0.0
    beats_per_bar: int = 4
    melody_patterns: list[MusicPattern] = field(default_factory=list)
    chord_patterns: list[MusicPattern] = field(default_factory=list)
    drum_patterns: list[DrumPattern] = field(default_factory=list)
    multi_track: MultiTrackPattern | None = None
    analyses: list[TrackAnalysis] = field(default_factory=list)
    issues: list[BridgeIssue] = field(default_factory=list)
    #: pattern 名 → 附加元信息（track_index / program / channel / kind / velocities）
    #: P1-2 DAW 回流需要逐音力度与 GM program，MusicPattern 本身无此字段
    pattern_meta: dict[str, dict] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """无 error 级 issue 即视为成功。"""
        return not any(i.is_error for i in self.issues)

    @property
    def all_music_patterns(self) -> list[MusicPattern]:
        """旋律 + 和弦 pattern 的合集（顺序稳定）。"""
        return list(self.melody_patterns) + list(self.chord_patterns)

    @property
    def all_patterns(self) -> list:
        """全部 pattern（旋律 + 和弦 + 鼓）。"""
        return self.all_music_patterns + list(self.drum_patterns)

    @property
    def duration_sec(self) -> float:
        """按 total_beats 精确反推的时长（秒）——D6：绝不用拍脑袋时长。"""
        if self.bpm <= 0:
            return 0.0
        return self.total_beats * 60.0 / float(self.bpm)

    @property
    def stem(self) -> str:
        """源文件名（不含扩展名）。"""
        return Path(self.source).stem

    def issues_by_level(self, level: str) -> list[BridgeIssue]:
        """按级别筛选 issue。"""
        return [i for i in self.issues if i.level == level]

    def has_code(self, code: str) -> bool:
        """是否存在指定错误码的 issue。"""
        return any(i.code == code for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典（写 import.json / report.json）。"""
        return {
            "source": str(self.source),
            "stem": self.stem,
            "bpm": self.bpm,
            "ticks_per_beat": self.ticks_per_beat,
            "total_beats": self.total_beats,
            "beats_per_bar": self.beats_per_bar,
            "duration_sec": round(self.duration_sec, 6),
            "ok": self.ok,
            "melody_patterns": [_music_pattern_to_dict(p) for p in self.melody_patterns],
            "chord_patterns": [_music_pattern_to_dict(p) for p in self.chord_patterns],
            "drum_patterns": [_drum_pattern_to_dict(p) for p in self.drum_patterns],
            "multi_track": (
                None
                if self.multi_track is None
                else {
                    "name": self.multi_track.name,
                    "bpm": self.multi_track.bpm,
                    "loop": self.multi_track.loop,
                    "music_tracks": [t.name for t in self.multi_track.music_tracks],
                    "drum_track": (
                        self.multi_track.drum_track.name
                        if self.multi_track.drum_track is not None
                        else None
                    ),
                }
            ),
            "analyses": [a.to_dict() for a in self.analyses],
            "issues": [i.to_dict() for i in self.issues],
            "pattern_meta": {k: _jsonable(v) for k, v in self.pattern_meta.items()},
        }

    def to_json(self, *, indent: int = 2) -> str:
        """序列化为 JSON 文本。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass(slots=True)
class RenderResult:
    """一次渲染作业的产物。"""

    source: Path
    audio_files: list[Path] = field(default_factory=list)
    duration_sec: float = 0.0
    fmt: str = "wav"
    out_dir: Path | None = None
    issues: list[BridgeIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """无 error 级 issue 即视为成功。"""
        return not any(i.is_error for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "source": str(self.source),
            "out_dir": str(self.out_dir) if self.out_dir else None,
            "audio_files": [str(p) for p in self.audio_files],
            "duration_sec": round(self.duration_sec, 6),
            "fmt": self.fmt,
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(slots=True)
class AssetProbe:
    """`scan` 子命令表格所需的轻量探测结果（不构造 pattern）。

    说明：设计文档 §3.11 要求 `scan` 输出「轨数 / BPM / 时长 / 鼓轨 / 和弦」列，
    这些列必须读文件头才能得到，故单列一个轻量探测结构，
    避免把 mido 依赖渗入纯文件系统的 scanner。
    """

    path: Path
    track_count: int = 0
    bpm: int = 0
    duration_sec: float = 0.0
    ticks_per_beat: int = 0
    note_count: int = 0
    has_drum: bool = False
    has_chord: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "path": str(self.path),
            "track_count": self.track_count,
            "bpm": self.bpm,
            "duration_sec": round(self.duration_sec, 3),
            "ticks_per_beat": self.ticks_per_beat,
            "note_count": self.note_count,
            "has_drum": self.has_drum,
            "has_chord": self.has_chord,
            "error": self.error,
        }


@dataclass(slots=True)
class BridgeReport:
    """一次批量作业的结构化报告（P1-4）。"""

    root: Path
    scanned: list[MidiAsset] = field(default_factory=list)
    imported: list[ImportResult] = field(default_factory=list)
    rendered: list[RenderResult] = field(default_factory=list)
    issues: list[BridgeIssue] = field(default_factory=list)
    elapsed_sec: float = 0.0
    command: str = ""

    @property
    def all_issues(self) -> list[BridgeIssue]:
        """全局 issue + 各文件 issue 的合集。"""
        merged: list[BridgeIssue] = list(self.issues)
        for r in self.imported:
            merged.extend(r.issues)
        for rr in self.rendered:
            merged.extend(rr.issues)
        return merged

    def summary(self) -> dict[str, Any]:
        """分级汇总。

        Returns:
            {scanned, imported, ok, failed, error, warn, info, audio_files, elapsed_sec}
        """
        merged = self.all_issues
        return {
            "scanned": len(self.scanned),
            "imported": len(self.imported),
            "ok": sum(1 for r in self.imported if r.ok),
            "failed": sum(1 for r in self.imported if not r.ok),
            "error": sum(1 for i in merged if i.level == "error"),
            "warn": sum(1 for i in merged if i.level == "warn"),
            "info": sum(1 for i in merged if i.level == "info"),
            "audio_files": sum(len(r.audio_files) for r in self.rendered),
            "elapsed_sec": round(self.elapsed_sec, 3),
        }

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "command": self.command,
            "root": str(self.root),
            "summary": self.summary(),
            "scanned": [a.to_dict() for a in self.scanned],
            "imported": [r.to_dict() for r in self.imported],
            "rendered": [r.to_dict() for r in self.rendered],
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_json(self, *, indent: int = 2) -> str:
        """序列化为 JSON 文本。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        """生成人读的 Markdown 报告。"""
        s = self.summary()
        lines: list[str] = [
            "# BloodMusic bridge 批量报告",
            "",
            f"- 命令: `{self.command or '-'}`",
            f"- 扫描根: `{self.root}`",
            f"- 扫描到: **{s['scanned']}** 个 MIDI 资产",
            f"- 导入: **{s['imported']}**（成功 {s['ok']} / 失败 {s['failed']}）",
            f"- 音频产物: **{s['audio_files']}** 个",
            f"- 问题: error **{s['error']}** / warn **{s['warn']}** / info **{s['info']}**",
            f"- 耗时: {s['elapsed_sec']} s",
            "",
            "## 资产清单",
            "",
            "| # | 文件 | 分组 | 大小(B) |",
            "|---:|---|---|---:|",
        ]
        for idx, asset in enumerate(self.scanned, start=1):
            lines.append(
                f"| {idx} | `{asset.rel_path}` | {asset.source_group} | {asset.size_bytes} |"
            )

        lines += [
            "",
            "## 导入结果",
            "",
            "| 文件 | BPM | PPQ | 拍数 | 旋律 | 和弦 | 鼓 | 状态 |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for r in self.imported:
            lines.append(
                f"| `{r.stem}` | {r.bpm} | {r.ticks_per_beat} | {r.total_beats:g} | "
                f"{len(r.melody_patterns)} | {len(r.chord_patterns)} | "
                f"{len(r.drum_patterns)} | {'OK' if r.ok else 'FAILED'} |"
            )

        if self.rendered:
            lines += [
                "",
                "## 渲染结果",
                "",
                "| 文件 | 时长(s) | 格式 | 产物数 |",
                "|---|---:|---|---:|",
            ]
            for rr in self.rendered:
                lines.append(
                    f"| `{Path(rr.source).stem}` | {rr.duration_sec:.3f} | "
                    f"{rr.fmt} | {len(rr.audio_files)} |"
                )

        merged = self.all_issues
        if merged:
            lines += [
                "",
                "## 问题明细",
                "",
                "| 级别 | 代码 | 描述 |",
                "|---|---|---|",
            ]
            for issue in merged:
                msg = issue.message.replace("|", "\\|")
                lines.append(f"| {issue.level} | `{issue.code}` | {msg} |")

        lines.append("")
        return "\n".join(lines)


# ──────────────────────────────── 内部辅助 ────────────────────────────────


def _jsonable(value: Any) -> Any:
    """把任意值转成 JSON 可序列化形式（尽力而为，绝不抛异常）。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return str(value)
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    enum_value = getattr(value, "value", None)
    if enum_value is not None and hasattr(value, "name"):
        return _jsonable(enum_value)
    return str(value)


def _music_pattern_to_dict(p: MusicPattern) -> dict[str, Any]:
    """MusicPattern → dict（仅导出 bridge 关心的字段）。"""
    return {
        "name": p.name,
        "bpm": p.bpm,
        "loop": p.loop,
        "notes": list(p.notes),
        "durations": [float(d) for d in p.durations],
        "octave_shifts": list(p.octave_shifts) if p.octave_shifts else None,
        "chords": [list(c) for c in p.chords] if p.chords else None,
        "osc_type": getattr(p.osc_type, "value", str(p.osc_type)),
        "env_shape": getattr(p.env_shape, "value", str(p.env_shape)),
        "volume": round(float(p.volume), 6),
        "lp_filter_hz": p.lp_filter_hz,
        "reverb_mix": p.reverb_mix,
        "total_beats": round(float(sum(p.durations)), 6),
    }


def _drum_pattern_to_dict(p: DrumPattern) -> dict[str, Any]:
    """DrumPattern → dict（步进矩阵用 0/1 列表表达，便于 diff）。"""
    return {
        "name": p.name,
        "bpm": p.bpm,
        "loop": p.loop,
        "steps": p.steps,
        "tracks": {k: [1 if v else 0 for v in seq] for k, seq in p.tracks.items()},
        "hits": {k: int(sum(1 for v in seq if v)) for k, seq in p.tracks.items()},
        "total_hits": int(sum(sum(1 for v in seq if v) for seq in p.tracks.values())),
        "sounds": sorted(p.sounds.keys()),
    }
