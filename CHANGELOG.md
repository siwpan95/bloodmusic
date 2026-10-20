# Changelog

本项目所有值得注意的变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.1.1] - 2026-10-20

### Fixed

- **版本号漂移**：包根 `__init__.py` 的 `__version__` 此前硬编码为 `"2.0.0"`，
  而 `pyproject.toml` 已升到 `2.1.0`，导致 `pip install bloodmusic` 后
  `bloodmusic.__version__` 与 `bloodmusic --info` 对外自报旧版本 `2.0.0`。
  现改为**单一真源**：`pyproject.toml` 通过
  `[tool.setuptools.dynamic] version = {attr = "bloodmusic.__version__"}` 动态读取，
  只改 `__init__.py` 一处即可，结构上不可能再漂移。
- 补充 `tests/test_integration.py` 两个守卫用例：锁死「pyproject 不得再写静态
  `version`」的结构，以及安装态下 `__version__` 必须等于发行包元数据版本。

## [2.1.0] - 2026-10-20

### Added

- **`bloodmusic.workstation` 子包（整合自 station 引擎层）**：将仓库 `station`
  中 bloodmusic 此前缺失的音频引擎能力沉淀为新子包，去除对 station domain/GUI/VST
  桩的耦合：
  - `nodes`：音频节点图（Kahn 拓扑排序 / DFS 无环检测 / 多通道总线）。
  - `commands`：命令模式系统（线程安全 `CommandBus` / undo / 宏录制回放）。
  - `ring_buffer`：无锁 SPSC 环形缓冲（实时音频流）。
  - `dsp_utils`：纯函数 DSP 工具（混音 / 增益 / 声伴 / 波形生成）。
  - 新增 `tests/test_workstation.py`（15 例）覆盖四模块核心行为。
  - station 远端仓库（`siwpan/station`）已删除，能力并入本仓。

## [Unreleased]

### Changed

- **仓库改名：`audio-generation` → `bloodmusic`**（2026-10-20，历史遗留问题清理）。
  此前仓库名与 PyPI 发行名 / 导入包名三者不一致：仓库叫 `audio-generation`、包叫
  `bloodmusic`，导致「`pip install audio-generation` 是错的」「本地目录名含连字符不是
  合法包名」这类反复踩的坑。现统一为 **仓库名 = 发行名 = 导入名 = `bloodmusic`**。
  - Gitee 仓库地址同步为 `siwpan/bloodmusic`。原仓库因启用了 Gitee Go
    （`.workflow/bloodmusic-ci.yml`）而被平台禁止修改 URL 路径，且该限制无法通过
    API 解除（改 path 返回「改仓库开启了 Gitee Go 服务」，`gitee_go` 端点 GET/POST/PUT
    全 405、DELETE 404）。故采取**删除旧仓重建**：新仓 `siwpan/bloodmusic` 为全新仓库，
    旧地址不再重定向，请以新地址为准。历史 issue/PR 原本均为 0 条；v1.0.0 发行版
    与其附件已在新仓重建。
  - 本地目录 `G:\repos\audio-generation` → `G:\repos\bloodmusic`；
    `bloodmusic_dev.pth` 同步指向新路径。
  - 本仓内所有路径/URL 引用已更新。历史产物里的旧路径（`automations/output/`、
    `_smoke_output/` 等）**保持原样**——那是当时生成的真实记录，回改等于伪造。

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
- 发布面：gitee [siwpan/bloodmusic](https://gitee.com/siwpan/bloodmusic) release `v1.0.0`（BloodMusic 程序化音频引擎 v1.0.0）。
  （原发布于 `siwpan/audio-generation`，仓库改名重建后发行版已迁至新地址。）