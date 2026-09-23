#!/usr/bin/env python3
"""BloodMusic JSON-RPC stdio 服务（host-js 的 Python 侧）。

协议：行分隔 JSON-RPC 2.0 —— stdin 每行一个请求对象，stdout 每行一个响应对象。
长任务前后发 `progress` 通知（无 id）。**stdout 只走协议**，日志一律 stderr。

方法面（对应 Node 侧 ctx.bloodmusic.* ）：
  ping                                          → { pong, pid, python, repo }
  sfx.list                                      → { presets, count }
  sfx.render        { name, out? }              → { wav, duration_sec, sample_rate, peak }
  album.styles                                  → { styles }
  album.quick       { style?, seed?, bpm?, bars?, out_dir? } → QuickResult 字段
  mirror.styles / mirror.mixers                 → { styles } / { mixers }
  mirror.remix      { count?, seed?, bars?, bpm?, style?, mixer_style?, out_dir?, fmt? }
                                                → { results: [RemixResult 字段] }
  autowav.generate  { duration?, bpm?, scale?, seed?, out? } → { wav, duration_sec }
  autowav.speak     { text, out?, rate?, volume?, voice? }   → { wav, duration_sec }

零协议层三方依赖（stdio/json/sys 全 stdlib）；合成依赖 bloodmusic 自身（numpy/soundfile）。
导入策略：仓库根 + autowav/ 进 sys.path，平铺包名导入（与 python main.py 一致），
不依赖 editable 安装；各方法首次调用时才导入对应模块（懒加载，单模块故障不拖垮服务）。
"""

import contextlib
import importlib.util
import json
import os
import random
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# autowav/ 目录进 sys.path：autowav.py 等脚本用平铺兄弟导入（from midi_io import ...）
_autowav_dir = str(REPO_ROOT / "autowav")
if _autowav_dir not in sys.path:
    sys.path.insert(0, _autowav_dir)


def _ensure_bloodmusic():
    """保证 `import bloodmusic.xxx` 可用。

    子包内部全用相对导入（from ..core.oscillator import ...），必须以 bloodmusic 包
    身份导入，平铺导入 sfx/core 会炸。优先用 editable 安装（F:\\Python314 已装）；
    没有安装时在进程内合成 bloodmusic 包锚点（submodule_search_locations 指仓库根），
    做到零安装依赖。
    """
    try:
        import bloodmusic  # noqa: F401
        return
    except ImportError:
        pass
    spec = importlib.util.spec_from_file_location(
        "bloodmusic",
        REPO_ROOT / "__init__.py",
        submodule_search_locations=[str(REPO_ROOT)],
    )
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["bloodmusic"] = pkg
    spec.loader.exec_module(pkg)


_ensure_bloodmusic()


def _fix_album_deps() -> None:
    """album_maker/track.py 的外部依赖默认指 G:\\tools\\audio\\*（本机不存在）。

    本地实有（es.exe 全盘定位，无需下载）：
      <repos>/audio-pipeline —— mixdown.py / config.py / manifest.py
      <repos>/remix          —— core/audio_mixer.py（mixdown 的 import 源）
    只在「用户未显式配置环境变量」且「候选目录存在」时注入，优先级不压用户配置。
    """
    candidates = {
        # 2026-09-23 去本地化：同级仓推导（原 G:\tools\audio\* 候选已失效，删除）
        "BLOODMUSIC_AUDIO_PIPELINE": [str(REPO_ROOT.parent / "audio-pipeline")],
        "BLOODMUSIC_REMIX": [str(REPO_ROOT.parent / "remix")],
    }
    for var, paths in candidates.items():
        if os.environ.get(var):
            continue
        for candidate in paths:
            if Path(candidate).is_dir():
                os.environ[var] = candidate
                break


_fix_album_deps()

DEFAULT_SR = 44100
OUT_ROOT = Path(tempfile.gettempdir()) / "bloodmusic-rpc"
OUT_ROOT.mkdir(parents=True, exist_ok=True)

# stdout 是协议通道，单行写入 + flush；stderr 才能随便打印
_write_lock_error = None


def _send(obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False, default=str)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _notify(method: str, params: dict) -> None:
    _send({"jsonrpc": "2.0", "method": method, "params": params})


def _log(msg: str) -> None:
    sys.stderr.write(f"[bloodmusic-rpc] {msg}\n")
    sys.stderr.flush()


def _default_out(stem: str, ext: str = ".wav") -> str:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return str(OUT_ROOT / f"{stem}{ext}")


def _write_wav(path: str, sig, sr: int = DEFAULT_SR) -> dict:
    """归一化 + 限幅后写 PCM_16 WAV，返回元数据。与 export/batch.py 的写出口径一致。"""
    import numpy as np
    import soundfile as sf

    sig = np.asarray(sig, dtype=np.float64)
    if sig.ndim > 1:  # 立体声混成单声道（SFX 预设多为单声道，防御性处理）
        sig = sig.mean(axis=-1)
    peak = float(np.max(np.abs(sig))) if sig.size else 0.0
    if peak > 0:
        sig = sig * (0.89 / peak)
    sig = np.clip(sig, -1.0, 1.0)
    sf.write(path, sig, sr, subtype="PCM_16")
    return {
        "wav": path,
        "duration_sec": round(sig.size / sr, 3),
        "sample_rate": sr,
        "peak": round(peak, 4),
    }


# ──────────────────────────── 方法实现 ────────────────────────────


def m_ping(_params: dict) -> dict:
    return {
        "pong": True,
        "pid": os.getpid(),
        "python": sys.version.split()[0],
        "repo": str(REPO_ROOT),
    }


def m_sfx_list(_params: dict) -> dict:
    from bloodmusic.sfx import ALL_PRESETS

    presets = sorted(ALL_PRESETS.keys())
    return {"presets": presets, "count": len(presets)}


def m_sfx_render(params: dict) -> dict:
    name = params.get("name")
    if not name:
        raise ValueError("sfx.render 需要参数 name")
    from bloodmusic.core.constants import SR
    from bloodmusic.core.voice import synthesize_voice
    from bloodmusic.sfx import get_preset

    voice = get_preset(name)
    sig = synthesize_voice(voice)
    out = params.get("out") or _default_out(f"sfx_{name}")
    return {"name": name, **_write_wav(out, sig, SR)}


def m_album_styles(_params: dict) -> dict:
    from bloodmusic.album_maker.quick import QuickMaker

    return {"styles": sorted(QuickMaker.list_styles().keys())}


def m_album_quick(params: dict) -> dict:
    from bloodmusic.album_maker.quick import QuickMaker

    style = params.get("style")
    seed = params.get("seed")
    # 不传 out_dir 时 QuickMaker 会落进仓库根的 album_maker_quick/ —— RPC 默认进临时目录
    out_dir = params.get("out_dir") or str(OUT_ROOT / "album")
    kwargs = {"out_dir": out_dir, "seed": seed}
    if style:
        result = QuickMaker.style(
            style,
            bpm=params.get("bpm"),
            bars=params.get("bars"),
            **kwargs,
        )
    else:
        result = QuickMaker.random(**kwargs)
    return {
        "title": result.title,
        "style": result.style,
        "bpm": result.bpm,
        "key": result.key,
        "bars": result.bars,
        "seed": result.seed,
        "duration_sec": result.duration_sec,
        "output_dir": str(result.output_dir),
        "wav": str(result.wave_path) if result.wave_path else None,
    }


def m_mirror_styles(_params: dict) -> dict:
    from bloodmusic.mirror.styles import list_styles

    return {"styles": list_styles()}


def m_mirror_mixers(_params: dict) -> dict:
    from bloodmusic.mirror.mixer_styles import list_mixers

    return {"mixers": list_mixers()}


def m_mirror_remix(params: dict) -> dict:
    from bloodmusic.mirror.renderer import run_remix

    results = run_remix(
        count=int(params.get("count", 1)),
        seed=params.get("seed"),
        bars=int(params.get("bars", 16)),
        bpm=params.get("bpm"),
        structure=params.get("structure"),
        style=params.get("style"),
        mixer_style=params.get("mixer_style"),
        out_dir=params.get("out_dir") or str(OUT_ROOT / "mirror"),
        fmt=params.get("fmt", "wav"),
    )
    return {
        "results": [
            {
                "song_path": str(r.song_path) if r.song_path else None,
                "stems": [str(s) for s in r.stems],
                "report_path": str(r.report_path) if r.report_path else None,
                "elapsed_sec": r.elapsed_sec,
            }
            for r in results
        ]
    }


def _load_autowav_script():
    """autowav/autowav.py 与 autowav 包同名，按文件路径装载避免冲突。"""
    script = REPO_ROOT / "autowav" / "autowav.py"
    spec = importlib.util.spec_from_file_location("autowav_script", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def m_autowav_generate(params: dict) -> dict:
    mod = _load_autowav_script()
    if params.get("seed") is not None:
        random.seed(int(params["seed"]))
    out = params.get("out") or _default_out("autowav")
    duration = float(params.get("duration", 30.0))
    kwargs = {"output_path": out, "target_duration": duration}
    if params.get("bpm"):
        kwargs["bpm"] = int(params["bpm"])
    if params.get("scale"):
        kwargs["scale_name"] = params["scale"]
    mod.generate_music_by_duration(**kwargs)
    size = os.path.getsize(out) if os.path.exists(out) else 0
    if not size:
        raise RuntimeError(f"autowav 未产出文件：{out}")
    return {"wav": out, "duration_sec": duration, "bytes": size}


def m_autowav_speak(params: dict) -> dict:
    text = params.get("text")
    if not text:
        raise ValueError("autowav.speak 需要参数 text")
    from bloodmusic.autowav.vocal_tts import speak

    out = params.get("out") or _default_out("speak")
    sig = speak(
        text,
        out_path=out,
        rate=int(params.get("rate", 0)),
        volume=int(params.get("volume", 100)),
        voice=params.get("voice"),
    )
    if os.path.exists(out):
        size = os.path.getsize(out)
        return {"wav": out, "duration_sec": round(len(sig) / DEFAULT_SR, 3), "bytes": size}
    # speak 没落盘时自己写
    return {**_write_wav(out, sig), "bytes": os.path.getsize(out)}


METHODS = {
    "ping": m_ping,
    "sfx.list": m_sfx_list,
    "sfx.render": m_sfx_render,
    "album.styles": m_album_styles,
    "album.quick": m_album_quick,
    "mirror.styles": m_mirror_styles,
    "mirror.mixers": m_mirror_mixers,
    "mirror.remix": m_mirror_remix,
    "autowav.generate": m_autowav_generate,
    "autowav.speak": m_autowav_speak,
}


def _handle(req: dict) -> None:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if method == "exit":
        raise SystemExit(0)
    if req_id is None:  # 通知：目前只有 exit 有意义，其余忽略
        return

    handler = METHODS.get(method)
    if handler is None:
        _send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"未知方法：{method}"},
        })
        return

    _notify("progress", {"phase": "start", "rpc": method})
    try:
        # 协议纪律：被调库可能直接 print 到 stdout（如 autowav.py），
        # 而 stdout 是 RPC 通道 —— 处理器执行期间一律拐到 stderr。
        with contextlib.redirect_stdout(sys.stderr):
            result = handler(params)
    except Exception as exc:  # noqa: BLE001 —— 协议层必须兜住一切，保证服务不死
        _log(f"{method} 失败：{exc}\n{traceback.format_exc()}")
        _send({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"},
        })
    else:
        _send({"jsonrpc": "2.0", "id": req_id, "result": result})
    finally:
        _notify("progress", {"phase": "done", "rpc": method})


def main() -> int:
    _log(f"就绪 pid={os.getpid()} repo={REPO_ROOT}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            _send({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"JSON 解析失败：{exc}"},
            })
            continue
        _handle(req)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as exc:
        raise exc
    except KeyboardInterrupt:
        sys.exit(0)
