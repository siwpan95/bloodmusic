# BloodMusic — 程序化游戏音频合成引擎

全功能程序化游戏音频合成引擎，支持 BGM + SFX 实时生成。

## 功能

- **多波形振荡器** — saw / square / sine / triangle / noise (white/pink/brown)
- **高级合成** — FM 合成、Karplus-Strong 物理建模、Granular 粒子合成
- **效果链** — 滤波器（低通/高通/带通/陷波）、EQ、压缩器、限制器、合唱、失真、混响
- **多轨音乐** — 旋律 + 和弦 + 鼓点 + 琶音，支持 MusicPattern / DrumPattern / MultiTrackPattern
- **乐理系统** — 音阶/调式选择、情绪映射、马尔可夫旋律生成
- **互动自适应引擎** — 状态机 + 分层混音 + 参数映射，适合游戏实时音乐
- **SFX 预设库** — 40+ 预设（UI / 卡牌 / 战斗 / 系统分类）
- **批量导出** — WAV / OGG / FLAC，含归一化 + 限幅
- **GUI 工作站** — Tkinter 可视化操作界面

## 快速开始

```bash
# 安装依赖
pip install numpy scipy sounddevice soundfile

# 启动 GUI
python main.py

# CLI 入口
python -m bloodmusic

# 运行测试
python -m pytest tests/
```

## 项目结构

```
bloodmusic/
├── core/          # 振荡器、包络、SynthVoice、FM/KS/Granular 合成
├── effects/       # 滤波器、失真、混响、压缩器、EQ、Chorus
├── music/         # MusicPattern、DrumPattern、MultiTrack、Arpeggiator
├── sfx/           # 40+ 预设音效
├── export/        # 批量导出 WAV/OGG/FLAC
├── playback/      # sounddevice 实时预览
├── gui/           # Tkinter 工作站界面
├── interactive/   # 实时游戏音乐引擎
├── docs/          # 产品需求文档 (PRD) + 架构设计文档
├── tests/         # 5 个测试文件
└── zhidao/        # 参考资料
```

## 依赖

- Python >= 3.10
- numpy, scipy, sounddevice, soundfile
- tkinter (标准库)

## 许可

内部项目，全哥创建。
