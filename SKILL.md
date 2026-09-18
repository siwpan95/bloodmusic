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
- host-js/：Cordis 宿主（2026-09-18 Phase A，见 docs/PLAN_cordis_host.md）
- cli.py / main.py / __main__.py / pyproject.toml

## 常用命令
- 测试：python -m pytest tests -q
- CLI：python cli.py --help / python -m bloodmusic

## 已知陷阱
- **music/sampler.py 是兼容层**：v2.0 镜像架构重构（7af5092）时删除，2026-08-23 为 audio_pipeline 恢复（Sample/SamplePad/load_sample/render_sampler_pattern）；audio_pipeline 迁到 PoolRenderer/InstrumentPool 后可再删
- v2.0 新 API：InstrumentPool/PoolRenderer（mirror 层），新代码走新 API
- editable 安装：改代码立即生效，无需重装
- **host-js 陷阱**（详见 docs/PLAN_cordis_host.md「关键设计决策」）：cordis rc.10 无 ctx.stop()（根 fiber dispose=重启，关停用 boot.mjs stopHost）；插件必须对象形态导出（{name,inject,apply}，函数形态 inject 会被 unwrapExports 丢弃）；rpc_server.py stdout 只走协议（库 print 一律 redirect 到 stderr）；bloodmusic 子包全是相对导入，必须包身份导入（_ensure_bloodmusic 包锚点）；album_maker 外部依赖默认指 G:\tools\audio\*（本机缺失），rpc_server 缺省注入 G:\repos\audio-pipeline + G:\repos\remix
- **pytest 修复（2026-09-18 P0）**：仓库根即包根 + pytest Package 收集器会以顶层模块导入根 `__init__.py`（目录名 audio-generation 含连字符非合法包名）→ 相对导入崩、583 项收集错误。已修：根/album_maker `__init__.py` 加 `__package__` 守卫（勿删，冻结门禁以已审计提交放行）；tests/__init__.py 保留。pytest 8/9 均可跑；跑法 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest`（本机 langsmith/aiohttp 插件链断，禁自动加载规避）。基线：559 passed / 4 failed（album_maker 环境依赖 mixdown+顺序污染，单跑可过，前置存在）/ 59 skipped。
