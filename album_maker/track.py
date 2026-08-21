"""
album_maker/track.py — 单曲目全流程处理器

流程分支:
  - midi_path 非空: MIDI 导入 → bridge render stems → mixdown → manifest
    （跳过 PoolGenerator 合成）
  - midi_path 为空: PoolGenerator → bridge render stems → mixdown → manifest
    （行为不变）
  - 两者可共存: MIDI stems + synth stems 合并进入 mixdown

任何阶段失败均返回 success=False 的 TrackResult，不抛异常。

依赖:
  - bloodmusic (PoolGenerator, InstrumentPool, StylePreset, render_pattern_file)
  - bloodmusic.bridge (midi_to_patterns_v2)
  - audio_pipeline (mixdown) — 通过 sys.path 注入，延迟 import
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ── sys.path 注入 audio_pipeline + remix（环境变量可配置） ──
# CRITICAL: remix 必须在 bloodmusic 之前，因为 bloodmusic 也有 core/ 子包
# bloodmusic 内部使用相对导入 (.core)，不受影响
_AUDIO_PIPELINE_ROOT = Path(os.environ.get(
    "BLOODMUSIC_AUDIO_PIPELINE", r"G:\tools\audio\audio_pipeline",
))
_REMIX_ROOT = Path(os.environ.get(
    "BLOODMUSIC_REMIX", r"G:\tools\audio\remix",
))
for _root in (_REMIX_ROOT, _AUDIO_PIPELINE_ROOT):
    _root_str = str(_root)
    if not _root.is_dir():
        logger.warning(
            "外部依赖路径不存在: %s（可用环境变量 BLOODMUSIC_AUDIO_PIPELINE / "
            "BLOODMUSIC_REMIX 覆盖默认值）", _root_str,
        )
    # 移除已存在的重复项
    while _root_str in sys.path:
        sys.path.remove(_root_str)
    sys.path.insert(0, _root_str)


# ═══════════════════════════════════════════════════════════════════════
# TrackResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TrackResult:
    """单曲目处理结果。

    Args:
        title: 曲目标题
        success: 是否成功
        song_path: song_final.wav 路径
        sources_dir: _sources/ 目录
        manifest_path: manifest.json 路径
        error: 失败原因
        duration_sec: 曲目时长（秒）
        bpm: BPM
        key: 调性
    """
    title: str
    success: bool = False
    song_path: Path | None = None
    sources_dir: Path | None = None
    manifest_path: Path | None = None
    error: str | None = None
    duration_sec: float = 0.0
    bpm: int = 120
    key: str = "C"


# ═══════════════════════════════════════════════════════════════════════
# TrackHandler
# ═══════════════════════════════════════════════════════════════════════

class TrackHandler:
    """单曲目全流程处理器。

    流程: PoolGenerator → bridge render stems → mixdown → manifest。
    任何阶段失败均返回 success=False 的 TrackResult，不抛异常。
    """

    def __init__(
        self,
        spec: "TrackSpec",
        pool: "InstrumentPool",
        mix_config_raw: dict,
        separate_mode: str = "manifest",
    ):
        """初始化单曲目处理器。

        Args:
            spec: 曲目配置
            pool: 基础乐器池（album 级别）
            mix_config_raw: 混音参数 raw dict
            separate_mode: 分离模式
        """
        self.spec = spec
        self.base_pool = pool
        self.mix_config_raw = mix_config_raw
        self.separate_mode = separate_mode

    # ── 主入口 ──

    def process(self, work_dir: Path) -> TrackResult:
        """执行单曲目全流程。

        Args:
            work_dir: 曲目工作目录（如 album_output/track_01_开场曲/）

        Returns:
            TrackResult（总是返回，不抛异常）

        流程分支：
            - 若 spec.midi_path 非空：MIDI 导入 → render stems，跳过 PoolGenerator 合成
            - 若 spec.midi_path 为空：走 synth 原路径（行为不变）
            - 两者可共存：MIDI stems + synth stems 合并进入 mixdown
        """
        try:
            work_dir = Path(work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)

            # 计算 duration_sec
            duration_sec = self.spec.bars * 60.0 / max(1, self.spec.bpm)

            # 构建曲目专属 pool
            track_pool = self._build_pool_for_track()

            # 阶段 M0：MIDI 导入 + 渲染 stems（若指定了 midi_path）
            midi_paths = self._render_midi_stems(work_dir, duration_sec)

            # 阶段 G：生成（synth 路径，MIDI 路径跳过 PoolGenerator）
            synth_paths: list[Path] = []
            if not self.spec.midi_path:
                multi = self._generate(track_pool)
                stems_dir = work_dir / "stems"
                synth_paths = self._render_stems(multi, stems_dir, duration_sec)

            # 合并所有 stems（MIDI + synth）
            all_stems = midi_paths + synth_paths
            if not all_stems:
                return TrackResult(
                    title=self.spec.title,
                    success=False,
                    error="渲染分轨失败：未产生任何 WAV 文件",
                    bpm=self.spec.bpm,
                    key=self.spec.key,
                )

            # 阶段 M：混音
            mix_result = self._mixdown(all_stems, work_dir)

            logger.info(
                f"✅ 曲目完成: {self.spec.title} "
                f"({duration_sec:.1f}s, {self.spec.bpm}BPM, {self.spec.key})"
            )

            return TrackResult(
                title=self.spec.title,
                success=True,
                song_path=mix_result.song_path,
                sources_dir=mix_result.sources_dir,
                manifest_path=mix_result.manifest_path,
                duration_sec=duration_sec,
                bpm=self.spec.bpm,
                key=self.spec.key,
            )

        except Exception as exc:
            logger.error(f"❌ 曲目失败: {self.spec.title} — {type(exc).__name__}: {exc}")
            return TrackResult(
                title=self.spec.title,
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                bpm=self.spec.bpm,
                key=self.spec.key,
            )

    # ── 阶段 G：生成 ──

    def _build_pool_for_track(self) -> "InstrumentPool":
        """根据 TrackSpec 构建曲目专属 InstrumentPool（应用 style + extra_instruments）。

        Returns:
            应用了 style 覆盖和 extra_instruments 的 InstrumentPool 副本
        """
        import copy

        from bloodmusic.music.instrument_pool import (
            InstrumentPool,
            InstrumentRole,
            PoolConfig,
            PoolInstrument,
            SynthEngine,
        )
        from bloodmusic.music.pool_styles import get_style

        # 从 base_pool 深拷贝（不污染原对象）
        pool = copy.deepcopy(self.base_pool)

        # 覆盖 BPM / key / seed
        pool.bpm = self.spec.bpm
        pool.key = self.spec.key
        if self.spec.seed is not None:
            pool.config.seed = self.spec.seed

        # 应用风格预设（pool_styles）
        if self.spec.style:
            try:
                style = get_style(self.spec.style)
                pool = style.apply_to(pool)
            except KeyError:
                logger.warning(
                    f"未知风格 '{self.spec.style}'，使用 pool 默认参数"
                )

        # 叠加 style_db 编配策略（随机 chord_progression + scale）
        pool = self._apply_style_db(pool)

        # 追加 extra_instruments
        if self.spec.extra_instruments:
            for inst_data in self.spec.extra_instruments:
                if not isinstance(inst_data, dict):
                    continue
                role_raw = inst_data.get("role", "melody")
                role = (
                    InstrumentRole.from_string(role_raw)
                    if isinstance(role_raw, str)
                    else InstrumentRole.MELODY
                )
                engine_raw = inst_data.get("engine", "wavetable")
                engine = (
                    SynthEngine.from_string(engine_raw)
                    if isinstance(engine_raw, str)
                    else SynthEngine.WAVETABLE
                )
                inst = PoolInstrument(
                    name=inst_data.get("name", "Extra"),
                    role=role,
                    engine=engine,
                    preset=inst_data.get("preset"),
                    volume=float(inst_data.get("volume", 0.8)),
                    pan=float(inst_data.get("pan", 0.0)),
                    note_sequence=inst_data.get("note_sequence"),
                )
                pool.instruments.append(inst)

        return pool

    def _apply_style_db(self, pool: "InstrumentPool") -> "InstrumentPool":
        """叠加 style_db 编配策略：随机 chord_progression + scale。

        在 pool_styles 应用之后调用，用联网调研的风格数据增强随机性。
        仅在 style_db 中存在该风格时生效，否则保持 pool 原样。
        """
        if not self.spec.style:
            return pool

        try:
            from .style_db import get_style as get_style_db
        except ImportError:
            return pool

        style_db = get_style_db(self.spec.style)
        if not style_db:
            return pool

        import random as _random

        # 随机 chord_progression（若 pool.config 未显式设置）
        if style_db.get("progressions") and pool.config.chord_progression in (None, ""):
            pool.config.chord_progression = _random.choice(style_db["progressions"])

        # 随机 scale（若 pool.scale 为默认 major）
        if style_db.get("scales") and getattr(pool, "scale", "major") == "major":
            pool.scale = _random.choice(style_db["scales"])

        # 随机 key（若 spec 未显式指定，且 pool.key 为默认 C）
        if style_db.get("keys") and getattr(pool, "key", "C") == "C" and self.spec.key == "C":
            pool.key = _random.choice(style_db["keys"])

        return pool

    def _generate(self, pool: "InstrumentPool") -> "MultiTrackPattern":
        """调用 PoolGenerator.generate_all()。

        Args:
            pool: 曲目专属 InstrumentPool

        Returns:
            MultiTrackPattern
        """
        from bloodmusic.music.pool_generator import PoolGenerator
        from bloodmusic.music.pool_styles import get_style

        # 获取风格预设（用于 PoolGenerator 构造）
        style = None
        if self.spec.style:
            try:
                style = get_style(self.spec.style)
            except KeyError:
                pass

        generator = PoolGenerator(pool, style)
        multi = generator.generate_all(self.spec.bars)
        logger.info(
            f"生成完成: {self.spec.title} — "
            f"{len(multi.music_tracks)} music track(s)"
            f"{' + drum' if multi.drum_track is not None else ''}"
        )
        return multi

    # ── 阶段 M0：MIDI 导入 + 渲染 ──

    def _render_midi_stems(
        self,
        work_dir: Path,
        duration_sec: float,
    ) -> list[Path]:
        """若 spec.midi_path 非空，导入 MIDI 并将每个 pattern 渲染为独立 WAV。

        流程: midi_to_patterns_v2(path, bpm) → 遍历 result.all_patterns
              → render_pattern_file() 写 stems/*.wav。

        Args:
            work_dir: 曲目工作目录。
            duration_sec: 目标时长（秒），与合成轨保持一致以便混音。

        Returns:
            MIDI stem 的 WAV 文件路径列表；midi_path 为空或导入失败时返回空列表。
        """
        if not self.spec.midi_path:
            return []

        # 延迟 import（bridge 依赖 mido 惰性加载）
        from bloodmusic.bridge import midi_to_patterns_v2
        from bloodmusic.bridge.renderer import render_pattern_file

        stems_dir = work_dir / "stems"
        stems_dir.mkdir(parents=True, exist_ok=True)

        midi_stems: list[Path] = []

        # 导入 MIDI
        try:
            import_result = midi_to_patterns_v2(
                self.spec.midi_path,
                bpm=self.spec.bpm,
            )
        except Exception as exc:
            logger.warning(
                f"MIDI 导入失败: {self.spec.midi_path} — "
                f"{type(exc).__name__}: {exc}"
            )
            return []

        # 渲染所有 pattern（旋律 + 和弦 + 鼓）
        for pattern in import_result.all_patterns:
            safe_name = self._safe_stem(
                getattr(pattern, "name", "midi_pattern")
            )
            out_path = stems_dir / f"{safe_name}.wav"
            try:
                written = render_pattern_file(pattern, out_path, duration_sec)
                midi_stems.append(written)
                logger.debug(f"  MIDI stem: {written.name}")
            except Exception as exc:
                logger.warning(
                    f"  MIDI stem 渲染失败 "
                    f"({getattr(pattern, 'name', '?')}): {exc}"
                )

        logger.info(
            f"MIDI 导入完成: {self.spec.midi_path} → "
            f"{len(midi_stems)} stems"
        )
        return midi_stems

    # ── 阶段 R：渲染分轨 ──

    @staticmethod
    def _safe_stem(name: str) -> str:
        """把 pattern 名规范成安全文件名。"""
        safe = [c if (c.isalnum() or c in ("_", "-")) else "_" for c in str(name)]
        return "".join(safe).strip("_") or "pattern"

    def _render_stems(
        self,
        multi: "MultiTrackPattern",
        stems_dir: Path,
        duration_sec: float,
    ) -> list[Path]:
        """将 MultiTrackPattern 的每轨渲染为独立 WAV。

        Args:
            multi: MultiTrackPattern 实例
            stems_dir: stems 输出目录
            duration_sec: 目标时长（秒）

        Returns:
            WAV 文件路径列表
        """
        from bloodmusic.bridge.renderer import render_pattern_file

        stems_dir = Path(stems_dir)
        stems_dir.mkdir(parents=True, exist_ok=True)

        stem_paths: list[Path] = []

        # 渲染 music tracks
        for i, pattern in enumerate(multi.music_tracks):
            safe_name = self._safe_stem(getattr(pattern, "name", f"track_{i:02d}"))
            out_path = stems_dir / f"{safe_name}.wav"
            try:
                written = render_pattern_file(pattern, out_path, duration_sec)
                stem_paths.append(written)
                logger.debug(f"  渲染分轨: {written.name}")
            except Exception as exc:
                logger.warning(
                    f"  渲染分轨失败 ({getattr(pattern, 'name', '?')}): {exc}"
                )
                # 单轨失败不中断，继续渲染其余

        # 渲染 drum track
        if multi.drum_track is not None:
            safe_name = self._safe_stem(
                getattr(multi.drum_track, "name", "drum_track")
            )
            out_path = stems_dir / f"{safe_name}.wav"
            try:
                written = render_pattern_file(multi.drum_track, out_path, duration_sec)
                stem_paths.append(written)
                logger.debug(f"  渲染鼓轨: {written.name}")
            except Exception as exc:
                logger.warning(f"  渲染鼓轨失败: {exc}")

        return stem_paths


    # ── 阶段 M：混音 ──

    def _build_mix_config(self) -> "MixConfig":
        """从 raw dict 构造 MixConfig。

        Returns:
            remix.core.audio_mixer.MixConfig 实例
        """
        # 延迟 import（在 sys.path 注入后可用）
        from core.audio_mixer import ClippingMode, MixConfig, NormalizeMode

        raw = self.mix_config_raw.copy()

        # 应用曲目级覆盖
        if self.spec.mix_config_override:
            raw.update(self.spec.mix_config_override)

        # 字符串 → 枚举转换
        clip_mode = ClippingMode.SOFT
        if raw.get("clip_mode") == "hard":
            clip_mode = ClippingMode.HARD

        normalize_mode = NormalizeMode.RMS
        nm = raw.get("normalize_mode", "rms")
        if nm == "peak":
            normalize_mode = NormalizeMode.PEAK
        elif nm == "none":
            normalize_mode = NormalizeMode.NONE

        low_pass_cutoff = int(raw.get("low_pass_cutoff", 0))
        high_pass_cutoff = int(raw.get("high_pass_cutoff", 0))

        return MixConfig(
            clip_mode=clip_mode,
            normalize_mode=normalize_mode,
            fade_in_ms=int(raw.get("fade_in_ms", 50)),
            fade_out_ms=int(raw.get("fade_out_ms", 200)),
            crossfade_ms=int(raw.get("crossfade_ms", 0)),
            rms_target_db=float(raw.get("rms_target_db", -3.0)),
            compress=bool(raw.get("compress", True)),
            compress_threshold=float(raw.get("compress_threshold", -20.0)),
            compress_ratio=float(raw.get("compress_ratio", 4.0)),
            low_pass_cutoff=low_pass_cutoff,
            high_pass_cutoff=high_pass_cutoff,
        )

    def _mixdown(
        self,
        sources: list[Path],
        work_dir: Path,
    ) -> "MixResult":
        """调用 audio_pipeline.mixdown() 混音。

        Args:
            sources: stems WAV 文件路径列表
            work_dir: 曲目工作目录

        Returns:
            MixResult(song_path, sources_dir, manifest_path)

        Raises:
            ModuleNotFoundError: audio_pipeline 不可用
            Exception: 混音失败
        """
        # 延迟 import
        from mixdown import mixdown, MixResult

        mix_config = self._build_mix_config()

        result: MixResult = mixdown(
            sources=sources,
            out_dir=work_dir,
            config=mix_config,
            fmt="wav",
            separate_mode=self.separate_mode,
            bpm=self.spec.bpm,
            musical_key=self.spec.key,
        )

        logger.info(
            f"  混音完成: {result.song_path.name} "
            f"(sources: {result.sources_dir.name})"
        )
        return result
