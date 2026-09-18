# Phase B 立项评审 —— Python 内部插件化（cordis 语义）

> 2026-09-18 · 评审人：WorkBuddy（GameAudioEngineer 视角）· 依据：Phase A 落地实测 + 代码库实测盘点
> 结论先行：**不建议全量立项；建议 B-lite（仅 interactive 层）+ 先做 Phase A 生态收编验证（P0）**

---

## TL;DR

Phase A（host-js）已经拿到了 cordis 化 80% 的价值：声明式装载、inject 拓扑、进程托管、
生态同构。Phase B 要解决的「Python 内部也插件化」，其核心卖点（运行时热替换、服务拓扑
动态重组）在 BloodMusic 的真实负载形态（单进程 CLI/批量渲染/离线专辑）里**没有消费方**；
而它的成本面（≈3.3 万行核心代码重构 + 唯一活外部消费者 audio_pipeline 的兼容风险）
是确定的、大的。**建议搁置全量 B，立项 B-lite：只把 interactive/（实时引擎层）服务化，
core/effects/music/sfx 保持纯函数库不动。**

## 结论卡

| 项 | 结论 |
|---|---|
| 全量 Phase B（13 包全部插件化） | ❌ **不立项**。价值/成本比不足，行为回归风险高 |
| B-lite（interactive/ 服务化 + mini-Context） | ✅ **可立项**，估 1–2 天，先等 P0 验证结论 |
| P0：Phase A 生态收编验证（players-unified 编排 bloodmusic） | ✅ **立即立项**，估 0.5 天，是 B-lite 的 go/no-go 依据 |
| 前置阻塞项 | pytest 9.1.1 收集错误（583 项）——任何重构前必须先修，否则无回归安全网 |

---

## 1. 证据盘点（全部实跑/实测，2026-09-18）

### 1.1 代码规模（待重构面）

| 包 | 文件 | 行数 | 性质 |
|---|---|---|---|
| core/ | 15 | 2,585 | 纯函数 DSP（振荡器/包络/FM/KS/Granular/波表） |
| effects/ | 11 | 2,259 | 纯函数效果链 |
| music/ | 25 | 11,473 | 模式/乐器池/渲染（v2.0 镜像架构核心） |
| sfx/ | 8 | 2,894 | 预设库 + 分层合成 |
| interactive/ | 6 | 1,660 | **实时引擎**（状态机 + 分层混音 + 参数映射） |
| album_maker/ | 11 | 2,724 | 批量编排（无实时语义） |
| mirror/ | 13 | 2,351 | 镜像渲染（无实时语义） |
| bridge/ | 15 | 4,747 | DAW/MIDI 桥 |
| remix/ | 10 | 2,569 | 纯机生成混音 |
| export/playback/gui | 9 | 2,000 | I/O 与 UI |
| **合计（核心，不含 autowav/pipeline 脚本）** | **≈113** | **≈34k** | |

### 1.2 外部消费者盘点（谁会被 Phase B 破坏）

| 消费者 | 依赖方式 | 实测证据 | Phase B 风险 |
|---|---|---|---|
| audio_pipeline（G:\repos\audio-pipeline） | sys.path 注入 + `bloodmusic.music.sampler` **兼容层**（Sample/SamplePad/render_sampler_pattern） | instrument_pool.py:33、source_maker.py:29、cli.py:106、tests/test_pipeline.py:73 | **高**：源码注明「零改造：仅调用，不修改其源码（R4）」——兼容层是它的工作前提 |
| alloy（G:\repos\an-engine） | **不是活依赖**：从 bloodmusic/core 提取并独立化的副本 | alloy/audio/synth.py:20 注释「从 bloodmusic/core/ 提取并独立化」 | 无（副本不受影响） |
| musickit | 无直接 bloodmusic import（镜像关系是产品语义不是代码依赖） | grep 零命中 | 无 |
| host-js（Phase A 新增） | JSON-RPC stdio，只吃 10 个方法面 | tests/run-all.mjs 10/10 | 无（协议隔离） |

### 1.3 内部先例（可复用，不必从零造）

- **alloy/core/context.py（257 行）**：已实现 `provide(key, service, dispose=)` /
  `fork()` / `dispose()` 逆序回收——Python 版 mini-cordis 语义在本机已被 alloy.trpg
  验证（484/484 全绿）。B-lite 若立项，**抄这个形态**，不引入 Node 侧任何依赖。
- dict-scene-engine：整个引擎就是 cordis 插件树（Node），但它是「应用」不是「库」——
  形态差异正是本评审的核心论据。

### 1.4 cordis 核心价值 vs BloodMusic 负载形态

| cordis 语义 | BloodMusic 哪里用得上 | 实测/推断 |
|---|---|---|
| 声明式装载（cordis.json） | ✅ 宿主层 | Phase A 已交付 |
| inject 响应式（服务消失→依赖卸载） | ✅ 宿主层 | 验收 09 实证 |
| Fiber 生命周期/副作用回收 | ✅ 子进程托管 | 验收 10 实证 |
| 运行时热替换/重载 | ⚠️ **仅 interactive/**（游戏内实时音乐引擎换装场景） | 尚无真实消费方；games/zhuangtaiji demo 是离线渲染 |
| 服务拓扑动态重组 | ❌ 批量渲染/专辑制作是**单向管线**，无重组需求 | album/mirror 流程实测 |

## 2. 方案对比

| 方案 | 内容 | 成本 | 收益 | 风险 |
|---|---|---|---|---|
| **全量 B** | 113 文件/34k 行重构为声明式插件体系 | 2–4 周 | 生态纯度（心理收益为主）；实时重载（无消费方） | audio_pipeline 兼容层断裂；合成器纯函数层被插件边界切碎（性能+可读性双输）；602 测试需全量重写断言 |
| **B-lite** | 仅 interactive/（1,660 行）服务化：RealtimeMusicEngine 暴露为 Context 服务（provide/dispose），状态机/分层为可替换单元；抄 alloy 257 行 Context 形态 | 1–2 天 | 游戏引擎（alloy/games）将来可运行时换装音乐引擎；与 Phase A 服务面对齐 | 低：interactive 无外部消费者（grep 实证仅 games demo 使用） |
| **不做 B** | 维持 Phase A | 0 | — | 无；但 alloy 若要运行时音乐引擎动态装载，将来还得补 |
| **P0（先做）** | players-unified 把 bloodmusic 作为一个 source bundle 编排（纯配置，写 1 个 bundle json + 适配 5 行） | 0.5 天 | Phase A 价值的最终实证；也是 B-lite 的 go/no-go 依据：如果统一编排层用得顺手，说明「宿主层 cordis 化」已经够用 | 极低 |

## 3. 全量 B 不立项的四条硬理由

1. **DSP 核心是纯函数**：`synthesize_voice(voice)->ndarray` 这类无状态变换，插件化
   （生命周期/依赖注入）对它没有语义增益，只有边界开销。cordis 解决的是「副作用的
   时空组合」，而纯函数没有副作用可组合。
2. **唯一活消费者以「零改造」为契约**（audio_pipeline R4 原则）：内部重构动 music/
   的导入面 = 单方面撕毁兼容层承诺；sampler.py 兼容层就会二度复活。
3. **实时重载当前没有需求方**：games/zhuangtaiji 是离线渲染 demo；BloodMusic 专辑/
   镜像/beat 全是批量管线。为「将来可能有」付 2–4 周 + 回归风险，违反 YAGNI。
4. **测试安全网当前是破的**：pytest 9.1.1 收集错误 583 项（前置环境问题，见
   SKILL.md 记录）——没有绿色基线就没有重构资格。这是任何 Phase 立项的第一阻塞项。

## 4. 建议的推进序列

```
P0  修 pytest 收集错误（快照 583→0，恢复回归安全网）        ← 阻塞项，最先
P1  players-unified 收编 bloodmusic source（0.5 天）        ← Phase A 价值实证
P2  B-lite：interactive/ 服务化（1–2 天，抄 alloy Context）  ← P1 验证后再拍板
P3  全量 B：重新评审（仅当出现 ≥2 个运行时动态装载的真实消费方）
```

## 5. 遗留与不足

- 本评审对 alloy 的 games/ 场景只盘点了 audio 层副本关系，未穷举 alloy 全部子项目
  是否有「运行时换音乐引擎」需求——P2 拍板前补一次 alloy 侧需求确认。
- pytest 收集错误的根因修复方案未含在本评审（另行任务）。
- 估时（0.5/1–2 天/2–4 周）为工程判断，未做任务级 WBS 分解。
