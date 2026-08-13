"""
BloodMusic 快捷入口 -- 程序化游戏音频合成引擎
=============================================

用法:
  python main.py                     # GUI 工作站模式（默认）
  python main.py --maker             # 制作工作室（单曲/专辑/Beats）
  python main.py --cli batch ...     # 命令行模式（委托给 cli.py）
  python main.py --demo              # 引擎能力演示
  python main.py --check             # 检查依赖和环境
  python main.py --config audio.toml # 从配置文件加载参数
  python main.py export --all        # 无头导出全部（委托 CLI）

快捷命令（直接委托 CLI）:
  python main.py batch              -> python -m bloodmusic batch
  python main.py preview <name>     -> python -m bloodmusic preview
  python main.py list               -> python -m bloodmusic list
  python main.py gui                -> python -m bloodmusic gui
"""

import sys
import time
import os
import textwrap
from pathlib import Path

# ---------- 路径注入 ----------
# main.py 位于包目录 bloodmusic/ 内，包根即其直接父目录（parent），
# 而非再上一级（parent.parent），否则 python main.py 直接运行时会把
# 错误的上层目录注入 sys.path，导致内部 `from bloodmusic...` 导入失败。
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ============================================================
# 依赖检查
# ============================================================

def check_dependencies() -> dict:
    """检查所有依赖是否就绪，返回 {模块名: (状态, 详情)}"""
    results = {}
    checks = [
        ("numpy",       "numpy",      "数值计算核心"),
        ("scipy",       "scipy",      "信号处理（滤波器/EQ）"),
        ("soundfile",   "soundfile",  "音频文件读写"),
        ("sounddevice", "sounddevice","实时音频播放"),
        ("tkinter",     "tkinter",    "GUI 工作站界面"),
    ]
    for display_name, import_name, purpose in checks:
        try:
            if import_name == "scipy":
                __import__("scipy.signal")
            else:
                __import__(import_name)
            results[display_name] = (True, purpose)
        except ImportError:
            results[display_name] = (False, purpose)
    return results


def print_dependency_report(results: dict) -> bool:
    """打印依赖报告，返回是否全部通过"""
    print("\n" + "=" * 58)
    print("  BloodMusic 依赖检查")
    print("=" * 58)
    all_ok = True
    for name, (ok, purpose) in results.items():
        status = "[OK]   " if ok else "[MISS] "
        print(f"  {status} {name:<15s}  <-- {purpose}")
        if not ok:
            all_ok = False
    print("=" * 58)

    if not all_ok:
        print("\n  [!] 缺少的依赖可通过以下方式安装：")
        print("  pip install numpy scipy soundfile sounddevice")
        print("  tkinter 通常内置，如缺失需安装系统包")
    else:
        print("  [OK] 所有依赖就绪！")
    print()
    return all_ok


# ============================================================
# 演示模式
# ============================================================

def run_demo():
    """引擎能力自演 Demo ---- 逐一展示各合成类型的音色"""
    print("\n" + "=" * 58)
    print("  [*] BloodMusic 引擎能力演示")
    print("=" * 58)

    # 第一阶段 -- 纯合成演示
    _demo_pure_synthesis()

    # 第二阶段 -- 效果器展示
    _demo_effects_showcase()

    # 第三阶段 -- FM 合成
    _demo_fm_synthesis()

    # 第四阶段 -- 音乐预设快闪
    _demo_music_showcase()

    print("\n" + "=" * 58)
    print("  Demo 完成！使用 'python main.py' 启动工作站深入探索。")
    print("=" * 58 + "\n")


def _demo_pure_synthesis():
    """演示基础波形和包络"""
    from bloodmusic.core import (
        SynthVoice, synthesize_voice, OscType, EnvShape, ADSRParams,
    )
    from bloodmusic.playback import PreviewPlayer
    import numpy as np

    player = PreviewPlayer()

    demos = [
        ("正弦波 · Pad 包络", OscType.SINE, EnvShape.PAD, "C4", 1.5,
         "最纯净的基频音色，适合氛围底层"),
        ("锯齿波 · Percussive", OscType.SAW, EnvShape.PERCUSSIVE, "C3", 0.8,
         "谐波丰富、有冲击力，适合战斗主旋律"),
        ("方波 · Pluck 包络", OscType.SQUARE, EnvShape.PLUCK, "C3", 0.6,
         "复古 8-bit 风味，适合像素风格游戏"),
        ("三角波 · Swell 包络", OscType.TRIANGLE, EnvShape.SWELL, "C5", 1.2,
         "柔和圆润，适合 UI 交互提示音"),
        ("白噪声 · Percussive", OscType.NOISE_WHITE, EnvShape.PERCUSSIVE, "A0", 0.3,
         "冲击/Hit 音效基础材料"),
    ]

    print("\n  -- 阶段 1: 波形 x 包络 --")
    for name, osc_type, env_shape, note, dur, desc in demos:
        from bloodmusic.core.note_utils import note_to_freq
        voice = SynthVoice(
            freq=note_to_freq(note), osc_type=osc_type,
            duration=dur, volume=0.25,
            env_shape=env_shape,
            adsr=ADSRParams(attack=0.02, decay=0.15, sustain=0.5, release=0.3),
        )
        audio = synthesize_voice(voice)
        print(f"  >> {name:30s}  {desc}")
        player.play(audio)
        time.sleep(max(dur + 1.5, 2.0))
        player.stop()

    print("  [OK] 阶段 1 完成\n")


def _demo_effects_showcase():
    """演示效果器链"""
    from bloodmusic.core import (
        SynthVoice, synthesize_voice, OscType, EnvShape, EffectChain,
    )
    from bloodmusic.playback import PreviewPlayer
    from bloodmusic.core.note_utils import note_to_freq

    player = PreviewPlayer()
    base_dur = 2.0

    demos = [
        ("干声 (无效果)", None,
         "原始合成音色，不加任何处理"),
        ("混响 · Schroeder", EffectChain(reverb_schroeder=True, reverb_mix=0.4, reverb_decay=0.6),
         "模拟空间感，从狭小房间到宏伟殿堂"),
        ("低通滤波", EffectChain(lp_filter_hz=800),
         "mWarm 音色，让刺耳高频变柔和"),
        ("失真", EffectChain(distortion=0.5),
         "增加谐波饱和度，摇滚/金属风战斗音乐"),
        ("合唱效果", EffectChain(chorus_mix=0.4, chorus_rate=0.8, chorus_depth=0.003),
         "加宽加厚，让单薄音色变得丰富"),
        ("全链路", EffectChain(
            lp_filter_hz=3000, hp_filter_hz=100,
            reverb_schroeder=True, reverb_mix=0.3, reverb_decay=0.4,
            chorus_mix=0.2, chorus_rate=0.6, chorus_depth=0.002,
            stereo_width=0.6,
        ), "效果器全链 -- 滤波器->压缩->失真->合唱->混响->立体声"),
    ]

    print("\n  -- 阶段 2: 效果器展示 --")
    for name, chain, desc in demos:
        voice = SynthVoice(
            freq=note_to_freq("E3"), osc_type=OscType.SAW,
            duration=base_dur, volume=0.25,
            env_shape=EnvShape.PAD,
            effect_chain=chain or EffectChain(),
        )
        audio = synthesize_voice(voice)
        print(f"  >> {name:30s}  {desc}")
        player.play(audio)
        time.sleep(base_dur + 1.5)
        player.stop()

    print("  [OK] 阶段 2 完成\n")


def _demo_fm_synthesis():
    """演示 FM 合成"""
    from bloodmusic.core import FMSynthVoice, synthesize_fm_voice, OscType, EnvShape
    from bloodmusic.playback import PreviewPlayer

    player = PreviewPlayer()
    base_dur = 1.5

    demos = [
        ("FM 贝尔音色", 1.4, 0.6, "经典的 FM 铃铛/钟声音色"),
        ("FM 铜管", 1.0, 0.3, "类似铜管乐器的丰富泛音"),
        ("FM 金属", 2.0, 0.8, "深度调制产生金属质感"),
        ("FM 人声", 0.5, 0.2, "类似元音共振峰"),
        ("FM 拨弦", 2.7, 0.5, "音叉/拨弦质感"),
    ]

    print("\n  -- 阶段 3: FM 合成 --")
    for name, ratio, depth, desc in demos:
        voice = FMSynthVoice(
            carrier_freq=440.0, carrier_type=OscType.SINE,
            modulator_freq_ratio=ratio, modulator_type=OscType.SINE,
            fm_depth=depth, duration=base_dur, volume=0.25,
            env_shape=EnvShape.PLUCK,
        )
        audio = synthesize_fm_voice(voice)
        print(f"  >> {name:30s}  ratio={ratio:.1f} depth={depth:.1f}  {desc}")
        player.play(audio)
        time.sleep(base_dur + 1.0)
        player.stop()

    print("  [OK] 阶段 3 完成\n")


def _demo_music_showcase():
    """演示音乐预设快闪"""
    from bloodmusic.music import generate_music_wav, ALL_MUSIC_PATTERNS
    from bloodmusic.playback import PreviewPlayer
    import tempfile
    import numpy as np

    player = PreviewPlayer()
    snippets = ["menu_music", "battle_high_music", "forest_music", "dungeon_music", "victory_fanfare"]

    print("\n  -- 阶段 4: 音乐预设快闪 --")
    for name in snippets:
        if name not in ALL_MUSIC_PATTERNS:
            print(f"  [X] 跳过: {name} (不存在)")
            continue
        pattern = ALL_MUSIC_PATTERNS[name]
        tmp_path = os.path.join(tempfile.gettempdir(), f"_bloodmusic_demo_{name}.wav")
        generate_music_wav(pattern, tmp_path, duration_sec=6.0)
        from scipy.io import wavfile
        sr, audio = wavfile.read(tmp_path)
        audio = audio.astype(np.float32) / 32767.0
        print(f"  >> {name:30s}  BPM={pattern.bpm}  type={pattern.osc_type.name if hasattr(pattern, 'osc_type') else '?'}")
        player.play(audio)
        time.sleep(7.5)
        player.stop()

    print("  [OK] 阶段 4 完成\n")


# ============================================================
# 配置加载
# ============================================================

def load_config(config_path: str) -> dict:
    """从 TOML / JSON 配置文件加载音频参数覆盖"""
    config_path = Path(config_path)
    if not config_path.exists():
        print(f"[X] 配置文件不存在: {config_path}")
        sys.exit(1)

    suffix = config_path.suffix.lower()
    if suffix in (".toml", ".tml"):
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                print("[X] 需要 tomli 库读取 TOML: pip install tomli")
                sys.exit(1)
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    elif suffix == ".json":
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"[X] 不支持的配置格式: {suffix} (支持 .toml / .json)")
        sys.exit(1)


def apply_config(config: dict):
    """将配置合并到模块常量（运行时覆盖）"""
    import bloodmusic.core.constants as const

    audio_cfg = config.get("audio", {})
    if "sr" in audio_cfg:
        const.SR = audio_cfg["sr"]
    if "bpm_default" in audio_cfg:
        const.BPM_DEFAULT = audio_cfg["bpm_default"]
    if "vol_sfx" in audio_cfg:
        const.VOL_SFX = audio_cfg["vol_sfx"]
    if "vol_music" in audio_cfg:
        const.VOL_MUSIC = audio_cfg["vol_music"]
    if "ogg_bitrate" in audio_cfg:
        const.DEFAULT_OGG_BITRATE = audio_cfg["ogg_bitrate"]

    export_cfg = config.get("export", {})
    default_format = export_cfg.get("format", "")
    default_output = export_cfg.get("output", "")

    print(f"  [OK] 配置已加载: {len(audio_cfg)} 音频参数 + {len(export_cfg)} 导出参数")
    return {
        "default_format": default_format,
        "default_output": default_output,
    }


# ============================================================
# 主入口
# ============================================================

def main():
    # 快速解析：先分离已知的自定义参数，其余委托给 cli.py
    raw_args = sys.argv[1:]

    # 如果用户传了子命令格式参数（batch / preview / list / gui），直接委托 CLI
    cli_commands = {"batch", "preview", "list", "gui", "--batch", "--preview", "--gui", "--list"}
    if raw_args and raw_args[0] in cli_commands:
        from bloodmusic.cli import main as cli_main
        return cli_main()

    # 解析自定义参数
    import argparse
    parser = argparse.ArgumentParser(
        description="[*] BloodMusic -- 程序化游戏音频合成引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        示例:
          python main.py                          # GUI 工作站
          python main.py --demo                   # 引擎能力演示
          python main.py --check                  # 依赖检查
          python main.py --config audio.toml      # 加载配置后启动 GUI
          python main.py --cli batch -o ./out     # CLI 批量导出
          python main.py --cli preview menu       # CLI 预览
        """),
    )
    parser.add_argument("--cli", nargs=argparse.REMAINDER,
                        help="通过 CLI 模式执行（后接 CLI 参数）")
    parser.add_argument("--demo", action="store_true",
                        help="运行引擎能力演示")
    parser.add_argument("--tutorial", action="store_true",
                        help="交互式教程模式（等同 --demo）")
    parser.add_argument("--check", action="store_true",
                        help="检查依赖和环境")
    parser.add_argument("--maker", action="store_true",
                        help="启动制作工作室 GUI（单曲/专辑/Beats）")
    parser.add_argument("--config", type=str,
                        help="从配置文件加载音频参数")

    args = parser.parse_args(raw_args)

    # --maker: 制作工作室（独立启动，不需完整工作站）
    if args.maker:
        try:
            from bloodmusic.gui.maker_gui import MakerGUI
            MakerGUI().root.mainloop()
            return
        except Exception as e:
            print(f"[!] 制作工作室启动失败 ({e})", file=sys.stderr)
            return 1

    # --check: 依赖检查
    if args.check:
        results = check_dependencies()
        ok = print_dependency_report(results)
        sys.exit(0 if ok else 1)

    # --demo / --tutorial
    if args.demo or args.tutorial:
        results = check_dependencies()
        ok = print_dependency_report(results)
        if not ok:
            print("[!] 缺少依赖，Demo 可能无法完整运行。\n")
        try:
            run_demo()
        except Exception as e:
            print(f"\n[X] Demo 运行出错: {e}")
            import traceback
            traceback.print_exc()
        return

    # --cli: 委托给 CLI 模块
    if args.cli is not None:
        sys.argv = ["bloodmusic"] + args.cli
        from bloodmusic.cli import main as cli_main
        return cli_main()

    # --config: 加载配置
    export_defaults = {}
    if args.config:
        config = load_config(args.config)
        export_defaults = apply_config(config)

    # 默认：启动 GUI（需要依赖检查）
    results = check_dependencies()
    all_ok = print_dependency_report(results)

    if not results["sounddevice"][0]:
        print("[!] sounddevice 缺失，预览功能将不可用。")
    if not results["tkinter"][0]:
        # 自动降级到 CLI 模式，而非直接崩溃退出
        print("[!] tkinter 缺失，无法启动 GUI 工作站。")
        print("    已自动降级到命令行模式 (python main.py --cli batch)。")
        print("    如需 GUI，请安装系统 tkinter 包 (如: apt install python3-tk)。\n")
        sys.argv = ["bloodmusic", "batch", "-o",
                    export_defaults.get("default_output", "./audio_output")]
        from bloodmusic.cli import main as cli_main
        return cli_main()

    try:
        from bloodmusic.gui.workstation import GameAudioWorkstationGUI
        import tkinter as tk

        output_dir = export_defaults.get("default_output", str(Path(__file__).resolve().parent / "output"))
        root = tk.Tk()
        app = GameAudioWorkstationGUI(root, output_dir)
        root.protocol("WM_DELETE_WINDOW", lambda: (app.player.stop(), root.destroy()))
        root.mainloop()
    except ImportError as e:
        # tkinter 在入口处被判断为可用但运行时导入失败，同样降级
        print(f"[!] GUI 模式启动失败 ({e})，自动降级到命令行模式。", file=sys.stderr)
        sys.argv = ["bloodmusic", "batch", "-o",
                    export_defaults.get("default_output", "./audio_output")]
        from bloodmusic.cli import main as cli_main
        return cli_main()
    except Exception as e:
        print(f"运行时错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
