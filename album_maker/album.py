"""
album_maker/album.py — 专辑级编排器

职责：遍历曲目列表，逐首调用 TrackHandler，汇总结果，生成 album_manifest。
支持并行模式（concurrent.futures.ProcessPoolExecutor）。
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import AlbumConfig, TrackSpec
from .track import TrackHandler, TrackResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# AlbumResult
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AlbumResult:
    """专辑制作结果。

    Args:
        title: 专辑标题
        out_dir: 输出根目录
        tracks: 各曲目结果列表
        album_manifest_path: album_manifest.json 路径
        video_bgm_path: 视频 BGM 输出路径（仅当指定 --video 时）
        success_count: 成功曲目数
        failure_count: 失败曲目数
        total_duration_sec: 总时长（秒）
    """
    title: str
    out_dir: Path = field(default_factory=Path)
    tracks: list[TrackResult] = field(default_factory=list)
    album_manifest_path: Path | None = None
    video_bgm_path: Path | None = None
    success_count: int = 0
    failure_count: int = 0
    total_duration_sec: float = 0.0

    @property
    def all_success(self) -> bool:
        """是否全部曲目成功。"""
        return self.failure_count == 0


# ═══════════════════════════════════════════════════════════════════════
# AlbumMaker
# ═══════════════════════════════════════════════════════════════════════

class AlbumMaker:
    """专辑制作器 —— 核心编排引擎。

    职责：遍历曲目列表，逐首调用 TrackHandler，汇总结果，生成 album_manifest。
    支持并行模式（concurrent.futures）。
    """

    def __init__(self, config: AlbumConfig):
        """初始化专辑制作器。

        Args:
            config: 专辑配置
        """
        self.config = config

    def make(
        self,
        out_dir: str | Path,
        *,
        parallel: bool = False,
        video_path: str | None = None,
    ) -> AlbumResult:
        """执行整张专辑制作。

        Args:
            out_dir: 输出根目录（如 album_output/）
            parallel: 是否并行生成曲目（默认 False）
            video_path: 视频文件路径。指定后会将首支成功曲目作为 BGM
                嵌入视频（使用 VideoProcessor.mux_audio_video）。

        Returns:
            AlbumResult（单曲目失败不中断，继续处理其余）
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 专辑级准备
        self._copy_config_copy(out_dir)

        # 封面：若配置了封面且文件存在，复制到输出目录
        cover_path: str | None = None
        if self.config.cover:
            cover_src = Path(self.config.cover)
            if cover_src.is_file():
                cover_ext = cover_src.suffix.lstrip(".") or "png"
                cover_dst = out_dir / f"cover.{cover_ext}"
                shutil.copy2(cover_src, cover_dst)
                cover_path = cover_dst.name
                logger.info(f"封面已复制: {cover_dst}")
            else:
                logger.warning(f"封面文件不存在，跳过: {cover_src}")

        base_pool = self._build_base_pool()

        # 遍历曲目
        if parallel:
            track_results = self._make_parallel(base_pool, out_dir)
        else:
            track_results = self._make_serial(base_pool, out_dir)

        # 汇总结果
        success_count = sum(1 for r in track_results if r.success)
        failure_count = len(track_results) - success_count
        total_duration = sum(r.duration_sec for r in track_results if r.success)

        # 写入 album_manifest
        album_result = AlbumResult(
            title=self.config.title,
            out_dir=out_dir,
            tracks=track_results,
            success_count=success_count,
            failure_count=failure_count,
            total_duration_sec=total_duration,
        )
        album_result.album_manifest_path = self._write_album_manifest(
            album_result, out_dir, cover_path=cover_path
        )

        # ── 视频 BGM：专辑完成后，可选地将母带嵌入视频 ──
        if video_path:
            try:
                video_output = self._mux_video_bgm(
                    video_path=video_path,
                    album_output=out_dir,
                    result=album_result,
                )
                album_result.video_bgm_path = video_output
                self._update_manifest_video_bgm(out_dir, video_output)
                logger.info(f"视频 BGM 已输出: {video_output}")
            except FileNotFoundError as exc:
                logger.error(f"视频 BGM 失败（文件不存在）: {exc}")
            except RuntimeError as exc:
                logger.error(f"视频 BGM 失败: {exc}")
            except Exception as exc:
                logger.error(
                    f"视频 BGM 异常: {type(exc).__name__}: {exc}"
                )

        logger.info(
            f"专辑完成: {self.config.title} — "
            f"成功 {success_count}/{len(track_results)}, "
            f"总时长 {total_duration:.1f}s"
        )

        return album_result

    # ── 内部方法 ──

    def _make_serial(
        self, base_pool: "InstrumentPool", out_dir: Path
    ) -> list[TrackResult]:
        """串行处理所有曲目。"""
        results: list[TrackResult] = []
        for i, track_spec in enumerate(self.config.tracks):
            safe_title = self._safe_dirname(track_spec.title)
            track_work_dir = out_dir / f"track_{i + 1:02d}_{safe_title}"
            logger.info(f"曲目 {i + 1}/{len(self.config.tracks)}: {track_spec.title}")

            handler = TrackHandler(
                spec=track_spec,
                pool=base_pool,
                mix_config_raw=self.config.mix_config_raw,
                separate_mode=self.config.separate_mode,
            )
            result = handler.process(track_work_dir)
            results.append(result)

            if not result.success:
                logger.warning(
                    f"  ⚠ 曲目失败: {track_spec.title} — {result.error}"
                )

        return results

    def _make_parallel(
        self, base_pool: "InstrumentPool", out_dir: Path
    ) -> list[TrackResult]:
        """并行处理所有曲目（concurrent.futures.ProcessPoolExecutor）。"""
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # 构建任务列表
        tasks: list[tuple[int, TrackSpec, Path]] = []
        for i, track_spec in enumerate(self.config.tracks):
            safe_title = self._safe_dirname(track_spec.title)
            track_work_dir = out_dir / f"track_{i + 1:02d}_{safe_title}"
            tasks.append((i, track_spec, track_work_dir))

        results_dict: dict[int, TrackResult] = {}

        with ProcessPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
            futures = {
                executor.submit(
                    _process_track_worker,
                    track_spec,
                    base_pool,
                    self.config.mix_config_raw,
                    self.config.separate_mode,
                    track_work_dir,
                ): idx
                for idx, track_spec, track_work_dir in tasks
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = TrackResult(
                        title=tasks[idx][1].title,
                        success=False,
                        error=f"并行执行异常: {type(exc).__name__}: {exc}",
                        bpm=tasks[idx][1].bpm,
                        key=tasks[idx][1].key,
                    )
                results_dict[idx] = result

        return [results_dict[i] for i in range(len(tasks))]

    def _build_base_pool(self) -> "InstrumentPool":
        """从 AlbumConfig.pool_raw 构建基础 InstrumentPool。

        Returns:
            InstrumentPool 实例
        """
        from bloodmusic.music.pool_serializer import PoolSerializer

        pool_data = self.config.pool_raw.copy()
        return PoolSerializer._dict_to_pool(pool_data)

    def _write_album_manifest(
        self,
        result: AlbumResult,
        out_dir: Path,
        *,
        cover_path: str | None = None,
    ) -> Path:
        """生成 album_manifest.json。

        Args:
            result: AlbumResult
            out_dir: 输出根目录
            cover_path: 封面相对路径（仅文件名），None 表示无封面

        Returns:
            album_manifest.json 路径
        """
        track_entries: list[dict] = []
        for i, tr in enumerate(result.tracks):
            entry: dict = {
                "index": i + 1,
                "title": tr.title,
                "success": tr.success,
                "bpm": tr.bpm,
                "key": tr.key,
                "duration_sec": tr.duration_sec,
            }
            if tr.success:
                entry["song_path"] = str(
                    tr.song_path.relative_to(out_dir)
                    if tr.song_path
                    else None
                )
                entry["manifest_path"] = str(
                    tr.manifest_path.relative_to(out_dir)
                    if tr.manifest_path
                    else None
                )
            else:
                entry["error"] = tr.error

            track_entries.append(entry)

        manifest: dict = {
            "version": "1.0",
            "album": {
                "title": self.config.title,
                "artist": self.config.artist,
                "genre": self.config.genre,
                "year": self.config.year,
                "cover": cover_path or self.config.cover,
                "separate_mode": self.config.separate_mode,
            },
            "summary": {
                "total_tracks": len(result.tracks),
                "success_count": result.success_count,
                "failure_count": result.failure_count,
                "total_duration_sec": result.total_duration_sec,
            },
            "tracks": track_entries,
            "honesty_note": (
                "混音不可逆，算法分离是有损近似。"
                "模式A(manifest) 提供 sha256 保真的分轨还原；"
                "模式B(algo) 通过 AI 模型重分离，结果仅为有损近似，不可视为原始分轨。"
            ),
        }

        manifest_path = out_dir / "album_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"album_manifest 已写入: {manifest_path}")
        return manifest_path

    def _copy_config_copy(self, out_dir: Path) -> None:
        """复制配置副本到输出目录（如果是从 YAML 加载则有原始文件路径）。"""
        # 将 pool_raw + mix_config_raw 序列化为 YAML 副本
        # 用于可复现性（用户可基于此重新生成）
        import yaml

        config_copy: dict = {
            "album": {
                "title": self.config.title,
                "artist": self.config.artist,
                "genre": self.config.genre,
                "year": self.config.year,
                "cover": self.config.cover,
            },
            "instrument_pool": self.config.pool_raw,
            "mix_config": self.config.mix_config_raw,
            "separate_mode": self.config.separate_mode,
            "tracks": [
                {
                    "title": ts.title,
                    "bpm": ts.bpm,
                    "bars": ts.bars,
                    "key": ts.key,
                    "style": ts.style,
                    "seed": ts.seed,
                }
                for ts in self.config.tracks
            ],
        }

        copy_path = out_dir / "album.yaml.copy"
        with open(copy_path, "w", encoding="utf-8") as f:
            yaml.dump(
                config_copy,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
            )

    # ── 视频 BGM ──

    def _mux_video_bgm(
        self,
        video_path: str,
        album_output: Path,
        result: AlbumResult,
    ) -> Path:
        """将专辑首支成功曲目作为 BGM 嵌入视频。

        逻辑：
        1. 取第一首成功曲目的 song_final.wav 作为 BGM
        2. 调用 VideoProcessor.mux_audio_video(mode=REPLACE)
        3. 返回输出视频路径

        Args:
            video_path: 源视频文件路径
            album_output: 专辑输出根目录
            result: AlbumResult（用于获取成功曲目）

        Returns:
            输出视频文件的 Path

        Raises:
            FileNotFoundError: 视频文件或音频文件不存在
            RuntimeError: 没有成功曲目 或 ffmpeg 执行失败 或 依赖缺失
        """
        # 尽早校验输入，避免延迟到 import 阶段才报错
        video_path_obj = Path(video_path)
        if not video_path_obj.is_file():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 取第一首成功曲目的成品 WAV
        audio_path: Path | None = None
        for track in result.tracks:
            if track.success and track.song_path is not None and track.song_path.is_file():
                audio_path = track.song_path
                break

        if audio_path is None:
            raise RuntimeError("没有成功的曲目可用作 BGM")

        # 延迟导入 remix 依赖（避免 album_maker 直接依赖 pydub/ffmpeg）
        try:
            from core.video_processor import VideoProcessor, MuxMode
        except ImportError as exc:
            raise RuntimeError(
                f"无法加载 VideoProcessor（缺少 remix 依赖）: {exc}"
            ) from exc

        # 输出路径：album_output 下，保留原视频扩展名
        video_suffix = video_path_obj.suffix or ".mp4"
        output_path = album_output / f"video_bgm{video_suffix}"

        logger.info(
            f"视频 BGM 合成: 视频={video_path_obj.name}, "
            f"音频={audio_path.name}"
        )

        vp = VideoProcessor()
        abs_output = vp.mux_audio_video(
            video_path=str(video_path_obj),
            audio_path=str(audio_path),
            output_path=str(output_path),
            mode=MuxMode.REPLACE,
        )

        return Path(abs_output)

    def _update_manifest_video_bgm(
        self,
        out_dir: Path,
        video_output: Path,
    ) -> None:
        """更新 album_manifest.json，写入 video_bgm 信息。

        Args:
            out_dir: 专辑输出根目录
            video_output: 视频 BGM 输出路径
        """
        manifest_path = out_dir / "album_manifest.json"
        if not manifest_path.is_file():
            logger.warning("album_manifest.json 不存在，跳过 video_bgm 记录")
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        manifest["video_bgm"] = {
            "path": str(video_output.relative_to(out_dir)),
            "abs_path": str(video_output),
            "mode": "REPLACE",
            "description": "首支成功曲目替换原视频音轨",
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        logger.info(f"album_manifest 已更新 video_bgm 记录")

    @staticmethod
    def _safe_dirname(name: str) -> str:
        """把曲目名规范成安全的目录名。"""
        safe = [c if (c.isalnum() or c in ("_", "-")) else "_" for c in str(name)]
        return "".join(safe).strip("_") or "track"


# ═══════════════════════════════════════════════════════════════════════
# 并行 Worker（模块级函数，供 ProcessPoolExecutor 使用）
# ═══════════════════════════════════════════════════════════════════════

def _process_track_worker(
    track_spec: TrackSpec,
    base_pool: "InstrumentPool",
    mix_config_raw: dict,
    separate_mode: str,
    work_dir: Path,
) -> TrackResult:
    """ProcessPoolExecutor worker：在子进程中处理单首曲目。

    Args:
        track_spec: 曲目配置
        base_pool: 基础乐器池
        mix_config_raw: 混音参数
        separate_mode: 分离模式
        work_dir: 工作目录

    Returns:
        TrackResult
    """
    handler = TrackHandler(
        spec=track_spec,
        pool=base_pool,
        mix_config_raw=mix_config_raw,
        separate_mode=separate_mode,
    )
    return handler.process(work_dir)
