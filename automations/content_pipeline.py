"""content_pipeline.py — P0 内容生成流水线（纯本地、项目内实现）。

设计目标（对齐 BloodMusic v2.0.0 主线：6 引擎 × 12 风格全功能覆盖）：
  C1  整专辑生成       album_maker.cli make --demo
  C2  风格覆盖巡检      12 风格各渲染 1 曲（album_maker.quick.QuickMaker.style）
  C2  引擎覆盖巡检      6 引擎各渲染 1 曲（强制 engine 的极简 pool，复用 AlbumMaker 路径）
  C5  AutoWav 随机作曲  bloodmusic.autowav --random --duration 30
  C8  质量巡检          扫描 OUTPUT_ROOT 全部 WAV，出覆盖率 + 异常报告

产物目录: automations/output/{album_demo,style_coverage,engine_coverage,autowav}
报告:     automations/output/reports/content_report.json + .md
退出码:   0=全部成功, 1=有步骤失败
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (  # noqa: E402
    OUTPUT_ROOT, ensure_bloodmusic, run_module,
    scan_wavs, write_reports, log,
)

# 6 个规范合成引擎（music/instrument_pool.py:DEFAULT_ENGINE_MAP 的角色绑定引擎）
ENGINES = ["wavetable", "fm_advanced", "subtractive", "noise", "granular", "karplus_strong"]
SEED_BASE = 20260917


def step_album_demo() -> dict:
    out = OUTPUT_ROOT / "album_demo"
    out.mkdir(parents=True, exist_ok=True)
    rc, so, se = run_module(
        "bloodmusic.album_maker.cli", "make", "--demo", "--out", str(out), timeout=1800,
    )
    wavs = scan_wavs(out)
    ok = rc == 0 and any(w.get("non_silent") for w in wavs)
    detail = (se.strip().splitlines()[-1] if se.strip() else "") if rc != 0 else ""
    return {
        "returncode": rc,
        "ok": ok,
        "wav_count": len(wavs),
        "non_silent": sum(1 for w in wavs if w.get("non_silent")),
        "note": detail,
    }


def step_style_coverage() -> list[dict]:
    from bloodmusic.album_maker.quick import QuickMaker
    out = OUTPUT_ROOT / "style_coverage"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    from bloodmusic.album_maker.style_db import STYLE_DB
    for i, style in enumerate(sorted(STYLE_DB.keys())):
        seed = SEED_BASE + i
        try:
            r = QuickMaker.style(style, out_dir=str(out), bars=4, seed=seed)
            path = r.wave_path
            from common import inspect_wav
            info = inspect_wav(Path(path)) if path else {"ok": False, "error": "no wave_path"}
            info["style"] = style
            results.append(info)
        except Exception as exc:
            results.append({"style": style, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return results


def step_engine_coverage() -> list[dict]:
    """引擎覆盖巡检：复用 QuickMaker.style 的**已验证路径**，仅把乐器池里
    每个乐器的 engine 强制替换为待测引擎，从而走官方 AlbumMaker 合成流程，
    覆盖 6 个规范合成引擎（wavetable/fm_advanced/subtractive/noise/granular/karplus_strong）。
    """
    from bloodmusic.album_maker.quick import (
        _build_synth_pool, MIX_CONFIG_DEFAULTS, STYLE_DB, BARS_OPTIONS,
    )
    import random as _rnd
    from bloodmusic.album_maker.config import TrackSpec, AlbumConfig
    from bloodmusic.album_maker.album import AlbumMaker
    from common import inspect_wav

    out_base = OUTPUT_ROOT / "engine_coverage"
    results = []
    probe_style = "ambient"
    style = STYLE_DB.get(probe_style)
    for i, engine in enumerate(ENGINES):
        out = out_base / engine
        out.mkdir(parents=True, exist_ok=True)
        seed = SEED_BASE + 100 + i
        try:
            _rnd.seed(seed)
            bpm = _rnd.randint(*style["bpm_range"])
            bars = _rnd.choice(BARS_OPTIONS)
            key = _rnd.choice(style["keys"])
            scale = _rnd.choice(style["scales"])
            progression = _rnd.choice(style["progressions"])

            # 与 QuickMaker.style 完全一致的 pool 构造
            pool = _build_synth_pool()
            pool["key"] = key
            pool["scale"] = scale
            pool.setdefault("generation", {})["chord_progression"] = progression
            pool["generation"]["seed"] = seed
            # 仅把每个乐器强制为待测引擎（其余字段保持 quick 合法 schema）
            for inst in pool.get("instruments", []):
                inst["engine"] = engine

            config = AlbumConfig(
                title=f"EngineProbe-{engine}", artist="BloodMusic Quick",
                genre=engine, year=2026,
                pool_raw=pool, mix_config_raw=dict(MIX_CONFIG_DEFAULTS),
                separate_mode="manifest",
                tracks=[TrackSpec(title=f"probe_{engine}", bpm=bpm, bars=bars,
                                  key=key, style=probe_style, seed=seed)],
            )
            res = AlbumMaker(config).make(str(out))
            tr = res.tracks[0] if res.tracks else None
            path = tr.song_path if tr else None
            info = inspect_wav(Path(path)) if path else {"ok": False, "error": "no song_path"}
            info["engine"] = engine
            results.append(info)
        except Exception as exc:
            results.append({"engine": engine, "ok": False,
                            "error": f"{type(exc).__name__}: {exc}"})
    return results


def step_autowav() -> dict:
    out = OUTPUT_ROOT / "autowav"
    out.mkdir(parents=True, exist_ok=True)
    rc, so, se = run_module(
        "bloodmusic.autowav", "--random", "--duration", "30",
        "--output-dir", str(out), timeout=1200,
    )
    wavs = scan_wavs(out)
    ok = rc == 0 and any(w.get("non_silent") for w in wavs)
    return {
        "returncode": rc,
        "ok": ok,
        "wav_count": len(wavs),
        "non_silent": sum(1 for w in wavs if w.get("non_silent")),
        "note": (se.strip().splitlines()[-1] if se.strip() else "") if rc != 0 else "",
    }


def main() -> int:
    log("=== content_pipeline 启动（纯本地 / 项目内）===")
    if not ensure_bloodmusic():
        log("[FATAL] bloodmusic 无法就绪，中止。")
        return 1

    steps: dict = {}
    log("C1  整专辑生成 ...")
    steps["album_demo"] = step_album_demo()

    log("C2  风格覆盖巡检 (12 风格) ...")
    style_res = step_style_coverage()
    steps["style_coverage"] = style_res

    log("C2  引擎覆盖巡检 (6 引擎) ...")
    engine_res = step_engine_coverage()
    steps["engine_coverage"] = engine_res

    log("C5  AutoWav 随机作曲 ...")
    steps["autowav"] = step_autowav()

    log("C8  质量巡检（全量扫描 OUTPUT_ROOT）...")
    all_wavs = scan_wavs(OUTPUT_ROOT)
    silent = [w for w in all_wavs if w.get("ok") and not w.get("non_silent")]
    broken = [w for w in all_wavs if not w.get("ok")]

    summary = {
        "album_demo": f"rc={steps['album_demo']['returncode']} "
                      f"({steps['album_demo']['non_silent']}/{steps['album_demo']['wav_count']} 非空)",
        "style_coverage": f"{sum(1 for x in style_res if x.get('ok'))}/{len(style_res)} 风格通过",
        "engine_coverage": f"{sum(1 for x in engine_res if x.get('ok'))}/{len(engine_res)} 引擎通过",
        "autowav": f"rc={steps['autowav']['returncode']} "
                   f"({steps['autowav']['non_silent']}/{steps['autowav']['wav_count']} 非空)",
        "total_wavs": len(all_wavs),
        "silent_wavs": len(silent),
        "broken_wavs": len(broken),
    }
    data = {
        "summary": summary,
        "steps": steps,
        "files": all_wavs,
    }
    json_path, md_path = write_reports("content_report", data)
    log(f"报告已写出: {json_path.name} / {md_path.name}")
    log(f"摘要: {summary}")

    failed = (
        not steps["album_demo"]["ok"]
        or any(not x.get("ok") for x in style_res)
        or any(not x.get("ok") for x in engine_res)
        or not steps["autowav"]["ok"]
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
