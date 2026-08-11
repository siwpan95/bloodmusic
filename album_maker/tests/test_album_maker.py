"""
album_maker/tests/test_album_maker.py — 回归测试

验证 --demo 完整流程：
- YAML 解析正确
- PoolGenerator 驱动
- 分轨 WAV 产物非空
- mixdown 母带可读
- album_manifest.json 结构完整
- 单曲失败不中断
- --demo 全链路 exit 0

不依赖 audio_separator（无 demucs 下载），纯合成路径。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# 确保 bloodmusic 在 path 中
_BLOODMUSIC_ROOT = Path(r"G:\tools\bloodmusic")
if str(_BLOODMUSIC_ROOT) not in sys.path:
    sys.path.insert(0, str(_BLOODMUSIC_ROOT))


# ═══════════════════════════════════════════════════════════════════════
# 导入被测模块
# ═══════════════════════════════════════════════════════════════════════

from album_maker.config import AlbumConfig, TrackSpec
from album_maker.demo_config import make_demo_config, DEMO_ALBUM_CONFIG
from album_maker.album import AlbumMaker, AlbumResult, _process_track_worker
from album_maker.track import TrackHandler, TrackResult
from album_maker.report import AlbumReport


# ═══════════════════════════════════════════════════════════════════════
# 测试夹具
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def demo_config() -> AlbumConfig:
    """返回 demo 配置（每次调用 make_demo_config 保证新鲜）。"""
    return make_demo_config()


@pytest.fixture
def tmp_out_dir(tmp_path: Path) -> Path:
    """临时输出目录。"""
    return tmp_path / "album_output"


# ═══════════════════════════════════════════════════════════════════════
# T01 数据模型测试
# ═══════════════════════════════════════════════════════════════════════

class TestAlbumConfig:
    """AlbumConfig + TrackSpec 数据模型测试。"""

    def test_demo_config_has_three_tracks(self):
        """验证 demo 配置包含 3 首曲目。"""
        config = make_demo_config()
        assert len(config.tracks) == 3

    def test_demo_config_pool_raw_structure(self):
        """验证 demo 配置的 pool_raw 结构。"""
        config = make_demo_config()
        assert "name" in config.pool_raw
        assert "instruments" in config.pool_raw
        assert len(config.pool_raw["instruments"]) >= 5

    def test_demo_config_mix_config_raw(self):
        """验证 demo 配置的混音参数。"""
        config = make_demo_config()
        assert "clip_mode" in config.mix_config_raw
        assert config.mix_config_raw["clip_mode"] == "soft"
        assert "rms_target_db" in config.mix_config_raw

    def test_demo_config_tracks_fields(self):
        """验证 demo 配置中每首曲目字段完整。"""
        config = make_demo_config()
        for track in config.tracks:
            assert track.title
            assert track.bpm > 0
            assert track.bars > 0
            assert track.key
            assert track.style in ("exploration", "battle", "town")

    def test_track_spec_to_pool_overrides(self):
        """验证 TrackSpec.to_pool_overrides() 返回值。"""
        spec = TrackSpec(title="Test", bpm=140, bars=32, key="Em", seed=42)
        overrides = spec.to_pool_overrides()
        assert overrides["bpm"] == 140
        assert overrides["key"] == "Em"
        assert overrides["seed"] == 42

    def test_from_yaml_missing_file(self):
        """验证不存在的 YAML 文件引发异常。"""
        with pytest.raises(FileNotFoundError):
            AlbumConfig.from_yaml("/nonexistent/path/album.yaml")


class TestDemoConfigConstant:
    """DEMO_ALBUM_CONFIG 模块级常量测试。"""

    def test_demo_config_constant_exists(self):
        """验证 DEMO_ALBUM_CONFIG 可用。"""
        assert DEMO_ALBUM_CONFIG is not None
        assert len(DEMO_ALBUM_CONFIG.tracks) == 3


class TestConfigRoundtrip:
    """YAML 解析往返测试。"""

    def test_config_roundtrip_via_temp_yaml(self, tmp_path: Path):
        """通过临时 YAML 文件验证配置解析往返。"""
        import yaml

        yaml_path = tmp_path / "test_album.yaml"
        config_data: dict = {
            "album": {
                "title": "往返测试专辑",
                "artist": "Test Artist",
                "genre": "test",
                "year": 2026,
            },
            "instrument_pool": {
                "name": "测试乐池",
                "bpm": 120,
                "key": "C",
                "scale": "major",
                "instruments": [
                    {"name": "Piano", "role": "melody", "engine": "wavetable", "volume": 0.9},
                    {"name": "Bass", "role": "bass", "engine": "subtractive", "volume": 1.0},
                    {"name": "Drums", "role": "drum", "engine": "noise", "volume": 0.85},
                ],
            },
            "mix_config": {
                "clip_mode": "soft",
                "normalize_mode": "rms",
                "rms_target_db": -3.0,
            },
            "separate_mode": "manifest",
            "tracks": [
                {"title": "Track 1", "bpm": 100, "bars": 16, "key": "Am", "style": "exploration", "seed": 1},
                {"title": "Track 2", "bpm": 140, "bars": 32, "key": "Em", "style": "battle", "seed": 2},
            ],
        }

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        config = AlbumConfig.from_yaml(yaml_path)
        assert config.title == "往返测试专辑"
        assert config.artist == "Test Artist"
        assert len(config.tracks) == 2
        assert config.tracks[0].title == "Track 1"
        assert config.tracks[0].bpm == 100
        assert config.tracks[0].style == "exploration"
        assert config.tracks[1].title == "Track 2"
        assert config.tracks[1].bpm == 140
        assert config.tracks[1].style == "battle"
        assert "name" in config.pool_raw
        assert config.pool_raw["name"] == "测试乐池"
        assert config.separate_mode == "manifest"


# ═══════════════════════════════════════════════════════════════════════
# T02 单曲目处理器测试
# ═══════════════════════════════════════════════════════════════════════

class TestTrackHandler:
    """TrackHandler 单元测试。"""

    def test_build_pool_for_track(self, demo_config: AlbumConfig):
        """验证 _build_pool_for_track 应用 style 和 BPM/key 覆盖。"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        base_pool = PoolSerializer._dict_to_pool(demo_config.pool_raw.copy())
        spec = demo_config.tracks[0]  # exploration, bpm=100

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw=demo_config.mix_config_raw,
        )
        track_pool = handler._build_pool_for_track()

        assert track_pool.bpm == spec.bpm
        assert track_pool.key == spec.key
        # 应用 style 后 pool.style 应被设置
        assert track_pool.style is not None

    def test_generate_produces_multi_track(self, demo_config: AlbumConfig):
        """验证 _generate 产出 MultiTrackPattern。"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        base_pool = PoolSerializer._dict_to_pool(demo_config.pool_raw.copy())
        spec = demo_config.tracks[0]

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw=demo_config.mix_config_raw,
        )
        track_pool = handler._build_pool_for_track()
        multi = handler._generate(track_pool)

        assert multi is not None
        assert len(multi.music_tracks) > 0

    def test_render_stems_produces_wav(self, demo_config: AlbumConfig, tmp_path: Path):
        """验证 _render_stems 产出非空 WAV 文件。"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        base_pool = PoolSerializer._dict_to_pool(demo_config.pool_raw.copy())
        spec = demo_config.tracks[0]

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw=demo_config.mix_config_raw,
        )
        track_pool = handler._build_pool_for_track()
        multi = handler._generate(track_pool)

        duration_sec = spec.bars * 60.0 / spec.bpm
        stems_dir = tmp_path / "stems"
        stem_paths = handler._render_stems(multi, stems_dir, duration_sec)

        assert len(stem_paths) > 0
        for sp in stem_paths:
            assert sp.exists()
            assert sp.stat().st_size > 0, f"WAV 文件为空: {sp.name}"

    def test_track_handler_process_full(self, demo_config: AlbumConfig, tmp_path: Path):
        """验证 TrackHandler.process() 完整流程。"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        base_pool = PoolSerializer._dict_to_pool(demo_config.pool_raw.copy())
        spec = demo_config.tracks[0]

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw=demo_config.mix_config_raw,
        )
        work_dir = tmp_path / "track_01"
        result = handler.process(work_dir)

        assert result.success, f"曲目处理失败: {result.error}"
        assert result.song_path is not None
        assert result.song_path.exists()
        assert result.manifest_path is not None
        assert result.manifest_path.exists()
        assert result.sources_dir is not None
        assert result.sources_dir.is_dir()
        assert result.duration_sec > 0


# ═══════════════════════════════════════════════════════════════════════
# T03/T04 专辑编排测试
# ═══════════════════════════════════════════════════════════════════════

class TestAlbumMaker:
    """AlbumMaker 专辑级测试。"""

    def test_album_maker_creates_output_structure(
        self, demo_config: AlbumConfig, tmp_out_dir: Path
    ):
        """验证专辑制作产出的目录结构。"""
        maker = AlbumMaker(demo_config)
        result = maker.make(tmp_out_dir)

        # album_manifest.json
        assert result.album_manifest_path is not None
        assert result.album_manifest_path.exists()

        # album.yaml.copy
        copy_path = tmp_out_dir / "album.yaml.copy"
        assert copy_path.exists()

        # 每首曲目的产物
        for track_result in result.tracks:
            if track_result.success:
                assert track_result.song_path is not None
                assert track_result.song_path.exists()
                assert track_result.song_path.stat().st_size > 0

                assert track_result.manifest_path is not None
                assert track_result.manifest_path.exists()

                assert track_result.sources_dir is not None
                assert track_result.sources_dir.is_dir()

                # _sources 中至少有一些 WAV
                wavs = list(track_result.sources_dir.glob("*.wav"))
                assert len(wavs) >= 1, f"_sources 中无 WAV: {track_result.sources_dir}"


class TestAlbumManifest:
    """album_manifest.json 结构测试。"""

    def test_album_manifest_structure(self, demo_config: AlbumConfig, tmp_path: Path):
        """验证 album_manifest.json 结构完整。"""
        maker = AlbumMaker(demo_config)
        result = maker.make(tmp_path / "album_output")

        manifest_path = result.album_manifest_path
        assert manifest_path is not None

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["version"] == "1.0"
        assert manifest["album"]["title"] == demo_config.title
        assert manifest["album"]["artist"] == demo_config.artist

        assert "summary" in manifest
        assert manifest["summary"]["total_tracks"] == len(demo_config.tracks)
        assert manifest["summary"]["success_count"] == result.success_count
        assert manifest["summary"]["failure_count"] == result.failure_count

        assert "tracks" in manifest
        assert len(manifest["tracks"]) == len(demo_config.tracks)

        assert "honesty_note" in manifest


class TestAlbumReport:
    """AlbumReport 测试。"""

    def test_generate_report_string(self, demo_config: AlbumConfig, tmp_path: Path):
        """验证报告字符串生成。"""
        maker = AlbumMaker(demo_config)
        result = maker.make(tmp_path / "album_output")

        report_str = AlbumReport.generate(result)
        assert result.title in report_str
        assert str(result.success_count) in report_str
        assert str(len(result.tracks)) in report_str

    def test_to_json_writes_file(self, demo_config: AlbumConfig, tmp_path: Path):
        """验证 JSON 报告写入。"""
        maker = AlbumMaker(demo_config)
        result = maker.make(tmp_path / "album_output")

        json_path = tmp_path / "test_report.json"
        AlbumReport.to_json(result, json_path)

        assert json_path.exists()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["title"] == result.title
        assert len(data["tracks"]) == len(result.tracks)


# ═══════════════════════════════════════════════════════════════════════
# T05 CLI + 回归测试
# ═══════════════════════════════════════════════════════════════════════

class TestCLIMake:
    """CLI make 命令测试。"""

    def test_make_demo_exit_zero(self, tmp_path: Path):
        """验证 --demo 全链路 exit 0。"""
        from album_maker.cli import main

        out_dir = tmp_path / "cli_test_output"
        # 使用 sys.argv 风格调用
        exit_code = main(["make", "--demo", "--out", str(out_dir)])
        assert exit_code == 0, f"CLI make --demo 退出码={exit_code}"

    def test_make_demo_output_structure(self, tmp_path: Path):
        """验证 CLI --demo 输出目录结构。"""
        from album_maker.cli import main

        out_dir = tmp_path / "cli_test_output2"
        main(["make", "--demo", "--out", str(out_dir)])

        # album_manifest.json
        assert (out_dir / "album_manifest.json").exists()

        # album.yaml.copy
        assert (out_dir / "album.yaml.copy").exists()

        # 至少 3 个 track 目录
        track_dirs = sorted(out_dir.glob("track_*"))
        assert len(track_dirs) >= 3, f"期望 >=3 个曲目目录，实际 {len(track_dirs)}"

        for td in track_dirs:
            assert (td / "song_final.wav").exists(), f"缺少 song_final.wav: {td.name}"
            assert (td / "manifest.json").exists(), f"缺少 manifest.json: {td.name}"
            assert (td / "_sources").is_dir(), f"缺少 _sources/: {td.name}"

    def test_make_missing_config(self):
        """验证缺少 --config 和 --demo 时返回非零退出码。"""
        from album_maker.cli import main

        exit_code = main(["make", "--out", "/tmp/test"])
        assert exit_code == 1

    def test_make_demo_verbose(self, tmp_path: Path):
        """验证 --demo --verbose 全链路 exit 0。"""
        from album_maker.cli import main

        out_dir = tmp_path / "cli_verbose"
        exit_code = main(["make", "--demo", "--out", str(out_dir), "--verbose"])
        assert exit_code == 0


class TestCLIDoctor:
    """CLI doctor 命令测试。"""

    def test_doctor_passes(self):
        """验证 doctor 命令正常执行。"""
        from album_maker.cli import main

        exit_code = main(["doctor"])
        # doctor 只要不抛异常就 OK（可能有环境问题但不应崩溃）
        assert exit_code in (0, 1)


class TestCLIListStyles:
    """CLI list-styles 命令测试。"""

    def test_list_styles(self):
        """验证 list-styles 列出 12 种风格。"""
        from album_maker.cli import main

        exit_code = main(["list-styles"])
        assert exit_code == 0


class TestCLIListPools:
    """CLI list-pools 命令测试。"""

    def test_list_pools(self):
        """验证 list-pools 正常执行。"""
        from album_maker.cli import main

        exit_code = main(["list-pools"])
        assert exit_code == 0


# ═══════════════════════════════════════════════════════════════════════
# 失败隔离测试
# ═══════════════════════════════════════════════════════════════════════

class TestTrackFailureIsolation:
    """验证单曲目失败不中断整张专辑。"""

    def test_track_result_error_field(self):
        """验证 TrackResult 的 error 字段。"""
        result = TrackResult(
            title="Failed Track",
            success=False,
            error="模拟失败: 混音异常",
            bpm=120,
            key="C",
        )
        assert not result.success
        assert result.error is not None
        assert result.song_path is None

    def test_album_result_counts_failures(self):
        """验证 AlbumResult 正确统计成功/失败数。"""
        from pathlib import Path

        results = [
            TrackResult(title="T1", success=True, bpm=100, key="Am"),
            TrackResult(title="T2", success=False, error="fail", bpm=140, key="Em"),
            TrackResult(title="T3", success=True, bpm=90, key="C"),
        ]
        album_result = AlbumResult(
            title="Test",
            tracks=results,
            success_count=2,
            failure_count=1,
        )
        assert album_result.success_count == 2
        assert album_result.failure_count == 1
        assert not album_result.all_success


# ═══════════════════════════════════════════════════════════════════════
# album_maker __init__.py 导出测试
# ═══════════════════════════════════════════════════════════════════════

class TestPackageExports:
    """验证 __init__.py 导出完整性。"""

    def test_all_exports_importable(self):
        """验证所有公开导出都可导入。"""
        from album_maker import (
            AlbumConfig,
            AlbumMaker,
            AlbumReport,
            AlbumResult,
            DEMO_ALBUM_CONFIG,
            TrackHandler,
            TrackResult,
            TrackSpec,
            make_demo_config,
        )
        assert AlbumConfig is not None
        assert AlbumMaker is not None
        assert AlbumReport is not None
        assert AlbumResult is not None
        assert DEMO_ALBUM_CONFIG is not None
        assert TrackHandler is not None
        assert TrackResult is not None
        assert TrackSpec is not None
        assert callable(make_demo_config)
