#!/usr/bin/env python3
"""
Tests for album_maker MIDI path support.

Verifies that TrackSpec with midi_path set:
  1. Produces WAV stems from MIDI import (not PoolGenerator)
  2. Generates a valid mixdown WAV
  3. Does NOT break the synth path (midi_path="" should behave unchanged)
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Known-good MIDI asset
PIANO_MIDI = Path("G:/midi/MusicStudio/Data/MIDI/Piano.mid")

# ── Helpers ────────────────────────────────────────────────


def _mido_available() -> bool:
    """Check if mido is importable (required for MIDI E2E tests)."""
    try:
        import mido  # noqa: F401
        return True
    except ImportError:
        return False


def _audio_pipeline_available() -> bool:
    """Check if audio_pipeline dependencies (pydub etc.) are available."""
    try:
        import pydub  # noqa: F401
        return True
    except ImportError:
        return False


def _make_test_pool(name: str = "test_pool"):
    """Create a minimal InstrumentPool with one wavetable instrument."""
    from bloodmusic.music.instrument_pool import (
        InstrumentPool,
        InstrumentRole,
        PoolConfig,
        PoolInstrument,
        SynthEngine,
    )

    inst = PoolInstrument(
        name="Synth Lead",
        role=InstrumentRole.MELODY,
        engine=SynthEngine.WAVETABLE,
        preset="bright_lead",
        volume=0.8,
        pan=0.0,
    )
    return InstrumentPool(
        name=name,
        instruments=[inst],
        config=PoolConfig(),
    )


# ═════════════════════════════════════════════════════════════
# 1. TrackSpec midi_path field
# ═════════════════════════════════════════════════════════════


def test_trackspec_has_midi_path_field():
    """TrackSpec dataclass must expose midi_path with default empty string."""
    from bloodmusic.album_maker.config import TrackSpec

    spec = TrackSpec(title="Test Track")
    assert hasattr(spec, "midi_path"), "TrackSpec missing midi_path field"
    assert spec.midi_path == "", "midi_path default must be empty string"


def test_trackspec_midi_path_settable():
    """TrackSpec.midi_path can be set to a non-empty path."""
    from bloodmusic.album_maker.config import TrackSpec

    spec = TrackSpec(title="MIDI Track", midi_path=str(PIANO_MIDI))
    assert spec.midi_path == str(PIANO_MIDI)


# ═════════════════════════════════════════════════════════════
# 2. YAML parsing round-trip
# ═════════════════════════════════════════════════════════════


def test_yaml_parses_midi_path():
    """AlbumConfig.from_yaml should parse midi_path from track entry."""
    from bloodmusic.album_maker.config import AlbumConfig

    yaml_content = yaml.safe_dump(
        {
            "album": {"title": "Test MIDI Album", "artist": "Test", "genre": "classical"},
            "tracks": [
                {
                    "title": "Piano Track",
                    "bpm": 120,
                    "bars": 16,
                    "key": "C",
                    "style": "classical",
                    "midi_path": str(PIANO_MIDI),
                }
            ],
        }
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        config = AlbumConfig.from_yaml(yaml_path)
        assert len(config.tracks) == 1
        track = config.tracks[0]
        assert track.midi_path == str(PIANO_MIDI)
        assert track.title == "Piano Track"
        assert track.bpm == 120
    finally:
        os.unlink(yaml_path)


def test_yaml_without_midi_path_defaults_empty():
    """YAML track without midi_path should default to empty string."""
    from bloodmusic.album_maker.config import AlbumConfig

    yaml_content = yaml.safe_dump(
        {
            "album": {"title": "No MIDI Album", "artist": "Test"},
            "tracks": [
                {"title": "Synth Track", "bpm": 140, "bars": 32, "key": "Am", "style": "battle"}
            ],
        }
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        config = AlbumConfig.from_yaml(yaml_path)
        assert len(config.tracks) == 1
        track = config.tracks[0]
        assert track.midi_path == "", "midi_path should default to empty string"
    finally:
        os.unlink(yaml_path)


# ═════════════════════════════════════════════════════════════
# 3. MIDI path end-to-end: stems → mixdown → readable WAV
# ═════════════════════════════════════════════════════════════


@pytest.mark.slow
class TestMidiPathE2E:
    """End-to-end: TrackHandler with midi_path produces mixdown WAV."""

    @pytest.fixture
    def check_mido(self):
        """Skip all tests in this class if mido is not installed."""
        if not _mido_available():
            pytest.skip("mido not installed — MIDI E2E tests require mido>=1.3")

    @pytest.fixture
    def midi_spec(self):
        """A TrackSpec with midi_path pointing to Piano.mid."""
        from bloodmusic.album_maker.config import TrackSpec

        return TrackSpec(
            title="MIDI Piano Test",
            bpm=120,
            bars=16,
            key="C",
            style="classical",
            midi_path=str(PIANO_MIDI),
        )

    def test_midi_path_produces_stems_and_mixdown(self, check_mido, midi_spec):
        """Full pipeline: MIDI import → stems → mixdown → readable WAV."""
        from bloodmusic.album_maker.track import TrackHandler

        pool = _make_test_pool()

        with tempfile.TemporaryDirectory(prefix="bloodmusic_midi_test_") as tmpdir:
            work_dir = Path(tmpdir)

            handler = TrackHandler(
                spec=midi_spec,
                pool=pool,
                mix_config_raw={},
                separate_mode="manifest",
            )

            result = handler.process(work_dir)

            # Must succeed
            assert result.success, (
                f"TrackHandler.process() failed: {result.error}"
            )
            assert result.title == "MIDI Piano Test"

            # Must produce a mixdown WAV
            assert result.song_path is not None, "No song_path returned"
            assert result.song_path.exists(), (
                f"song_path does not exist: {result.song_path}"
            )
            assert result.song_path.suffix == ".wav", (
                f"Expected .wav, got {result.song_path.suffix}"
            )

            # WAV must be non-trivial size
            size_kb = result.song_path.stat().st_size / 1024
            assert size_kb > 10, (
                f"Mixdown WAV too small: {size_kb:.1f} KB"
            )

            # Must have stems directory
            stems_dir = work_dir / "stems"
            assert stems_dir.exists(), "stems directory not created"
            stem_files = list(stems_dir.glob("*.wav"))
            assert len(stem_files) > 0, (
                "No WAV stems produced from MIDI import"
            )
            for sf in stem_files:
                assert sf.stat().st_size > 1024, (
                    f"Stem {sf.name} is too small: {sf.stat().st_size} bytes"
                )

            # Verify manifest
            if result.manifest_path:
                assert result.manifest_path.exists(), (
                    f"manifest does not exist: {result.manifest_path}"
                )

    def test_midi_path_skips_pool_generator(self, check_mido, midi_spec):
        """Verify that midi_path results include MIDI-imported pattern names.

        MIDI stems (from midi_to_patterns_v2) are named "{stem}_{track_name}",
        where stem = MIDI filename stem. Synth stems would be named differently.
        """
        from bloodmusic.album_maker.track import TrackHandler

        pool = _make_test_pool()

        with tempfile.TemporaryDirectory(prefix="bloodmusic_midi_test_") as tmpdir:
            work_dir = Path(tmpdir)

            handler = TrackHandler(
                spec=midi_spec,
                pool=pool,
                mix_config_raw={},
                separate_mode="manifest",
            )

            result = handler.process(work_dir)
            assert result.success, f"process() failed: {result.error}"

            stems_dir = work_dir / "stems"
            stem_files = list(stems_dir.glob("*.wav"))
            stem_names = {sf.stem for sf in stem_files}

            # MIDI-imported stems should contain "Piano" in the name
            # (midi_to_patterns_v2 names patterns as "{stem}_{track_name}")
            piano_named = [n for n in stem_names if "Piano" in n or "piano" in n]
            assert len(piano_named) > 0, (
                f"No Piano-named stems found in {stem_names}. "
                f"MIDI import may not have worked."
            )


# ═════════════════════════════════════════════════════════════
# 4. Regression: midi_path="" preserves original behavior
# ═════════════════════════════════════════════════════════════


@pytest.mark.slow
class TestNoMidiPathRegression:
    """midi_path="" (default) must behave exactly as before."""

    @pytest.fixture
    def check_deps(self):
        """Skip if audio_pipeline dependencies not available."""
        if not _audio_pipeline_available():
            pytest.skip("pydub not installed — synth mixdown E2E requires audio_pipeline")

    def test_empty_midi_path_uses_pool_generator(self, check_deps):
        """TrackSpec without midi_path should still use PoolGenerator."""
        from bloodmusic.album_maker.config import TrackSpec
        from bloodmusic.album_maker.track import TrackHandler

        spec = TrackSpec(
            title="Synth Track",
            bpm=140,
            bars=4,
            key="Am",
            style="battle",
        )
        pool = _make_test_pool()

        with tempfile.TemporaryDirectory(prefix="bloodmusic_nomidi_") as tmpdir:
            work_dir = Path(tmpdir)
            handler = TrackHandler(
                spec=spec,
                pool=pool,
                mix_config_raw={},
                separate_mode="manifest",
            )

            result = handler.process(work_dir)
            assert result.success, (
                f"Synth path failed: {result.error}"
            )
            assert result.song_path is not None
            assert result.song_path.exists()
            size_kb = result.song_path.stat().st_size / 1024
            assert size_kb > 10, (
                f"Synth mixdown WAV too small: {size_kb:.1f} KB"
            )


# ═════════════════════════════════════════════════════════════
# 5. Error handling: invalid / missing MIDI path
# ═════════════════════════════════════════════════════════════


def test_midi_path_file_not_found_does_not_crash():
    """A non-existent midi_path should produce a warning but not crash."""
    from bloodmusic.album_maker.config import TrackSpec
    from bloodmusic.album_maker.track import TrackHandler

    spec = TrackSpec(
        title="Bad MIDI",
        bpm=120,
        bars=8,
        key="C",
        midi_path="Z:/nonexistent/ghost.mid",
    )
    # Use an empty pool (no instruments) — MIDI path failure + no synth fallback
    # → should fail gracefully, no crash
    from bloodmusic.music.instrument_pool import (
        InstrumentPool,
        PoolConfig,
    )
    pool = InstrumentPool(name="test_pool", config=PoolConfig())

    with tempfile.TemporaryDirectory(prefix="bloodmusic_badmidi_") as tmpdir:
        work_dir = Path(tmpdir)
        handler = TrackHandler(
            spec=spec,
            pool=pool,
            mix_config_raw={},
            separate_mode="manifest",
        )

        result = handler.process(work_dir)
        # MIDI import fails, no synth stems (midi_path non-empty skips PoolGenerator)
        # → should fail gracefully with error message
        assert not result.success, (
            "Should fail when midi_path is invalid and no synth fallback"
        )
        assert result.error is not None
        assert "未产生任何 WAV" in result.error or "wav" in result.error.lower()
