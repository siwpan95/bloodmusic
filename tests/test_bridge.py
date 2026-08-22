"""bridge 子包验收测试 —— 覆盖 P0-2 ~ P0-7 与 R1/R4/R6/R7/R8 硬规则

运行::

    cd G:\\tools\\bloodmusic
    python -m pytest tests/test_bridge.py -v

设计说明:
    - 断言全部锚定在 `G:\\midi` 的 **6 个真实素材** 上（PPQ=220 / 120BPM / 4-4 拍）,
      而不是构造数据 —— 构造数据测不出 F5/F7/F8 这类真实坑；
    - 素材树不存在时整体 skip，保证在没有素材的机器上不误报红；
    - 任何写盘一律落在 `tempfile` 目录，**绝不**写进 `G:\\midi`（R1）。
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
import unittest
from pathlib import Path

from bloodmusic.bridge import (
    DAW_MIDI_DIRS,
    BridgeConfig,
    BridgeWriteDenied,
    IssueCode,
    assert_daw_write_allowed,
    assert_write_allowed,
    cluster_simultaneous,
    clusters_to_pattern_fields,
    default_chord_tolerance,
    export_import_result_to_daw,
    fold_into_range,
    import_asset,
    is_renderable,
    lossless_note_count,
    midi_to_patterns_v2,
    mido_available,
    probe_midi,
    quantize_to_steps,
    render_import_result,
    resolve_preset,
    safe_note_and_shift,
    scan_midi_assets,
    snapshot_tree,
)
from bloodmusic.bridge.models import NoteEvent
from bloodmusic.bridge.note_range import midi_to_note_name, note_name_to_midi
from bloodmusic.bridge.renderer import drum_duration_sec, resolve_duration

#: 素材根（PRD 指定）
MIDI_ROOT = Path("G:/midi")
#: 该目录下**恰好**应扫出这 6 个资产（第 7 个在 dist/_internal 里，属打包噪声）
EXPECTED_ASSET_COUNT = 6
EXPECTED_NAMES = {
    "Bass_130406",
    "Chords_130406",
    "Drum Kit_130406",
    "Drums",
    "Piano",
    "Piano_130406",
}

_HAS_MATERIAL = MIDI_ROOT.is_dir()
_HAS_MIDO = mido_available()
_REQUIRES = unittest.skipUnless(
    _HAS_MATERIAL and _HAS_MIDO, "需要 G:/midi 素材库与 mido 才能运行"
)


def _assets_by_name() -> dict:
    """扫描素材并按文件名索引。"""
    return {asset.name: asset for asset in scan_midi_assets(MIDI_ROOT)}


def _carried_note_count(patterns) -> int:
    """按无损判据统计 pattern 集合真实承载的音符数。"""
    total = 0
    for pattern in patterns:
        total += sum(1 for note in pattern.notes if note is not None)
        if pattern.chords:
            total += sum(len(chord) for chord in pattern.chords)
    return total


def _drum_hits(drum_pattern) -> int:
    """统计一个 DrumPattern 的总鼓点数。"""
    return sum(sum(1 for hit in row if hit) for row in drum_pattern.tracks.values())


# ════════════════════════════ P0-2 扫描 ════════════════════════════


@_REQUIRES
class TestScanner(unittest.TestCase):
    """P0-2：资产扫描器。"""

    def test_scan_returns_exactly_six_assets(self):
        """对 G:/midi 必须恰好返回 6 个资产。"""
        assets = scan_midi_assets(MIDI_ROOT)
        self.assertEqual(len(assets), EXPECTED_ASSET_COUNT)
        self.assertEqual({a.name for a in assets}, EXPECTED_NAMES)

    def test_scan_prunes_packaging_noise(self):
        """dist/_internal/build/site-packages 下的 MIDI 必须被剪枝。"""
        assets = scan_midi_assets(MIDI_ROOT)
        for asset in assets:
            lowered = asset.rel_path.lower()
            for blocked in ("dist/", "_internal/", "build/", "site-packages/"):
                self.assertNotIn(blocked, lowered, f"未剪枝: {asset.rel_path}")

    def test_scan_is_deterministic(self):
        """重复扫描结果顺序完全一致（rel_path 升序）。"""
        first = [a.rel_path for a in scan_midi_assets(MIDI_ROOT)]
        second = [a.rel_path for a in scan_midi_assets(MIDI_ROOT)]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_scan_single_file(self):
        """root 直接给单个 .mid 时返回单元素列表。"""
        target = _assets_by_name()["Drums"].path
        assets = scan_midi_assets(target)
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].name, "Drums")


# ════════════════════════════ P0-3 和弦无损 ════════════════════════════


@_REQUIRES
class TestChordImport(unittest.TestCase):
    """P0-3：和弦导入必须零丢失（旧实现会拆成连续单音）。"""

    def setUp(self):
        self.result = midi_to_patterns_v2(_assets_by_name()["Chords_130406"].path)

    def test_chord_track_is_recognized(self):
        """Chords_130406 应识别为 1 条和弦轨，没有旋律轨。"""
        self.assertEqual(len(self.result.chord_patterns), 1)
        self.assertEqual(len(self.result.melody_patterns), 0)

    def test_chord_lossless_twelve_notes(self):
        """12 个源音符必须一个不少地落进 notes + chords。"""
        self.assertEqual(_carried_note_count(self.result.chord_patterns), 12)

    def test_chord_cluster_shape(self):
        """4 个和弦、每簇 3 音：根音 4 个 + 上方音 8 个。"""
        pattern = self.result.chord_patterns[0]
        roots = [n for n in pattern.notes if n is not None]
        self.assertEqual(len(roots), 4)
        self.assertEqual([len(c) for c in pattern.chords], [2, 2, 2, 2])

    def test_parallel_arrays_are_aligned(self):
        """notes / durations / chords / octave_shifts 必须严格等长。"""
        pattern = self.result.chord_patterns[0]
        self.assertEqual(len(pattern.notes), len(pattern.durations))
        self.assertEqual(len(pattern.notes), len(pattern.chords))
        self.assertEqual(len(pattern.notes), len(pattern.octave_shifts))

    def test_root_is_lowest_note(self):
        """根音必须是簇内最低音，否则和弦听感会翻转。"""
        pattern = self.result.chord_patterns[0]
        for index, root in enumerate(pattern.notes):
            if root is None:
                continue
            root_midi = note_name_to_midi(root)
            for upper in pattern.chords[index]:
                self.assertGreaterEqual(note_name_to_midi(upper), root_midi)

    def test_tolerance_derived_from_ppq(self):
        """U1：容差按 round(ppq/16) 推导 —— 220→14、480→30。"""
        self.assertEqual(default_chord_tolerance(220), 14)
        self.assertEqual(default_chord_tolerance(480), 30)
        self.assertEqual(default_chord_tolerance(0), 1)

    def test_cluster_anchor_does_not_chain(self):
        """簇锚点固定为簇首，间隔恰为容差的音符不得被链式串成一大簇。"""
        events = [
            NoteEvent(start_tick=i * 14, end_tick=i * 14 + 10, midi_note=60 + i,
                      velocity=100, channel=0, track_index=0)
            for i in range(5)
        ]
        clusters = cluster_simultaneous(events, 14)
        self.assertGreater(len(clusters), 1, "锚点漂移导致 5 个音被串成一簇")

    def test_lossless_counter_matches_source(self):
        """`lossless_note_count` 与源事件数一致。"""
        events = [
            NoteEvent(start_tick=0, end_tick=220, midi_note=60, velocity=100,
                      channel=0, track_index=0),
            NoteEvent(start_tick=0, end_tick=220, midi_note=64, velocity=100,
                      channel=0, track_index=0),
            NoteEvent(start_tick=220, end_tick=440, midi_note=67, velocity=100,
                      channel=0, track_index=0),
        ]
        fields = clusters_to_pattern_fields(cluster_simultaneous(events, 14), 220)
        self.assertEqual(lossless_note_count(fields), 3)


# ════════════════════════════ P0-3 旋律不误判 ════════════════════════════


@_REQUIRES
class TestMelodyImport(unittest.TestCase):
    """未量化的单音轨不得被误判成和弦（F7 的 legato 重叠陷阱）。"""

    def setUp(self):
        self.result = midi_to_patterns_v2(_assets_by_name()["Bass_130406"].path)

    def test_bass_is_melody_not_chord(self):
        """Bass_130406 是 32 个单音，必须落在 melody_patterns。"""
        self.assertEqual(len(self.result.melody_patterns), 1)
        self.assertEqual(len(self.result.chord_patterns), 0)

    def test_bass_has_no_fake_chord(self):
        """单音轨绝不能凭空长出和弦。"""
        pattern = self.result.melody_patterns[0]
        self.assertTrue(
            pattern.chords is None or all(not chord for chord in pattern.chords),
            f"单音轨出现伪和弦: {pattern.chords}",
        )

    def test_bass_note_count_preserved(self):
        """32 个源音符全部保留。"""
        self.assertEqual(_carried_note_count(self.result.melody_patterns), 32)

    def test_bass_uses_gm_bass_preset(self):
        """P1-3：program=33 → GM bass 族（低通 800Hz）。"""
        analysis = next(a for a in self.result.analyses if a.kind == "melody")
        self.assertEqual(analysis.program, 33)
        preset = resolve_preset(analysis)
        self.assertEqual(preset.name, "bass")
        self.assertEqual(preset.lp_filter_hz, 800.0)

    def test_piano_legato_overlap_repaired(self):
        """F7：Piano.mid 的负 gap 必须被修复并记 info 级 issue。"""
        result = midi_to_patterns_v2(_assets_by_name()["Piano"].path)
        self.assertEqual(_carried_note_count(result.melody_patterns), 8)
        for pattern in result.melody_patterns:
            self.assertTrue(all(d > 0 for d in pattern.durations), "存在非正时值")


# ════════════════════════════ P0-4 鼓轨 ════════════════════════════


@_REQUIRES
class TestDrumImport(unittest.TestCase):
    """P0-4：鼓轨识别与还原（旧实现整轨丢弃）。"""

    def test_drums_mid_lossless(self):
        """Drums.mid：64 步、kick 8 / snare 4 / hihat 16，总 28 击零丢失。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        self.assertEqual(len(result.drum_patterns), 1)
        drum = result.drum_patterns[0]
        self.assertEqual(drum.steps, 64)
        self.assertEqual(_drum_hits(drum), 28)
        self.assertEqual(sum(1 for x in drum.tracks["kick"] if x), 8)
        self.assertEqual(sum(1 for x in drum.tracks["snare"] if x), 4)
        self.assertEqual(sum(1 for x in drum.tracks["hihat"] if x), 16)

    def test_drum_kit_lossless(self):
        """Drum Kit_130406：64 步、kick 8 / snare 8 / hihat 32，总 48 击零丢失。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drum Kit_130406"].path)
        drum = result.drum_patterns[0]
        self.assertEqual(drum.steps, 64)
        self.assertEqual(_drum_hits(drum), 48)
        self.assertEqual(sum(1 for x in drum.tracks["kick"] if x), 8)
        self.assertEqual(sum(1 for x in drum.tracks["snare"] if x), 8)
        self.assertEqual(sum(1 for x in drum.tracks["hihat"] if x), 32)

    def test_every_track_has_sound_params(self):
        """每个 tracks key 都必须有 sounds，否则 DrumPattern 会 warnings.warn。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        drum = result.drum_patterns[0]
        self.assertEqual(set(drum.tracks.keys()) - set(drum.sounds.keys()), set())

    def test_no_quantize_drift_on_real_material(self):
        """实测 6 素材 onset 全为 55 tick 整数倍，不应出现量化漂移告警。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        self.assertFalse(result.has_code(IssueCode.DRUM_QUANTIZE_DRIFT))

    def test_fold_policy_folds_into_one_bar(self):
        """U2：fold 策略把 4 小节按位 OR 折回 16 步。"""
        result = midi_to_patterns_v2(
            _assets_by_name()["Drums"].path, drum_bar_policy="fold"
        )
        self.assertEqual(result.drum_patterns[0].steps, 16)

    def test_split_policy_yields_one_pattern_per_bar(self):
        """U2：split 策略每小节一个 pattern，共 4 个。"""
        result = midi_to_patterns_v2(
            _assets_by_name()["Drums"].path, drum_bar_policy="split"
        )
        self.assertEqual(len(result.drum_patterns), 4)
        for drum in result.drum_patterns:
            self.assertEqual(drum.steps, 16)

    def test_unsupported_grid_reports_error_and_falls_back(self):
        """U3：--drum-grid 32 必须报 error 并回退 16（steps 仍是 16 的倍数）。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path, drum_steps=32)
        self.assertTrue(result.has_code(IssueCode.DRUM_GRID_UNSUPPORTED))
        self.assertFalse(result.ok, "不支持的网格必须让 ok 为 False")
        self.assertEqual(result.drum_patterns[0].steps % 16, 0)

    def test_unknown_drum_note_is_kept(self):
        """未知鼓音符号映射为 perc_<n>，绝不丢弃。"""
        events = [
            NoteEvent(start_tick=0, end_tick=55, midi_note=99, velocity=100,
                      channel=9, track_index=0)
        ]
        grid = quantize_to_steps(events, 220, grid=16, beats_per_bar=4)
        self.assertIn("perc_99", grid.tracks)


# ════════════════════════════ P0-5 渲染 ════════════════════════════


@_REQUIRES
class TestRenderer(unittest.TestCase):
    """P0-5：复用本体渲染管线，时长必须精确（D6）。"""

    def test_duration_derived_from_total_beats(self):
        """16 拍 @120BPM = 8.000 秒，误差 < 0.05s。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        self.assertAlmostEqual(result.duration_sec, 8.0, delta=0.05)
        self.assertAlmostEqual(resolve_duration(result), 8.0, delta=0.05)

    def test_drum_duration_matches_hardcoded_step(self):
        """F9：render_drum_pattern 的 step_dur 恒为 beat/4 → 64 步 = 8 秒。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        self.assertAlmostEqual(drum_duration_sec(result.drum_patterns[0]), 8.0, delta=0.01)

    def test_render_writes_audio_with_correct_length(self):
        """渲染产物真实存在，且 wav 时长 ≈ 8 秒。"""
        import soundfile as sf

        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = BridgeConfig(output_root=Path(tmp), render_mode="both")
            render = render_import_result(result, cfg)
            self.assertTrue(render.ok, f"渲染失败: {[str(i) for i in render.issues]}")
            self.assertGreaterEqual(len(render.audio_files), 2)  # mix + 至少 1 个 stem
            for path in render.audio_files:
                self.assertTrue(path.is_file(), f"缺少产物: {path}")
                data, samplerate = sf.read(str(path))
                self.assertAlmostEqual(len(data) / samplerate, 8.0, delta=0.1)

    def test_render_output_lands_under_output_root(self):
        """R2：产物必须落在指定输出根之下。"""
        result = midi_to_patterns_v2(_assets_by_name()["Piano"].path)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = BridgeConfig(output_root=Path(tmp), render_mode="mix")
            render = render_import_result(result, cfg)
            for path in render.audio_files:
                self.assertTrue(str(path).startswith(str(Path(tmp).resolve()))
                                or str(path).startswith(tmp))


# ════════════════════════════ 音高守卫（F10） ════════════════════════════


class TestNoteRange(unittest.TestCase):
    """F10：note_to_freq 查不到会静默降级 440Hz，守卫层必须拦住。"""

    def test_name_roundtrip(self):
        """midi ↔ 音名 双向可逆。"""
        for midi_note in range(12, 97):
            self.assertEqual(note_name_to_midi(midi_to_note_name(midi_note)), midi_note)

    def test_middle_c_is_c4(self):
        """GM 惯例：MIDI 60 = C4。"""
        self.assertEqual(midi_to_note_name(60), "C4")

    def test_safe_note_is_lossless(self):
        """旋律轨：超界音高转 octave_shift，频率完全等价。"""
        name, shift = safe_note_and_shift(108)  # C8，超出 NOTES 上界
        self.assertTrue(is_renderable(name))
        self.assertEqual(note_name_to_midi(name) + 12 * shift, 108)

    def test_fold_returns_renderable_note(self):
        """和弦音：只能折叠，但结果必须落在 NOTES 表内。"""
        name, folded = fold_into_range(4)  # E-1，低于 C0
        self.assertTrue(is_renderable(name))
        self.assertNotEqual(folded, 0)

    def test_in_range_notes_untouched(self):
        """域内音高不得被改动。"""
        for midi_note in (12, 60, 96):
            name, shift = safe_note_and_shift(midi_note)
            self.assertEqual(shift, 0)
            self.assertEqual(note_name_to_midi(name), midi_note)


# ════════════════════════════ R1 / Q3 只读硬规则 ════════════════════════════


class TestWriteGuard(unittest.TestCase):
    """R1：G:/midi 只读，唯一例外是 export-to-daw --apply + bm_ 前缀。"""

    def test_plain_write_into_readonly_root_denied(self):
        """未授权写入只读根 → BridgeWriteDenied。"""
        cfg = BridgeConfig()
        with self.assertRaises(BridgeWriteDenied):
            assert_write_allowed(MIDI_ROOT / "whatever.wav", cfg)

    def test_apply_without_prefix_denied(self):
        """开了 --apply 但文件名没有 bm_ 前缀 → 仍然拒绝。"""
        cfg = BridgeConfig(allow_daw_write=True)
        with self.assertRaises(BridgeWriteDenied):
            assert_write_allowed(MIDI_ROOT / "MusicStudio" / "evil.mid", cfg)

    def test_apply_with_prefix_allowed(self):
        """--apply + bm_ 前缀 → 放行（仅返回路径，不落盘）。"""
        cfg = BridgeConfig(allow_daw_write=True)
        target = assert_write_allowed(MIDI_ROOT / "MusicStudio" / "bm_x.mid", cfg)
        self.assertTrue(target.name.startswith("bm_"))

    def test_output_root_is_never_readonly(self):
        """默认输出根不在只读根内，正常放行。"""
        cfg = BridgeConfig()
        self.assertIsNotNone(assert_write_allowed(cfg.output_root / "report.json", cfg))


@_REQUIRES
class TestReadOnlyInvariant(unittest.TestCase):
    """Q3：整条流水线跑完，G:/midi 必须字节级不变。"""

    def test_full_pipeline_does_not_touch_material(self):
        """扫描 + 全量导入 + 渲染 + DAW dry-run 之后，素材树快照一致。"""
        before = snapshot_tree(MIDI_ROOT)
        self.assertGreater(len(before), 0, "快照为空，测试无意义")

        with tempfile.TemporaryDirectory() as tmp:
            cfg = BridgeConfig(output_root=Path(tmp), render_mode="mix")
            for asset in scan_midi_assets(MIDI_ROOT):
                result = import_asset(asset.path, cfg)
                render_import_result(result, cfg)
                # dry-run 回流：一个字节都不能写进 G:/midi
                paths, issues = export_import_result_to_daw(result, cfg)
                self.assertTrue(
                    all(i.code == IssueCode.DRY_RUN for i in issues if i.level == "info")
                    or not issues
                )
                for path in paths:
                    self.assertFalse(path.exists() and path.name.startswith("bm_") is False)

        after = snapshot_tree(MIDI_ROOT)
        self.assertEqual(before, after, "G:/midi 被修改了，违反 R1/Q3")


# ════════════════════════════ P1-2 DAW 回流 ════════════════════════════


@_REQUIRES
class TestDawExport(unittest.TestCase):
    """P1-2：回流 MIDI，默认 dry-run。"""

    def test_dry_run_writes_nothing(self):
        """未加 --apply → 只返回计划路径 + DRY_RUN issue。"""
        result = midi_to_patterns_v2(_assets_by_name()["Chords_130406"].path)
        cfg = BridgeConfig()
        paths, issues = export_import_result_to_daw(result, cfg)
        self.assertTrue(paths)
        self.assertTrue(any(i.code == IssueCode.DRY_RUN for i in issues))
        for path in paths:
            self.assertTrue(path.name.startswith("bm_"))
            self.assertFalse(path.exists(), f"dry-run 竟然落盘了: {path}")

    def test_apply_into_temp_dir_roundtrip(self):
        """写到临时目录再读回：和弦音符数守恒（验证绕开 F11 的写出器）。"""
        result = midi_to_patterns_v2(_assets_by_name()["Chords_130406"].path)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = BridgeConfig(allow_daw_write=True)
            paths, _ = export_import_result_to_daw(result, cfg, out_dir=Path(tmp))
            self.assertTrue(paths)
            import mido

            total = 0
            for path in paths:
                self.assertTrue(path.is_file())
                mid = mido.MidiFile(str(path))
                total += sum(
                    1
                    for track in mid.tracks
                    for msg in track
                    if msg.type == "note_on" and msg.velocity > 0
                )
            self.assertEqual(total, 12)

    def test_backflow_lands_in_source_owned_daw_dir(self):
        """QA BUG-1 回归：回流目标必须按来源归位，不得全塞进单一 DAW 目录。

        素材库里有两个独立 DAW，pro4 来源的 4 个素材若被写进
        `MusicStudio\\Data\\MIDI`，MusicStudioPro 永远看不到自己的回流文件。
        """
        cfg = BridgeConfig()  # dry-run，不落盘
        misrouted: list[str] = []
        checked = 0
        for asset in scan_midi_assets(
            MIDI_ROOT, exclude_dirs=cfg.exclude_dirs, suffixes=cfg.suffixes
        ):
            result = import_asset(asset.path, cfg)
            paths, _ = export_import_result_to_daw(result, cfg)
            expected = Path(result.source).resolve(strict=False).parent
            for path in paths:
                checked += 1
                if path.parent.resolve(strict=False) != expected:
                    misrouted.append(f"{asset.rel_path} -> {path.parent}")
        self.assertTrue(checked, "没有任何回流产物可校验")
        self.assertEqual(misrouted, [], f"回流目录误路由: {misrouted}")

    def test_pro4_material_backflows_to_pro4_dir(self):
        """pro4 来源的素材必须落回 pro4 的 Data/MIDI（QA 点名的断言）。"""
        result = midi_to_patterns_v2(_assets_by_name()["Bass_130406"].path)
        paths, _ = export_import_result_to_daw(result, BridgeConfig())
        self.assertTrue(paths)
        for path in paths:
            parts = [p.lower() for p in path.parts]
            self.assertIn("musicstudiopro", parts, f"pro4 素材被误路由到 {path.parent}")
            self.assertEqual(path.parent.name.lower(), "midi")
            self.assertEqual(path.parent.parent.name.lower(), "data")

    def test_daw_dir_whitelist_has_both_daws(self):
        """常量必须是设计文档 §3.10 的**两个**目录，而不是单目录。"""
        lowered = {str(d).lower().replace("/", "\\") for d in DAW_MIDI_DIRS}
        self.assertEqual(len(DAW_MIDI_DIRS), 2, f"白名单目录数不对: {DAW_MIDI_DIRS}")
        self.assertIn("g:\\midi\\musicstudio\\data\\midi", lowered)
        self.assertIn("g:\\midi\\pro4\\musicstudiopro\\data\\midi", lowered)

    def test_write_allowed_in_second_daw_dir(self):
        """鉴权必须认第二个 DAW 目录，否则 pro4 回流会被自己的守卫拦死。"""
        cfg = BridgeConfig(allow_daw_write=True)
        target = Path(r"G:\midi\pro4\MusicStudioPro\Data\MIDI\bm_probe.mid")
        self.assertEqual(
            assert_daw_write_allowed(target, cfg),
            target.resolve(strict=False),
        )
        self.assertFalse(target.exists(), "鉴权函数不应产生任何文件")

    def test_unresolvable_source_denied_under_apply(self):
        """OBS-1 收紧：来源无法确证时，--apply 也拒绝猜着往 DAW 库里写。"""
        result = midi_to_patterns_v2(_assets_by_name()["Chords_130406"].path)
        result.source = str(Path(tempfile.gettempdir()) / "nowhere" / "x.mid")

        # dry-run：只记 warn，不抛
        paths, issues = export_import_result_to_daw(result, BridgeConfig())
        self.assertTrue(paths)
        self.assertTrue(any(i.level == "warn" for i in issues))

        # --apply：直接拒绝
        with self.assertRaises(BridgeWriteDenied):
            export_import_result_to_daw(result, BridgeConfig(allow_daw_write=True))


# ════════════════════════════ 探测 / 报告 ════════════════════════════


@_REQUIRES
class TestProbeAndReport(unittest.TestCase):
    """scan 表格数据源与报告序列化。"""

    def test_probe_detects_drum_and_chord(self):
        """探测应正确标记鼓轨与和弦轨。"""
        assets = _assets_by_name()
        drum_probe = probe_midi(assets["Drums"].path)
        chord_probe = probe_midi(assets["Chords_130406"].path)
        self.assertTrue(drum_probe.has_drum)
        self.assertFalse(drum_probe.has_chord)
        self.assertTrue(chord_probe.has_chord)
        self.assertEqual(chord_probe.bpm, 120)
        self.assertEqual(chord_probe.ticks_per_beat, 220)

    def test_probe_on_broken_file_returns_error(self):
        """损坏文件不抛异常，只把错误写进 probe.error（§9.2）。"""
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.mid"
            broken.write_bytes(b"not a midi file at all")
            probe = probe_midi(broken)
            self.assertIsNotNone(probe.error)

    def test_import_result_json_serializable(self):
        """ImportResult.to_json 不得抛异常，且含关键字段。"""
        result = midi_to_patterns_v2(_assets_by_name()["Drums"].path)
        text = result.to_json()
        self.assertIn("drum_patterns", text)
        self.assertIn("ticks_per_beat", text)


# ════════════════════════════ 架构硬规则 ════════════════════════════


class TestArchitectureRules(unittest.TestCase):
    """R4 / R6 / R7：渲染三件套零改造、本体入口未改、单向依赖。"""

    PACKAGE_ROOT = Path(__file__).resolve().parent.parent
    #: R4 要求 git diff 必须为空的三个文件
    FROZEN_FILES = (
        "music/pattern.py",
        "export/batch.py",
        "export/midi_export.py",
        "__init__.py",  # R6：本体入口也不许改
    )

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        """在包根执行 git 命令。"""
        return subprocess.run(
            ["git", *args],
            cwd=str(self.PACKAGE_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_frozen_paths_actually_exist(self):
        """QA 加固：路径写错时 `git diff` 会静默返回空，让 R4 校验形同虚设。

        必须先证明每个冻结路径真实存在，R4 断言才有意义
        （例：`music/midi_export.py` 并不存在，真实路径是 `export/midi_export.py`）。
        """
        missing = [f for f in self.FROZEN_FILES if not (self.PACKAGE_ROOT / f).is_file()]
        self.assertEqual(missing, [], f"冻结清单里的路径不存在，R4 校验会被架空: {missing}")

    def test_frozen_files_have_no_diff(self):
        """R4 / R6：渲染三件套 + 本体 __init__.py 相对 HEAD 必须零改动。

        用 `git diff HEAD` 而非 `git diff`：后者看不到**已暂存**的改动，
        `git add music/pattern.py` 就能绕过校验。
        """
        probe = self._git("rev-parse", "--is-inside-work-tree")
        if probe.returncode != 0:
            self.skipTest("不是 git 仓库，跳过 diff 校验")
        diff = self._git("diff", "HEAD", "--name-only", "--", *self.FROZEN_FILES)
        self.assertEqual(
            diff.stdout.strip(), "", f"以下文件被改动，违反 R4/R6: {diff.stdout.strip()}"
        )

    def test_core_never_imports_bridge(self):
        """R7：本体任何模块都不得 import bridge（单向依赖）。

        用 AST 判定「真实 import」，避免把 docstring 里的迁移指引
        （`>>> from bloodmusic.bridge import ...`）误判成反向依赖。
        """
        offenders: list[str] = []
        # 只扫描本体（白名单，与 R7 的语义一致）：根目录入口 .py + 核心包
        # core/effects/music/sfx/export/playback/gui/interactive。扩展层
        # （album_maker、pipeline、remix、skill、autowav、mirror、games）
        # 是 bridge 的合法消费者；.venv/.git/tests 等非产品代码一律不扫
        # （也避免把第三方包里的 SyntaxWarning 误报进测试日志）。
        core_dirs = {"core", "effects", "music", "sfx", "export",
                     "playback", "gui", "interactive"}
        for path in self.PACKAGE_ROOT.rglob("*.py"):
            parts = path.relative_to(self.PACKAGE_ROOT).parts
            is_root_entry = len(parts) == 1  # cli.py / util.py / __init__.py 等
            is_core = parts[0] in core_dirs
            if not (is_root_entry or is_core):
                continue
            if "__pycache__" in parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:  # pragma: no cover - 本体源码应始终可解析
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] == "bridge" or ".bridge" in alias.name:
                            offenders.append(f"{path.name}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "bridge" or module.endswith(".bridge") or ".bridge." in module:
                        offenders.append(f"{path.name}: from {module}")
        self.assertEqual(offenders, [], f"本体反向依赖 bridge: {offenders}")

    def test_bridge_not_eagerly_imported(self):
        """R6：`bloodmusic/__init__.py` 不得自动 import bridge。"""
        text = (self.PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("bridge", text)

    def test_mido_is_lazily_imported(self):
        """R5：bridge 各模块**模块级**不得 import mido（函数体内惰性导入才合法）。"""
        bridge_dir = self.PACKAGE_ROOT / "bridge"
        offenders: list[str] = []
        for path in bridge_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # 只看模块顶层语句，函数体内的惰性导入合法
                if isinstance(node, ast.Import):
                    offenders += [
                        f"{path.name}: import {a.name}"
                        for a in node.names
                        if a.name.split(".")[0] == "mido"
                    ]
                elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("mido"):
                    offenders.append(f"{path.name}: from {node.module}")
        self.assertEqual(offenders, [], f"存在模块级 mido 导入，违反 R5: {offenders}")

    def test_bridge_importable_without_mido(self):
        """R5 佐证：mido 的导入点唯一，且集中在 `errors.load_mido()`。"""
        errors_src = (self.PACKAGE_ROOT / "bridge" / "errors.py").read_text(encoding="utf-8")
        self.assertIn("def load_mido", errors_src)
        self.assertIn("pip install mido", errors_src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
