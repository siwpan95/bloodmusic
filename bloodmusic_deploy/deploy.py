#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BloodMusic 本地依赖部署脚本
==========================
把本目录下的 lib/（已内置 numpy / scipy / sounddevice / soundfile / PyYAML /
mido 及其依赖 + PortAudio 动态库 portaudio.dll）接入项目，使项目「从项目根目录
内加载」依赖、无需联网 pip 安装即可运行。

用法（在项目根目录 X:\\audio-generation-master 下执行）：
    python deploy.py

脚本会：
  1. 确认 lib/ 已存在（请先把部署包里的 lib/ 复制到项目根目录）。
  2. 幂等地在 __init__.py 顶部注入「本地依赖引导」代码（已注入则跳过）。
  3. 幂等地在 main.py 的路径注入块后注入同一段「本地依赖引导」代码
     （保证 `python main.py --check` / `--demo` 等也能从 lib/ 找到依赖）。
  4. 在项目根目录创建指向自身的 `bloodmusic` 目录联结(junction)：
        X:\\audio-generation-master\\bloodmusic  ->  X:\\audio-generation-master
     这样 `python -m bloodmusic` 能正确解析包名（项目目录名为
     audio-generation-master，包名是 bloodmusic，需注册一次）。
     该步骤不依赖 pip，且无需管理员权限（junction 与普通符号链接不同，
     不需要 Developer Mode）。

部署完成后即可运行：
    python -m bloodmusic --help
    python main.py --check
    python main.py
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(ROOT, "lib")
INIT = os.path.join(ROOT, "__init__.py")
MAIN = os.path.join(ROOT, "main.py")
# 项目目录名为 audio-generation-master，包名是 bloodmusic；
# 创建一个指向自身的目录联结，让 `python -m bloodmusic` 能找到包。
PKG_LINK = os.path.join(ROOT, "bloodmusic")
MARKER = "# 本地依赖引导 (local dependency bootstrap)"


def _dump_dll_variants():
    return ("portaudio.dll", "libportaudio-2.dll", "libportaudio.dll")


BOOTSTRAP = '''# ───────────────────────────────────────────────────────────────────────────
# 本地依赖引导 (local dependency bootstrap)
# 从「项目根目录」下的 lib/ 加载第三方库，实现依赖全部内置于项目、无需 pip 安装。
# 同时把 lib/ 加入 PATH，使 sounddevice 能找到 PortAudio 动态库 (portaudio.dll)。
# 本段幂等，可安全重复执行；如不需要本地依赖可整段删除。
# ───────────────────────────────────────────────────────────────────────────
import os as _bm_os
import sys as _bm_sys

_BM_LIB = _bm_os.path.join(_bm_os.path.dirname(_bm_os.path.abspath(__file__)), "lib")
if _bm_os.path.isdir(_BM_LIB):
    if _BM_LIB not in _bm_sys.path:
        _bm_sys.path.insert(0, _BM_LIB)
    _bm_path = _bm_os.environ.get("PATH", "")
    if _BM_LIB not in _bm_path:
        _bm_os.environ["PATH"] = _BM_LIB + _bm_os.pathsep + _bm_path
    for _bm_name in ("portaudio.dll", "libportaudio-2.dll", "libportaudio.dll"):
        _bm_dll = _bm_os.path.join(_BM_LIB, _bm_name)
        if _bm_os.path.exists(_bm_dll):
            try:
                import ctypes as _bm_ct
                _bm_ct.CDLL(_bm_dll)
            except Exception:
                pass
            break

'''

# 用于 main.py 的变体：main.py 已定义 _PROJECT_ROOT，直接复用它定位 lib/。
BOOTSTRAP_MAIN = '''# ───────────────────────────────────────────────────────────────────────────
# 本地依赖引导 (local dependency bootstrap)
# 从「项目根目录」下的 lib/ 加载第三方库，使 `python main.py` 也能从 lib/ 找到依赖。
# 与 __init__.py 中的引导逻辑一致，幂等、可安全重复执行、可整段删除。
# ───────────────────────────────────────────────────────────────────────────
import os as _bm_os
_BM_LIB = _bm_os.path.join(str(_PROJECT_ROOT), "lib")
if _bm_os.path.isdir(_BM_LIB):
    if _BM_LIB not in sys.path:
        sys.path.insert(0, _BM_LIB)
    _bm_path = _bm_os.environ.get("PATH", "")
    if _BM_LIB not in _bm_path:
        _bm_os.environ["PATH"] = _BM_LIB + _bm_os.pathsep + _bm_path
    for _bm_name in ("portaudio.dll", "libportaudio-2.dll", "libportaudio.dll"):
        _bm_dll = _bm_os.path.join(_BM_LIB, _bm_name)
        if _bm_os.path.exists(_bm_dll):
            try:
                import ctypes as _bm_ct
                _bm_ct.CDLL(_bm_dll)
            except Exception:
                pass
            break

'''


def _insert_after(content, anchor, block):
    """在 anchor 之后插入 block（用于 main.py 的路径注入块之后）。"""
    idx = content.find(anchor)
    if idx == -1:
        return None
    insert_at = idx + len(anchor)
    # 找到 anchor 行尾
    nl = content.find("\n", insert_at)
    if nl == -1:
        nl = len(content)
    return content[:nl + 1] + "\n" + block + content[nl + 1:]


def patch_init():
    if not os.path.isfile(INIT):
        print("! 未找到 __init__.py，请在项目根目录运行本脚本。")
        sys.exit(1)
    with open(INIT, "r", encoding="utf-8") as f:
        content = f.read()
    if MARKER in content:
        print("[1/4] __init__.py 已包含本地依赖引导，跳过注入。")
        return
    idx = 0
    stripped = content.lstrip()
    if stripped.startswith('"""'):
        end = content.find('"""', 3)
        if end != -1:
            idx = end + 3
    new_content = content[:idx].rstrip() + "\n\n" + BOOTSTRAP + content[idx:].lstrip()
    with open(INIT, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("[1/4] 已在 __init__.py 注入本地依赖引导。")


def patch_main():
    if not os.path.isfile(MAIN):
        print("[2/4] 未找到 main.py，跳过（不影响 `python -m bloodmusic`）。")
        return
    with open(MAIN, "r", encoding="utf-8") as f:
        content = f.read()
    if MARKER in content:
        print("[2/4] main.py 已包含本地依赖引导，跳过注入。")
        return
    anchor = "sys.path.insert(0, str(_PROJECT_ROOT))"
    new_content = _insert_after(content, anchor, BOOTSTRAP_MAIN)
    if new_content is None:
        print("[2/4] 未能在 main.py 定位路径注入块，跳过（可使用 `python -m bloodmusic`）。")
        return
    with open(MAIN, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("[2/4] 已在 main.py 注入本地依赖引导。")


def _junction_target_is_correct(link):
    """检查 link 是否已指向 ROOT（支持 junction / 符号链接 / 真实目录同路径）。"""
    try:
        if os.path.islink(link) or _is_junction(link):
            real = os.path.realpath(link)
            return os.path.realpath(real) == os.path.realpath(ROOT)
    except OSError:
        pass
    return False


def _is_junction(path):
    try:
        import stat as _stat
        st = os.lstat(path)
        return bool(st.st_file_attributes & _stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False


def _remove_existing_link(link):
    """删除已存在的 wrong 联结/符号链接（仅删除空的重解析点，绝不删除真实目录）。"""
    try:
        if os.path.islink(link):
            os.unlink(link)
            return True
        if _is_junction(link):
            # 用 rmdir 删除 junction（junction 是空目录重解析点）
            os.rmdir(link)
            return True
    except OSError:
        pass
    return False


def register_package():
    print("[3/4] 注册 bloodmusic 包（创建自指向目录联结，无需 pip）...")
    if _junction_target_is_correct(PKG_LINK):
        print("      已存在正确的 bloodmusic 联结，跳过。")
        return
    # 如果已存在但指向错误，先尝试清除（仅限联结/符号链接）
    if os.path.exists(PKG_LINK) or os.path.islink(PKG_LINK):
        if not _remove_existing_link(PKG_LINK):
            print("! 已存在 %s 且无法自动移除，请手动删除后再运行。" % PKG_LINK)
            sys.exit(1)

    created = _try_mklink_junction(PKG_LINK, ROOT)
    if not created:
        created = _try_powershell_junction(PKG_LINK, ROOT)
    if not created:
        created = _try_os_symlink(PKG_LINK, ROOT)
    if not created:
        print("! 无法自动创建 bloodmusic 联结。请手动执行以下任一命令后重跑本脚本：")
        print('        cmd /c mklink /J "%s" "%s"' % (PKG_LINK, ROOT))
        print('        New-Item -ItemType Junction -Path "%s" -Target "%s"' % (PKG_LINK, ROOT))
        sys.exit(1)
    print("      已创建联结: %s  ->  %s" % (PKG_LINK, ROOT))


def _try_mklink_junction(link, target):
    try:
        subprocess.check_call(
            ["cmd", "/c", "mklink", "/J", link, target],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return os.path.exists(link)
    except (subprocess.CalledProcessError, OSError):
        return False


def _try_powershell_junction(link, target):
    try:
        ps = (
            'New-Item -ItemType Junction -Path "%s" -Target "%s" '
            '| Out-Null' % (link, target)
        )
        subprocess.check_call(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return os.path.exists(link)
    except (subprocess.CalledProcessError, OSError):
        return False


def _try_os_symlink(link, target):
    # 需要管理员权限或 Developer Mode（Windows）；Posix 下直接可用。
    try:
        os.symlink(target, link, target_is_directory=True)
        return os.path.exists(link)
    except (OSError, NotImplementedError):
        return False


def main():
    print("BloodMusic 本地依赖部署")
    print("项目根目录:", ROOT)
    if not os.path.isdir(LIB):
        print("! 未找到 lib/ 目录。请先把部署包中的 lib/ 复制到项目根目录。")
        sys.exit(1)
    print("[0/4] 检测到 lib/ :", LIB)
    patch_init()
    patch_main()
    register_package()
    print("[4/4] 部署完成。现在可运行:")
    print("        python -m bloodmusic --help")
    print("        python main.py --check")
    print("        python main.py")
    print("（如需撤销：删除根目录下的 bloodmusic 联结、__init__.py 与 main.py 顶部的")
    print(" 引导代码块，以及 lib/ 目录即可；本方案未对 Python 环境做任何全局改动。）")


if __name__ == "__main__":
    main()
