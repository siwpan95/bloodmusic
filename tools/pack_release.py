#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包 Gitee Release 用的便携源码 zip（Windows / Linux / macOS 通用）。

设计原则
--------
1. **只从 git 取文件**（``git ls-files``），不扫工作树。
   工作树里有大量被 .gitignore 的产物（album_output/、*.wav、.venv/、__pycache__），
   扫盘打包必然把几百兆运行输出和 .pyc 卷进去 —— 早期 v1.0.0 的便携包就是这样
   （1742 个条目里有 1225 个是 .pyc/__pycache__，92MB 里绝大部分是垃圾）。
2. **体积来自提交内容，不掺运行输出**，因此产物稳定、可重复。
3. 附一个 ``MANIFEST.txt`` 记录打包时刻与 HEAD 提交，方便日后核对来源。

用法
----
    python tools/pack_release.py --tag v2.0.0
    python tools/pack_release.py --tag v2.0.0 --out D:/tmp        # 指定输出目录
    python tools/pack_release.py --tag v2.0.0 --ref HEAD

产物命名：``bloodmusic-<ver>-src.zip``（ver 取 tag 名去掉前缀 ``v``）。
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 即便已入库，也不进便携包的内容（发布元数据 / 大二进制 / 平台残留）
EXTRA_EXCLUDE_PREFIXES = (
    ".git/",
    "release/",          # 历史上存放既有 zip，避免包套包
    "deliverables/",     # 大体积交付物
)
EXTRA_EXCLUDE_SUFFIXES = (
    ".zip", ".exe", ".dll", ".so", ".dylib", ".whl", ".tar.gz",
)


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="surrogateescape",
    )
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 失败：{proc.stderr.strip()}")
    return proc.stdout


def collect_files(ref: str) -> list[str]:
    """按 ref 的树列出文件（而不是工作树），过滤掉不该进包的类型。

    用 ``-z`` 取 NUL 分隔的原始字节名：仓库里有中文路径（`_smoke_output/晨雾___苏醒/`），
    而 git 默认会按 ``core.quotepath`` 把非 ASCII 字节转义成 ``\\346\\231\\250``，
    再拿去 ``cat-file`` 就找不到文件。``-z`` 输出的是真实路径，不转义。
    """
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "-z", "--full-tree", ref],
        cwd=ROOT, capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"git ls-tree 失败：{proc.stderr.decode('utf-8', 'replace')}")
    raw = proc.stdout
    files: list[bytes] = []
    for name in raw.split(b"\0"):
        if not name:
            continue
        # 路径过滤在 bytes 上做（都是 ASCII 前缀/后缀，无需解码）
        if any(name.startswith(p.encode()) for p in EXTRA_EXCLUDE_PREFIXES):
            continue
        if any(name.endswith(s.encode()) for s in EXTRA_EXCLUDE_SUFFIXES):
            continue
        files.append(name)
    return files


def read_blob(ref: str, raw_path: bytes) -> bytes:
    """直接读 git 对象，路径以原始字节传递，避免中文路径被二次编码。

    ``\\.\\git\\cmd\\git.exe`` 在 Windows 上按 ANSI/OEM 解释命令行；
    因此这里显式把参数以 UTF-8 字节拼进列表后交给 subprocess，
    并把 git 的行为固定为 ``core.quotepath=false`` 以外的方式 —— 用 bytes 传参。
    """
    proc = subprocess.run(
        [b"git", b"cat-file", b"blob", ref.encode() + b":" + raw_path],
        cwd=str(ROOT), capture_output=True,
    )
    if proc.returncode != 0:
        display = raw_path.decode("utf-8", "replace")
        raise SystemExit(
            f"读取 {ref}:{display} 失败：{proc.stderr.decode('utf-8', 'replace')}"
        )
    return proc.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 Gitee Release 便携源码 zip")
    ap.add_argument("--tag", required=True, help="版本 tag（如 v2.0.0），用于命名与 MANIFEST")
    ap.add_argument("--ref", default=None, help="取哪个引用打包（缺省同 --tag）")
    ap.add_argument("--out", default=None, help="输出目录（缺省 <repo>/release）")
    args = ap.parse_args()

    ref = args.ref or args.tag
    ver = args.tag[1:] if args.tag.startswith("v") else args.tag

    # 先用 git 校验引用存在，并拿到其提交 SHA
    sha = _git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    files = collect_files(sha)
    if not files:
        raise SystemExit(f"{ref} 下没有可打包文件")

    out_dir = Path(args.out) if args.out else ROOT / "release"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"bloodmusic-{ver}-src.zip"

    manifest = [
        f"package : bloodmusic-{ver}-src.zip",
        f"version : {ver}",
        f"ref     : {ref}",
        f"commit  : {sha}",
        f"files   : {len(files)}",
        f"built   : {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} (UTC)",
        "",
        "说明：本包由 tools/pack_release.py 从 git 提交内容生成，",
        "不含 .venv / __pycache__ / 运行输出等未入库产物。",
        "依赖与运行方式见包内 README.md。",
    ]

    total_raw = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for raw_name in files:
            data = read_blob(sha, raw_name)
            total_raw += len(data)
            # zip 规范要求 UTF-8 文件名；中文路径必须显式置 UTF-8 标志位，
            # 否则解压工具会按本地代码页猜编码，出现乱码目录
            name = raw_name.decode("utf-8", "surrogateescape")
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.flag_bits |= 0x800
            zf.writestr(info, data)
        zf.writestr("MANIFEST.txt", "\n".join(manifest) + "\n")

    # 自校验：能被 zipfile 正常打开，且条目数与预期一致
    with zipfile.ZipFile(out_path) as zf:
        bad = zf.testzip()
        n = len(zf.namelist())
    if bad:
        raise SystemExit(f"打包后自检失败，损坏条目：{bad}")
    if n != len(files) + 1:
        raise SystemExit(f"条目数不符：期望 {len(files) + 1}，实际 {n}")

    size = out_path.stat().st_size
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    print(f"✓ {out_path}")
    print(f"  提交     : {sha[:10]}")
    print(f"  文件数   : {len(files)} (+MANIFEST.txt)")
    print(f"  原始体积 : {total_raw / 1024 / 1024:.2f} MB")
    print(f"  压缩体积 : {size / 1024 / 1024:.2f} MB")
    print(f"  SHA256   : {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
