"""
album_maker/report.py — 专辑报告生成器

生成控制台可打印的专辑报告和 JSON 序列化结果。
"""

from __future__ import annotations

import json
from pathlib import Path

from .album import AlbumResult


class AlbumReport:
    """专辑报告生成器。

    提供两种输出方式：
    - generate(): 返回可打印的控制台报告字符串
    - to_json(): 将 AlbumResult 序列化为 JSON 文件
    """

    @staticmethod
    def generate(result: AlbumResult) -> str:
        """生成可打印的控制台报告字符串。

        Args:
            result: AlbumResult 实例

        Returns:
            格式化的报告字符串
        """
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append(f"  专辑报告: {result.title}")
        lines.append("=" * 60)
        lines.append(f"  输出目录: {result.out_dir}")
        lines.append(f"  总曲目数: {len(result.tracks)}")
        lines.append(f"  成功: {result.success_count} 首")
        lines.append(f"  失败: {result.failure_count} 首")
        lines.append(f"  总时长: {result.total_duration_sec:.1f} 秒")
        lines.append("-" * 60)

        for i, tr in enumerate(result.tracks):
            icon = "✓" if tr.success else "✗"
            lines.append(f"  [{icon}] 曲目 {i + 1}: {tr.title}")
            lines.append(f"       BPM={tr.bpm}, Key={tr.key}, "
                         f"时长={tr.duration_sec:.1f}s")
            if tr.success:
                if tr.song_path:
                    lines.append(f"       成品: {tr.song_path.name}")
                if tr.manifest_path:
                    lines.append(f"       清单: {tr.manifest_path.name}")
            else:
                lines.append(f"       错误: {tr.error}")

        lines.append("-" * 60)

        if result.failure_count > 0:
            lines.append(f"  ⚠ 警告: {result.failure_count} 首曲目失败，退出码非零")
        else:
            lines.append(f"  ✅ 全部 {result.success_count} 首曲目成功生成")

        lines.append("=" * 60)
        return "\n".join(lines)

    @staticmethod
    def to_json(result: AlbumResult, path: Path) -> None:
        """将 AlbumResult 序列化为 JSON 报告。

        Args:
            result: AlbumResult 实例
            path: 输出 JSON 文件路径
        """
        data: dict = {
            "title": result.title,
            "out_dir": str(result.out_dir),
            "summary": {
                "total_tracks": len(result.tracks),
                "success_count": result.success_count,
                "failure_count": result.failure_count,
                "total_duration_sec": result.total_duration_sec,
            },
            "tracks": [],
        }

        for tr in result.tracks:
            entry: dict = {
                "title": tr.title,
                "success": tr.success,
                "bpm": tr.bpm,
                "key": tr.key,
                "duration_sec": tr.duration_sec,
            }
            if tr.success:
                entry["song_path"] = str(tr.song_path) if tr.song_path else None
                entry["manifest_path"] = (
                    str(tr.manifest_path) if tr.manifest_path else None
                )
                entry["sources_dir"] = (
                    str(tr.sources_dir) if tr.sources_dir else None
                )
            else:
                entry["error"] = tr.error
            data["tracks"].append(entry)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
