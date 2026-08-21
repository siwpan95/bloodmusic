# -*- coding: utf-8 -*-
"""
piano_roll.py —— 钢琴卷帘 + 编曲音序器可视化（PRD P2 GUI 收尾）

- 钢琴卷帘：把 MusicPattern 渲染为「时间(拍) × 音高(半音)」音符网格，
  点击格子可增删音符（点击切换，1 拍时长），并可将网格重建为 MusicPattern。
- 编曲音序器：把 SongArrangement 渲染为横向段落块（intro/verse/chorus…），
  块长 = 小节数，直观展示曲式结构。

matplotlib 为可选依赖：缺失时窗口降级为文本提示（与工作站一致）。
绘图与窗口分离：draw_* 为纯函数，可无 Tk 环境（Agg）直接测试。
"""

from __future__ import annotations

import re
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# matplotlib 可选
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    # 中文标题字体（Windows 常见 CJK 字体，缺失时回退默认）
    matplotlib.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "PingFang SC", "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False
    _HAS_MPL = True
except Exception:  # pragma: no cover - 环境依赖
    _HAS_MPL = False

_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 卷帘音高范围（C2..C7）
_ROLL_LOW = 36
_ROLL_HIGH = 96


def note_to_semitone(name: str) -> Optional[int]:
    """'C4' / 'C#4' / 'Gb3' → MIDI 半音号；无法解析返回 None。"""
    m = _NOTE_RE.match(name.strip())
    if not m:
        return None
    letter, acc, octave = m.group(1).upper(), m.group(2), int(m.group(3))
    semi = _BASE[letter] + (1 if acc == "#" else -1 if acc == "b" else 0)
    return (octave + 1) * 12 + semi


def semitone_to_note(midi: int) -> str:
    return f"{_SHARP_NAMES[midi % 12]}{midi // 12 - 1}"


def pattern_to_events(pattern) -> list[tuple]:
    """MusicPattern → [(start_beat, midi, dur_beats)]（休止符跳过）。"""
    events: list[tuple] = []
    t = 0.0
    for name, dur in zip(pattern.notes, pattern.durations):
        dur = float(dur)
        if name is not None:
            midi = note_to_semitone(str(name))
            if midi is not None:
                events.append((t, midi, dur))
        t += dur
    return events


def draw_piano_roll(ax, pattern, title: str = "") -> None:
    """在 ax 上绘制钢琴卷帘（纯函数，可 Agg 测试）。"""
    events = pattern_to_events(pattern)
    total = sum(float(d) for d in pattern.durations)
    total = max(total, 0.5)

    ax.clear()
    # 网格 + 黑键行底色
    for midi in range(_ROLL_LOW, _ROLL_HIGH + 1):
        if midi % 12 in (1, 3, 6, 8, 10):
            ax.axhspan(midi - 0.5, midi + 0.5, color="#22222e", zorder=1)
    for x in range(0, int(total) + 2):
        ax.axvline(x, color="#333", linewidth=0.4, zorder=2)
    for midi in range(_ROLL_LOW, _ROLL_HIGH + 1, 12):
        ax.axhline(midi, color="#555", linewidth=0.6, zorder=2)

    for start, midi, dur in events:
        if _ROLL_LOW <= midi <= _ROLL_HIGH:
            ax.add_patch(
                __import__("matplotlib").patches.Rectangle(
                    (start, midi - 0.5), max(dur, 0.1), 1.0,
                    facecolor="#e94560", edgecolor="#fff", linewidth=0.5, zorder=3,
                )
            )

    ax.set_xlim(0, max(int(total) + 1, 4))
    ax.set_ylim(_ROLL_LOW - 1, _ROLL_HIGH + 1)
    ax.set_yticks(range(_ROLL_LOW, _ROLL_HIGH + 1, 12))
    ax.set_yticklabels([semitone_to_note(m) for m in range(_ROLL_LOW, _ROLL_HIGH + 1, 12)])
    ax.set_xlabel("beat")
    ax.set_ylabel("pitch")
    ax.set_title(f"{title}（{len(events)} 音符）", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.grid(False)


def draw_arrangement(ax, arrangement, title: str = "") -> None:
    """在 ax 上绘制编曲段落块（纯函数，可 Agg 测试）。"""
    sections = getattr(arrangement, "sections", [])
    colors = ["#e94560", "#1a73e8", "#0f9d58", "#f9ab00", "#a142f4", "#00bcd4", "#ff7043", "#8d6e63"]
    ax.clear()
    x = 0.0
    for i, sec in enumerate(sections):
        bars = getattr(sec, "bars", 4)
        color = colors[i % len(colors)]
        ax.add_patch(
            __import__("matplotlib").patches.Rectangle(
                (x, 0), bars, 1.0, facecolor=color, alpha=0.75,
                edgecolor="#fff", linewidth=1.0,
            )
        )
        ax.text(x + bars / 2, 0.5, f"{sec.name}\n{bars}b", ha="center", va="center",
                fontsize=8, color="#111", fontweight="bold")
        x += bars
    ax.set_xlim(0, max(x, 4))
    ax.set_ylim(0, 1)
    ax.set_xlabel("bars")
    ax.set_yticks([])
    ax.set_title(f"{title}（{len(sections)} 段落 · {int(x)} 小节）", fontsize=10)
    ax.tick_params(labelsize=8)


class PianoRollWindow(tk.Toplevel):
    """钢琴卷帘 + 编曲音序器窗口（嵌入工作站）。"""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("🎼 钢琴卷帘 / 编曲音序器")
        self.geometry("760x560")
        self.configure(bg="#1a1a2e")
        self._pattern = None
        self._cells: dict = {}          # (beat, midi) -> dur
        self._arrangement = None

        if not _HAS_MPL:  # pragma: no cover
            ttk.Label(self, text="(matplotlib 未安装，卷帘/音序器不可用)").pack(padx=20, pady=20)
            return

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── 卷帘页 ──
        roll_tab = ttk.Frame(nb, padding=4)
        nb.add(roll_tab, text=" 钢琴卷帘 ")
        self._roll_fig = Figure(figsize=(9, 5.2), dpi=100, facecolor="#1a1a2e")
        self._roll_ax = self._roll_fig.add_subplot(111)
        self._roll_ax.set_facecolor("#16213e")
        self._roll_canvas = FigureCanvasTkAgg(self._roll_fig, master=roll_tab)
        self._roll_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._roll_canvas.mpl_connect("button_press_event", self._on_roll_click)
        bar = ttk.Frame(roll_tab)
        bar.pack(fill=tk.X, pady=4)
        ttk.Button(bar, text="💾 导出 MIDI", command=self._export_midi).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="🔊 播放", command=self._play_pattern).pack(side=tk.LEFT, padx=4)
        self._roll_info = ttk.Label(roll_tab, text="点击网格增删音符（1 拍）")
        self._roll_info.pack(anchor=tk.W, pady=2)

        # ── 音序器页 ──
        seq_tab = ttk.Frame(nb, padding=4)
        nb.add(seq_tab, text=" 编曲音序器 ")
        self._seq_fig = Figure(figsize=(9, 2.2), dpi=100, facecolor="#1a1a2e")
        self._seq_ax = self._seq_fig.add_subplot(111)
        self._seq_ax.set_facecolor("#16213e")
        self._seq_canvas = FigureCanvasTkAgg(self._seq_fig, master=seq_tab)
        self._seq_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ── 对外接口 ──

    def show_pattern(self, pattern) -> None:
        """显示（并载入为可编辑网格）一个 MusicPattern。"""
        self._pattern = pattern
        self._cells = {
            (int(round(start)), midi): max(dur, 0.1)
            for start, midi, dur in pattern_to_events(pattern)
            if _ROLL_LOW <= midi <= _ROLL_HIGH
        }
        self._redraw_roll()

    def show_arrangement(self, arrangement) -> None:
        """显示一个 SongArrangement 的段落结构。"""
        if not _HAS_MPL:
            return
        self._arrangement = arrangement
        draw_arrangement(self._seq_ax, arrangement, title="SongArrangement")
        self._seq_fig.tight_layout()
        self._seq_canvas.draw_idle()

    def get_pattern(self):
        """把当前网格重建为 MusicPattern（休止符补拍）。"""
        from ..music.pattern import MusicPattern
        cells = sorted(self._cells.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        notes: list = []
        durs: list = []
        t = 0.0
        for (beat, midi), dur in cells:
            gap = beat - t
            if gap > 1e-6:
                notes.append(None)
                durs.append(gap)
            notes.append(semitone_to_note(midi))
            durs.append(dur)
            t = beat + dur
        if not notes:
            notes.append(None)
            durs.append(4.0)
        return MusicPattern(
            name="卷帘编辑", notes=notes, durations=durs,
            bpm=getattr(self._pattern, "bpm", 120) if self._pattern is not None else 120,
        )

    # ── 交互 ──

    def _on_roll_click(self, event):
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        beat = int(round(event.xdata))
        midi = int(round(event.ydata))
        if not (_ROLL_LOW <= midi <= _ROLL_HIGH):
            return
        key = (beat, midi)
        if key in self._cells:
            del self._cells[key]
        else:
            self._cells[key] = 1.0
        self._roll_info.config(text=f"{(beat, semitone_to_note(midi))} "
                                     f"{'移除' if key not in self._cells else '添加'} · "
                                     f"共 {len(self._cells)} 音符")
        self._redraw_roll()

    def _redraw_roll(self) -> None:
        if not _HAS_MPL:
            return
        from ..music.pattern import MusicPattern
        tmp = MusicPattern(name="grid", notes=[], durations=[])
        # 直接按 cells 绘制（不用 pattern 事件）
        self._roll_ax.clear()
        self._roll_ax.set_facecolor("#16213e")
        for midi in range(_ROLL_LOW, _ROLL_HIGH + 1):
            if midi % 12 in (1, 3, 6, 8, 10):
                self._roll_ax.axhspan(midi - 0.5, midi + 0.5, color="#22222e", zorder=1)
        max_beat = max((b for b, _ in self._cells), default=8) + 2
        for x in range(0, max_beat + 1):
            self._roll_ax.axvline(x, color="#333", linewidth=0.4, zorder=2)
        for midi in range(_ROLL_LOW, _ROLL_HIGH + 1, 12):
            self._roll_ax.axhline(midi, color="#555", linewidth=0.6, zorder=2)
        for (beat, midi), dur in self._cells.items():
            self._roll_ax.add_patch(
                __import__("matplotlib").patches.Rectangle(
                    (beat, midi - 0.5), max(dur, 0.1), 1.0,
                    facecolor="#e94560", edgecolor="#fff", linewidth=0.5, zorder=3,
                )
            )
        self._roll_ax.set_xlim(0, max_beat)
        self._roll_ax.set_ylim(_ROLL_LOW - 1, _ROLL_HIGH + 1)
        self._roll_ax.set_yticks(range(_ROLL_LOW, _ROLL_HIGH + 1, 12))
        self._roll_ax.set_yticklabels([semitone_to_note(m) for m in range(_ROLL_LOW, _ROLL_HIGH + 1, 12)])
        self._roll_ax.set_xlabel("beat")
        self._roll_ax.set_ylabel("pitch")
        self._roll_ax.set_title(f"钢琴卷帘（点击增删 · {len(self._cells)} 音符）", fontsize=10)
        self._roll_ax.tick_params(labelsize=8)
        self._roll_fig.tight_layout()
        self._roll_canvas.draw_idle()

    def _export_midi(self) -> None:
        from ..music.midi_io import music_pattern_to_midi
        path = filedialog.asksaveasfilename(
            defaultextension=".mid", filetypes=[("MIDI", "*.mid")], title="导出 MIDI"
        )
        if not path:
            return
        music_pattern_to_midi(self.get_pattern(), path)
        messagebox.showinfo("导出完成", f"已导出: {path}")

    def _play_pattern(self) -> None:
        from ..music import generate_music_wav
        from ..playback import PreviewPlayer
        try:
            audio = generate_music_wav(self.get_pattern())
            player = getattr(self, "_player", None) or PreviewPlayer()
            self._player = player
            player.play(audio)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("播放失败", str(exc))
