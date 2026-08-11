"""
bloodmusic.bridge —— MIDI 素材库 × BloodMusic 合成引擎 桥接子包

定位:
    把 `G:/midi` 下的历史 MIDI 素材无损导入 BloodMusic 的 pattern 体系，
    复用本体渲染管线产出音频，并可把 pattern 回流成 DAW 可用的 `bm_*.mid`。

依赖方向（R7，单向，不可逆）:
    bridge  ──依赖──▶  bloodmusic 本体（core / music / export）
    bloodmusic 本体   ──绝不 import──▶  bridge

    因此 `bloodmusic/__init__.py` **没有**、也不应该 eager import 本子包（R6）；
    使用时显式 `from bloodmusic.bridge import ...` 或 `python -m bloodmusic.bridge`。

本模块是纯门面：只做 re-export，不含任何业务逻辑。

Example:
    >>> from bloodmusic.bridge import scan_midi_assets, midi_to_patterns_v2
    >>> assets = scan_midi_assets("G:/midi")                    # doctest: +SKIP
    >>> result = midi_to_patterns_v2(assets[0].path)            # doctest: +SKIP
    >>> result.ticks_per_beat                                   # doctest: +SKIP
    220
"""

from __future__ import annotations

from .chord_merge import (
    ChordFields,
    cluster_simultaneous,
    clusters_to_pattern_fields,
    default_chord_tolerance,
    lossless_note_count,
    repair_negative_gaps,
)
from .config import (
    BRIDGE_VERSION,
    DEFAULT_DAW_MIDI_DIRS,
    DEFAULT_DRUM_BAR_POLICY,
    DEFAULT_DRUM_GRID,
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SCAN_ROOT,
    BridgeConfig,
    assert_write_allowed,
    is_under_readonly_root,
)
from .daw_export import (
    DAW_MIDI_DIR,
    DAW_MIDI_DIRS,
    assert_daw_write_allowed,
    export_import_result_to_daw,
    resolve_daw_dir_for_source,
    write_drum_pattern_midi,
    write_music_pattern_midi,
)
from .drum_map import (
    build_reverse_drum_map,
    default_drum_sounds,
    midi_note_to_drum_track,
    quantize_to_steps,
)
from .errors import (
    BridgeConfigError,
    BridgeError,
    BridgeImportError,
    BridgeRenderError,
    BridgeScanError,
    BridgeWriteDenied,
    IssueCode,
    MidoMissingError,
    load_mido,
    mido_available,
)
from .instrument_map import TonePreset, resolve_preset
from .midi_import import import_asset, midi_to_patterns_v2, probe_midi
from .models import (
    AssetProbe,
    BridgeIssue,
    BridgeReport,
    ImportResult,
    MidiAsset,
    NoteCluster,
    NoteEvent,
    RenderResult,
    TrackAnalysis,
)
from .note_range import (
    fold_into_range,
    is_renderable,
    midi_to_note_name,
    note_name_to_midi,
    safe_note_and_shift,
)
from .renderer import render_import_result, render_pattern_file, resolve_duration
from .report import configure_logging, get_logger, run_batch, write_report
from .scanner import scan_midi_assets, snapshot_tree

__version__ = BRIDGE_VERSION

__all__ = [
    # 版本
    "__version__",
    "BRIDGE_VERSION",
    # 配置
    "BridgeConfig",
    "DEFAULT_OUTPUT_ROOT",
    "DEFAULT_SCAN_ROOT",
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_DRUM_GRID",
    "DEFAULT_DRUM_BAR_POLICY",
    "DEFAULT_DAW_MIDI_DIRS",
    "assert_write_allowed",
    "is_under_readonly_root",
    # 扫描
    "scan_midi_assets",
    "snapshot_tree",
    # 导入
    "midi_to_patterns_v2",
    "import_asset",
    "probe_midi",
    # 渲染
    "render_import_result",
    "render_pattern_file",
    "resolve_duration",
    # DAW 回流
    "DAW_MIDI_DIRS",
    "DAW_MIDI_DIR",
    "assert_daw_write_allowed",
    "resolve_daw_dir_for_source",
    "export_import_result_to_daw",
    "write_music_pattern_midi",
    "write_drum_pattern_midi",
    # 批量与报告
    "run_batch",
    "write_report",
    "get_logger",
    "configure_logging",
    # 领域算法
    "ChordFields",
    "cluster_simultaneous",
    "clusters_to_pattern_fields",
    "default_chord_tolerance",
    "repair_negative_gaps",
    "lossless_note_count",
    "build_reverse_drum_map",
    "midi_note_to_drum_track",
    "quantize_to_steps",
    "default_drum_sounds",
    "TonePreset",
    "resolve_preset",
    "safe_note_and_shift",
    "fold_into_range",
    "is_renderable",
    "midi_to_note_name",
    "note_name_to_midi",
    # 数据模型
    "MidiAsset",
    "NoteEvent",
    "NoteCluster",
    "TrackAnalysis",
    "BridgeIssue",
    "ImportResult",
    "RenderResult",
    "BridgeReport",
    "AssetProbe",
    # 异常
    "BridgeError",
    "MidoMissingError",
    "BridgeScanError",
    "BridgeImportError",
    "BridgeRenderError",
    "BridgeWriteDenied",
    "BridgeConfigError",
    "IssueCode",
    "load_mido",
    "mido_available",
]
