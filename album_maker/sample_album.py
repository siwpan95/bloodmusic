"""album_maker/sample_album.py — 采样专辑制作器
============================================================
仅从 G:\\radio_music_stems 挑选材料：随机选择 bass / drums / other 三轨
（排除 vocals），按现有风格（style_db 12 风格）组织成一张专辑。

复用 AlbumMaker 管线：每首曲目通过 TrackSpec.extra_instruments 挂 3 个
SAMPLER 乐器（bass/drums/other），由 TrackHandler 阶段 S 渲染真实采样。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import AlbumConfig, TrackSpec
from .album import AlbumMaker
from .style_db import STYLE_DB
from .quick import BARS_OPTIONS, MIX_CONFIG_DEFAULTS, TITLE_TEMPLATES

__all__ = ["scan_stems", "make_sample_album", "SampleAlbumConfig"]

#: 默认 stems 目录
DEFAULT_STEMS_DIR = Path(r"G:/radio_music_stems")

#: 参与采样的 stem 角色 → 乐器角色映射（vocals 被排除）
STEM_ROLES = {
    "bass": "bass",
    "drums": "drum",
    "other": "pad",
}

#: 默认输出目录
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "album_output_samples"


@dataclass
class SampleAlbumConfig:
    """采样专辑参数（可 JSON 化，便于 CLI/GUI 传递）。"""
    stems_dir: str = str(DEFAULT_STEMS_DIR)
    n_tracks: int = 8
    styles: list[str] = field(default_factory=lambda: list(STYLE_DB.keys()))
    seed: Optional[int] = None
    out_dir: str = str(DEFAULT_OUT_DIR)
    allow_same_song: bool = False
    min_stem_sec: float = 10.0   # 忽略过短采样（秒）


def scan_stems(stems_dir: str | Path | None = None) -> dict[str, list[Path]]:
    """扫描 stems 目录，按角色收集 bass/drums/other 采样路径。

    每首已拆解歌曲目录含 bass.wav / drums.wav / other.wav / vocals.wav，
    只收集 bass/drums/other，vocals 明确排除。

    Returns:
        {"bass": [Path, ...], "drums": [...], "other": [...]}
    """
    root = Path(stems_dir) if stems_dir else DEFAULT_STEMS_DIR
    by_role: dict[str, list[Path]] = {"bass": [], "drums": [], "other": []}
    if not root.is_dir():
        return by_role

    for wav in sorted(root.rglob("*.wav")):
        stem = wav.stem.lower()
        if stem in by_role:
            by_role[stem].append(wav)
    return by_role


def _pick_stems(by_role: dict[str, list[Path]], rng: random.Random,
                allow_same_song: bool = False) -> list[dict]:
    """随机挑一个 bass / drums / other 采样，构造 sampler 乐器列表。

    默认三个采样来自不同歌曲（避免同源自相关）。
    """
    used_songs: set[str] = set()
    picks: list[dict] = []
    volume_by_role = {"bass": 0.9, "drums": 0.85, "other": 0.6}

    for stem_role, role in STEM_ROLES.items():
        pool = by_role[stem_role]
        candidates = pool if allow_same_song else [
            p for p in pool
            if p.parent.name not in used_songs or all(
                q.parent.name in used_songs for q in pool
            )
        ]
        # 兜底：若过滤后为空（采样都同源），回退全池
        if not candidates:
            candidates = pool
        chosen = rng.choice(candidates)
        used_songs.add(chosen.parent.name)
        picks.append({
            "name": stem_role,
            "role": role,
            "engine": "sampler",
            "sample_path": chosen.as_posix(),
            "volume": volume_by_role[stem_role],
            "pan": 0.0 if stem_role != "other" else 0.2,
        })
    return picks


def make_sample_album(
    stems_dir: str | Path | None = None,
    n_tracks: int = 8,
    styles: Optional[list[str]] = None,
    seed: Optional[int] = None,
    out_dir: str | Path | None = None,
    allow_same_song: bool = False,
    album_title: str = "Sample Collage",
) -> "AlbumResult":
    """仅从 stems 随机挑 bass/drums/other，按现有风格制作一张专辑。

    Args:
        stems_dir: stems 根目录（默认 G:\\radio_music_stems）
        n_tracks: 曲目数
        styles: 允许的风格名列表（默认全部 12 种）
        seed: 随机种子（可复现）
        out_dir: 输出目录
        allow_same_song: 允许同一首歌的多个 stem 同时出现
        album_title: 专辑名

    Returns:
        AlbumResult（AlbumMaker.make 的返回，含逐曲结果 + manifest）
    """
    rng = random.Random(seed)
    by_role = scan_stems(stems_dir)
    for role in ("bass", "drums", "other"):
        if not by_role[role]:
            raise ValueError(
                f"stems 目录缺少 {role} 采样（{stems_dir}）。"
                f"请确认拆解已完成且含 bass/drums/other 三轨。"
            )

    style_list = list(styles) if styles else list(STYLE_DB.keys())
    style_list = [s for s in style_list if s in STYLE_DB]
    if not style_list:
        raise ValueError(f"没有可用风格，styles={styles}")

    base_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR

    # 每曲构造一个 TrackSpec（extra_instruments 挂 3 个采样乐器）
    tracks: list[TrackSpec] = []
    for i in range(n_tracks):
        style_name = rng.choice(style_list)
        style = STYLE_DB[style_name]
        bpm = rng.randint(*style["bpm_range"])
        bars = rng.choice(BARS_OPTIONS)
        key = rng.choice(style["keys"])
        scale = rng.choice(style["scales"])
        progression = rng.choice(style["progressions"])
        seed_val = rng.randint(0, 99999)
        title = rng.choice(TITLE_TEMPLATES).format(mood=style["mood"])

        extra = _pick_stems(by_role, rng, allow_same_song)
        # 把调性/进行塞进乐器 note_sequence 之外，通过 pool 的 generation 传达
        tracks.append(TrackSpec(
            title=f"{i + 1:02d} · {title}",
            bpm=bpm, bars=bars, key=key, style=style_name, seed=seed_val,
            extra_instruments=extra,
            mix_config_override=None,
        ))

    # 共享空 pool（全曲由 extra_instruments 采样驱动，无合成器兜底）
    config = AlbumConfig(
        title=album_title,
        artist="BloodMusic Sample Collage",
        genre="sample collage",
        year=2026,
        pool_raw={
            "name": album_title,
            "bpm": 120, "key": "C", "scale": "major",
            "global_volume": 0.85,
            "generation": {"humanize": True},
            "instruments": [],  # 仅采样，无合成器
        },
        mix_config_raw=MIX_CONFIG_DEFAULTS,
        separate_mode="manifest",
        tracks=tracks,
    )

    return AlbumMaker(config).make(str(base_dir))
