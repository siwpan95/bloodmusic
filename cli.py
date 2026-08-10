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


def cmd_pool_list(_args):
    """列出所有内置乐器池模板"""
    from bloodmusic.music.pool_serializer import PoolSerializer
    from bloodmusic.music.pool_templates import POOL_TEMPLATES

    print("\n  🎻 乐器池模板 (YAML 预设):")
    presets = PoolSerializer.list_presets()
    if presets:
        for p in presets:
            print(f"      {p}")
    else:
        print("      (无)")

    print("\n  📦 编程式模板:")
    for key in POOL_TEMPLATES:
        tmpl = POOL_TEMPLATES[key]
        print(f"      {key:25s} — {tmpl.description}")

    print()


def cmd_pool_show(args):
    """查看乐器池详情"""
    from bloodmusic.music.pool_serializer import PoolSerializer
    from bloodmusic.music.pool_templates import POOL_TEMPLATES

    name = args.template_or_file

    # 先尝试从预设加载
    presets = PoolSerializer.list_presets()
    if name in presets:
        pool = PoolSerializer.load_preset(name)
    elif name in POOL_TEMPLATES:
        pool = POOL_TEMPLATES[name].to_pool()
    else:
        # 尝试作为文件路径加载
        try:
            pool = PoolSerializer.load_yaml(name)
        except Exception as e:
            print(f"❌ 无法加载: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"\n  🎵 {pool.name} v{pool.version}")
    print(f"     BPM: {pool.bpm}  Key: {pool.key}  Scale: {pool.scale}")
    if pool.style:
        print(f"     Style: {pool.style}")
    print(f"     Instruments ({len(pool.instruments)}):")
    for inst in pool.instruments:
        preset_info = f" [{inst.preset}]" if inst.preset else ""
        print(f"       {inst.role.value:8s} | {inst.name:20s} | {inst.engine.value:15s}{preset_info} | vol={inst.volume:.1f} pan={inst.pan:+.1f}")
    print()

    # 校验
    warnings = pool.validate()
    if warnings:
        print(f"  ⚠️  校验警告 ({len(warnings)}):")
        for w in warnings:
            print(f"       - {w}")
    else:
        print("  ✅ 校验通过")


def cmd_pool_render(args):
    """渲染乐器池为成品音频"""
    import logging
    from bloodmusic.music.pool_serializer import PoolSerializer
    from bloodmusic.music.pool_renderer import PoolRenderer
    from bloodmusic.music.pool_templates import POOL_TEMPLATES
    from bloodmusic.export.batch import export_audio

    # 配置日志
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")

    # 加载乐池
    template_or_file = args.template_or_file
    presets = PoolSerializer.list_presets()

    if template_or_file in presets:
        pool = PoolSerializer.load_preset(template_or_file)
        print(f"📦 加载预设: {template_or_file}")
    elif template_or_file in POOL_TEMPLATES:
        pool = POOL_TEMPLATES[template_or_file].to_pool()
        print(f"📦 加载模板: {template_or_file}")
    else:
        try:
            pool = PoolSerializer.load_yaml(template_or_file)
            print(f"📄 加载文件: {template_or_file}")
        except Exception as e:
            print(f"❌ 加载失败: {e}", file=sys.stderr)
            sys.exit(1)

    # 覆盖参数
    if args.key:
        pool.key = args.key
    if args.bpm:
        pool.bpm = args.bpm
    if args.style:
        pool.style = args.style

    # 渲染
    output_path = args.output or f"{pool.name}_{args.duration}s.{args.format}"
    renderer = PoolRenderer(
        pool=pool,
        duration_sec=args.duration,
        style_name=args.style,
    )

    try:
        if args.stems_only:
            print("🎧 仅渲染分轨...")
            stems = renderer.render_stems_only()
            print(f"✅ 生成 {len(stems)} 个分轨")
            import os
            stem_dir = args.output or "./stems"
            os.makedirs(stem_dir, exist_ok=True)
            for name, audio in stems.items():
                stem_path = os.path.join(stem_dir, f"{name}.{args.format}")
                export_audio(audio, stem_path, format=args.format)
                print(f"   → {stem_path}")
        else:
            print(f"🎼 渲染中... ({args.duration}s, {pool.bpm}BPM, {pool.key})")
            final_audio, stems = renderer.render()
            export_audio(final_audio, output_path, format=args.format)
            print(f"✅ 导出: {output_path}")
            print(f"   📊 分轨数: {len(stems)}, 时长: {len(final_audio)/44100:.1f}s")
    except Exception as e:
        print(f"❌ 渲染失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_pool_create(args):
    """交互式创建自定义乐器池"""
    from bloodmusic.music.instrument_pool import (
        InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
    )
    from bloodmusic.music.pool_serializer import PoolSerializer

    pool = InstrumentPool(
        name=args.name,
        bpm=args.bpm or 120,
        key=args.key or "C",
        scale=args.scale or "major",
    )

    if args.add:
        for spec in args.add:
            try:
                role_str, preset = spec.split(":", 1)
                role = InstrumentRole.from_string(role_str)
                inst = PoolInstrument(
                    name=preset.replace("_", " ").title(),
                    role=role,
                    preset=preset,
                )
                pool.instruments.append(inst)
                print(f"  + {role.value}: {preset}")
            except ValueError as e:
                print(f"  ⚠️ 跳过无效规格 '{spec}': {e}", file=sys.stderr)

    save_path = args.save or f"{args.name}.yaml"
    PoolSerializer.save_yaml(pool, save_path)
    print(f"\n✅ 乐池已保存: {save_path}")
    print(f"   {len(pool.instruments)} 件乐器, BPM={pool.bpm}, Key={pool.key}")


def cmd_pool_preview(args):
    """试听乐器池中某件乐器"""
    from bloodmusic.music.pool_serializer import PoolSerializer
    from bloodmusic.music.pool_templates import POOL_TEMPLATES

    template_or_file = args.template_or_file
    presets = PoolSerializer.list_presets()

    if template_or_file in presets:
        pool = PoolSerializer.load_preset(template_or_file)
    elif template_or_file in POOL_TEMPLATES:
        pool = POOL_TEMPLATES[template_or_file].to_pool()
    else:
        try:
            pool = PoolSerializer.load_yaml(template_or_file)
        except Exception as e:
            print(f"❌ 加载失败: {e}", file=sys.stderr)
            sys.exit(1)

    # 按角色筛选
    if args.instrument:
        from bloodmusic.music.instrument_pool import InstrumentRole
        try:
            role = InstrumentRole.from_string(args.instrument)
            matches = pool.get_by_role(role)
        except ValueError:
            # 按名称搜索
            matches = [i for i in pool.instruments if args.instrument.lower() in i.name.lower()]
    else:
        matches = pool.instruments

    if not matches:
        print(f"❌ 未找到匹配的乐器: {args.instrument}")
        sys.exit(1)

    inst = matches[0]
    print(f"\n🔊 试听乐器: {inst.name} (role={inst.role.value}, engine={inst.engine.value})")
    if inst.preset:
        print(f"   Preset: {inst.preset}")

    # 生成预览片段
    try:
        from bloodmusic.music.instruments import get_instrument
        from bloodmusic.music.pattern import MusicPattern, render_pattern_to_array
        from bloodmusic.core.constants import SR
        import sounddevice as sd

        pattern = MusicPattern(
            name="preview",
            notes=["C4", "E4", "G4", "C5", "G4", "E4", "C4"],
            durations=[0.5, 0.5, 0.5, 1.0, 0.5, 0.5, 1.0],
            bpm=pool.bpm,
        )

        if inst.preset:
            try:
                preset_obj = get_instrument(inst.preset)
                preset_obj.apply_to(pattern)
            except KeyError:
                print(f"   ⚠️ 预设 '{inst.preset}' 未找到，使用默认音色")

        audio = render_pattern_to_array(pattern, 4.0)
        print(f"   播放中... Ctrl+C 停止")
        sd.play(audio.astype("float32"), SR)
        sd.wait()
    except ImportError:
        print("   ⚠️ sounddevice 未安装，无法播放")
    except Exception as e:
        print(f"   ❌ 试听失败: {e}")


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

    # ── pool 子命令组 ──
    p_pool = sub.add_parser("pool", help="乐器池命令")
    pool_sub = p_pool.add_subparsers(dest="pool_command", help="pool 子命令")

    # pool list
    p_pool_list = pool_sub.add_parser("list", help="列出所有内置乐器池模板")
    p_pool_list.set_defaults(func=cmd_pool_list)

    # pool show
    p_pool_show = pool_sub.add_parser("show", help="查看乐器池详情")
    p_pool_show.add_argument("template_or_file", help="模板名或 YAML 文件路径")
    p_pool_show.set_defaults(func=cmd_pool_show)

    # pool render
    p_pool_render = pool_sub.add_parser("render", help="渲染乐器池为成品音频")
    p_pool_render.add_argument("template_or_file", help="模板名或 YAML 文件路径")
    p_pool_render.add_argument("--style", "-s", default=None,
                               help="风格预设 (exploration/battle/town/dungeon/ambient)")
    p_pool_render.add_argument("--duration", "-d", type=float, default=30.0,
                               help="时长/秒 (默认 30)")
    p_pool_render.add_argument("--key", "-k", default=None, help="调性 (如 C, Am)")
    p_pool_render.add_argument("--bpm", "-b", type=int, default=None, help="BPM")
    p_pool_render.add_argument("--format", "-f", default="wav",
                               choices=["wav", "ogg", "flac"],
                               help="导出格式 (默认 wav)")
    p_pool_render.add_argument("--output", "-o", default=None,
                               help="输出文件路径")
    p_pool_render.add_argument("--stems-only", action="store_true",
                               help="仅导出分轨，不混音")
    p_pool_render.set_defaults(func=cmd_pool_render)

    # pool create
    p_pool_create = pool_sub.add_parser("create", help="创建自定义乐器池")
    p_pool_create.add_argument("name", help="乐池名称")
    p_pool_create.add_argument("--add", "-a", action="append",
                               help="添加乐器 (格式: role:preset, 如 melody:piano)")
    p_pool_create.add_argument("--bpm", type=int, default=None, help="BPM")
    p_pool_create.add_argument("--key", default=None, help="调性")
    p_pool_create.add_argument("--scale", default=None, help="音阶类型")
    p_pool_create.add_argument("--save", "-o", default=None,
                               help="保存路径 (默认 <name>.yaml)")
    p_pool_create.set_defaults(func=cmd_pool_create)

    # pool preview
    p_pool_preview = pool_sub.add_parser("preview", help="试听乐器池中的乐器")
    p_pool_preview.add_argument("template_or_file", help="模板名或 YAML 文件路径")
    p_pool_preview.add_argument("--instrument", "-i", default=None,
                                help="乐器角色或名称 (如 melody)")
    p_pool_preview.set_defaults(func=cmd_pool_preview)

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
    elif args.command == "pool":
        if hasattr(args, "func"):
            return args.func(args)
        else:
            p_pool.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
