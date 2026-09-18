# PLAN — host-js：BloodMusic 的 Cordis 插件宿主（Phase A）

> 2026-09-18 · Phase A 已落地并 10/10 端到端验收通过。
> Phase B（Python 内部插件化）仅留设计方向，未实施。

## 背景与目标

BloodMusic 是纯 Python 的程序化音频合成引擎。本方案为其增加一个 **进程外
Cordis 插件宿主**（`host-js/`），把引擎能力暴露为 cordis 服务与声明式插件，
与 players-unified / pluginplayer / dict-scene-engine 的宿主生态同构，
使专辑制作、镜像混音、SFX 渲染等能力可被统一编排层（如 players-unified）
按 inject 依赖拓扑装载、热替换、回收。

**Python DSP 核心零改动**：宿主只做编排与桥接，CLI/GUI/pytest 等存量入口不受影响。

## 借鉴记账（创新三原则）

| 来源 | 许可证 | 借鉴范围 |
|---|---|---|
| cordiverse/cordis 4.0.0-rc.10 + @cordisjs/plugin-loader 1.0.0-rc.7 | MIT | 插件元框架本体（Context/Fiber/inject/Loader 语义）；依赖复用自本机 players-unified 的 node_modules（免下载、版本对齐） |
| pluginplayer/host-js（本机兄弟项目，MIT） | MIT | 「进程外 JS 插件宿主 + 服务面（ctx.player）」形态；本项目协议改为 stdio 行分隔 JSON-RPC（无端口、随进程生灭） |
| players-unified/host（本机兄弟项目，MIT） | MIT | `--check`/`--dump-config` 门禁 CLI 形态、logging exporter 接法（src/logging.mjs 照搬并标注）、对象形态插件导出等实测坑记录 |

## 架构

```
cordis 插件（inject: ['bloodmusic']）          host-js/src/plugins/0x-*.mjs
  → ctx.bloodmusic（BloodmusicService）        host-js/src/core/bloodmusic.mjs
    → JsonRpcBridge（stdio 行分隔 JSON-RPC）   host-js/src/core/bridge.mjs
      → python -u host-js/python/rpc_server.py（bloodmusic 引擎，F:\Python314）
```

### Cordis 语义落点

- **服务即插件**：`BloodmusicService extends Service`，`[Service.init]()` 启动
  Python 子进程并返回清理函数 —— Fiber dispose 时子进程随之被杀，
  进程生命周期由框架托管（验收 10 实证无孤儿进程）。
- **inject 响应式**：四个功能插件 `inject: ['bloodmusic']`。禁用核心服务条目 →
  依赖插件自动离开 ACTIVE；恢复 → 自动重载并自检（验收 09 实证）。
- **声明式装载**：`cordis.json` 是唯一配置源；`--dump-config` 打印实际启动后的
  插件树，`--check` 做启用条目全 ACTIVE + ping 门禁。
- **事件面**：Python `progress` 通知 → `bloodmusic/progress`；子进程异常退出 →
  `bloodmusic/exit`；插件自检 → `bloodmusic/capability-ready`。

### 关键设计决策（含踩坑记录）

1. **cordis rc.10 没有 `ctx.stop()`**。根 Fiber 的 `dispose` 语义是「重启」而非关停
   （`packages/core/src/fiber.ts` root 分支：`this.dispose = () => this.restart()`）。
   正确关停 = 逆序串行 dispose 顶层条目 + dispose Loader fiber
   （见 `src/boot.mjs stopHost`）。
2. **插件必须对象形态导出**（`{ name, inject, apply }`）。函数形态 + 模块级
   `export const inject` 会被 loader 的 `unwrapExports()` 丢弃（players-unified 实测坑）。
3. **stdout 协议纪律**：rpc_server.py 的 stdout 只走 JSON-RPC；被调库
   （如 autowav.py）直接 print 会污染协议通道 —— 处理器执行期间
   `contextlib.redirect_stdout(sys.stderr)`。
4. **bloodmusic 包锚点**：子包内部全用相对导入（`from ..core...`），平铺导入
   必炸。优先用 editable 安装；无安装时在进程内以
   `spec_from_file_location(submodule_search_locations=[repo])` 合成包锚点。
5. **album_maker 外部依赖**：`track.py` 默认指 `G:\tools\audio\*`（本机不存在）。
   rpc_server 启动时按环境变量缺省注入本地实有路径
   `G:\repos\audio-pipeline`（mixdown.py）+ `G:\repos\remix`（core/audio_mixer），
   不覆盖用户显式配置。
6. **RPC 产物默认落临时目录**（`%TEMP%/bloodmusic-rpc/`），不写仓库。

## 使用

```bash
cd host-js
node src/index.mjs                 # 常驻宿主（打印插件树与服务面）
node src/cli.mjs --check           # 门禁：启用条目全 ACTIVE + ping
node src/cli.mjs --dump-config     # 实际启动后的插件树
node src/cli.mjs --list-services   # 服务面 + 自检状态
node src/cli.mjs --call sfx.render '{"name":"explosion"}'   # 直接调服务面
node tests/run-all.mjs             # 端到端验收（10 项）
```

配置：`host-js/cordis.json`。Python 解释器默认 `F:\Python314\python.exe`，
可用环境变量 `BLOODMUSIC_PYTHON` 或 cordis.json 的 config.python 覆盖。

## 验收记录（2026-09-18，全部实跑）

`node tests/run-all.mjs` → **10 通过 / 0 失败**：

| # | 项 | 证据 |
|---|---|---|
| 01 | cordis.json 5 条目全 ACTIVE | collectEntries 断言 |
| 02 | 核心服务 ping | python 3.14.7 / repo 路径回显 |
| 03 | 四服务面已 provide | ctx['bloodmusic.sfx'|'album'|'mirror'|'autowav'] 非空 |
| 04 | sfx 清单 + explosion 渲染 | 40+ 预设；WAV RIFF 头 + 时长校验 |
| 05 | album 风格 + quick 单曲（lofi/4 小节/seed42） | WAV 存在且合法 |
| 06 | mirror 清单 + remix（4 小节/seed42） | 65 风格/24 混音师；song_final.wav 校验 |
| 07 | autowav generate(4s) + SAPI speak | WAV 存在且合法 |
| 08 | progress start/done 事件 | 渲染期间事件流断言 |
| 09 | inject 响应式 | 禁用核心→4 插件离 ACTIVE；恢复→自动重载+ping 通 |
| 10 | Fiber 回收 | stopHost 后 python pid 不存在（无孤儿） |

Python 主套件（pytest）零回归依据：本 Phase 只新增 `host-js/`（未跟踪目录），
不改动任何被跟踪文件；套件当前在本机的收集错误（pytest 9.1.1 将仓库根
`__init__.py` 以顶层模块 `__init__` 导入导致 583 项同源 ImportError）
为前置存在的环境问题，与本次改动无关（错误签名单一、不涉及 host-js 任何文件）。

## Phase B 设计方向（未实施）

把 Python 侧的 core/effects/music/sfx/mirror 等收编为声明式插件体系
（cordis 语义的 Python 实现：Context 服务注入 / Fiber 生命周期 / inject
拓扑加载）。待 Phase A 在生态内跑稳后再评审开工。
