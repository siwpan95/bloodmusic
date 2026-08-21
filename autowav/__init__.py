"""AutoWav — 纯标准库算法作曲 + 共振峰人声合成（自 wav_music_gen 并入，2026-08）

机生成翼的核心作曲引擎：
  - 14 调式 / 13 和弦进行 / 加权马尔可夫旋律 / motif 变奏 / 对位 / 曲式（ABA/AABA/ABAC）
  - 6 种合成音色 + ADSR + 混响/压缩/低通滤波 + 鼓机 + 琶音 + 低音轨（全部零依赖）
  - vocal_formant: Klatt 共振峰人声（8 元音吟唱/哼鸣），pinyin_to_vowel 拼音韵母映射
  - MIDI 导入/导出桥（midi_io），后端抽象（symbolic 默认 / acestep 可选懒加载）

用法：
    python -m bloodmusic.autowav --random --duration 60     # 完整 CLI（同原 autowav.py）
    python -m bloodmusic.autowav.gui                        # Tkinter GUI
    from bloodmusic.autowav import generate_music           # 编程接口

注意：本包保留了原项目的扁平模块导入约定（autowav/theory/synthesis/...），
      包初始化时会把本目录加入 sys.path，保证原脚本与模块名不变。
"""

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

# 主编排模块（导入即触发可选后端注册，无第三方依赖时安全）
from autowav import (  # noqa: E402
    generate_music,
    generate_music_by_duration,
    mix_tracks,
    samples_to_wav,
    render_chord_track,
    compress_wav_file,
    save_gzip_wav,
    OUTPUT_DIR,
)

from theory import (  # noqa: E402
    NOTE_NAMES,
    SCALES,
    CHORD_PROGRESSIONS,
    note_freq,
    build_scale_notes,
)

from vocal_formant import (  # noqa: E402
    pinyin_to_vowel,
    vocal_note,
    sing,
)

__all__ = [
    "generate_music",
    "generate_music_by_duration",
    "mix_tracks",
    "samples_to_wav",
    "render_chord_track",
    "compress_wav_file",
    "save_gzip_wav",
    "OUTPUT_DIR",
    "NOTE_NAMES",
    "SCALES",
    "CHORD_PROGRESSIONS",
    "note_freq",
    "build_scale_notes",
    "pinyin_to_vowel",
    "vocal_note",
    "sing",
]
