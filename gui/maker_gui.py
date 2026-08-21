"""制作工作室 GUI — 单曲 / 专辑 / Beats 三模式统一界面。

独立运行:
    python gui/maker_gui.py

嵌入现有工作站:
    from bloodmusic.gui.maker_gui import MakerGUI
    MakerGUI(parent_window)   # 以 Toplevel 子窗口打开

四页签:
    单曲 — QuickMaker 12 风格（或随机），BPM/小节/种子可调，生成后可试听
    专辑 — Demo 专辑或自定义 YAML，后台生成 + 进度，完成后可查看报告
    Beats — 7 种 beat 风格（trap/boom bap/lofi/battle/drum only/edm/ambient）
    镜像 — mirror 机生成混音（65 风格/曲式/24 混音师，镜像 musickit 采样混音）

生成任务在后台线程执行（避免 GUI 冻结），经 queue 回传主线程更新界面。
"""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Callable, Optional

import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from bloodmusic.album_maker.quick import QuickMaker
from bloodmusic.album_maker.style_db import STYLE_DB
from bloodmusic.album_maker.album import AlbumMaker
from bloodmusic.album_maker.config import AlbumConfig
from bloodmusic.album_maker.demo_config import make_demo_config
from bloodmusic.core.constants import SR

# 镜像层（机生成混音，musickit 采样混音的镜像）
from bloodmusic.mirror import STYLE_SLUGS, list_structures, list_mixers, run_remix

# beats 工具（skill/make_beats.py，动态加载避免顶层依赖）
_BEATS_PATH = _PROJECT_ROOT / "skill" / "make_beats.py"
_BEAT_STYLES: dict = {}
_HAS_BEATS = False
try:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_make_beats", _BEATS_PATH)
    _beats_mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_beats_mod)
    _BEAT_STYLES = {
        "Trap": _beats_mod.make_trap_beat,
        "Boom Bap": _beats_mod.make_boom_bap_beat,
        "Lo-Fi": _beats_mod.make_lofi_beat,
        "Battle": _beats_mod.make_battle_beat,
        "Drum Only": _beats_mod.make_drum_only_beat,
        "EDM": _beats_mod.make_edm_beat,
        "Ambient": _beats_mod.make_ambient_beat,
    }
    _BEATS_OUTPUT_DIR = str(_beats_mod.OUTPUT_DIR)
    _HAS_BEATS = True
except Exception:  # pragma: no cover - beats 模块缺失时降级
    _BEATS_OUTPUT_DIR = ""
    _HAS_BEATS = False


# ═══════════════════════════════════════════════════════════════════
# 主窗口
# ═══════════════════════════════════════════════════════════════════

class MakerGUI:
    """制作工作室 — 单曲 / 专辑 / Beats 统一图形界面。"""

    BG = "#1a1a2e"
    FG = "#eee"
    ACCENT = "#e94560"
    PANEL = "#16213e"
    SUCCESS = "#0f9d58"

    def __init__(self, master: Optional[tk.Misc] = None):
        self._owns_root = master is None
        self.root = master if master is not None else tk.Tk()
        self.root.title("🎧 BloodMusic 制作工作室")
        self.root.geometry("780x600")
        self.root.minsize(680, 480)
        if self._owns_root:
            self.root.configure(bg=self.BG)

        self._queue: queue.Queue = queue.Queue()
        self._busy = False
        self._last_result = None          # 最近生成结果（wav 路径或 dict）
        self._last_audio_path = None      # 最近可试听的 WAV 路径

        self._build_ui()
        self._poll_queue()

    # ── UI 构建 ───────────────────────────────────────────────

    def _build_ui(self):
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._tab_single()
        self._tab_album()
        self._tab_beats()
        self._tab_mirror()

        # 底部状态栏
        self._status = tk.Label(self.root, text="就绪", bg=self.PANEL,
                                fg="#888", anchor=tk.W, padx=8)
        self._status.pack(side=tk.BOTTOM, fill=tk.X)

    # ── 页签 1: 单曲 ─────────────────────────────────────────

    def _tab_single(self):
        frame = ttk.Frame(self._notebook, padding=12)
        self._notebook.add(frame, text=" 单曲 ")

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="风格:").pack(side=tk.LEFT)
        self.single_style_var = tk.StringVar(value="(随机)")
        cb = ttk.Combobox(row1, textvariable=self.single_style_var,
                          values=["(随机)"] + list(STYLE_DB.keys()),
                          state="readonly", width=18)
        cb.pack(side=tk.LEFT, padx=6)

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=4)
        self.single_bpm_var = self._var_int()
        self.single_bars_var = self._var_int()
        self.single_seed_var = self._var_int()
        self._single_field(row2, "BPM", self.single_bpm_var)
        self._single_field(row2, "小节", self.single_bars_var)
        self._single_field(row2, "种子", self.single_seed_var)

        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=4)
        ttk.Label(row3, text="输出:").pack(side=tk.LEFT)
        self.single_out_var = tk.StringVar(value=str(
            _PROJECT_ROOT / "album_maker_quick"))
        ttk.Entry(row3, textvariable=self.single_out_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(row3, text="浏览…",
                   command=lambda: self._browse_dir(self.single_out_var)
                   ).pack(side=tk.LEFT)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=8)
        self.single_btn = ttk.Button(btn_row, text="🎵 生成单曲",
                                     command=self._generate_single)
        self.single_btn.pack(side=tk.LEFT)
        self.single_play_btn = ttk.Button(btn_row, text="▶ 试听",
                                          command=self._on_play_last,
                                          state=tk.DISABLED)
        self.single_play_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="📁 打开目录",
                   command=lambda: self._open_dir(self.single_out_var.get())
                   ).pack(side=tk.LEFT)

        self.single_result = tk.Label(frame, text="选择风格后点击生成",
                                      bg=self.BG, fg=self.FG, justify=tk.LEFT,
                                      anchor=tk.W, wraplength=700)
        self.single_result.pack(fill=tk.X, pady=6)

    def _single_field(self, parent, label, var):
        ttk.Label(parent, text=label + ":").pack(side=tk.LEFT, padx=(0, 2))
        ttk.Entry(parent, textvariable=var, width=8).pack(side=tk.LEFT, padx=(0, 14))

    @staticmethod
    def _var_int():
        v = tk.StringVar(value="")
        return v

    @staticmethod
    def _parse_opt_int(var) -> Optional[int]:
        """解析可选整数输入。空 → None；非整数 → ValueError（纯函数，可测）。"""
        text = var.get().strip()
        if not text:
            return None
        return int(text)

    # ── 页签 2: 专辑 ─────────────────────────────────────────

    def _tab_album(self):
        frame = ttk.Frame(self._notebook, padding=12)
        self._notebook.add(frame, text=" 专辑 ")

        self.album_mode_var = tk.StringVar(value="demo")
        ttk.Radiobutton(frame, text="Demo 专辑（3 首内置曲目）",
                        variable=self.album_mode_var, value="demo",
                        command=self._on_album_mode_change
                        ).pack(anchor=tk.W)
        ttk.Radiobutton(frame, text="自定义 YAML 专辑配置",
                        variable=self.album_mode_var, value="yaml",
                        command=self._on_album_mode_change
                        ).pack(anchor=tk.W, pady=(2, 4))

        yaml_row = ttk.Frame(frame)
        yaml_row.pack(fill=tk.X, pady=4)
        ttk.Label(yaml_row, text="YAML:").pack(side=tk.LEFT)
        self.album_yaml_var = tk.StringVar(value="")
        self.yaml_entry = ttk.Entry(yaml_row, textvariable=self.album_yaml_var)
        self.yaml_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(yaml_row, text="浏览…",
                   command=self._browse_yaml).pack(side=tk.LEFT)

        out_row = ttk.Frame(frame)
        out_row.pack(fill=tk.X, pady=4)
        ttk.Label(out_row, text="输出:").pack(side=tk.LEFT)
        self.album_out_var = tk.StringVar(value=str(
            _PROJECT_ROOT / "album_output"))
        ttk.Entry(out_row, textvariable=self.album_out_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(out_row, text="浏览…",
                   command=lambda: self._browse_dir(self.album_out_var)
                   ).pack(side=tk.LEFT)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=8)
        self.album_btn = ttk.Button(btn_row, text="💿 生成专辑",
                                    command=self._generate_album)
        self.album_btn.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="📁 打开目录",
                   command=lambda: self._open_dir(self.album_out_var.get())
                   ).pack(side=tk.LEFT, padx=6)

        self.album_progress = ttk.Progressbar(frame, mode="indeterminate")
        self.album_progress.pack(fill=tk.X, pady=4)

        self.album_result = tk.Label(frame, text="选择模式后点击生成",
                                     bg=self.BG, fg=self.FG, justify=tk.LEFT,
                                     anchor=tk.W, wraplength=700)
        self.album_result.pack(fill=tk.X, pady=6)
        self._on_album_mode_change()

    def _on_album_mode_change(self):
        mode = self.album_mode_var.get()
        if mode == "yaml":
            self.yaml_entry.config(state=tk.NORMAL)
        else:
            self.yaml_entry.config(state=tk.DISABLED)

    def _browse_yaml(self):
        path = filedialog.askopenfilename(
            title="选择专辑 YAML", filetypes=[("YAML", "*.yaml *.yml"), ("所有文件", "*.*")])
        if path:
            self.album_yaml_var.set(path)

    # ── 页签 3: Beats ────────────────────────────────────────

    def _tab_beats(self):
        frame = ttk.Frame(self._notebook, padding=12)
        self._notebook.add(frame, text=" Beats ")

        tk.Label(frame, text="选择一种 beat 风格生成（输出到 skill/output_beats/）",
                 bg=self.BG, fg=self.FG, anchor=tk.W).pack(fill=tk.X)

        self.beat_var = tk.StringVar(value="Trap")
        grid = ttk.Frame(frame)
        grid.pack(fill=tk.X, pady=8)
        for i, name in enumerate(_BEAT_STYLES.keys()):
            ttk.Radiobutton(grid, text=name, variable=self.beat_var,
                            value=name).grid(row=i // 2, column=i % 2,
                                             sticky=tk.W, padx=8, pady=3)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=4)
        self.beat_btn = ttk.Button(btn_row, text="🥁 生成 Beat",
                                   command=self._generate_beat)
        self.beat_btn.pack(side=tk.LEFT)
        self.beat_play_btn = ttk.Button(btn_row, text="▶ 试听",
                                        command=self._on_play_last,
                                        state=tk.DISABLED)
        self.beat_play_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="📁 打开目录",
                   command=lambda: self._open_dir(_BEATS_OUTPUT_DIR)
                   ).pack(side=tk.LEFT)

        self.beat_result = tk.Label(frame, text="选择风格后点击生成",
                                    bg=self.BG, fg=self.FG, justify=tk.LEFT,
                                    anchor=tk.W, wraplength=700)
        self.beat_result.pack(fill=tk.X, pady=6)

    # ── 文件/目录工具 ────────────────────────────────────────

    @staticmethod
    def _browse_dir(var: tk.StringVar):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            var.set(path)

    @staticmethod
    def _open_dir(path: str):
        if not path:
            return
        try:
            os.startfile(path)  # Windows
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["xdg-open", path])
            except Exception:
                pass

    # ── 后台任务机制 ─────────────────────────────────────────

    def _run_bg(self, fn: Callable, on_done: Callable, on_error: Callable):
        """后台线程执行 fn，结果经 queue 回传主线程。"""
        if self._busy:
            messagebox.showinfo("忙碌", "已有生成任务在运行，请稍候")
            return
        self._busy = True
        self._status.config(text="⏳ 生成中…")

        def worker():
            try:
                result = fn()
                self._queue.put(("done", result))
            except Exception as e:  # noqa: BLE001 - 回传任意异常
                self._queue.put(("error", f"{type(e).__name__}: {e}"))

        threading.Thread(target=worker, daemon=True).start()
        on_done()  # 立即切换到进度显示（真正的完成处理在 _poll_queue）

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "done":
                    self._on_task_done(payload)
                else:
                    self._on_task_error(payload)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def _on_task_done(self, result):
        self._busy = False
        self._status.config(text="✅ 完成")

    def _on_task_error(self, err):
        self._busy = False
        self._status.config(text="❌ 失败")
        messagebox.showerror("生成失败", err)

    # ── 单曲生成 ─────────────────────────────────────────────

    def _generate_single(self):
        try:
            bpm = self._parse_opt_int(self.single_bpm_var)
            bars = self._parse_opt_int(self.single_bars_var)
            seed = self._parse_opt_int(self.single_seed_var)
        except ValueError:
            messagebox.showwarning("输入无效", "BPM / 小节 / 种子必须是整数或留空")
            return
        style = self.single_style_var.get()
        out_dir = self.single_out_var.get().strip() or None

        def task():
            if style == "(随机)":
                return QuickMaker.random(out_dir, seed)
            return QuickMaker.style(style, out_dir, bpm, bars, seed)

        def handle_done(qr):
            self._on_task_done(qr)
            wav = str(qr.wave_path) if qr.wave_path else None
            self._last_audio_path = wav
            self._last_result = qr
            self.single_result.config(
                text=f"✅ {qr.title} · 风格 {qr.style} · {qr.bpm} BPM · "
                     f"{qr.key} · {qr.bars} 小节 · {qr.duration_sec:.1f}s\n"
                     f"输出: {wav or '未生成 WAV'}")
            if wav:
                self.single_play_btn.config(state=tk.NORMAL)
            else:
                self.single_play_btn.config(state=tk.DISABLED)

        def handle_error(err):
            self._on_task_error(err)

        self._run_bg(task, handle_done, handle_error)
        self.single_result.config(text="⏳ 生成中…（后台进行，可切换页签）")
        self.single_play_btn.config(state=tk.DISABLED)

    # ── 专辑生成 ─────────────────────────────────────────────

    def _generate_album(self):
        mode = self.album_mode_var.get()
        out_dir = self.album_out_var.get().strip() or None

        if mode == "demo":
            def task():
                return AlbumMaker(make_demo_config()).make(str(out_dir))
        else:
            yaml_path = self.album_yaml_var.get().strip()
            if not yaml_path:
                messagebox.showwarning("缺少配置", "请选择 YAML 文件路径")
                return
            if not Path(yaml_path).is_file():
                messagebox.showerror("文件不存在", f"YAML 不存在: {yaml_path}")
                return

            def task():
                return AlbumMaker(AlbumConfig.from_yaml(yaml_path)).make(str(out_dir))

        def handle_done(result):
            self._on_task_done(result)
            self.album_progress.stop()
            ok = sum(1 for t in result.tracks if t.success)
            total = len(result.tracks)
            self.album_result.config(
                text=f"✅ 专辑完成: {ok}/{total} 曲成功\n输出: {out_dir}\n"
                     + "\n".join(
                         f"  {'✓' if t.success else '✗'} {t.title}"
                         for t in result.tracks))
            self.album_btn.config(state=tk.NORMAL)

        def handle_error(err):
            self.album_progress.stop()
            self.album_btn.config(state=tk.NORMAL)
            self._on_task_error(err)

        self.album_btn.config(state=tk.DISABLED)
        self.album_progress.start(12)
        self.album_result.config(text="⏳ 专辑生成中…（视曲目数可能需数分钟）")
        self._run_bg(task, handle_done, handle_error)

    # ── Beat 生成 ────────────────────────────────────────────

    def _generate_beat(self):
        name = self.beat_var.get()
        func = _BEAT_STYLES.get(name)
        if func is None:
            messagebox.showerror("不可用", f"beat 风格不可用: {name}")
            return

        def task():
            return name, func()

        def handle_done(payload):
            name, wav_or_audio = payload
            self._on_task_done(payload)
            if isinstance(wav_or_audio, str):
                self._last_audio_path = wav_or_audio
                msg = f"✅ {name} 完成 → {wav_or_audio}"
            elif wav_or_audio is not None and hasattr(wav_or_audio, "size"):
                msg = f"✅ {name} 完成（音频已生成）"
            else:
                msg = f"⚠️ {name}: 未产出（可能缺采样素材）"
                self._last_audio_path = None
            self.beat_result.config(text=msg)
            self.beat_play_btn.config(
                state=tk.NORMAL if self._last_audio_path else tk.DISABLED)

        def handle_error(err):
            self._on_task_error(err)

        self._run_bg(task, handle_done, handle_error)
        self.beat_result.config(text=f"⏳ {name} 生成中…")
        self.beat_play_btn.config(state=tk.DISABLED)

    # ── 页签 4: 镜像（机生成混音） ────────────────────────

    def _tab_mirror(self):
        frame = ttk.Frame(self._notebook, padding=12)
        self._notebook.add(frame, text=" 镜像 ")

        tk.Label(frame, text="纯机生成混音（musickit 纯采样混音的镜像）— 65 风格 × 5 曲式 × 24 混音师",
                 bg=self.BG, fg=self.FG, anchor=tk.W).pack(fill=tk.X)

        row1 = ttk.Frame(frame)
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="风格:").pack(side=tk.LEFT)
        self.mirror_style_var = tk.StringVar(value="(随机)")
        ttk.Combobox(row1, textvariable=self.mirror_style_var,
                     values=["(随机)"] + list(STYLE_SLUGS),
                     state="readonly", width=20).pack(side=tk.LEFT, padx=6)
        ttk.Label(row1, text="曲式:").pack(side=tk.LEFT, padx=(12, 0))
        self.mirror_struct_var = tk.StringVar(value="classic_drop")
        ttk.Combobox(row1, textvariable=self.mirror_struct_var,
                     values=list_structures(), state="readonly", width=20
                     ).pack(side=tk.LEFT, padx=6)

        row2 = ttk.Frame(frame)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="混音师:").pack(side=tk.LEFT)
        self.mirror_mixer_var = tk.StringVar(value="(随机)")
        ttk.Combobox(row2, textvariable=self.mirror_mixer_var,
                     values=["(随机)"] + list_mixers(),
                     state="readonly", width=20).pack(side=tk.LEFT, padx=6)
        ttk.Label(row2, text="BPM:").pack(side=tk.LEFT, padx=(12, 0))
        self.mirror_bpm_var = self._var_int()
        ttk.Entry(row2, textvariable=self.mirror_bpm_var, width=7).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row2, text="小节:").pack(side=tk.LEFT)
        self.mirror_bars_var = self._var_int()
        ttk.Entry(row2, textvariable=self.mirror_bars_var, width=7).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row2, text="种子:").pack(side=tk.LEFT)
        self.mirror_seed_var = self._var_int()
        ttk.Entry(row2, textvariable=self.mirror_seed_var, width=9).pack(side=tk.LEFT)

        row3 = ttk.Frame(frame)
        row3.pack(fill=tk.X, pady=4)
        ttk.Label(row3, text="输出:").pack(side=tk.LEFT)
        self.mirror_out_var = tk.StringVar(value=str(_PROJECT_ROOT / "mirror_output"))
        ttk.Entry(row3, textvariable=self.mirror_out_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(row3, text="浏览…",
                   command=lambda: self._browse_dir(self.mirror_out_var)
                   ).pack(side=tk.LEFT)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=8)
        self.mirror_btn = ttk.Button(btn_row, text="🎧 生成镜像混音",
                                     command=self._generate_mirror)
        self.mirror_btn.pack(side=tk.LEFT)
        self.mirror_play_btn = ttk.Button(btn_row, text="▶ 试听",
                                          command=self._on_play_last,
                                          state=tk.DISABLED)
        self.mirror_play_btn.pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="📁 打开目录",
                   command=lambda: self._open_dir(self.mirror_out_var.get())
                   ).pack(side=tk.LEFT)

        self.mirror_result = tk.Label(frame, text="选择参数后点击生成（默认 16 小节约 30 秒）",
                                      bg=self.BG, fg=self.FG, justify=tk.LEFT,
                                      anchor=tk.W, wraplength=700)
        self.mirror_result.pack(fill=tk.X, pady=6)

    def _generate_mirror(self):
        try:
            bpm = self._parse_opt_int(self.mirror_bpm_var)
            bars = self._parse_opt_int(self.mirror_bars_var)
            seed = self._parse_opt_int(self.mirror_seed_var)
        except ValueError:
            messagebox.showwarning("输入无效", "BPM / 小节 / 种子必须是整数或留空")
            return
        style = self.mirror_style_var.get()
        structure = self.mirror_struct_var.get()
        mixer = self.mirror_mixer_var.get()
        out_dir = self.mirror_out_var.get().strip() or None

        def task():
            return run_remix(
                count=1,
                seed=seed,
                bars=bars if bars is not None else 16,
                bpm=bpm,
                structure=structure,
                style=None if style == "(随机)" else style,
                mixer_style=None if mixer == "(随机)" else mixer,
                out_dir=out_dir or "mirror_output",
                fmt="wav",
                release_safe=True,
            )[0]

        def handle_done(result):
            self._on_task_done(result)
            wav = str(result.song_path) if result.song_path else None
            self._last_audio_path = wav
            rep = result.report
            self.mirror_result.config(
                text=f"✅ {rep.prompt['style']} · {rep.bpm}BPM · {rep.bars} 小节 · "
                     f"曲式 {rep.structure} · 混音师 {rep.mixer_style} · {rep.duration_sec}s"
                     f"\n→ {wav}\n分轨: {len(rep.stems)} 条 · license_tier=selfgen")
            self.mirror_play_btn.config(state=tk.NORMAL if wav else tk.DISABLED)
            self.mirror_btn.config(state=tk.NORMAL)

        def handle_error(err):
            self.mirror_btn.config(state=tk.NORMAL)
            self._on_task_error(err)

        self.mirror_btn.config(state=tk.DISABLED)
        self.mirror_result.config(text="⏳ 机生成混音中…（视小节数约 5~60 秒）")
        self._run_bg(task, handle_done, handle_error)

    # ── 试听 ─────────────────────────────────────────────────

    def _on_play_last(self):
        if not self._last_audio_path:
            messagebox.showinfo("无音频", "还没有可试听的生成结果")
            return
        try:
            import soundfile as sf
            audio, _sr = sf.read(self._last_audio_path, dtype="float32")
            from bloodmusic.playback import PreviewPlayer
            self._player = getattr(self, "_player", None) or PreviewPlayer()
            self._player.play(audio)
            self._status.config(text=f"▶ 试听: {Path(self._last_audio_path).name}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("播放失败", str(e))


def main():
    """独立运行入口。"""
    app = MakerGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
