# -*- coding: utf-8 -*-
"""
report.py —— 混音报告（镜像 musickit remix 报告字段：
prompt/style/seed/bpm/bars/structure/mixer_style/sources/song/stems）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class RemixReport:
    title: str = ""
    prompt: dict = field(default_factory=dict)
    seed: int = 0
    bpm: int = 120
    bars: int = 16
    structure: str = "classic_drop"
    mixer_style: str = ""
    release_safe: bool = True
    license_tier: str = "selfgen"
    sources: list = field(default_factory=list)   # SourceSpec.as_dict()
    stems: list = field(default_factory=list)     # 分轨文件名
    song: str = ""                                # 成品文件名
    duration_sec: float = 0.0
    out_dir: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    def to_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p
