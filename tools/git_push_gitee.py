# -*- coding: utf-8 -*-
"""
tools/git_push_gitee.py —— 无需 git 客户端的 Gitee 推送工具（基于 dulwich）
============================================================================

背景：本机未安装 git 命令，改用纯 Python 的 dulwich 完成「提交 + 推送」。
本工具把该流程封装为一条命令：解析 .gitignore → 收集待提交文件 →
（浅）克隆远端 → 覆盖工作区 → 重建索引 → 追加提交 → 推送，全程保留远端历史。

用法:
    # 令牌用环境变量（推荐，不落盘、不出现在命令行）
    set GITEE_TOKEN=xxxxxxxx
    python tools/git_push_gitee.py

    # 或命令行传令牌（会短暂出现在进程列表中）
    python tools/git_push_gitee.py --token xxxxxxxx

    # 自定义提交信息 / 远端 / 分支 / 只预览不提交
    python tools/git_push_gitee.py --message "fix: ..."
    python tools/git_push_gitee.py --remote https://gitee.com/<owner>/<repo>.git --branch main
    python tools/git_push_gitee.py --dry-run

行为:
    1. 令牌校验（Gitee API /user）→ 远端存在性检查（ls-remote）
    2. 若本地文件集合与远端 tip 树完全一致（路径 + blob sha），
       打印「已是最新」并退出
    3. 否则浅克隆远端到临时目录 → 清空工作区 → 复制本地文件
       → 重建索引 → 提交（父提交 = 远端 tip；空仓库则为首个提交）
       → 推送分支 → 校验远端 refs 与本地一致 → 清理临时目录

安全说明:
    令牌只经 HTTP 头传递（API 校验用 `Authorization: Bearer`；git 传输由
    dulwich 以 Basic 认证头发送），绝不写入 URL（避免 query/日志泄漏）。

环境变量:
    GITEE_TOKEN   令牌（Gitee 私人令牌）
    GITEE_REMOTE  远端地址（默认 https://gitee.com/siwpan/audio-generation.git）
    GITEE_BRANCH  分支名（默认 master）
    GITEE_AUTHOR  作者 "Name <email>"（默认 siwpan <siwpan@users.noreply.gitee.com>）

依赖: dulwich（pip install dulwich）
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

DEFAULT_REMOTE = "https://gitee.com/siwpan/audio-generation.git"
DEFAULT_BRANCH = "master"
DEFAULT_AUTHOR = "siwpan <siwpan@users.noreply.gitee.com>"

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ═══════════════════════════════════════════════════════════════
# .gitignore 解析与文件收集
# ═══════════════════════════════════════════════════════════════

class IgnoreRules:
    """本项目的 .gitignore 规则集（支持目录/glob/取反，最后匹配生效）。"""

    def __init__(self) -> None:
        self.rules: list[tuple[bool, str]] = []   # (是否取反, 原始pattern)

    @classmethod
    def from_file(cls, path: Path) -> "IgnoreRules":
        rules = cls()
        if path.is_file():
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                negate = line.startswith("!")
                if negate:
                    line = line[1:].strip()
                if line:
                    rules.rules.append((negate, line))
        return rules

    def _match(self, rel_path: str, is_dir: bool) -> bool:
        """rel_path 为 POSIX 风格相对路径（目录不以 / 结尾）。"""
        parts = rel_path.split("/")
        basename = parts[-1]
        for negate, pat in self.rules:
            if pat.endswith("/"):  # 目录模式
                p = pat[:-1]
                if p.startswith("**/"):
                    p = p[3:]
                if "/" in p:
                    hit = is_dir and fnmatch.fnmatchcase(rel_path, p)
                else:
                    hit = is_dir and any(fnmatch.fnmatchcase(d, p) for d in parts)
            elif "/" in pat:       # 带路径的 glob
                hit = fnmatch.fnmatchcase(rel_path, pat)
            else:                  # 纯文件名 glob
                hit = fnmatch.fnmatchcase(basename, pat)
            if hit:
                return not negate
        return False

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        return self._match(rel_path, is_dir)


def collect_files(root: Path, rules: IgnoreRules) -> list[str]:
    """按 .gitignore 规则收集待提交文件（POSIX 相对路径）。"""
    out: list[str] = []

    def walk(dirp: Path, rel: str) -> None:
        for e in sorted(dirp.iterdir(), key=lambda x: x.name):
            rel_e = f"{rel}{e.name}"
            if e.is_dir():
                if e.name == ".git" or rules.is_ignored(rel_e, True):
                    continue
                walk(e, rel_e + "/")
            else:
                if rules.is_ignored(rel_e, False):
                    continue
                out.append(rel_e)

    walk(root, "")
    return out


def blob_sha(path: Path) -> str:
    """计算 git blob 对象 sha1。"""
    data = path.read_bytes()
    header = b"blob " + str(len(data)).encode() + b"\x00"
    return hashlib.sha1(header + data).hexdigest()


# ═══════════════════════════════════════════════════════════════
# 远端工具
# ═══════════════════════════════════════════════════════════════

def check_dulwich() -> None:
    try:
        import dulwich  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        sys.exit(f"缺少依赖 dulwich：pip install dulwich（{exc}）")


def get_remote_refs(url: str, username: str | None = None,
                    password: str | None = None) -> dict:
    """ls-remote；给出 username/password 时经 Basic 认证头访问私有仓库。"""
    from dulwich.client import get_transport_and_path
    client, path = get_transport_and_path(
        url, username=username, password=password
    )
    try:
        result = client.get_refs(path)
        # dulwich >= 0.22 返回 LsRemoteResult（.refs 为字典）
        return dict(getattr(result, "refs", result))
    finally:
        client.close()


def validate_token(token: str) -> str:
    """Gitee API /user 校验令牌，返回登录名；失败给出明确指引。

    令牌经 `Authorization: Bearer` 头传递，不出现在 URL query（避免
    服务端访问日志记录令牌）。
    """
    import urllib.request
    import urllib.error
    import json
    req = urllib.request.Request(
        "https://gitee.com/api/v5/user",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("login", ""))
    except urllib.error.HTTPError as exc:
        sys.exit(f"令牌无效（HTTP {exc.code}）：请检查 GITEE_TOKEN / --token")
    except Exception as exc:
        sys.exit(f"无法访问 Gitee API：{exc}")


def auth_kwargs(login: str, token: str) -> dict:
    """返回传给 dulwich 传输层的凭证 kwargs。

    dulwich 会将其转成 HTTP Basic 认证头（Gitee 私人令牌按
    「用户名 + 令牌作密码」使用 Basic 认证），令牌不进入任何 URL 字符串。
    """
    return {"username": login, "password": token}


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def remote_tree_map(repo) -> dict:
    """远端 tip 树的 {posix_path: blob_sha}。"""
    head = repo.head()
    tree = repo[repo[head].tree]
    out: dict[str, str] = {}

    def walk(t, prefix: str) -> None:
        for item in t.items():
            p = f"{prefix}{item.path.decode()}"
            if item.mode == 0o040000:
                walk(repo[item.sha], p + "/")
            else:
                out[p] = item.sha.decode()

    walk(tree, "")
    return out


def run(args: argparse.Namespace) -> int:
    check_dulwich()
    from dulwich import porcelain
    from dulwich.repo import Repo

    remote = args.remote or os.environ.get("GITEE_REMOTE", DEFAULT_REMOTE)
    branch = args.branch or os.environ.get("GITEE_BRANCH", DEFAULT_BRANCH)
    author = args.author or os.environ.get("GITEE_AUTHOR", DEFAULT_AUTHOR)
    root = Path(args.root) if args.root else _PROJECT_ROOT
    if not (root / ".gitignore").is_file():
        print(f"警告: {root} 下未找到 .gitignore，将收集全部文件")

    # 1) 收集本地文件（dry-run 无需令牌）
    rules = IgnoreRules.from_file(root / ".gitignore")
    files = collect_files(root, rules)
    print(f"== 本地待提交文件: {len(files)} 个")

    if args.dry_run:
        for f in files:
            print("   ", f)
        print("[dry-run] 已列出文件，未做任何修改/推送")
        return 0

    token = args.token or os.environ.get("GITEE_TOKEN", "")
    if not token:
        sys.exit("未提供令牌：请设置环境变量 GITEE_TOKEN 或使用 --token")

    print(f"== 目标: {remote} 分支: {branch} 根目录: {root}")
    login = validate_token(token)
    print(f"== 令牌校验: {login}")
    creds = auth_kwargs(login, token)

    # 2) 远端 refs（匿名读取）
    refs = get_remote_refs(remote)
    ref_name = f"refs/heads/{branch}"
    remote_tip = refs.get(ref_name.encode())
    if isinstance(remote_tip, bytes):
        remote_tip = remote_tip.decode()
    print(f"== 远端 {ref_name}: {remote_tip or '(空仓库)'}")

    # 3) 临时仓库：浅克隆远端（有提交时），否则空初始化
    work = Path(tempfile.mkdtemp(prefix="bm_push_"))
    try:
        if remote_tip:
            repo = porcelain.clone(remote, str(work), depth=1, **creds)
        else:
            repo = Repo.init(str(work))

        # 4) 变更检测：路径 + blob sha 与远端 tip 树一致 → 无需推送
        if remote_tip:
            local_map = {f: blob_sha(root / f) for f in files}
            remote_map = remote_tree_map(repo)
            changed = local_map != remote_map
            if not changed:
                print("== 无变化（本地文件与远端 tip 完全一致），跳过提交与推送")
                return 0

        # 5) 覆盖工作区（保留 .git）并复制本地文件
        for e in work.iterdir():
            if e.name == ".git":
                continue
            if e.is_dir():
                shutil.rmtree(e, ignore_errors=True)
            else:
                e.unlink(missing_ok=True)
        for rel in files:
            dst = work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / rel, dst)

        # 6) 重建索引 + 提交（父提交 = 远端 tip；空仓库则为首个提交）
        idx = os.path.join(repo.controldir(), "index")
        if os.path.exists(idx):
            os.remove(idx)
        repo = Repo(str(work))
        cfg = repo.get_config()
        name, _, email = author.partition("<")
        cfg.set((b"user",), b"name", name.strip().encode("utf-8"))
        cfg.set((b"user",), b"email", email.strip(">").strip().encode("utf-8"))
        cfg.write_to_path()

        posix = [f.replace("\\", "/") for f in files]
        porcelain.add(repo, posix)

        message = (args.message or "chore: 同步工作区（tools/git_push_gitee.py）").encode("utf-8")
        author_bytes = author.encode("utf-8")
        sha = porcelain.commit(repo, message=message, author=author_bytes, committer=author_bytes)
        print(f"== 已提交: {sha.decode()}（父提交: {remote_tip or '无（根提交）'}）")

        # 7) 推送（令牌经 Basic 认证头，不进 URL）
        try:
            porcelain.push(repo, remote, ref_name.encode("utf-8"), **creds)
        except Exception as exc:
            if "Unauthorized" in type(exc).__name__ or "401" in str(exc):
                sys.exit(f"推送认证失败（{exc}）：请确认令牌归属账号 {login} 且对本仓库有写权限")
            raise
        print("== 推送成功")

        # 8) 校验
        new_refs = get_remote_refs(remote, **creds)
        pushed = new_refs.get(ref_name.encode())
        if isinstance(pushed, bytes):
            pushed = pushed.decode()
        if pushed != sha.decode():
            sys.exit(f"校验失败：远端 {ref_name}={pushed}，本地提交={sha.decode()}")
        print(f"== 校验通过: 远端 {ref_name} = {pushed}")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="git_push_gitee",
        description="无需 git 客户端的 Gitee 提交+推送工具（dulwich）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--token", help="Gitee 私人令牌（推荐用环境变量 GITEE_TOKEN）")
    p.add_argument("--remote", help=f"远端地址（默认 {DEFAULT_REMOTE}）")
    p.add_argument("--branch", help=f"分支名（默认 {DEFAULT_BRANCH}）")
    p.add_argument("--message", help="提交信息（默认自动生成）")
    p.add_argument("--author", help=f"作者 Name <email>（默认 {DEFAULT_AUTHOR}）")
    p.add_argument("--root", help="要推送的项目根目录（默认脚本所在项目）")
    p.add_argument("--dry-run", action="store_true", help="只列出待提交文件，不修改/推送")
    return p


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
