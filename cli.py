"""
BloodMusic CLI — 程序化游戏音频合成
=====================================

用法:
  python -m bloodmusic --help
  python -m bloodmusic batch --output ./audio --duration 30 --format ogg
  python -m bloodmusic --gui
  python -m bloodmusic --preview menu
"""

import argparse
import sys


def cmd_batch(args):
    """批量导出全部音频"""
    from bloodmusic.export import AudioBatchExporter

    exporter = AudioBatchExporter(args.output, format=args.format)
    result = exporter.export_everything(music_duration=args.duration)

    total_sfx = len([k for k in result if "/" in k])
    total_music = len([k for k in result if "/" not in k])
    print(f"\n✅ 完成：{total_sfx} 个 SFX + {total_music} 首音乐 → {args.output}")


def cmd_preview(args):
    """预览某个预设"""
    from bloodmusic.playback import PreviewPlayer
    from bloodmusic.sfx import UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
    from bloodmusic.music import generate_music_wav, ALL_MUSIC_PATTERNS
    from bloodmusic.core import synthesize_voice
    import numpy as np

    # 搜 SFX
    all_sfx = {}
    for d in [UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS]:
        all_sfx.update(d)

    if args.name in all_sfx:
        audio = synthesize_voice(all_sfx[args.name])
        print(f"🔊 预览 SFX: {args.name}")
    elif args.name in ALL_MUSIC_PATTERNS:
        pattern = ALL_MUSIC_PATTERNS[args.name]
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), "_bloodmusic_preview.wav")
        generate_music_wav(pattern, tmp, duration_sec=8.0)
        from scipy.io import wavfile
        sr, audio = wavfile.read(tmp)
        audio = audio.astype(np.float32) / 32767.0
        print(f"🎵 预览 Music: {args.name}")
    else:
        print(f"❌ 未找到预设: {args.name}")
        available = sorted(list(all_sfx.keys())[:10]) + ["..."] + sorted(ALL_MUSIC_PATTERNS.keys())
        print(f"   可用: {', '.join(available[:15])}")
        return

    player = PreviewPlayer()
    player.play(audio)
    print("   播放中... Ctrl+C 停止")
    try:
        while player.is_playing:
            import time
            time.sleep(0.1)
    except KeyboardInterrupt:
        player.stop()


def cmd_list(_args):
    """列出所有可用预设"""
    from bloodmusic.sfx import UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
    from bloodmusic.music import ALL_MUSIC_PATTERNS

    print("  🎵 Music 预设:")
    for k in ALL_MUSIC_PATTERNS:
        print(f"      {k}")
    print()
    for cat_name, cat in [("UI", UI_FX_PRESETS), ("Card", CARD_FX_PRESETS),
                           ("Combat", COMBAT_FX_PRESETS), ("System", SYSTEM_FX_PRESETS)]:
        print(f"  🔊 {cat_name} SFX ({len(cat)} 个):")
        for k in cat:
            print(f"      {k}")


def cmd_gui(_args):
    """启动 GUI 工作站"""
    try:
        from bloodmusic.gui.workstation import GameAudioWorkstationGUI
        import tkinter as tk
        root = tk.Tk()
        app = GameAudioWorkstationGUI(root)
        root.protocol("WM_DELETE_WINDOW", lambda: (app.player.stop(), root.destroy()))
        root.mainloop()
    except ImportError as e:
        print(f"GUI 模式需要 tkinter: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="🎧 BloodMusic — 程序化游戏音频合成引擎",
        prog="bloodmusic",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # batch
    p_batch = sub.add_parser("batch", help="批量导出全部音频")
    p_batch.add_argument("--output", "-o", default="./audio_output",
                         help="输出目录 (默认 ./audio_output)")
    p_batch.add_argument("--duration", "-d", type=float, default=30.0,
                         help="音乐时长/秒 (默认 30)")
    p_batch.add_argument("--format", "-f", default="wav",
                         choices=["wav", "ogg", "flac"],
                         help="导出格式 (默认 wav)")
    p_batch.add_argument("--bitrate", "-b", type=int, default=128000,
                         help="OGG 比特率 (默认 128000)")

    # preview
    p_preview = sub.add_parser("preview", help="预览一个预设")
    p_preview.add_argument("name", help="预设名称")

    # list
    sub.add_parser("list", help="列出所有预设")

    # gui
    sub.add_parser("gui", help="启动 GUI 工作站")

    # 兼容简写
    parser.add_argument("--batch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", "-o", default="./audio_output", help=argparse.SUPPRESS)
    parser.add_argument("--duration", "-d", type=float, default=30.0, help=argparse.SUPPRESS)
    parser.add_argument("--gui", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--preview", help=argparse.SUPPRESS)
    parser.add_argument("--list", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # 兼容简写模式
    if args.batch:
        return cmd_batch(args)
    if args.gui:
        return cmd_gui(args)
    if args.preview:
        args.name = args.preview
        return cmd_preview(args)
    if args.list:
        return cmd_list(args)

    # 子命令模式
    if args.command == "batch":
        return cmd_batch(args)
    elif args.command == "preview":
        return cmd_preview(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "gui":
        return cmd_gui(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
