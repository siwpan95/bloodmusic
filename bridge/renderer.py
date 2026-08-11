"""
bridge/renderer.py —— 复用本体渲染管线把 ImportResult 变成音频（P0-5）

命中需求: **P0-5**（渲染与导出）

复用（R4：这三个文件 git diff 必须为空，本模块只调用、绝不修改）:
    - `music/pattern.py::render_pattern_to_array`  旋律 / 和弦轨
    - `music/pattern.py::render_drum_pattern`      鼓轨
    - `music/pattern.py::render_multi_track`       混音
    - `export/batch.py::export_audio`              wav/ogg/flac 落盘（内部已归一化）

关联发现:
    - **D6**：`render_pattern_to_array` 末尾用 `np.tile` 把信号**自动重复**到目标时长。
      因此 `duration_sec` 必须由 pattern 时值精确反推；随手传 30s 会把 8 秒的乐句
      硬生生重复 3.75 遍 —— 这是最容易踩的坑。
    - **R8**：`export_audio` 内部已做 `_normalize_and_limit`（-1 dBFS），
      本模块**不做任何额外归一化**。

输出布局（R2，默认根 `<包根>/bridge_output/`）:
    bridge_output/
      └── <midi 文件名>/
            ├── <stem>_mix.wav        （render_mode = mix | both）
            └── stems/<pattern>.wav   （render_mode = stems | both）
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..export.batch import export_audio
from ..music.pattern import (
    DrumPattern,
    MusicPattern,
    render_drum_pattern,
    render_multi_track,
    render_pattern_to_array,
)
from .config import BridgeConfig, assert_write_allowed
from .errors import BridgeRenderError, IssueCode
from .models import BridgeIssue, ImportResult, RenderResult

__all__ = [
    "pattern_duration_sec",
    "drum_duration_sec",
    "resolve_duration",
    "render_import_result",
    "render_pattern_file",
]

#: 时长下限（秒），防止空 pattern 让 soundfile 写出 0 采样文件
MIN_RENDER_SEC: float = 0.05


def pattern_duration_sec(pattern: MusicPattern) -> float:
    """`MusicPattern` 的自然时长（秒）。

    Args:
        pattern: 音乐 pattern。

    Returns:
        `sum(durations) * 60 / bpm`，下限 `MIN_RENDER_SEC`。
    """
    bpm = max(1, int(pattern.bpm))
    beats = float(sum(pattern.durations))
    return max(MIN_RENDER_SEC, beats * 60.0 / bpm)


def drum_duration_sec(pattern: DrumPattern) -> float:
    """`DrumPattern` 的自然时长（秒）。

    `render_drum_pattern` 的步长恒为 `beat/4`（F9），与 `steps` 无关，
    因此时长 = steps × (beat/4)。steps=64 @120BPM → 8.0 秒。

    Args:
        pattern: 鼓 pattern。

    Returns:
        时长（秒），下限 `MIN_RENDER_SEC`。
    """
    bpm = max(1, int(pattern.bpm))
    beat_dur = 60.0 / bpm
    return max(MIN_RENDER_SEC, int(pattern.steps) * beat_dur / 4.0)


def resolve_duration(result: ImportResult, override: float | None = None) -> float:
    """确定一次渲染的目标时长（D6 的唯一出口）。

    优先级：显式 override → `ImportResult.total_beats` 反推 →
    各 pattern 自然时长的最大值 → `MIN_RENDER_SEC`。

    Args:
        result: 导入产物。
        override: 强制时长（秒）；None 表示自动。

    Returns:
        时长（秒）。
    """
    if override is not None and float(override) > 0:
        return float(override)

    natural = result.duration_sec
    if natural > 0:
        return max(MIN_RENDER_SEC, natural)

    candidates: list[float] = [pattern_duration_sec(p) for p in result.all_music_patterns]
    candidates += [drum_duration_sec(p) for p in result.drum_patterns]
    return max(candidates) if candidates else MIN_RENDER_SEC


def _safe_stem(name: str) -> str:
    """把 pattern 名规范成安全文件名。"""
    safe = [c if (c.isalnum() or c in ("_", "-")) else "_" for c in str(name)]
    return "".join(safe).strip("_") or "pattern"


def render_pattern_file(
    pattern: MusicPattern | DrumPattern,
    out_path: str | Path,
    duration_sec: float,
    *,
    cfg: BridgeConfig | None = None,
) -> Path:
    """渲染单个 pattern 并落盘。

    Args:
        pattern: MusicPattern 或 DrumPattern。
        out_path: 输出文件路径（后缀决定格式）。
        duration_sec: 目标时长（秒）——务必由 `resolve_duration` 得来（D6）。
        cfg: 配置；用于写盘鉴权（R1）。

    Returns:
        实际写入的路径。

    Raises:
        BridgeWriteDenied: 目标落在只读根内且未通过鉴权。
        BridgeRenderError: 渲染或落盘失败。
    """
    target = assert_write_allowed(out_path, cfg)
    duration = max(MIN_RENDER_SEC, float(duration_sec))
    try:
        if isinstance(pattern, DrumPattern):
            signal = render_drum_pattern(pattern, duration)
        else:
            signal = render_pattern_to_array(pattern, duration)
        target.parent.mkdir(parents=True, exist_ok=True)
        # R8：export_audio 内部已归一化到 -1 dBFS，此处不再做任何幅度处理
        export_audio(np.asarray(signal, dtype=np.float64), str(target), format=target.suffix.lstrip("."))
    except Exception as exc:
        raise BridgeRenderError(
            f"渲染失败: {getattr(pattern, 'name', '?')} → {target.name}"
            f"（{type(exc).__name__}: {exc}）",
            path=str(target),
        ) from exc
    return target


def render_import_result(
    result: ImportResult,
    cfg: BridgeConfig | None = None,
    *,
    out_dir: str | Path | None = None,
) -> RenderResult:
    """把一个 `ImportResult` 渲染成音频文件。

    Args:
        result: `midi_to_patterns_v2` 的产物。
        cfg: 配置（决定输出根、格式、mix/stems 模式）；None → 全默认。
        out_dir: 覆盖输出目录；None → `cfg.output_root / result.stem`。

    Returns:
        RenderResult（含产物路径列表与 issue；单个 stem 失败不中断其余，§9.2）。

    Note:
        混音走 `render_multi_track`（自带每轨效果链 + 归一化），
        随后 `export_audio` 再做一次同目标（-1 dBFS）的峰值归一化 ——
        两次归一化到同一目标是幂等的，不构成 R8 所禁止的「重复归一化」。
    """
    config = cfg if cfg is not None else BridgeConfig()
    duration = resolve_duration(result, config.duration_sec)
    fmt = config.audio_format

    base_dir = Path(out_dir) if out_dir is not None else Path(config.output_root) / result.stem
    render = RenderResult(source=result.source, duration_sec=duration, fmt=fmt, out_dir=base_dir)

    if not result.all_patterns:
        render.issues.append(
            BridgeIssue(
                level="warn",
                code=IssueCode.NO_PATTERN_PRODUCED,
                message=f"{result.source.name} 没有可渲染的 pattern，已跳过。",
                context={"source": str(result.source)},
            )
        )
        return render

    want_mix = config.render_mode in ("mix", "both")
    want_stems = config.render_mode in ("stems", "both")

    # ── 混音 ──
    if want_mix and result.multi_track is not None:
        mix_path = base_dir / f"{_safe_stem(result.stem)}_mix.{fmt}"
        try:
            target = assert_write_allowed(mix_path, config)
            signal = render_multi_track(result.multi_track, duration)
            target.parent.mkdir(parents=True, exist_ok=True)
            export_audio(np.asarray(signal, dtype=np.float64), str(target), format=fmt)
            render.audio_files.append(target)
        except Exception as exc:
            render.issues.append(
                BridgeIssue(
                    level="error",
                    code=IssueCode.RENDER_FAILED,
                    message=f"混音渲染失败: {type(exc).__name__}: {exc}",
                    context={"source": str(result.source)},
                )
            )

    # ── 分轨 ──
    if want_stems:
        stem_dir = base_dir / "stems"
        for pattern in result.all_patterns:
            stem_path = stem_dir / f"{_safe_stem(pattern.name)}.{fmt}"
            try:
                written = render_pattern_file(pattern, stem_path, duration, cfg=config)
                render.audio_files.append(written)
            except Exception as exc:
                render.issues.append(
                    BridgeIssue(
                        level="error",
                        code=IssueCode.RENDER_FAILED,
                        message=f"分轨渲染失败（{pattern.name}）: {type(exc).__name__}: {exc}",
                        context={"pattern": pattern.name},
                    )
                )

    return render
