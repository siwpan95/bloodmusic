# -*- coding: utf-8 -*-
"""
conftest.py —— pytest fixtures（合成小样本、临时工作区）

合成策略（零外部采样 / 零联网）：
  - 用标准库 wave 生成几秒正弦 .wav 作为合成音源输入
  - 所有 fixture 基于 tmp_path，测试结束自动清理

注意：本文件仅定义数据桩，不做全局 import。
"""

from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

import pytest

# 确保 test 进程能 import 扁平米模块（cli.py 同级目录）
_HERE = Path(__file__).resolve().parent
_PROJ_ROOT = _HERE.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))


# ═══════════════════════ 工具函数 ═══════════════════════


def make_sine_wav(
    path: Path,
    duration_sec: float = 1.0,
    sr: int = 44100,
    freq: float = 440.0,
    amplitude: float = 0.5,
    channels: int = 1,
) -> Path:
    """生成正弦波 16-bit PCM WAV 文件。

    Args:
        path: 输出路径。
        duration_sec: 时长（秒）。
        sr: 采样率。
        freq: 频率（Hz）。
        amplitude: 幅度 0.0-1.0。
        channels: 声道数。

    Returns:
        实际写入路径。
    """
    n_samples = int(duration_sec * sr)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit signed
        wf.setframerate(sr)
        for i in range(n_samples):
            val = int(32767 * amplitude * math.sin(2 * math.pi * freq * i / sr))
            wf.writeframes(struct.pack("<h", val))
    return path


# ═══════════════════════ fixtures ═══════════════════════


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """临时工作区（含 stems/mixdown 子目录）。"""
    ws = tmp_path / "audio_pipeline_workspace"
    for d in ("stems", "mixdown", "mixdown/_sources"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def synthetic_midi(tmp_path: Path) -> Path:
    """生成一段最小 MIDI（C4-E4-G4 八分音符，供 bridge 测试）。

    注意：需要 mido 已安装（bloodmusic 依赖它）。
    """
    try:
        import mido
    except ImportError:  # pragma: no cover
        pytest.skip("mido 未安装，跳过 MIDI 导入测试")

    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120)))
    notes = [60, 64, 67, 72]  # C4, E4, G4, C5
    tick = 0
    step = 480  # quarter note
    for note in notes:
        track.append(mido.Message("note_on", note=note, velocity=80, time=tick))
        track.append(mido.Message("note_off", note=note, velocity=0, time=step))
        tick = 0
    out = tmp_path / "demo.mid"
    mid.save(str(out))
    return out


# ═══════════════════════ 全局环境引导 ═══════════════════════

# 在 pytest 收集阶段即调用 bootstrap_env，确保所有后续模块 import
# 时 remix PATH 已注入、pydub 已 pin、bloodmusic 已验证。
# 幂等调用，多次执行安全。

from config import bootstrap_env
bootstrap_env()


def pytest_configure(config: pytest.Config) -> None:
    """注册自定义标记。"""
    config.addinivalue_line(
        "markers", "slow: 需要较长运行时间，默认跳过"
    )
