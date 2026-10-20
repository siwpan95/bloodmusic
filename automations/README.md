# BloodMusic 自动化脚本（automations/）

纯本地、项目内实现的自动化脚本集合，服务 BloodMusic v2.0.0 的两条主线：
**内容生成（6 引擎 × 12 风格全功能覆盖）** 与 **工程侧质量门禁**。
不涉及任何外部项目、外部仓库或外部发布（无 Gitee 推送、无 musickit 同步、无网易云发布）。

## 运行环境
- 解释器：`F:\Python314\python.exe`（已装齐 numpy/scipy/sounddevice/soundfile/mido/pyyaml/pytest），
  可用环境变量 `BM_PYTHON` 覆盖。
- `bloodmusic` 可导入性由 **目录联接 + .pth** 保证（非 editable pip）：
  - `F:\Python314\Lib\site-packages\bloodmusic` → junction → `G:\repos\bloodmusic`
  - `F:\Python314\Lib\site-packages\bloodmusic_dev.pth` 内容 `G:\repos\bloodmusic`
    （满足仓库内 `import core` / `import music` 等兄弟包绝对导入）
  - ⚠️ 本机 `F:\Python314` 的 pip 在「写盘/解包/卸载」阶段会卡死（已多次实测超时 kill），
    **脚本不做任何 pip 安装/自修复**，只做导入检测（`ensure_bloodmusic()`）。
- 混音阶段依赖（关键）：`album_maker` 的母带混音 `_mixdown` 延迟 `from mixdown import mixdown`，
  该模块来自 **项目内置的 `pipeline/`**（audio_pipeline），其内部经 `pipeline/config.bootstrap_env()`
  把项目内置的 `remix/`（提供 `core.audio_mixer` / `core.audio_loader`）注入 sys.path。
  `common.py` 默认把 `BLOODMUSIC_AUDIO_PIPELINE` / `BLOODMUSIC_REMIX` 指向仓库内目录，
  因此**内容生成完全本地、不依赖仓库外部的音频工具目录**，可被同名环境变量覆盖。
- 所有产物落在 `automations/output/`（已被根 `.gitignore` 忽略），报告在 `automations/output/reports/`。

## 脚本一览
| 脚本 | 内容 | 触发建议 |
|------|------|----------|
| `content_pipeline.py` | C1 整专辑生成 + C2 风格覆盖(12) + C2 引擎覆盖(6) + C5 autowav + C8 质量巡检 | 每周 |
| `qa_pipeline.py` | T1 回归测试 + T2 流水线测试 + T3 ruff 扫描(album_maker/automations)（+T4 基准，需 `BM_BENCH=1`） | 每日 |
| `run_all.py` | 串联 content + qa，退出码汇总 | 手动/按需 |
| `common.py` | 共享工具：路径/解释器/导入检测/WAV 巡检/报告写入/混音依赖 env | 被依赖 |

## 直接运行
```bash
# 内容流水线
F:/Python314/python.exe automations/content_pipeline.py

# 工程侧流水线（含基准：BM_BENCH=1）
BM_BENCH=1 F:/Python314/python.exe automations/qa_pipeline.py

# 全量
F:/Python314/python.exe automations/run_all.py
```

## 报告
- `automations/output/reports/content_report.json` / `.md`
- `automations/output/reports/qa_report.json` / `.md`

报告含：各步骤返回码、12 风格 / 6 引擎覆盖率、全部产出 WAV 的峰值(dBFS)/时长/是否静音。

## 工程侧 QA 的环境注意点
- **pytest 第三方插件**：本机额外装了 `hydra_core` / `langsmith` / `pytest_aiohttp` 等插件，其依赖
  （`antlr4` / `annotated_types` / `aiohttp`）部分损坏，会在 pytest 启动时崩溃。这些插件与
  BloodMusic 测试无关，故脚本通过 `-p no:hydra_pytest -p no:langsmith_plugin -p no:aiohttp` 关闭，
  套件本身 602 个用例可正常收集运行。
- **ruff**：`ruff` 的 PyPI 包只是薄壳，真正可执行的是 `ruff.exe` 二进制。脚本仅扫描
  `album_maker` 与 `automations`（聚焦核心相关包，避免对庞大遗留代码全量 lint 产生噪声）；
  若二进制缺失会**软跳过**（不挂死、不误报），待二进制就位后下次即生效。
- **pydub/ffmpeg 警告**：WAV 导出走 `wave`/numpy，不依赖 ffmpeg；仅 ogg/flac 需要。
  `remix/bin/` 已内置 `ffmpeg.exe`/`ffprobe.exe`，无害警告可忽略。

## 已注册的定时任务（WorkBuddy automation，均为 ACTIVE）
> 脚本已验证可端到端运行（run_all EXIT=0）；两条任务已注册并由 WorkBuddy 调度执行。
- `BloodMusic 内容覆盖巡检（周）`：`FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0` → 跑 `content_pipeline.py`
- `BloodMusic 工程侧 QA（日）`：`FREQ=DAILY;BYHOUR=3;BYMINUTE=0` → 跑 `qa_pipeline.py`

> 注：本机另有 3 个 PAUSED 的无关任务（musickit 混音 / dict-scene-engine / MOBA 模拟），与本仓库无关，保持暂停。

> 注：内容生成类任务耗时较长（渲染多首曲目，约 4–5 分钟），建议排在下班后/夜间；
> 若某引擎/风格渲染失败，报告会标记 `ok=false` 并附错误，不会整体崩溃。
