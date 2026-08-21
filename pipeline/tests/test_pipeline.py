# -*- coding: utf-8 -*-
"""
test_pipeline.py —— 纯合成流水线回归测试（T7）

测试覆盖（设计 §8）：
  - 依赖隔离（R1: torch ∉ sys.modules）
  - make_source synth（无 MIDI 程序化 pattern / MIDI 导入两种路径）
  - mixdown + manifest + sha256（P0-3 / P0-4）
  - run_pipeline B→C 集成（断点续跑）
  - 异常路径（空音源 / 无效音频 / 阶段失败不崩）

所有测试使用 conftest 的合成小样本（标准库 wave 生成），
零外部采样、不依赖网络或真实歌曲。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from config import bootstrap_env
bootstrap_env()  # 幂等，确保测试进程内环境就绪

from config import (
    HONESTY_DISCLAIMER,
    HONESTY_MODE_A,
)
from source_maker import TrackSpec, make_source
from mixdown import mixdown
from manifest import Manifest, SourceManifestEntry, sha256_file, write_manifest, read_manifest
from orchestrator import PipelineConfig, run_pipeline
from core.audio_mixer import MixConfig


# ═════════════════════ R1 依赖隔离 ═════════════════════


def test_torch_not_in_sys_modules() -> None:
    """R1：编排进程内 torch 绝不在 sys.modules。"""
    assert "torch" not in sys.modules, (
        "违反 R1 依赖隔离！torch 被意外 import 进编排进程。"
    )


def test_remix_importable() -> None:
    """R2：remix.core 可 import（sys.path 注入生效）。"""
    from core.audio_mixer import AudioMixer
    from core.audio_loader import AudioLoader
    assert AudioMixer is not None
    assert AudioLoader is not None


def test_bloodmusic_importable() -> None:
    """R4：bloodmusic 可 import（editable install 有效，零改造）。"""
    import bloodmusic.bridge
    assert bloodmusic.bridge is not None


def test_pydub_pinned() -> None:
    """pydub converter / ffprobe 已 pin 到 remix/bin。"""
    from pydub import AudioSegment
    conv = Path(AudioSegment.converter)
    assert conv.name in ("ffmpeg.exe", "ffmpeg"), f"converter={conv}"
    assert conv.exists(), f"ffmpeg 缺失: {conv}"


# ═════════════════════ T3 单音源导出 ═════════════════════


def test_make_source_synth_programmatic(tmp_workspace: Path) -> None:
    """synth 路径：无 MIDI 的程序化 pattern → 振荡器合成 WAV。"""
    stems_dir = tmp_workspace / "stems"
    spec = TrackSpec(name="test_synth", kind="synth", bpm=120, duration_sec=2.0, fmt="wav")
    out = make_source(spec, stems_dir)
    assert out.is_file()
    assert out.suffix == ".wav"
    assert out.stat().st_size > 100, "产物过小——渲染可能为空"
    # 文件名符合 §6.2
    assert out.name == "synth__test_synth.wav"


def test_make_source_synth_from_midi(synthetic_midi: Path, tmp_workspace: Path) -> None:
    """synth 路径：从 MIDI 文件 import → 渲染。"""
    stems_dir = tmp_workspace / "stems"
    spec = TrackSpec(
        name="midi_synth", kind="synth",
        pattern_source=synthetic_midi, bpm=120, fmt="wav",
    )
    out = make_source(spec, stems_dir)
    assert out.is_file()
    assert out.stat().st_size > 100


def test_make_source_rejects_unknown_kind(tmp_workspace: Path) -> None:
    """非 synth kind 应抛 ValueError（纯合成流水线）。"""
    spec = TrackSpec(name="bad", kind="sampled", bpm=120, fmt="wav")
    with pytest.raises(ValueError, match="synth"):
        make_source(spec, tmp_workspace / "stems")


# ═════════════════════ T4 混音 + manifest ═════════════════════


def test_manifest_roundtrip(tmp_path: Path) -> None:
    """manifest 写 → 读 往返一致。"""
    m = Manifest(
        song="song_final.wav", bpm=120, sample_rate=44100,
        sources=[SourceManifestEntry("a.wav", "synth", "stems/a.wav", "abc123")],
        separate_mode="manifest", note=HONESTY_DISCLAIMER,
    )
    p = tmp_path / "manifest.json"
    write_manifest(p, m)
    m2 = read_manifest(p)
    assert m2.song == m.song
    assert m2.bpm == 120
    assert m2.sources[0].sha256 == "abc123"


def test_sha256_file(tmp_path: Path) -> None:
    """sha256 计算正确。"""
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    h = sha256_file(f)
    assert len(h) == 64
    assert sha256_file(f) == h  # 幂等


def test_mixdown_with_synth_stems(tmp_workspace: Path) -> None:
    """阶段B→C 集成：生成 synth stems → 混音 → manifest + _sources。"""
    stems_dir = tmp_workspace / "stems"
    sources: list[Path] = []
    for name, dur in [("bass", 2.0), ("pad", 2.0)]:
        spec = TrackSpec(name=name, kind="synth", bpm=120, duration_sec=dur, fmt="wav")
        sources.append(make_source(spec, stems_dir))

    # 混音
    mixdown_dir = tmp_workspace / "mixdown"
    result = mixdown(sources, mixdown_dir, MixConfig(), fmt="wav", separate_mode="manifest")

    assert result.song_path.is_file()
    assert result.song_path.stat().st_size > 100
    assert result.sources_dir.is_dir()
    assert result.manifest_path.is_file()

    # _sources 含全部源
    for src in sources:
        assert (result.sources_dir / src.name).is_file()

    # manifest 校验
    mani = read_manifest(result.manifest_path)
    assert mani.song == result.song_path.name
    assert mani.bit_depth == 16
    assert mani.separate_mode == "manifest"
    assert len(mani.sources) == len(sources)


# ═════════════════════ 诚实性声明 ═════════════════════


def test_honesty_disclaimer_constant() -> None:
    """HONESTY_DISCLAIMER 含零外部采样声明。"""
    assert "混音不可逆" in HONESTY_DISCLAIMER
    assert "零外部采样" in HONESTY_DISCLAIMER
    assert "100% 保真" in HONESTY_DISCLAIMER
    assert "100% 保真" in HONESTY_MODE_A


# ═════════════════════ T6 全链路集成（B→C） ═════════════════════


def test_run_pipeline_bc_integration(tmp_workspace: Path) -> None:
    """run_pipeline B→C：合成 stems → 混音 → manifest + _sources。"""
    ws = tmp_workspace
    cfg = PipelineConfig(
        workspace=ws,
        stages=["B", "C"],
        separate_mode="manifest",
        track_specs=[
            TrackSpec(name="b1", kind="synth", bpm=120, duration_sec=1.5, fmt="wav"),
            TrackSpec(name="p1", kind="synth", bpm=120, duration_sec=1.5, fmt="wav"),
        ],
        mix_fmt="wav",
    )
    report = run_pipeline(cfg)
    assert report["ok"], f"流水线失败: {report['errors']}"
    assert "B" in report["stages"]
    assert "C" in report["stages"]

    # 产物文件存在
    assert (ws / "stems").is_dir()
    assert any((ws / "stems").glob("*.wav"))
    assert (ws / "mixdown" / "song_final.wav").is_file()
    manifest_path = ws / "mixdown" / "manifest.json"
    assert manifest_path.is_file()

    # _sources 保留且 sha256 与 manifest 一致
    sources_dir = ws / "mixdown" / "_sources"
    mani = read_manifest(manifest_path)
    assert len(mani.sources) == 2
    for e in mani.sources:
        orig = sources_dir / e.output_name
        assert orig.is_file()
        assert sha256_file(orig) == e.sha256


def test_run_pipeline_resume(tmp_workspace: Path) -> None:
    """断点续跑：首次运行 B→C 后第二次运行应全部 skip。"""
    ws = tmp_workspace
    cfg = PipelineConfig(
        workspace=ws,
        stages=["B", "C"],
        separate_mode="manifest",
        track_specs=[
            TrackSpec(name="r1", kind="synth", bpm=120, duration_sec=1.0, fmt="wav"),
        ],
        mix_fmt="wav",
    )
    report1 = run_pipeline(cfg)
    assert report1["ok"]

    # 第二次运行
    report2 = run_pipeline(cfg)
    assert report2["ok"]
    # 各阶段应标记为 skipped
    for stage in ("B", "C"):
        status = report2["stages"].get(stage, "")
        assert "skip" in status.lower() or "already" in status.lower(), (
            f"阶段 {stage} 未预期跳过: '{status}'"
        )


# ═════════════════════ 异常路径 ═════════════════════


def test_mixdown_empty_sources(tmp_workspace: Path) -> None:
    """混音空音源应抛 ValueError。"""
    with pytest.raises(ValueError, match="至少"):
        mixdown([], tmp_workspace / "mixdown", MixConfig())


def test_invalid_audio(tmp_path: Path) -> None:
    """传入损坏/空文件应报明确错误。"""
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"\x00\x00\x00\x00")  # 无效 WAV 头
    from core.audio_loader import AudioLoader
    loader = AudioLoader()
    with pytest.raises(Exception):
        loader.load(str(bad))


def test_pipeline_stage_failure_does_not_block_later(
    tmp_workspace: Path,
) -> None:
    """异常不破坏已产物：直接跑阶段C（缺 stems）→ 报错但 report 正常返回。"""
    ws = tmp_workspace
    cfg = PipelineConfig(
        workspace=ws,
        stages=["C"],  # 直接跑 C，缺 stems
        separate_mode="manifest",
        mix_fmt="wav",
    )
    report = run_pipeline(cfg)
    # C 会失败（缺 stems），但 report 仍返回
    assert not report["ok"]
    assert any("C" in e[0] for e in report["errors"])
