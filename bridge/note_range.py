"""
bridge/note_range.py —— 音高守卫层（F10）

命中需求: 全局（P0-3 / P0-4 / P1-2 均依赖）
关联发现: **F10** —— `core/note_utils.py::NOTES` 仅覆盖 C0(12)–C7(96)，
          `note_to_freq()` 查不到时**静默 return 440.0**（不抛错、不告警），
          是隐蔽的音高事故。

关键不对称（决定和弦与旋律走不同分支）:
    - 旋律轨：`render_pattern_to_array` 用 `note_to_freq(note) * 2 ** octave_shift`
      → 超界音可用 octave_shift 表达，音高**完全无损**；
    - 和弦音：`music/pattern.py` 的和弦分支只调 `note_to_freq(cn)`，
      **不施加 octave_shift** → 超界音只能折叠进范围，并记 warn 级 issue。

约束: L2 领域层，纯函数，无 IO、无 mido。
"""

from __future__ import annotations

from ..core.note_utils import NOTES

__all__ = [
    "MIN_SUPPORTED_MIDI",
    "MAX_SUPPORTED_MIDI",
    "MIDI_MIN",
    "MIDI_MAX",
    "SHARP_NAMES",
    "midi_to_note_name",
    "note_name_to_midi",
    "is_renderable",
    "safe_note_and_shift",
    "fold_into_range",
]

#: NOTES 表下界 = C0（MIDI 12）
MIN_SUPPORTED_MIDI: int = 12
#: NOTES 表上界 = C7（MIDI 96）；C#7 起表中已无
MAX_SUPPORTED_MIDI: int = 96
#: MIDI 协议合法音高域
MIDI_MIN: int = 0
MIDI_MAX: int = 127

#: 使用升号拼写（NOTES 表同时收录了 # 与 b，统一取 # 侧）
SHARP_NAMES: tuple[str, ...] = (
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
)

#: 音名 → 半音序号（解析用，兼容 # 与 b 两种拼写）
_PITCH_CLASS: dict[str, int] = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4,
    "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9,
    "A#": 10, "BB": 10, "B": 11,
}


def midi_to_note_name(midi_note: int) -> str:
    """MIDI 音符号 → 音符名（纯算术，不校验是否在 NOTES 表内）。

    Args:
        midi_note: MIDI 音符号，如 60。

    Returns:
        音符名，如 "C4"（60 → C4，遵循 Yamaha/GM 惯例 C4 = 60）。
    """
    value = int(midi_note)
    octave = value // 12 - 1
    return f"{SHARP_NAMES[value % 12]}{octave}"


def note_name_to_midi(note_name: str) -> int:
    """音符名 → MIDI 音符号（`midi_to_note_name` 的逆运算）。

    Args:
        note_name: 音符名，如 "C4" / "F#3" / "Bb5" / "Eb_4"。

    Returns:
        MIDI 音符号；无法解析时返回 60（C4）作为保守兜底。
    """
    if not note_name:
        return 60
    text = str(note_name).replace("_", "").strip()
    if not text:
        return 60

    # 分离音名部分与八度部分（八度可能带负号，如 C-1）
    idx = 1
    if len(text) > 1 and text[1] in ("#", "b", "B"):
        idx = 2
    head = text[:idx].upper()
    tail = text[idx:]

    pitch = _PITCH_CLASS.get(head)
    if pitch is None:
        return 60
    try:
        octave = int(tail)
    except ValueError:
        octave = 4
    return (octave + 1) * 12 + pitch


def is_renderable(note_name: str | None) -> bool:
    """音符名是否存在于 `core.note_utils.NOTES`。

    这是「是否会被静默降级到 440Hz」的唯一判据（F10）。

    Args:
        note_name: 音符名；None（休止符）视为可渲染。

    Returns:
        True 表示 `note_to_freq()` 能查到真实频率。
    """
    if note_name is None:
        return True
    return str(note_name).replace("_", "") in NOTES


def _fold_midi(midi_note: int) -> tuple[int, int]:
    """把 MIDI 音高按八度平移进 [MIN_SUPPORTED_MIDI, MAX_SUPPORTED_MIDI]。

    Args:
        midi_note: 原始 MIDI 音符号。

    Returns:
        (折叠后的音符号, 平移的八度数)；满足
        `原始频率 == freq(折叠后) * 2 ** 平移八度数`。
    """
    value = max(MIDI_MIN, min(MIDI_MAX, int(midi_note)))
    shift = 0
    while value < MIN_SUPPORTED_MIDI:
        value += 12
        shift -= 1
    while value > MAX_SUPPORTED_MIDI:
        value -= 12
        shift += 1
    return value, shift


def safe_note_and_shift(midi_note: int) -> tuple[str, int]:
    """用于**旋律轨**的安全转换：超界音高转成 octave_shift，音高无损。

    渲染器计算 `note_to_freq(name) * 2 ** shift`，因此返回值组合起来
    与原始 MIDI 音高**完全等价**。

    Args:
        midi_note: 原始 MIDI 音符号。

    Returns:
        (可渲染音名, octave_shift)。shift != 0 时调用方应记
        `BridgeIssue('warn', 'PITCH_OUT_OF_RANGE')`。
    """
    folded, shift = _fold_midi(midi_note)
    return midi_to_note_name(folded), shift


def fold_into_range(midi_note: int) -> tuple[str, int]:
    """用于**和弦音**的安全转换：只能折叠，音高会被改变。

    因 `music/pattern.py` 的和弦分支不施加 octave_shift（F10），
    超界的和弦音若原样传入会被 `note_to_freq()` 静默变成 440Hz。

    Args:
        midi_note: 原始 MIDI 音符号。

    Returns:
        (可渲染音名, 被折叠的八度数)。folded != 0 时调用方**必须**记
        `BridgeIssue('warn', 'CHORD_PITCH_FOLDED')`。
    """
    folded, shift = _fold_midi(midi_note)
    return midi_to_note_name(folded), shift
