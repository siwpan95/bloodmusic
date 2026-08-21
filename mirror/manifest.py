# -*- coding: utf-8 -*-
"""
manifest.py —— 生成资产清单（镜像 musickit 各池 manifest.json + manifest_index.json）

字段对齐（musickit manifest_index.json entries）：
    file / source_pack / original / duration_s / sha256 / subcategory /
    license_tier / content_kind / bpm / key
bloodmusic 侧差异：
    source_pack/ original → 合成引擎/预设（selfgen，无来源文件）
    license_tier 恒为 "selfgen"（自生成，天然 release-safe）
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class SourceManifestEntry:
    """单条生成音源的清单记录。"""

    file: str                      # 文件名（如 stems/lead.wav）
    subcategory: str               # 子类（镜像采样子目录）
    license_tier: str = "selfgen"  # 恒 selfgen
    content_kind: str = "loop"     # stem | loop | one_shot（镜像同名语义）
    duration_s: float = 0.0
    sha256: str = ""
    synth_engine: str = ""         # 合成引擎（镜像 source_pack）
    synth_preset: str = ""         # 预设（镜像 original）
    bpm: int = 120
    key: str = "C"
    role: str = ""                 # 混音角色（镜像 mixer_role）
    seed: int = 0                  # 生成种子（可复现）

    def as_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class PoolManifest:
    """单池清单（镜像 musickit <pool>/manifest.json）。"""

    pool: str
    generated: str = ""
    entries: list[SourceManifestEntry] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pool": self.pool,
            "generated": self.generated,
            "license_tier": "selfgen",
            "entries": [e.as_dict() for e in self.entries],
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_pool_manifest(path: str | Path, manifest: PoolManifest) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def read_pool_manifest(path: str | Path) -> PoolManifest:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = [SourceManifestEntry(**e) for e in data.get("entries", [])]
    return PoolManifest(pool=data["pool"], generated=data.get("generated", ""), entries=entries)


def build_index(manifest_paths: list[str | Path]) -> dict:
    """聚合多个池清单为总索引（镜像 musickit manifest_index.json）。"""
    categories: dict[str, dict] = {}
    for mp in manifest_paths:
        m = read_pool_manifest(mp)
        categories[m.pool] = {
            "dir": str(Path(mp).parent),
            "audio_files": len(m.entries),
            "manifest_entries": len(m.entries),
            "entries": [e.as_dict() for e in m.entries],
        }
    return {"categories": categories}
