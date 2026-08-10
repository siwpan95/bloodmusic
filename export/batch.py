"""批量音频导出引擎"""

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ..core.constants import SR, NORMALIZE_DBFS, DEFAULT_OGG_BITRATE
from ..core.voice import SynthVoice, synthesize_voice
from ..music.pattern import generate_music_wav
from ..sfx.presets import UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
from ..music.presets import ALL_MUSIC_PATTERNS


def _normalize_and_limit(sig: np.ndarray, target_dbfs: float = NORMALIZE_DBFS) -> np.ndarray:
    """归一化到目标 dBFS + 硬限幅。

    Args:
        sig: 输入信号 (float64)
        target_dbfs: 目标 dBFS 值 (默认 -1.0)
    Returns:
        归一化 + 限幅后的信号
    """
    target_amp = 10 ** (target_dbfs / 20.0)  # e.g. -1dBFS ≈ 0.8913
    peak = np.max(np.abs(sig))
    if peak > 0:
        sig = sig * (target_amp / peak)
    sig = np.clip(sig, -1.0, 1.0)
    return sig


def export_audio(
    sig: np.ndarray,
    path: str,
    format: str = "wav",
    bitrate: int = DEFAULT_OGG_BITRATE,
    metadata: dict | None = None,
    sr: int = SR,
) -> str:
    """统一音频导出函数，支持 WAV/OGG/FLAC。

    Args:
        sig: 音频信号 (float32/float64)
        path: 输出文件路径
        format: "wav" / "ogg" / "flac"
        bitrate: OGG 比特率 (bps)
        metadata: 元数据字典 (仅 WAV/FLAC)
        sr: 采样率
    Returns:
        输出文件路径
    """
    sig = sig.astype(np.float64)
    sig = _normalize_and_limit(sig)

    format = format.lower().strip(".")
    filepath = Path(path)

    # 确保输出目录存在
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if format == "wav":
        import soundfile as sf
        sf.write(str(filepath), sig, sr, subtype='PCM_16')
    elif format == "ogg":
        import soundfile as sf
        sf.write(str(filepath), sig, sr, format='OGG', subtype='VORBIS')
    elif format == "flac":
        import soundfile as sf
        sf.write(str(filepath), sig, sr, format='FLAC', subtype='PCM_24')
    else:
        raise ValueError(f"不支持的格式: {format}。支持: wav, ogg, flac")

    return str(filepath)


class AudioBatchExporter:
    """批量音频文件导出器。

    Usage:
        exporter = AudioBatchExporter("./output")
        exporter.export_everything(music_duration=30.0)
    """

    def __init__(self, base_output_dir: str, format: str = "wav"):
        self.base_dir = Path(base_output_dir)
        self.format = format.lower().strip(".")
        self.sfx_dir = self.base_dir / "sfx"
        self.music_dir = self.base_dir / "music"
        self.export_log: List[str] = []

    @property
    def _ext(self) -> str:
        """根据格式返回文件扩展名"""
        return f".{self.format}"

    def ensure_dirs(self):
        for cat in ["ui", "combat", "card", "system"]:
            (self.sfx_dir / cat).mkdir(parents=True, exist_ok=True)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    def export_sfx(self, preset_name: str, voice: SynthVoice,
                   category: str) -> str:
        """导出单个 SFX。返回文件路径。"""
        sig = synthesize_voice(voice)
        sig = _normalize_and_limit(sig.astype(np.float64))

        filepath = self.sfx_dir / category / f"{preset_name}{self._ext}"
        export_audio(sig, str(filepath), format=self.format)

        log_msg = f"[SFX] {category}/{preset_name}{self._ext} ({len(sig) / SR:.2f}s)"
        self.export_log.append(log_msg)
        return str(filepath)

    def export_all_sfx(self) -> Dict[str, str]:
        """导出全部 SFX 预设，返回 {key: path}。"""
        self.ensure_dirs()
        exported: Dict[str, str] = {}

        categories = {
            "ui":      UI_FX_PRESETS,
            "card":    CARD_FX_PRESETS,
            "combat":  COMBAT_FX_PRESETS,
            "system":  SYSTEM_FX_PRESETS,
        }
        for cat, presets in categories.items():
            for name, voice in presets.items():
                path = self.export_sfx(name, voice, cat)
                exported[f"{cat}/{name}"] = path

        return exported

    def export_all_music(self, duration_sec: float = 30.0) -> Dict[str, str]:
        """导出全部音乐，返回 {key: path}。"""
        self.ensure_dirs()
        exported: Dict[str, str] = {}

        for key, pattern in ALL_MUSIC_PATTERNS.items():
            filepath = self.music_dir / f"{pattern.name}{self._ext}"
            # 生成音频（总是先生成 WAV 再按格式导出）
            from ..music.pattern import render_pattern_to_array
            sig = render_pattern_to_array(pattern, duration_sec)
            export_audio(sig, str(filepath), format=self.format)
            exported[key] = str(filepath)

        return exported

    def export_everything(self, music_duration: float = 30.0) -> Dict[str, str]:
        """一键导出全部音频资源。"""
        all_files: Dict[str, str] = {}
        all_files.update(self.export_all_sfx())
        all_files.update(self.export_all_music(music_duration))
        return all_files
