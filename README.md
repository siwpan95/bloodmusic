# BloodMusic — 程序化游戏音频合成引擎

全功能程序化游戏音频合成引擎，支持 BGM + SFX 实时生成、专辑制作。
纯自生成定位：全部音频由程序化合成产生，零外部采样。

## 功能

- **多波形振荡器** — saw / square / sine / triangle / noise (white/pink/brown)
- **高级合成** — FM 合成、Karplus-Strong 物理建模、Granular 粒子合成、Wavetable、减法合成
- **效果链** — 滤波器（低通/高通/带通/陷波）、EQ、压缩器、限制器、合唱、失真、混响、延迟、Flanger/Phaser
- **多轨音乐** — 旋律 + 和弦 + 鼓点 + 琶音，支持 MusicPattern / DrumPattern / MultiTrackPattern
- **乐理系统** — 音阶/调式选择、情绪映射、马尔可夫旋律生成、和弦进行
- **互动自适应引擎** — 状态机 + 分层混音 + 参数映射，适合游戏实时音乐（实测 8 层 60fps 仅 1.6ms/帧）
- **SFX 系统** — 40+ 预设（UI/卡牌/战斗/系统）+ 游戏通用 8 类（pickup/laser/explosion/power_up/hit/jump/blip/random）
- **参数序列化** — SynthVoice ↔ JSON / 紧凑短串（仿 jsfxr base58 短 URL，典型 <120 字符）
- **变异引擎** — mutate / randomize / 锁定字段（仿 bfxr lock 图标）
- **多声部混合** — mix_voices N 路加权叠加（仿 bfxr Mixer）
- **专辑制作** — 单曲（12 风格）/ 完整专辑（demo 或自定义 YAML）
- **Beat 制作** — 7 种风格（trap / boom bap / lofi / battle / drum only / edm / ambient）
- **批量导出** — WAV / OGG / FLAC，含归一化 + 限幅
- **GUI 工作站** — Tkinter 预览/导出/波形可视化/实时参数滑块
- **制作工作室 GUI** — 单曲/专辑/Beats 三页签统一界面
- **AutoWav 作曲核心**（autowav/，自 wav_music_gen 并入）— 14 调式、13 和弦进行、加权马尔可夫旋律、对位、曲式、鼓机，零依赖；Klatt 共振峰人声（8 元音吟唱/哼鸣 + 拼音韵母映射）；MIDI 导入导出桥；symbolic 默认 / acestep 可选懒加载
- **镜像层**（mirror/）— 与 musickit（纯采样混音项目）互为镜像的纯机生成混音：13 机生成声池（同名 13 池）、63 风格提示词、5 曲式模板、24 混音师签名链，license_tier 恒 selfgen（详见 docs/PLAN_mirror_2026.md）

## 快速开始

```bash
# 安装依赖
pip install numpy scipy sounddevice soundfile

# 启动 GUI 工作站（预览/导出/波形/滑块）
python main.py

# 启动制作工作室（单曲/专辑/Beats）
python main.py --maker

# CLI 入口
python -m bloodmusic

# 专辑制作
python -m bloodmusic.album_maker.cli make --demo --out ./album_output

# 镜像层：纯机生成混音（musickit 采样混音的镜像，参数同名）
python -m bloodmusic.mirror --remix --bars 16 --bpm 140 --seed 42
python -m bloodmusic.mirror --list-styles --list-mixers

# AutoWav 算法作曲（自 wav_music_gen 并入）
python -m bloodmusic.autowav --random --duration 60

# 运行测试（渲染类 slow 测试需 --runslow）
python -m pytest tests/
```

## 项目结构

```
bloodmusic/
├── core/          # 振荡器、包络、SynthVoice、FM/KS/Granular/Wavetable 合成
├── effects/       # 滤波器、失真、混响、压缩器、EQ、Chorus、Delay、Flanger
├── music/         # MusicPattern、DrumPattern、乐器池、编排渲染
├── sfx/           # 预设库、分层音效、鼓合成、序列化、变异引擎
├── interactive/   # 实时游戏音乐引擎（状态机 + 分层混音）
├── album_maker/   # 专辑制作（单曲/专辑）
├── export/        # 批量导出 WAV/OGG/FLAC
├── playback/      # sounddevice 实时预览
├── gui/           # Tkinter 工作站 + 制作工作室
├── bridge/        # DAW 桥接（MIDI 渲染）
├── autowav/       # [并入] 算法作曲 + 共振峰人声（纯 stdlib）
├── mirror/        # 镜像层：13 机生成声池/63 风格/曲式/24 混音师（musickit 镜像）
├── benchmarks/    # 实时性能基准（bench_engine.py）
├── docs/          # 产品需求文档 (PRD) + 架构设计文档 + PLAN_mirror_2026.md
└── tests/         # 单元 + 集成测试
```

## 依赖

- Python >= 3.10
- numpy, scipy, sounddevice, soundfile
- matplotlib（可选，GUI 波形可视化）
- tkinter (标准库)

## 许可

MIT License · Copyright (c) 2026 siwpan
