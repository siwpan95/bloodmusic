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

## [1.0.0] - 2026-08-27

### Added

- 首个发行版：便携源码 zip（剔除 .venv/构建产物/输出物，依赖见 README）。
- 发布面：gitee [siwpan/audio-generation](https://gitee.com/siwpan/audio-generation) release `v1.0.0`（BloodMusic 程序化音频引擎 v1.0.0）。