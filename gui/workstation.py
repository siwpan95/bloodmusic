"""
GUI 工作站界面 (Tkinter) — 预览 / 导出 / 参数调节

依赖: tkinter (Python 标准库)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from ..playback import PreviewPlayer
from ..export import AudioBatchExporter
from ..sfx.presets import UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
from ..music.presets import ALL_MUSIC_PATTERNS
from ..core import synthesize_voice, FMSynthVoice, synthesize_fm_voice
from ..music import generate_music_wav, render_multi_track, MultiTrackPattern, DrumPattern


class GameAudioWorkstationGUI:
    """游戏音频工作站 — 预览 + 批量导出"""

    BG_COLOR = "#1a1a2e"
    FG_COLOR = "#eee"
    ACCENT_COLOR = "#e94560"
    PANEL_COLOR = "#16213e"
    SUCCESS_COLOR = "#0f9d58"

    def __init__(self, root: tk.Tk, output_dir: str | None = None):
        self.root = root
        self.root.title("🎧 BloodMusic 音频工作站 v2.0")
        self.root.geometry("920x680")
        self.root.configure(bg=self.BG_COLOR)
        self.root.minsize(800, 550)

        self.player = PreviewPlayer()
        self.exporter: Optional[AudioBatchExporter] = None
        self.output_dir = tk.StringVar(value=output_dir or "./audio_output")
        self.format_var = tk.StringVar(value="wav")
        self.selected_preset: Optional[tuple] = None
        self._build_ui()

    # ═══════ UI 构建 ═══════

    def _build_ui(self):
        # 顶部工具栏
        toolbar = ttk.Frame(self.root, padding=(8, 4))
        toolbar.pack(fill=tk.X)

        tk.Label(toolbar, text="📁 输出:", bg=self.BG_COLOR,
                 fg=self.FG_COLOR, font=("Arial", 9)).pack(side=tk.LEFT)
        tk.Entry(toolbar, textvariable=self.output_dir, width=45,
                 bg=self.PANEL_COLOR, fg=self.FG_COLOR,
                 insertbackground=self.FG_COLOR).pack(side=tk.LEFT, padx=4)

        # 格式选择
        format_frame = tk.Frame(toolbar, bg=self.BG_COLOR)
        format_frame.pack(side=tk.LEFT, padx=8)
        tk.Label(format_frame, text="格式:", bg=self.BG_COLOR, fg=self.FG_COLOR,
                 font=("Arial", 9)).pack(side=tk.LEFT)
        for fmt in ["wav", "ogg", "flac"]:
            tk.Radiobutton(format_frame, text=fmt.upper(), variable=self.format_var,
                          value=fmt, bg=self.BG_COLOR, fg=self.FG_COLOR,
                          selectcolor=self.PANEL_COLOR).pack(side=tk.LEFT)

        tk.Button(toolbar, text="🔊 全部导出", bg=self.SUCCESS_COLOR, fg=self.FG_COLOR,
                  command=self._export_all).pack(side=tk.RIGHT, padx=4)
        tk.Button(toolbar, text="🎵 导出音乐", bg="#1a73e8", fg=self.FG_COLOR,
                  command=self._export_music).pack(side=tk.RIGHT, padx=2)
        tk.Button(toolbar, text="🔊 导出 SFX", bg="#1a73e8", fg=self.FG_COLOR,
                  command=self._export_sfx).pack(side=tk.RIGHT, padx=2)

        # 主区域
        main = ttk.Frame(self.root, padding=4)
        main.pack(fill=tk.BOTH, expand=True)

        # 左侧: 预设列表
        left = ttk.Frame(main, padding=(4, 0))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sfx_list(left)
        self._build_music_list(left)

        # 右侧: 预览 / 信息
        right = ttk.Frame(main, width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        right.pack_propagate(False)

        tk.Button(right, text="▶ 预览选中", bg=self.ACCENT_COLOR, fg=self.FG_COLOR,
                  font=("Arial", 11, "bold"), height=2,
                  command=self._preview_selected).pack(fill=tk.X, pady=4)
        tk.Button(right, text="⏹ 停止", bg="#555", fg=self.FG_COLOR,
                  font=("Arial", 10), command=self.player.stop).pack(fill=tk.X, pady=2)

        self._info_label = tk.Label(right, text="选择预设后点击预览", bg=self.BG_COLOR,
                                     fg=self.FG_COLOR, wraplength=260, justify=tk.LEFT)
        self._info_label.pack(pady=10)

        # 底部状态栏
        self._status = tk.Label(self.root, text="就绪", bg=self.PANEL_COLOR,
                                 fg="#888", anchor=tk.W, padx=8)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_sfx_list(self, parent):
        tk.Label(parent, text="🔊 SFX 音效预设", bg=self.BG_COLOR,
                 fg=self.ACCENT_COLOR, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(4, 2))

        sfx_frame = ttk.Frame(parent)
        sfx_frame.pack(fill=tk.BOTH, expand=True)

        sfx_cats = [
            ("UI", UI_FX_PRESETS),
            ("Card", CARD_FX_PRESETS),
            ("Combat", COMBAT_FX_PRESETS),
            ("System", SYSTEM_FX_PRESETS),
        ]

        for cat_name, presets in sfx_cats:
            f = tk.LabelFrame(sfx_frame, text=f" {cat_name} ({len(presets)})",
                              bg=self.BG_COLOR, fg=self.FG_COLOR, font=("Arial", 8))
            f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)

            lb = tk.Listbox(f, height=10, bg=self.PANEL_COLOR, fg=self.FG_COLOR,
                            selectbackground=self.ACCENT_COLOR, font=("Consolas", 8))
            lb.pack(fill=tk.BOTH, expand=True)

            for name in presets:
                lb.insert(tk.END, name)

            lb.bind("<<ListboxSelect>>",
                    lambda e, c=cat_name, p=presets: self._on_select_sfx(c, p, e))

    def _build_music_list(self, parent):
        tk.Label(parent, text="🎵 Music 音乐预设", bg=self.BG_COLOR,
                 fg=self.ACCENT_COLOR, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))

        lb = tk.Listbox(parent, height=8, bg=self.PANEL_COLOR, fg=self.FG_COLOR,
                        selectbackground=self.ACCENT_COLOR, font=("Consolas", 9))
        lb.pack(fill=tk.X)

        for name in ALL_MUSIC_PATTERNS:
            lb.insert(tk.END, name)

        lb.bind("<<ListboxSelect>>", self._on_select_music)

    # ═══════ 事件处理 ═══════

    def _on_select_sfx(self, category, presets, event):
        lb = event.widget
        sel = lb.curselection()
        if sel:
            name = list(presets.keys())[sel[0]]
            voice = presets[name]
            self.selected_preset = (category, name, voice)
            self._info_label.config(text=f"SFX: {category}/{name}\n"
                                         f"频率: {voice.freq:.0f}Hz | "
                                         f"时长: {voice.duration:.2f}s | "
                                         f"波形: {voice.osc_type.value}")

    def _on_select_music(self, event):
        lb = event.widget
        sel = lb.curselection()
        if sel:
            name = list(ALL_MUSIC_PATTERNS.keys())[sel[0]]
            pattern = ALL_MUSIC_PATTERNS[name]
            self.selected_preset = ("music", name, pattern)
            self._info_label.config(text=f"Music: {name}\n"
                                         f"BPM: {pattern.bpm} | "
                                         f"循环: {'是' if pattern.loop else '否'}")

    def _preview_selected(self):
        if not self.selected_preset:
            messagebox.showinfo("提示", "请先在左侧选择一个预设")
            return

        cat, name, data = self.selected_preset
        import numpy as np

        if cat == "music":
            import tempfile, os
            tmp = os.path.join(tempfile.gettempdir(), "_bloodmusic_preview.wav")
            generate_music_wav(data, tmp, duration_sec=8.0)
            from scipy.io import wavfile
            _, audio = wavfile.read(tmp)
            audio = audio.astype(np.float32) / 32767.0
        else:
            audio = synthesize_voice(data)

        self.player.play(audio)
        self._status.config(text=f"▶ 播放中: {name}")

    def _export_sfx(self):
        ex = AudioBatchExporter(self.output_dir.get(), format=self.format_var.get())
        ex.export_all_sfx()
        self._status.config(text=f"✅ SFX 导出完成 ({self.format_var.get().upper()}) → {self.output_dir.get()}/sfx/")

    def _export_music(self):
        ex = AudioBatchExporter(self.output_dir.get(), format=self.format_var.get())
        ex.export_all_music()
        self._status.config(text=f"✅ 音乐导出完成 ({self.format_var.get().upper()}) → {self.output_dir.get()}/music/")

    def _export_all(self):
        ex = AudioBatchExporter(self.output_dir.get(), format=self.format_var.get())
        ex.export_everything()
        self._status.config(text=f"✅ 全部导出完成 ({self.format_var.get().upper()}) → {self.output_dir.get()}")
