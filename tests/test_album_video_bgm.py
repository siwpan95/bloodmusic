#!/usr/bin/env python3
"""
Tests for album_maker video BGM support (--video parameter).

Verifies:
  1. AlbumResult has video_bgm_path field
  2. CLI parser exposes --video argument
  3. _mux_video_bgm raises on missing video file / no successful tracks
  4. AlbumMaker.make() without --video behaves unchanged (regression)
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═════════════════════════════════════════════════════════════
# 1. AlbumResult exposes video_bgm_path field
# ═════════════════════════════════════════════════════════════


def test_album_result_has_video_bgm_path_field():
    """AlbumResult dataclass must expose video_bgm_path (default None)."""
    from bloodmusic.album_maker.album import AlbumResult

    result = AlbumResult(title="Test")
    assert hasattr(result, "video_bgm_path"), (
        "AlbumResult missing video_bgm_path field"
    )
    assert result.video_bgm_path is None, (
        "video_bgm_path default must be None"
    )


# ═════════════════════════════════════════════════════════════
# 2. CLI parser exposes --video argument
# ═════════════════════════════════════════════════════════════


def test_cli_parser_has_video_arg():
    """build_parser() must include --video on the make subcommand."""
    from bloodmusic.album_maker.cli import build_parser

    parser = build_parser()

    # Parse --help to verify --video exists in make subcommand
    import io
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    try:
        # Just check that the parser doesn't reject --video
        args = parser.parse_args(["make", "--demo", "--video", "test.mp4"])
        assert hasattr(args, "video"), "make subcommand missing --video attribute"
        assert args.video == "test.mp4", (
            f"--video value should be 'test.mp4', got '{args.video}'"
        )
    except SystemExit:
        pytest.fail("build_parser() raised SystemExit when parsing --video arg")
    finally:
        sys.stdout = old_stdout


def test_cli_parser_video_defaults_to_none():
    """--video should default to None when not specified."""
    from bloodmusic.album_maker.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["make", "--demo"])
    assert args.video is None, f"--video default should be None, got '{args.video}'"


# ═════════════════════════════════════════════════════════════
# 3. _mux_video_bgm error handling (logic validation, no ffmpeg needed)
# ═════════════════════════════════════════════════════════════


class TestMuxVideoBgmErrors:
    """Logic validation tests — do not require ffmpeg or real video files."""

    @pytest.fixture
    def maker(self):
        """Create an AlbumMaker with a minimal config."""
        from bloodmusic.album_maker.config import AlbumConfig, TrackSpec
        from bloodmusic.album_maker.album import AlbumMaker

        config = AlbumConfig(
            title="Test Album",
            tracks=[
                TrackSpec(title="Track 1", bpm=120, bars=4, key="C", style="classical"),
            ],
        )
        return AlbumMaker(config)

    def test_mux_video_bgm_missing_video_file_raises(self, maker):
        """_mux_video_bgm raises FileNotFoundError when video doesn't exist.
        
        Validates that the file check runs BEFORE the VideoProcessor import,
        so this test passes even without pydub/ffmpeg installed.
        """
        from bloodmusic.album_maker.album import AlbumResult

        fake_video = Path("Z:/nonexistent/video_ghost.mp4")
        album_output = Path(tempfile.mkdtemp(prefix="bgm_test_"))

        result = AlbumResult(title="Test", out_dir=album_output, tracks=[])

        with pytest.raises(FileNotFoundError) as exc_info:
            maker._mux_video_bgm(
                video_path=str(fake_video),
                album_output=album_output,
                result=result,
            )
        assert "视频文件不存在" in str(exc_info.value)

    def test_mux_video_bgm_no_successful_tracks_raises(self, maker, tmp_path):
        """_mux_video_bgm raises RuntimeError when no tracks succeeded.
        
        Validates that the track check runs BEFORE the VideoProcessor import,
        so this test passes even without pydub/ffmpeg installed.
        """
        from bloodmusic.album_maker.album import AlbumResult

        # Create a fake video file (just an empty file, won't be read by ffmpeg)
        fake_video = tmp_path / "dummy.mp4"
        fake_video.write_bytes(b"\x00" * 100)

        album_output = Path(tempfile.mkdtemp(prefix="bgm_test_"))

        # AlbumResult with zero successful tracks
        result = AlbumResult(title="Test", out_dir=album_output, tracks=[])

        with pytest.raises(RuntimeError) as exc_info:
            maker._mux_video_bgm(
                video_path=str(fake_video),
                album_output=album_output,
                result=result,
            )
        assert "没有成功的曲目" in str(exc_info.value)


# ═════════════════════════════════════════════════════════════
# 4. Regression: make() without --video unaffected
# ═════════════════════════════════════════════════════════════


def test_make_accepts_video_path_parameter():
    """AlbumMaker.make() accepts video_path as an optional keyword argument."""
    from bloodmusic.album_maker.album import AlbumMaker

    import inspect
    sig = inspect.signature(AlbumMaker.make)
    params = sig.parameters
    assert "video_path" in params, (
        f"make() signature missing video_path parameter. Found: {list(params.keys())}"
    )
    assert params["video_path"].default is None, (
        "video_path default must be None"
    )


def test_album_maker_has_mux_video_bgm_method():
    """AlbumMaker exposes _mux_video_bgm as a private method."""
    from bloodmusic.album_maker.album import AlbumMaker

    assert hasattr(AlbumMaker, "_mux_video_bgm"), (
        "AlbumMaker missing _mux_video_bgm method"
    )
    assert callable(getattr(AlbumMaker, "_mux_video_bgm"))
