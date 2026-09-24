"""common.py — 自动化脚本共享工具（纯本地、项目内）。

路径约定
--------
- REPO_ROOT    : G:/repos/audio-generation
- OUTPUT_ROOT  : REPO_ROOT/automations/output  （已被 .gitignore 忽略）
- REPORTS_DIR  : OUTPUT_ROOT/reports
- DEFAULT_PYTHON: 项目运行解释器，优先 F:/Python314/python.exe（已装齐依赖 + tkinter），
                 可用环境变量 BM_PYTHON 覆盖。

提供能力
--------
- ensure_bloodmusic(): 自检 bloodmusic 可导入（本环境 pip 写盘会卡死，已禁用自动安装，只做检测）。
- run_module(module, *args): 用 DEFAULT_PYTHON 跑 `python -m <module> ...`，返回 (returncode, stdout, stderr)。
- inspect_wav(path) / scan_wavs(root): WAV 质量巡检（峰值/时长/非零/声道/采样率）。
- write_reports(name, data): 写 JSON + Markdown 到 REPORTS_DIR。
- log(msg): 带时间戳的简易日志。
"""
from __future__ import annotations

import os
import sys
import json
import math
import subprocess
import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "automations" / "output"
REPORTS_DIR = OUTPUT_ROOT / "reports"
DEFAULT_PYTHON = os.environ.get("BM_PYTHON", r"F:\Python314\python.exe")

# ── album_maker 混音阶段依赖（关键）────────────────────────────────────────
# album_maker 的母带混音 `_mixdown` 延迟 `from mixdown import mixdown`，
# 而 `mixdown` 来自 audio_pipeline（本项目内置于 pipeline/），其内部又通过
# pipeline/config.bootstrap_env() 把 <repo>/remix 注入 sys.path 以取到
# `core.audio_mixer` / `core.audio_loader`。
# 默认指向仓库内目录 => 内容生成完全本地、不依赖外部旧分类目录，
# 符合「所有内容均在项目内实现」的约束。可被同名环境变量覆盖。
os.environ.setdefault("BLOODMUSIC_AUDIO_PIPELINE", str(REPO_ROOT / "pipeline"))
os.environ.setdefault("BLOODMUSIC_REMIX", str(REPO_ROOT / "remix"))


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def ensure_bloodmusic(python: str = DEFAULT_PYTHON) -> bool:
    """确保 bloodmusic 可导入。

    说明：本机 F:/Python314 的 pip 在「写盘/解包/卸载」阶段会卡死（已实测，
    多次超时 kill 子进程），因此这里**只做导入检测，绝不触发 pip 安装**，
    否则任何被调度起来的自动化任务都会被 pip 挂死。

    bloodmusic 的可导入性由 site-packages 下的目录联接 (junction)
    bloodmusic -> G:\\repos\\audio-generation 以及 bloodmusic_dev.pth
    （内容 G:\\repos\\audio-generation，用于满足仓库内 `import core` /
    `import music` 等兄弟包绝对导入）共同保证。详见 automations/README.md。

    若导入失败，直接返回 False 并给出可执行的修复提示，交由调用方决定，
    避免自动化任务被 pip 挂死。
    """
    try:
        import bloodmusic  # noqa: F401
        return True
    except Exception as exc:
        log(f"[ensure] bloodmusic 不可导入: {type(exc).__name__}: {exc}")
        log("[ensure] 本环境 pip 写盘阶段会卡死，已禁用自动安装；"
            "请确认 F:/Python314/Lib/site-packages/bloodmusic (junction) 与"
            " bloodmusic_dev.pth 均存在且指向 G:\\repos\\audio-generation。")
        return False


def run_module(module: str, *args: str, timeout: int = 1800, cwd=None) -> tuple[int, str, str]:
    """用 DEFAULT_PYTHON 跑 `python -m <module> ...`。返回 (rc, stdout, stderr)。"""
    cmd = [DEFAULT_PYTHON, "-m", module, *args]
    log(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(cwd) if cwd else str(REPO_ROOT))
    return proc.returncode, proc.stdout, proc.stderr


# ─────────────────────────────────────────────────────────────────────────────
# WAV 质量巡检
# ─────────────────────────────────────────────────────────────────────────────
def inspect_wav(path: Path) -> dict:
    """单文件质量指标。失败返回 ok=False 并带 error。"""
    import numpy as np
    try:
        import soundfile as sf
    except Exception as exc:  # pragma: no cover
        return {"path": str(path), "ok": False, "error": f"soundfile: {exc}"}
    try:
        data, sr = sf.read(str(path), always_2d=False)
    except Exception as exc:
        return {"path": str(path), "ok": False, "error": f"read: {exc}"}
    if data.ndim == 2:
        channels = data.shape[1]
        mono = data.mean(axis=1)
    else:
        channels = 1
        mono = data
    frames = int(mono.shape[0])
    peak = float(np.max(np.abs(mono))) if frames else 0.0
    peak_db = 20.0 * math.log10(peak) if peak > 0 else float("-inf")
    rms = float(np.sqrt(np.mean(np.square(mono)))) if frames else 0.0
    duration = frames / sr if sr else 0.0
    return {
        "path": str(path),
        "ok": True,
        "frames": frames,
        "sr": int(sr),
        "channels": channels,
        "duration_sec": round(duration, 3),
        "peak": round(peak, 6),
        "peak_db": round(peak_db, 2) if peak > 0 else None,
        "rms": round(rms, 6),
        "non_silent": bool(peak > 1e-4),
    }


def scan_wavs(root: Path) -> list[dict]:
    """递归扫描目录下全部 *.wav 并逐个巡检。"""
    root = Path(root)
    out = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.wav")):
        out.append(inspect_wav(p))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 报告写入
# ─────────────────────────────────────────────────────────────────────────────
def write_reports(name: str, data: dict) -> tuple[Path, Path]:
    """写 JSON + Markdown 到 REPORTS_DIR/{name}.{json,md}。返回 (json_path, md_path)。"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    data = {"generated_at": ts, **data}
    json_path = REPORTS_DIR / f"{name}.json"
    md_path = REPORTS_DIR / f"{name}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(name, data), encoding="utf-8")
    return json_path, md_path


def _to_markdown(name: str, data: dict) -> str:
    lines = [f"# {name} 报告", "", f"- 生成时间: {data.get('generated_at','')}", ""]
    summary = data.get("summary")
    if isinstance(summary, dict):
        lines.append("## 摘要")
        for k, v in summary.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    steps = data.get("steps")
    if isinstance(steps, dict):
        lines.append("## 步骤明细")
        for sname, sval in steps.items():
            lines.append(f"### {sname}")
            if isinstance(sval, list):
                ok = sum(1 for x in sval if isinstance(x, dict) and x.get("ok"))
                lines.append(f"- 条目数: {len(sval)}，成功(可巡检): {ok}")
            elif isinstance(sval, dict):
                for k, v in sval.items():
                    lines.append(f"- {k}: {v}")
            else:
                lines.append(f"- {sval}")
            lines.append("")
    files = data.get("files")
    if isinstance(files, list) and files:
        lines.append("## 产出文件")
        for f in files[:200]:
            p = f.get("path", "") if isinstance(f, dict) else str(f)
            extra = ""
            if isinstance(f, dict):
                extra = f"  (peak_db={f.get('peak_db')}, dur={f.get('duration_sec')}s, silent={not f.get('non_silent')})"
            lines.append(f"- {p}{extra}")
        lines.append("")
    return "\n".join(lines)
