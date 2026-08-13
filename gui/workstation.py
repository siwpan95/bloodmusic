"""
GUI 工作站界面 (Tkinter) — 预览 / 导出 / 参数调节 / 波形可视化

依赖: tkinter (Python 标准库)；matplotlib 可选（缺失时波形面板降级为文本）
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import numpy as np

from ..playback import PreviewPlayer
from ..export import AudioBatchExporter
from ..sfx.presets import (
    UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
    GAME_FX_PRESETS,
)
from ..music.presets import ALL_MUSIC_PATTERNS
from ..core import synthesize_voice, FMSynthVoice, synthesize_fm_voice
from ..music import generate_music_wav, render_multi_track, MultiTrackPattern, DrumPattern

# matplotlib 为可选依赖 — 缺失时波形面板显示文本信息而非图
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _HAS_MPL = True
except Exception:  # pragma: no cover - 环境依赖
    _HAS_MPL = False


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
        # ── 实时参数滑块状态 ──
        self._sliders: dict = {}          # 参数名 → {"var": DoubleVar, "widget": Scale}
        self._param_syncing = False        # 同步滑块值时不触发回调
        self._live_voice = None            # 当前可实时调节的 voice 副本
        self._live_name = ""               # 当前 voice 名称
        self._last_live_play = 0.0         # 上次实时播放时间（节流）
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
        tk.Button(toolbar, text="🎛 制作工作室", bg=self.SUCCESS_COLOR, fg=self.FG_COLOR,
                  command=self._open_maker).pack(side=tk.RIGHT, padx=4)

        # 主区域
        main = ttk.Frame(self.root, padding=4)
        main.pack(fill=tk.BOTH, expand=True)

        # 左侧: 预设列表
        left = ttk.Frame(main, padding=(4, 0))
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sfx_list(left)
        self._build_music_list(left)

        # 右侧: 预览 / 信息 / 波形
        right = ttk.Frame(main, width=300)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 0))
        right.pack_propagate(False)

        tk.Button(right, text="▶ 预览选中", bg=self.ACCENT_COLOR, fg=self.FG_COLOR,
                  font=("Arial", 11, "bold"), height=2,
                  command=self._preview_selected).pack(fill=tk.X, pady=4)
        tk.Button(right, text="⏹ 停止", bg="#555", fg=self.FG_COLOR,
                  font=("Arial", 10), command=self.player.stop).pack(fill=tk.X, pady=2)

        self._info_label = tk.Label(right, text="选择预设后点击预览", bg=self.BG_COLOR,
                                     fg=self.FG_COLOR, wraplength=280, justify=tk.LEFT)
        self._info_label.pack(pady=10)

        # ── 波形可视化面板（matplotlib 可选） ──
        self._wave_label = tk.Label(right, text="波形", bg=self.BG_COLOR,
                                     fg=self.ACCENT_COLOR, font=("Arial", 9, "bold"),
                                     anchor=tk.W)
        self._wave_label.pack(fill=tk.X, padx=4)
        self._canvas = None
        self._wave_text = None
        if _HAS_MPL:
            self._fig = Figure(figsize=(3.2, 2.0), dpi=90, facecolor=self.BG_COLOR)
            self._ax = self._fig.add_subplot(111)
            self._ax.set_facecolor(self.PANEL_COLOR)
            self._canvas = FigureCanvasTkAgg(self._fig, master=right)
            self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        else:  # pragma: no cover - 无 matplotlib 环境降级
            self._wave_text = tk.Label(right, text="(matplotlib 未安装，波形面板不可用)",
                                        bg=self.BG_COLOR, fg="#888", font=("Arial", 8))
            self._wave_text.pack(fill=tk.X, padx=4)

        # ── 实时参数滑块（选中 SFX 后可用） ──
        self._build_param_sliders(right)

        # 底部状态栏
        self._status = tk.Label(self.root, text="就绪", bg=self.PANEL_COLOR,
                                 fg="#888", anchor=tk.W, padx=8)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

    #: 实时参数滑块规格: (参数名, 显示名, 最小值, 最大值)
    _PARAM_SPECS = [
        ("freq", "频率 Hz", 80.0, 2400.0),
        ("duration", "时长 s", 0.02, 1.0),
        ("volume", "音量", 0.05, 1.0),
        ("pitch_mod", "音高偏移", -24.0, 24.0),
        ("distortion", "失真", 0.0, 1.0),      # effect_chain 字段
        ("reverb_mix", "混响", 0.0, 0.8),       # effect_chain 字段
    ]

    def _build_param_sliders(self, parent):
        """右侧面板的实时参数滑块区（选中 SFX 后可拖）。"""
        tk.Label(parent, text="参数（拖动实时试听）", bg=self.BG_COLOR,
                 fg=self.ACCENT_COLOR, font=("Arial", 9, "bold"),
                 anchor=tk.W).pack(fill=tk.X, padx=4, pady=(6, 0))

        for param, label, lo, hi in self._PARAM_SPECS:
            row = tk.Frame(parent, bg=self.BG_COLOR)
            row.pack(fill=tk.X, padx=4, pady=0)
            tk.Label(row, text=label, bg=self.BG_COLOR, fg=self.FG_COLOR,
                     font=("Arial", 8), width=8, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.DoubleVar(value=0.0)
            scale = tk.Scale(
                row, from_=lo, to=hi, resolution=(hi - lo) / 200.0,
                orient=tk.HORIZONTAL, variable=var,
                bg=self.PANEL_COLOR, fg=self.FG_COLOR, highlightthickness=0,
                troughcolor=self.BG_COLOR, activebackground=self.ACCENT_COLOR,
                font=("Arial", 7), length=180,
                command=lambda v, p=param: self._on_slider_change(p, v),
            )
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._sliders[param] = {"var": var, "widget": scale}

    def _sync_sliders_to_voice(self):
        """把滑块值同步为当前 voice 的字段值（不触发回调）。"""
        if self._live_voice is None:
            return
        self._param_syncing = True
        try:
            chain = self._live_voice.effect_chain
            for param, _label, _lo, _hi in self._PARAM_SPECS:
                if param in ("distortion", "reverb_mix"):
                    value = getattr(chain, param, 0.0) if chain is not None else 0.0
                else:
                    value = getattr(self._live_voice, param, 0.0)
                if param in self._sliders:
                    self._sliders[param]["var"].set(float(value or 0.0))
        finally:
            self._param_syncing = False

    def _on_slider_change(self, param: str, raw_value):
        """滑块拖动回调 — 节流 200ms 重合成 + 播放。"""
        if self._param_syncing or self._live_voice is None:
            return
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return

        # 写入 voice 副本（distortion/reverb_mix 属于 effect_chain）
        if param in ("distortion", "reverb_mix"):
            if self._live_voice.effect_chain is None:
                from ..effects.chain import EffectChain
                self._live_voice.effect_chain = EffectChain()
            setattr(self._live_voice.effect_chain, param, value)
        else:
            setattr(self._live_voice, param, value)

        # 节流：200ms 内只更新波形，不重复播放
        now = __import__("time").time()
        if now - self._last_live_play >= 0.2:
            self._apply_live_voice()
        else:
            self._update_waveform(synthesize_voice(self._live_voice),
                                  title=self._live_name)

    def _apply_live_voice(self):
        """用当前参数重合成 → 播放 + 波形。"""
        import time
        if self._live_voice is None:
            return
        audio = synthesize_voice(self._live_voice)
        self._update_waveform(audio, title=self._live_name)
        self.player.play(audio)
        self._last_live_play = time.time()
        self._status.config(text=f"▶ 实时调节: {self._live_name}")

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
            ("Game", GAME_FX_PRESETS),
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
            # 复制为可实时调节的 voice（不污染预设）
            import copy as _copy
            self._live_voice = _copy.deepcopy(voice)
            self._live_name = name
            self._sync_sliders_to_voice()
            self._info_label.config(text=f"SFX: {category}/{name}\n"
                                         f"频率: {voice.freq:.0f}Hz | "
                                         f"时长: {voice.duration:.2f}s | "
                                         f"波形: {voice.osc_type.value}")
            # 选中即合成并绘制波形（SFX 时长短，合成开销可忽略）
            try:
                self._update_waveform(synthesize_voice(voice), title=name)
            except Exception:
                pass  # 波形失败不影响选择

    def _update_waveform(self, audio, title: str = ""):
        """在右侧面板绘制波形（时域 + 包络轮廓）。"""
        if not _HAS_MPL or self._ax is None:
            return
        audio = np.asarray(audio, dtype=np.float64)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if audio.size == 0:
            return

        t = np.arange(audio.size) / 44100.0
        envelope = np.abs(audio)

        self._ax.clear()
        self._ax.plot(t, audio, color="#e94560", linewidth=0.5, label="waveform")
        self._ax.plot(t, envelope, color="#1a73e8", linewidth=1.0, alpha=0.8,
                      label="envelope")
        self._ax.set_facecolor(self.PANEL_COLOR)
        self._ax.set_title(title or "waveform", color=self.FG_COLOR, fontsize=8)
        self._ax.tick_params(colors="#888", labelsize=7)
        for spine in self._ax.spines.values():
            spine.set_color("#555")
        self._ax.set_xlabel("time (s)", color="#888", fontsize=7)
        self._ax.set_ylim(-1.05, 1.05)
        self._fig.tight_layout()
        if self._canvas is not None:
            self._canvas.draw_idle()

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

    def _open_maker(self):
        """打开制作工作室（单曲/专辑/Beats 统一界面）。"""
        try:
            from .maker_gui import MakerGUI
            MakerGUI(master=self.root)  # 以 Toplevel 子窗口打开
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("打开失败", f"制作工作室启动失败:\n{e}")

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
