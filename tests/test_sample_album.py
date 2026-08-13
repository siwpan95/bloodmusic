"""采样专辑制作器测试 — scan_stems + make_sample_album。"""

import numpy as np
import pytest

from bloodmusic.album_maker.sample_album import (
    scan_stems, make_sample_album, STEM_ROLES, DEFAULT_STEMS_DIR,
)


def test_stem_roles_exclude_vocals():
    assert set(STEM_ROLES) == {"bass", "drums", "other"}
    assert "vocals" not in STEM_ROLES


def test_scan_stems_collects_three_roles():
    by_role = scan_stems()
    if not DEFAULT_STEMS_DIR.is_dir():
        pytest.skip("stems 目录不存在")
    if not by_role["bass"]:
        pytest.skip("stems 目录为空（拆解未完成）")
    assert by_role["bass"], "bass 采样应为空"
    assert by_role["drums"], "drums 采样应为空"
    assert by_role["other"], "other 采样应为空"
    # 所有采样都是 .wav
    for role in ("bass", "drums", "other"):
        for p in by_role[role][:3]:
            assert p.suffix.lower() == ".wav"


def test_scan_stems_missing_dir_returns_empty():
    by_role = scan_stems("Z:/no_such_dir_xyz")
    assert by_role == {"bass": [], "drums": [], "other": []}


@pytest.mark.slow
def test_make_sample_album_single_track(tmp_path):
    """生成 1 首采样曲目，验证采样专辑管线端到端。"""
    if not DEFAULT_STEMS_DIR.is_dir():
        pytest.skip("stems 目录不存在")
    result = make_sample_album(
        n_tracks=1, seed=42, out_dir=str(tmp_path),
    )
    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert track.success, "单曲采样专辑应生成成功"
    assert track.song_path and str(track.song_path).endswith(".wav")
    assert track.duration_sec > 5.0


def test_make_sample_album_missing_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        make_sample_album(stems_dir="Z:/no_such_dir_xyz", n_tracks=1,
                          out_dir=str(tmp_path))


def test_make_sample_album_bad_style_ignored(tmp_path):
    """styles 白名单中的未知风格被忽略，不影响生成。"""
    if not DEFAULT_STEMS_DIR.is_dir():
        pytest.skip("stems 目录不存在")
    result = make_sample_album(
        n_tracks=1, styles=["lofi", "no_such_style"], seed=1,
        out_dir=str(tmp_path),
    )
    assert len(result.tracks) == 1
    assert result.tracks[0].success, "未知风格应被忽略且不影响生成"
