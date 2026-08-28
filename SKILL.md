---
name: bloodmusic
description: Maintain the bloodmusic procedural audio synthesis engine (G:/repos/audio-generation). v2.0 mirror architecture with pool renderer and legacy sampler compat layer.
agent_created: true
---

# bloodmusic 程序化音频合成引擎维护

## 概述
程序化游戏音频合成引擎 v2.0（镜像架构）：FM/粒子/波表/物理建模 + 效果链，BGM/SFX 实时生成。独立 .git，editable 安装于 F:\Python314。消费者：alloy 引擎 audio 层、audio_pipeline、remix、musickit。

## 结构
- music/：arpeggiator/bass/harmony/pattern/instrument_pool/pool_renderer/presets/... + sampler.py（兼容层，见下）
- core/：note_utils/constants 等
- bridge/、pipeline/、autowav/、mirror/、remix/、album_maker/
- cli.py / main.py / __main__.py / pyproject.toml

## 常用命令
- 测试：python -m pytest tests -q
- CLI：python cli.py --help / python -m bloodmusic

## 已知陷阱
- **music/sampler.py 是兼容层**：v2.0 镜像架构重构（7af5092）时删除，2026-08-23 为 audio_pipeline 恢复（Sample/SamplePad/load_sample/render_sampler_pattern）；audio_pipeline 迁到 PoolRenderer/InstrumentPool 后可再删
- v2.0 新 API：InstrumentPool/PoolRenderer（mirror 层），新代码走新 API
- editable 安装：改代码立即生效，无需重装
