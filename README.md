# BloodMusic — 程序化游戏音频合成引擎

> 仓库：<https://gitee.com/siwpan/audio-generation> ｜ 许可：MIT（见 [LICENSE](LICENSE)）
> 注：文中 <PATH> 为路径占位符，请替换为你本机实际的目录 / 可执行文件路径。

[![PyPI](https://img.shields.io/pypi/v/bloodmusic)](https://pypi.org/project/bloodmusic/)
[![Python](https://img.shields.io/pypi/pyversions/bloodmusic)](https://pypi.org/project/bloodmusic/)
[![License](https://img.shields.io/pypi/l/bloodmusic)](https://pypi.org/project/bloodmusic/)

**PyPI**：<https://pypi.org/project/bloodmusic/> ｜ **仓库名 / 发行名 / 导入名统一为 `bloodmusic`**
（`pip install bloodmusic`、`import bloodmusic`、仓库 `siwpan/bloodmusic` 三者同名，
不会再出现"仓库叫什么、包叫什么"的歧义。仓库地址以 Gitee 上实际显示的为准 ——
本仓曾用名 `audio-generation`，改名后旧地址会由 Gitee 重定向。）

全功能程序化游戏音频合成引擎，支持 BGM + SFX 实时生成、专辑制作。
纯自生成定位：全部音频由程序化合成产生，零外部采样。

## 功能

- **多波形振荡器** — saw / square / sine / triangle / noise (white/pink/brown)
- **高级合成** — FM 合成、Karplus-Strong 物理建模、Granular 粒子合成、Wavetable、减法合成
- **效果链** — 滤波器（低通/高通/带通/陷波）、EQ、压缩器、限制器、合唱、失真、混响、延迟、Flanger/Phaser
- **多轨音乐** — 旋律 + 和弦 + 鼓点 + 琶音，支持 MusicPattern / DrumPattern / MultiTrackPattern
- **乐理系统** — 音阶/调式选择、情绪映射、马尔可夫旋律生成、和弦进行
- **互动自适应引擎** — 状态机 + 分层混音 + 参数映射，适合游戏实时音乐（实测 8 层 60fps 仅 1.6ms/帧）；**B-lite 服务化**（interactive/service.py）：mini-Context + 引擎四服务 + 状态机运行时热替换（Phase B-lite，docs/REVIEW_phase_b_20260918.md）
- **SFX 系统** — 40+ 预设（UI/卡牌/战斗/系统）+ 游戏通用 8 类（pickup/laser/explosion/power_up/hit/jump/blip/random）
- **参数序列化** — SynthVoice ↔ JSON / 紧凑短串（仿 jsfxr base58 短 URL，典型 <120 字符）
- **变异引擎** — mutate / randomize / 锁定字段（仿 bfxr lock 图标）
- **多声部混合** — mix_voices N 路加权叠加（仿 bfxr Mixer）
- **专辑制作** — 单曲（12 风格）/ 完整专辑（demo 或自定义 YAML）
- **Beat 制作** — 7 种风格（trap / boom bap / lofi / battle / drum only / edm / ambient）
- **批量导出** — WAV / OGG / FLAC，含归一化 + 限幅
- **GUI 工作站** — Tkinter 预览/导出/波形可视化/实时参数滑块
- **制作工作室 GUI** — 单曲/专辑/Beats/镜像四页签统一界面
- **钢琴卷帘 / 编曲音序器**（gui/piano_roll.py）— MusicPattern 音符网格（点击增删/导出 MIDI）+ SongArrangement 段落块视图，工作站一键打开
- **真实引擎接入验证**（games/zhuangtaiji/）— 多范式决策引擎 FSM 驱动 RealtimeMusicEngine 的端到端 demo（探索→战斗→BOSS→胜利自适应音乐，离线渲染 WAV）
- **AutoWav 作曲核心**（autowav/，自 wav_music_gen 并入）— 14 调式、13 和弦进行、加权马尔可夫旋律、对位、曲式、鼓机，零依赖；Klatt 共振峰人声（8 元音吟唱/哼鸣 + 拼音韵母映射）；**人声档 B：SAPI 念白**（vocal_tts，中文语音自动选择，Piper 可选降级）；MIDI 导入导出桥；symbolic 默认 / acestep 可选懒加载
- **镜像层**（mirror/）— 与 musickit（纯采样混音项目）互为镜像的纯机生成混音：13 机生成声池（同名 13 池）、65 风格提示词（Phase 2 全量精调）、5 曲式模板、24 混音师签名链、固定 stems×24 混音师专辑镜像（mirror/album.py）、制作工作室镜像页签，license_tier 恒 selfgen（详见 docs/PLAN_mirror_2026.md）
- **Cordis 宿主**（host-js/）— 进程外 Cordis 插件宿主：Python 引擎作 JSON-RPC stdio 子进程，SFX/专辑/镜像/AutoWav 四面暴露为 cordis 服务与声明式插件（inject 响应式、Fiber 托管子进程生命周期、cordis.json 声明式装载），与 players-unified/pluginplayer 宿主生态同构（详见 docs/PLAN_cordis_host.md）

## 快速开始

### 从 PyPI 安装（用库 / 用 CLI）

```bash
pip install bloodmusic            # 依赖（numpy/scipy/sounddevice/soundfile/mido）自动带上

python -c "import bloodmusic; print(bloodmusic.__version__)"
bloodmusic --help                 # CLI 入口（脚本名也是 bloodmusic）
```

### 从源码运行（开发）

> 仓库根即包根（目录名就是 `bloodmusic`），各子包由 `pyproject.toml` 的 `package-dir`
> 逐个映射进 `bloodmusic.*` 命名空间。`python -m bloodmusic` 这类按包名调用的命令
> 需要先 `pip install -e .`（或让仓库根在 `sys.path` 上）；直接跑脚本则不受影响。

```bash
# 安装依赖
pip install numpy scipy sounddevice soundfile
pip install -e .                  # 需要 python -m bloodmusic 时执行一次

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
python -m bloodmusic.mirror --build-album --style lofi --seed 42 --bars 16   # 固定 stems × 24 混音师专辑

# AutoWav 算法作曲（自 wav_music_gen 并入）
python -m bloodmusic.autowav --random --duration 60

# 人声档 B：语音念白（SAPI 零依赖，中文语音自动选择）
python -m bloodmusic.autowav.vocal_tts "你好，血音" --out n.wav
python -m bloodmusic.autowav.vocal_tts --list-voices

# 真实引擎接入验证：FSM 驱动自适应音乐（32s 探索→战斗→BOSS→胜利）
python games/zhuangtaiji/demo_adaptive_music.py
python games/zhuangtaiji/demo_adaptive_music.py --play   # 实时播放

# Cordis 宿主（Node 22+，cordis 依赖已随仓在 host-js/node_modules）
cd host-js
node src/index.mjs                 # 常驻宿主
node src/cli.mjs --check           # 门禁：启用条目全 ACTIVE + 核心服务 ping
node src/cli.mjs --call sfx.render '{"name":"explosion"}'
node tests/run-all.mjs             # 端到端验收（10 项）


# 提交+推送到 Gitee（无需 git 命令，基于 dulwich；令牌用环境变量）
# 令牌只经 HTTP 请求头传输（API 校验 Bearer / git 传输 Basic），绝不写入 URL
set GITEE_TOKEN=xxxxxxxx
python tools/git_push_gitee.py --message "feat: ..."

# 运行测试：根目录直接 pytest（testpaths 已配置 tests + album_maker/tests；
# slow 渲染/端到端用例默认跳过，需 --runslow 显式运行）
python -m pytest

# pipeline/tests 与主套件合并收集会冲突，需单独运行
python -m pytest pipeline/tests

# games/zhuangtaiji 的验证脚本（非 pytest 用例，直接运行）
python games/zhuangtaiji/test/test_verify.py
python games/zhuangtaiji/test/test_enhancements.py
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
├── gui/           # Tkinter 工作站（波形/滑块/卷帘/音序）+ 制作工作室
├── games/         # 真实引擎接入验证（zhuangtaiji FSM → 自适应音乐 demo）
├── bridge/        # DAW 桥接（MIDI 渲染）
├── autowav/       # [并入] 算法作曲 + 共振峰人声（纯 stdlib）
├── mirror/        # 镜像层：13 机生成声池/63 风格/曲式/24 混音师（musickit 镜像）
├── benchmarks/    # 实时性能基准（bench_engine.py / bench_realtime_e2e.py）
├── docs/          # 产品需求文档 (PRD) + 架构设计文档 + PLAN_mirror_2026.md
├── pipeline/      # 生成流水线（tests 需单独运行）
├── host-js/       # Cordis 宿主（Node，进程外 JSON-RPC 桥接 Python 引擎）
├── tools/         # git_push_gitee.py 等仓库工具
├── .workflow/     # Gitee Go 流水线（CI，push/PR 到 master 触发）
└── tests/         # 单元 + 集成测试
```

## 依赖

- Python >= 3.10
- numpy, scipy, sounddevice, soundfile
- matplotlib（可选，GUI 波形可视化）
- tkinter (标准库)

## 测试与 CI

- **一键回归**：仓库根目录 `python -m pytest`（testpaths = tests + album_maker/tests；slow 用例默认跳过，`--runslow` 显式运行）
- **Gitee Go 流水线**：`.workflow/bloodmusic-ci.yml`（push/PR 到 master 自动跑 `pip install -e .` + 全量 pytest）——在 Gitee 仓库「DevOps → Gitee Go → 新建流水线 → 从 Yml 导入」启用
- **本地门禁**：`.pre-commit-config.yaml`（ruff lint + format，只检查本次提交改动的文件）

## 许可

MIT License · Copyright (c) 2026 siwpan


---

## 仓库索引标注（2026-08-27 · siwpan 统一治理）

> BloodMusic 程序化音频合成引擎（现行，独立仓 siwpan/audio-generation，2026-10-20 起显示名为 siwpan/bloodmusic）；本地对应 <PATH> 旧版已转 tag。
> 本标注为发布面统一追加，不改变原有内容。
