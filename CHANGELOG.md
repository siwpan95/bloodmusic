# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **host-js/ Cordis 插件宿主（Phase A）**：进程外 Node 宿主，Python 引擎作
  JSON-RPC stdio 子进程；`ctx.bloodmusic` 核心服务 + sfx/album/mirror/autowav
  四个 inject 声明式插件；cordis.json 声明式装载；`--check`/`--dump-config`/
  `--list-services`/`--call` CLI 门禁；`tests/run-all.mjs` 端到端验收 10 项
  （含 inject 响应式与 Fiber 回收无孤儿进程实证）。设计与借鉴记账见
  docs/PLAN_cordis_host.md。cordis 依赖（4.0.0-rc.10 + plugin-loader rc.7）
  复用自本机 players-unified，随仓置于 host-js/node_modules。
- **host-js/python/list_media.py（P1 生态收编）**：BloodMusic 媒体枚举器，
  产出跨端 MediaItem[] 契约（players-unified 第四来源消费，实测聚合 36 项）。
- **interactive/service.py（Phase B-lite / 评审 P2）**：mini-Context（cordis 语义
  的 Python 实现，形态借鉴 alloy/core/context.py，MIT）+ MusicEnginePlugin
  （music.engine/state_machine/mapper/mixer 四服务）+ replace_state_machine
  运行时热替换（引擎不重启、状态继承）。新增 tests/test_interactive_service.py
  20 项测试。

### Changed

- **打包结构改造（命名空间包）**：`pyproject.toml` 改用 `package-dir` 映射，把
  `core/ effects/ music/ sfx/ export/ playback/ gui/ bridge/ album_maker/ pipeline/
  interactive/ autowav/ mirror/` 收进 `bloodmusic` 命名空间。此前它们以**顶层名**
  装入 site-packages，其中 `core` `music` `export` `gui` `pipeline` `mirror`
  过于通用，会与他人环境中的同名包冲突（只在别人 `pip install` 时才暴露，
  本机因是 editable 安装而未显现）。改造后 wheel 顶层仅剩 `bloodmusic/`。
- `__init__.py` 新增**扁平导入兼容垫片**：把包目录加回 `sys.path`，使历史写法
  `from core import ...` 在安装后仍能解析（与 `autowav/__init__.py` 保留扁平
  模块名的既有做法一致）。注意：用了 `..` 跨包相对导入的子包（如 `music`）
  扁平加载本来就不成立，改造前后行为一致。
- `pyproject.toml` 补 `readme` 字段 —— 此前缺 `long_description`，PyPI 页面无描述。
- `.gitignore` 补 `build/`、`dist/`。
- 已发布测试版至 TestPyPI：<https://test.pypi.org/project/bloodmusic/2.0.0/>

### Fixed

- **pytest 全套件收集错误（583 项 → 0）**：仓库根即 bloodmusic 包根（flat 布局）
  与 pytest Package 收集器结构性冲突（根 `__init__.py` 被以顶层模块导入，相对
  导入崩）；修法 = 根与 album_maker 的 `__init__.py` 加 `__package__` 守卫，
  包导入行为零改变。pytest 8.4.2 / 9.1.1 双版本验证；基线 559 passed /
  4 failed（album_maker 环境依赖+顺序污染，前置存在）/ 59 skipped。

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/audio-generation](https://gitee.com/siwpan/audio-generation) release `v1.0.0`（BloodMusic 程序化音频引擎 v1.0.0）。