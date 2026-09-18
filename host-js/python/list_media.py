#!/usr/bin/env python3
"""BloodMusic 媒体枚举器 —— 产出跨端 MediaItem[] 契约（players-unified 宿主消费）。

形态对齐 daily_player/media_source.py 的 MediaItem（schema/media-item.schema.json）：
  { id, uri, title, artist, kind, durationMs, source, subtitleTracks, thumbnail }

roots 可配置（命令行参数；默认扫 BloodMusic 的典型产物目录）：
  - 仓库内：album_output/ mirror_output/ album_maker_quick/
  - 临时：  %TEMP%/bloodmusic-rpc/（host-js RPC 服务的默认产物目录）

零三方依赖（纯 stdlib）。用法：
  python list_media.py [root ...]        # 默认 roots = 上述四目录（存在才扫）
  python list_media.py --roots-json '["G:/x","G:/y"]'
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

AUDIO_EXTS = {".wav", ".ogg", ".flac", ".mp3", ".m4a", ".aac"}

# 默认 roots：BloodMusic 的典型产物目录（存在才扫，缺省不报错）
DEFAULT_ROOTS = [
    REPO_ROOT / "album_output",
    REPO_ROOT / "mirror_output",
    REPO_ROOT / "album_maker_quick",
    Path(tempfile.gettempdir()) / "bloodmusic-rpc",
]

MAX_PER_ROOT = 500  # 防御性上限：产物目录失控时不至于把宿主聚合撑爆


def _stable_id(path: Path) -> str:
    return "bm-" + hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]


def _media_item(path: Path) -> dict | None:
    ext = path.suffix.lower()
    if ext not in AUDIO_EXTS:
        return None
    return {
        "id": _stable_id(path),
        "uri": str(path.resolve()),
        "title": path.stem,
        "artist": "BloodMusic",
        "kind": "audio",
        "durationMs": None,
        "source": "bloodmusic",
        "subtitleTracks": [],
        "thumbnail": None,
    }


def list_media(root: Path) -> list[dict]:
    """递归枚举一个产物目录下的音频文件 → MediaItem[]。"""
    if not root.is_dir():
        return []
    items: list[dict] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        item = _media_item(p)
        if item:
            items.append(item)
        if len(items) >= MAX_PER_ROOT:
            break
    return items


def main(argv: list[str]) -> int:
    if "--roots-json" in argv:
        i = argv.index("--roots-json")
        roots = [Path(x) for x in json.loads(argv[i + 1])]
    elif len(argv) > 1:
        roots = [Path(a) for a in argv[1:]]
    else:
        roots = DEFAULT_ROOTS

    items: list[dict] = []
    for root in roots:
        items.extend(list_media(root))

    print(json.dumps(items, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
