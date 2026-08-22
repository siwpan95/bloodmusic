# BloodMusic 深度项目评估报告

**日期**：2026-08-22
**场景**：深度项目评估（代码质量/架构 + 产品/文档一致性 + 安全审计 + 测试与质量门禁）
**评估方式**：主理人直调模式（本环境 Agent 子代理工具依赖 TeamCreate，不可用；由主理人沽思航独立完成四维度静态审查 + 实测验证）
**项目**：BloodMusic v2.0.0 — 程序化游戏音频合成引擎
**路径**：`G:\tools\audio\bloodmusic`
**规模**：225 个 `.py`、61,362 行（不含 venv/git）；14+ 子包

---

## 📌 TL;DR（执行摘要）

- **整体结论**：🟢 **通过（Go，条件发布：清理中危技术债 + 补齐 CI）**
- **无高危/严重问题**：未发现 RCE、命令注入、路径穿越、令牌泄露到代码或日志的风险点
- **阻塞项数量**：0
- **历史评估（2026-08-13）提出的 7 项风险已全部实际治理**（本次独立审查确认）
- **下一步重点**：清理 deprecated 双实现与 `archive/` 残留、收敛 `_safe_stem` 三处重复、补齐 CI、修复 `damping_hz=0` 除零

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| Go / No-Go | 🟢 Go（发布前清理中危技术债即可） |
| 严重度分布 | 🔴 0 / 🟠 0 / 🟡 5 / 🟢 4 |
| 关键行动项 | 6 条 |
| 建议负责人 | 全哥（独立开发者） |
| 维度评分 | 代码质量 88 · 安全 90 · 测试 82 · 产品/文档 90 |

---

## 1. 各维度核心结论

### 🔧 1.1 代码质量与架构健康（investigator 视角）
- **基线良好**：全仓无裸 `except:`；数值稳定性在 `oscillator/voice/fm/granular` 多处 `np.clip` 防护；`waveguide` 用 `np.nan_to_num` 处理 NaN；序列化走结构化 dataclass，无 `eval/pickle`。
- **技术债信号**：
  - `music/midi_io.py` 的旧 MIDI I/O 与 `bridge/midi_import.py` v2 双轨并存（`midi_io.py` 已标 `@deprecated`，但未删除）。
  - `archive/album_generator.py` 残留 deprecated 模块（历史报告称"已移入 archive/ 解决"，但模块仍带 deprecated 标记未清理）。
  - `_safe_stem` 在 `album_maker/track.py`、`bridge/renderer.py`、`mirror/renderer.py` **三处完全重复实现**（应抽为共享工具）。
- **性能**：`core` 大量向量化（`np.cumsum`/`clip`），整体偏向量化；但除 `interactive` 引擎外，缺少对逐样本 Python 循环热点的系统性基准。

### 🎯 1.2 产品架构与文档一致性（product-reviewer 视角）
- **文档体系完备**：README / PRD / ARCHITECTURE / system_design(66KB) / 多份 mermaid 类图时序图，与代码高度一致。
- **功能声称可实证**：README 宣称的 `pool` CLI 子命令、GUI 工作站、autowav/vocal_tts、mirror 镜像层、games/zhuangtaiji 真实引擎接入——均实测存在于代码。
- **历史 7 项风险已实际治理**：sfx 爬虫已剥离、硬编码路径改环境变量（`BLOODMUSIC_AUDIO_PIPELINE` 等）、GUI 已补强（钢琴卷帘/音序器落地）、实时性能已有 benchmark 验证。
- **轻微**：`archive/` 残留与 deprecated 双实现说明"范围收敛"仍在进行中，尚未完全收口。

### 🛡️ 1.3 安全审计（security-officer 视角）
- **无危险反序列化**：全仓未命中 `eval/exec/pickle/yaml.load/shell=True`。
- **subprocess 全部列表形式（无注入）**：
  - `autowav/vocal_tts.py`：SAPI 调用用 `["powershell", ..., "-Command", ps]` 列表形式，且 `text/voice/out_path` 经 `_powershell_quote()` 做 PowerShell 单引号转义（杜绝命令注入）；Piper 把文本写入临时文件再 `--input_file` 传参（非命令行注入）。
  - `remix/core/video_processor.py`：ffmpeg/ffprobe 全部列表形式、非 `shell=True`、`CREATE_NO_WINDOW`。
- **序列化信任边界**：compact 串（`bm1:` + zlib + base64url）按 dataclass 字段结构化还原，**无 RCE**；仅篡改字段索引可致 `IndexError`（低危健壮性，非安全漏洞）。
- **GITEE_TOKEN 处理规范**：仅内联到本次 HTTP URL、不写盘/不进日志；文档明确 `--token` 会短暂出现于进程列表。小风险：令牌经 Gitee API 的 URL query 传送（服务端访问日志可能记录）。
- **文件 IO 防穿越**：`_safe_stem` 白名单 `isalnum/_/-` 并 `strip("_")`，生成 basename 不含 `/` 或 `..`，无法路径穿越。

### ✅ 1.4 测试与质量门禁（qa-lead 视角）
- **测试健康**：`tests/` 全量收集 **584 个用例、无收集错误**；抽样运行 `test_core/effects/music/export/serialize` → **151 passed**（14.4s）。
- **slow 策略规范**：渲染/端到端用例标记 `@pytest.mark.slow`，默认跳过，需 `--runslow` 显式运行（conftest 实现正确）。
- **质量门禁缺口**：**缺 CI**（无 `.github/workflows`、tox.ini、pre-commit）。
- **pytest 可发现性小坑**：根目录直接 `pytest` 仅收集 `album_maker/tests` 的 26 个用例，需显式 `pytest tests/` 才全量——疑似 rootdir/测试路径推断配置问题，易让开发者误以为"只有 26 个测试通过"。

---

## 2. 综合审查发现（去重合并，按严重度）

| # | 严重度 | 类别 | 位置 | 问题描述 | 建议 | 来源 |
|---|--------|------|------|---------|------|------|
| 1 | 🟡 | 健壮性 | `core/karplus_strong.py:173` | `1.0/(2π·damping_hz)` 在 `damping_hz=0` 时除零产生 inf | 对 `damping_hz` 做 `max(eps, …)` 钳制或参数校验 | investigator |
| 2 | 🟡 | 技术债 | `music/midi_io.py` vs `bridge/midi_import.py` | 旧 MIDI I/O（deprecated）与 v2 双轨并存，未清理 | 删除旧 `midi_io.py` 或改为显式 re-export 转发 | investigator |
| 3 | 🟡 | 技术债 | `archive/album_generator.py` | deprecated 模块残留未真正清理 | 确认无引用后删除，或归档为独立历史分支 | investigator |
| 4 | 🟡 | 技术债 | `track.py:395` / `bridge/renderer.py:112` / `mirror/renderer.py:63` | `_safe_stem` 三处完全相同实现 | 抽为 `bloodmusic.util.safe_filename` 共享工具 | investigator |
| 5 | 🟡 | 安全 | `tools/git_push_gitee.py:164,297` | Gitee 令牌经 URL query 传送（`?access_token=`），服务端日志可能记录 | 改用 Header 认证（如 `Authorization: token` 或 dulwich 凭证）；文档标注 `--token` 风险 | security |
| 6 | 🟢 | 健壮性 | `sfx/serialize.py:200-205` | compact 串字段索引被篡改会 `IndexError` | 对紧凑串长度/字段数设上限校验，越界抛友好错误 | security |
| 7 | 🟢 | 工程 | `cli.py:225-228` | `cmd_pool_render` 异常时 `traceback.print_exc()` 调试残留 | 改为 logging 或精简错误提示 | investigator |
| 8 | 🟢 | 测试 | 根目录 pytest 配置 | `pytest` 仅收集 album_maker 26 用例，需 `pytest tests/` 才全量 | 在 pyproject 显式设 `testpaths = ["tests","album_maker/tests","games/zhuangtaiji/test"]` | qa |
| 9 | 🟢 | 安全 | `tools/git_push_gitee.py:16` | `--token` 明文出现在进程列表 | 文档持续强调环境变量优先（已做，保持） | security |

---

## ✅ 行动清单

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | 清理 deprecated 双实现：删除/转发 `music/midi_io.py`、移除 `archive/album_generator.py` | 全哥 | P1 | 下次提交 |
| 2 | 收敛 `_safe_stem` 三处重复为 `bloodmusic.util.safe_filename` 共享函数 | 全哥 | P1 | 下次提交 |
| 3 | 修复 `karplus_strong` `damping_hz=0` 除零（钳制 + 校验） | 全哥 | P1 | 下次提交 |
| 4 | 补齐 CI：GitHub Actions 跑 `pytest` + pre-commit（ruff/black）；pyproject 设 `testpaths` 修复可发现性 | 全哥 | P1 | 发布前 |
| 5 | Gitee 推送改 Header 认证，避免令牌进 URL query；在 README 强化"环境变量优先"提示 | 全哥 | P2 | 发布前 |
| 6 | compact 串加长度/字段数上限校验 | 全哥 | P2 | 后续迭代 |

### 修复执行状态（2026-08 收尾批次）

| 行动 | 状态 | 落地位置 |
|------|------|---------|
| #3 karplus damping_hz=0 除零 | ✅ 已修复 | `core/karplus_strong.py`（`damping_hz>0` 守卫，否则 `alpha=0.0`）+ `tests/test_core_karplus.py` 回归用例 |
| #6 compact 串字段数越界 | ✅ 已修复 | `sfx/serialize.py`（字段索引越界抛友好 `ValueError`）+ 篡改用例 |
| #7 cli traceback 残留 | ✅ 已修复 | `cli.py`（`cmd_pool_render` 移除 `traceback.print_exc()`） |
| #8 根目录 pytest 可发现性 | ✅ 已修复 | `pyproject.toml` `testpaths = ["tests","album_maker/tests"]`；`games/zhuangtaiji/test` 为独立验证脚本（模块级执行 + 重写 sys.stdout，非 pytest 用例），已排除出收集并加 `pytest` 守卫与路径引导，脚本直跑恢复正常 |
| #4 _safe_stem 三处重复 | ✅ 已修复 | 新增 `util.py::safe_filename`；`album_maker/track.py`、`bridge/renderer.py`、`mirror/renderer.py` 统一调用 |
| #2 midi_io 双实现 | ✅ 已修复 | `music/midi_io.py::midi_to_patterns` 纯转发 `bridge.midi_import.midi_to_patterns_v2`；导出函数保留 |
| #3 archive/album_generator.py | ✅ 已移除 | 文件删除（历史保留于 git）；`tests/test_album_generator_integration.py` 收口为乐池/SKILL 集成测试；SKILL.md 引用更新 |
| #5 Gitee 令牌 Header 认证 | ✅ 已修复 | `tools/git_push_gitee.py`：API 校验改 `Authorization: Bearer` 头；git 传输由 dulwich 以 Basic 认证头发送（`username`/`password` kwargs，实测三种方式均 200）；令牌不再进入任何 URL |
| #4 补齐 CI | ✅ 已落地 | `.workflow/bloodmusic-ci.yml`（Gitee Go 流水线，官方 schema：push/PR 到 master 触发，`build@python` 跑 `pip install -e .` + `python3 -m pytest`）+ `.pre-commit-config.yaml`（ruff lint/format）+ pyproject `[tool.ruff]` |
| 顺带修复 | ✅ | `.gitignore` 补 `.venv/`（此前 dry-run 会把 2.1 万个 venv 文件纳入推送清单）；`tests/test_bridge.py` R7 扫描改白名单（原 deny-list 扫进 `.venv` 第三方源码，产生 4 个 SyntaxWarning，现 0 警告且更快） |

---

## ⚠️ 已知局限与历史报告核对

- **历史 `docs/EVALUATION_REPORT.md`（2026-08-13）+ 2026-08-21 整改跟进**：原 7 项风险（sfx 爬虫合规、范围蔓延、实时性能、GUI 滞后、测试瑕疵、署名许可、硬编码路径）全部标记为"已解决"。本次**独立审查确认**：sfx 爬虫全家桶已剥离（全仓 grep 无 `crawl/playwright/stealth` 残留）、硬编码路径已改环境变量、GUI 已补强、实时性能已有 `benchmarks/` 验证。
- **本次新发现、历史报告未覆盖的中危项**：`damping_hz` 除零、deprecated 双实现并存、`_safe_stem` 三处重复、Gitee 令牌 URL query 传送——均属"已治理项目上的残留技术债"，非回归。
- **实时性能边界**：`benchmarks/` 报告 2–6 层 1.13~1.49ms/帧（60fps 可行），但真实游戏引擎端到端音频延迟未经独立第三方基准验证。✅ **本次已闭环**：新增独立实测 `benchmarks/bench_realtime_e2e.py`（真实状态源 = zhuangtaiji GenericStateMachine → `AdaptiveBGM`；真实设备 = sounddevice/PortAudio 默认输出），测量 CPU 合成、设备输出缓冲、状态切换响应三类延迟，详见下方附录。结论：CPU 远非瓶颈（亚 5ms/帧），**真实端到端延迟由音频输出设备/缓冲（本机蓝牙 90–180ms）与 `transition_duration=3.0s` 过渡平滑共同主导**，与 `benchmarks/report.md` 量级交叉一致。

---

## 📡 附录：真实游戏引擎端到端延迟独立实测（补测，2026-08-22）

**脚本**：`benchmarks/bench_realtime_e2e.py`（新增，独立于 `bench_engine.py`）
**真实状态源**：zhuangtaiji `GenericStateMachine`（外部 FSM）→ `bloodmusic_audio.AdaptiveBGM` 桥 → `RealtimeMusicEngine`（即 `games/zhuangtaiji/demo_adaptive_music.py` 的端到端路径）
**真实音频设备**：sounddevice / PortAudio 默认输出 = 蓝牙耳机 *blu&blue e300* @ 44100Hz
**环境**：Python 3.14.7 / numpy 2.5.2（CPU 实测机与 `benchmarks/report.md` 的 3.14.6 机不同，仅可比量级）

### A. CPU 合成耗时（process_frame 仅计时，无设备）— 与 `benchmarks/report.md` 交叉验证

| 配置 | 本次 P95 | 既有报告 P95 | 结论 |
|------|----------|-------------|------|
| 2 层 / 512 | 2.31 ms | 4.72 ms | 同量级，均 << 16.6ms |
| 5 层 / 512 | 3.01 ms | —（报告测 4/6 层） | 亚 5ms，60fps 可行 |
| 8 层 / 128 | 1.57 ms | 1.61 ms | 几乎一致 |

> 全部配置 P95 ≤ 5.15ms，远低于 60fps 预算 16.6ms。**CPU 合成非瓶颈**（与既有报告量级一致，确认稳健）。

### B. 真实设备输出延迟（sounddevice 实际打开 OutputStream）

| buffer | 每帧音频 | stream.latency（实测） |
|--------|----------|------------------------|
| 128 | 2.9 ms | 182.9 ms |
| 256 | 5.8 ms | 203.2 ms |
| 512 | 11.6 ms | 209.0 ms |

> PortAudio 默认低延迟模式 90ms、高延迟模式 180ms。**设备输出缓冲是端到端延迟的绝对主导项**，本机蓝牙设备尤高。

### C. 真实 FSM 事件 → 音频响应（引擎日志定响应帧，RMS 持续偏离定声学 onset）

- explore → combat（自然事件 `enemy_spotted`）：基线 RMS 0.0533（σ 0.0194）→ 战斗稳态 0.0804（**仅 1.51×**）；**引擎命令→合成响应同帧即时（0 帧）**；可感知起点（越过 RMS 中点，持续≥3帧）≈ 2148ms；明显偏离（>基线+1σ）≈ 2368ms；CPU 合成 1.73ms/帧（p95 2.95ms）。
- 参考 explore → boss（高对比）：稳态 RMS 0.1195（2.11×）；可感知起点 ≈ 2287ms，明显偏离 ≈ 1765ms。
- **端到端可闻延迟（buffer 512）**：变化「开始合成」可闻 ≈ 209ms（即时响应 + 设备缓冲）；「开始可感知」可闻 ≈ 2357ms；「明显可辨」可闻 ≈ 2577ms；过渡完全收敛 ≈ 3000ms（`transition_duration` 设计值）。

### 结论

1. **CPU 合成**：亚 5ms/帧，占端到端可忽略。
2. **设备输出缓冲（本机 90–180ms）** 与 **3.0s 过渡平滑** 共同主导真实端到端延迟；探索→战斗声学对比仅 1.51×，清晰可感知需 ~1.5s 爬升。
3. **原 `bench_engine.py`「仅测 CPU、不含设备 I/O」边界已闭环**——真实端到端延迟由音频后端与过渡设计决定，而非层密度。游戏实时集成优先级：(1) 低延迟音频后端（有线/WASAPI 独占/ASIO，~10–20ms）；(2) 按需缩短 `transition_duration`；(3) 而非降层密度（CPU 富余）。
4. **局限**：CPU 实测机与原报告机不同（仅可比量级）；设备延迟依赖本机蓝牙输出（偏高），换低延迟设备显著改善；声学 onset 以 RMS 持续偏离判定，阈值与过渡曲线相关。

完整数据见 `benchmarks/report_e2e.md`。

---

## 📚 审计方法索引

- **静态审查**：Grep 全仓扫描 `TODO/FIXME/裸 except/eval/exec/pickle/subprocess/GITEE_TOKEN`；Read 核心文件（`sfx/serialize.py`、`tools/git_push_gitee.py`、`autowav/vocal_tts.py`、`remix/core/video_processor.py`、三处 `_safe_stem`、`core` 数值处理）。
- **实测验证**：`pytest --collect-only` 全量收集（584 用例无错）；抽样运行 `test_core/effects/music/export/serialize`（151 passed）。
- **文档核对**：README / PRD / ARCHITECTURE / system_design / 历史 EVALUATION_REPORT 与代码交叉验证。

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。
