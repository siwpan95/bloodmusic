# BloodMusic 乐器池（Instrument Pool）系统 — 产品需求文档

> 产品经理: Alice · 版本: 1.0 · 日期: 2025-07

---

## 1. 项目信息

| 字段 | 值 |
|------|------|
| **项目名称** | `bloodmusic_instrument_pool` |
| **编程语言** | Python 3.10+（复用现有技术栈） |
| **原始需求** | 构建乐器池系统，从多种合成引擎中选取/组合乐器，自动为每件乐器生成分轨，最后混音为完整纯音乐 |
| **技术栈约束** | 纯 Python，零外部采样依赖，增量增强不破坏现有 API |
| **目标用户** | 独立游戏开发者，希望"一条命令把乐器池变成完整 BGM" |

---

## 2. 产品定义

### 2.1 产品目标

1. **乐器池即配器师**：用户声明"我要什么乐器、什么风格"，系统自动将乐器分配角色（旋律/和弦/Bass/打击乐），一键生成完整编曲。
2. **端到端一键产出**：从乐器池定义 → 分轨生成 → 自动混音 → 成品纯音乐，不需要用户手动编程拼接。
3. **可配置、可干预**：提供合理的默认行为，同时允许用户在任意环节（乐器选择、生成策略、混音参数）介入和覆盖。

### 2.2 用户故事

1. **作为独立游戏开发者**，我想定义一个乐器池（如"钢琴+弦乐+FM Bass+电子鼓"），然后一键生成 2 分钟的探索 BGM，这样我不需要懂编曲也能给游戏配乐。
2. **作为独立游戏开发者**，我想为同一个乐器池切换不同风格（战斗/城镇/森林），看哪个版本最合适，这样可以快速迭代找到最佳方案。
3. **作为独立游戏开发者**，我想在自动生成后手动替换某个分轨的乐器或调整混音参数（如"Bass 太响了，降低 3dB"），这样自动生成不是黑盒，我有最终控制权。
4. **作为独立游戏开发者**，我想把乐器池定义存为 YAML/JSON 配置文件，方便复用到不同游戏场景和在团队中共享。
5. **作为独立游戏开发者**，我想在 CLI 中一条命令完成"定义乐器池→生成→导出 OGG"，这样能集成到我的 CI/构建流程中自动产出音频。

---

## 3. 需求池

### P0 — 必做（乐器池核心闭环）

| 编号 | 需求 | 说明 |
|------|------|------|
| **P0-1** | 乐器池定义与配置 | `InstrumentPool` 作为一级概念：声明乐器列表、每件乐器的合成引擎类型、角色分配（melody/chord/bass/drum/pad/fx）|
| **P0-2** | 乐器池→分轨自动生成 | 根据乐器池配置，自动为每个乐器生成对应的 MusicPattern / DrumPattern / BassPattern，产出独立分轨音频数组 |
| **P0-3** | 角色到引擎的智能映射 | melody 默认用减法/波表/chord 用 FM/弦乐建模，bass 用 Sub/FM Bass，drum 用噪声合成。用户可覆盖 |
| **P0-4** | 分轨→成品自动混音 | 复用 `arrangement.py` 的 `SongMixer` + `render_song()` + `mix_assist.py` 的自动电平/频率分配，实现一键混音 |
| **P0-5** | 端到端 CLI 入口 | `python -m bloodmusic pool render my_pool.yaml --style exploration --duration 120 --format ogg` 一条命令出成品 |
| **P0-6** | YAML/JSON 配置序列化 | 乐器池可导出/导入为 YAML 文件，支持版本标记 |

### P1 — 应做（显著提升可用性）

| 编号 | 需求 | 说明 |
|------|------|------|
| **P1-1** | 风格预设系统 | 内置 5+ 风格模板（exploration / battle / town / dungeon / ambient），每种风格自动调整生成策略参数 |
| **P1-2** | 乐器池模板库 | 预置 5+ 乐器池模板（管弦小乐队 / 电子合成器组 / 爵士三重奏 / 摇滚乐队 / 氛围环境），开箱即用 |
| **P1-3** | 分轨独立导出 | 除最终混音外，可选导出每个乐器的独立分轨 WAV，方便在 DAW 中再处理 |
| **P1-4** | 生成多样性控制 | 每次生成可产生不同变体（通过 seed 控制 + temperature 参数），避免"每次听起来都一样" |
| **P1-5** | 乐池试听 | 可单独试听池中任一乐器的预览片段，确认音色满意后再生成完整曲目 |

### P2 — 可做（锦上添花）

| 编号 | 需求 | 说明 |
|------|------|------|
| **P2-1** | GUI 乐池编辑器 | 在现有 `workstation.py` 中新增乐器池配置面板（拖拽乐器、试听、角色分配） |
| **P2-2** | 自适应编排 | 分析目标时长和曲式结构，自动规划 Intro-Verse-Chorus-Bridge-Outro 段落的乐器进出 |
| **P2-3** | 音域冲突自动避让 | 分析乐器音域，自动将和弦/旋律分配到不同八度避免"打架" |
| **P2-4** | 情绪曲线联动 | 与现有 `emotion.py` 情绪系统联动，沿时间线动态调整乐器密度和强度 |

---

## 4. 功能概要设计

### 4.1 核心概念：InstrumentPool

```
InstrumentPool
├── name: str                         # 乐池名称
├── instruments: List[PoolInstrument]  # 乐器列表
├── style: StylePreset                # 风格预设（可选）
├── bpm: int = 120
├── key: str = "C"                    # 调性
├── scale: str = "major"              # 音阶
└── config: PoolConfig                # 生成参数
```

```
PoolInstrument
├── name: str                         # 显示名
├── role: InstrumentRole              # melody / chord / bass / drum / pad / fx
├── engine: SynthEngine               # subtractive / fm / fm_advanced / karplus_strong / granular / wavetable / waveguide
├── preset: str                       # 引用 instruments.py 中的预设名，或内联合成参数
├── params: dict                      # 覆盖/微调参数
├── effect_chain: EffectChain         # 该乐器专属效果链
├── pan: float = 0.0                  # 声像
└── volume: float = 1.0               # 相对音量
```

### 4.2 生成流程

```
1. 加载乐池配置 (YAML/JSON)
       │
2. 解析每个 PoolInstrument → 实例化为具体的合成引擎 Voice
       │
3. 按角色分配生成策略：
   ├── melody  → markov.py + motif.py + scale.py（生成旋律线）
   ├── chord   → harmony.py + scale.py（生成和弦进行 + 声部排列）
   ├── bass    → bass.py + scale.py（生成 Bass 线）
   ├── drum    → euclidean.py + DrumPattern（生成节奏轨）
   ├── pad     → harmony.py + arpeggiator.py（生成铺底/琶音）
   └── fx      → 特殊效果（riser、hit、sweep 等）
       │
4. 生成各分轨音频（MusicPattern / DrumPattern → 渲染为 numpy 数组）
       │
5. 混音阶段：
   ├── auto_level() 平衡各轨音量
   ├── freq_slot_allocator() 频率避让
   ├── MixBus 分组处理（DrumBus / MelodyBus / BassBus）
   └── render_song() 最终渲染
       │
6. 导出（WAV / OGG / FLAC + 分轨可选）
```

### 4.3 角色→引擎智能映射

| 角色 | 默认引擎 | 典型乐器 | 说明 |
|------|----------|---------|------|
| melody | wavetable / subtractive | Piano, Violin, Flute | 需要丰富谐波和表现力 |
| chord | fm_advanced / wavetable | String Ensemble, Pad, Organ | 需要多声部叠加 |
| bass | subtractive / fm | Sub Bass, FM Bass, Acoustic Bass | 需要低频扎实 |
| drum | noise synthesis | Kick, Snare, Hi-hat, Crash | 纯合成打击乐 |
| pad | granular / fm_advanced | Warm Pad, Atmosphere | 需要长时域演化 |
| fx | karplus_strong / waveguide | Pluck, Wind, Special | 特殊音色效果 |

### 4.4 与现有模块的关系

#### 复用（直接调用，无需修改）

| 模块 | 复用方式 |
|------|----------|
| `music/instruments.py` | `InstrumentPreset.apply_to()` 一键应用乐色到 MusicPattern |
| `music/pattern.py` | `MusicPattern` / `DrumPattern` / `MultiTrackPattern` 已是标准分轨容器 |
| `music/arrangement.py` | `SongArrangement` + `SongMixer` + `render_song()` 完整渲染管线 |
| `music/scale.py` | 音阶约束旋律/Bass/和弦生成 |
| `music/markov.py` | 马尔可夫旋律生成 |
| `music/euclidean.py` | 欧几里得节奏生成鼓点 |
| `music/harmony.py` | 多声部和声编排 |
| `music/bass.py` | Bass 合成器（Sub/FM/Acid/Pluck） |
| `music/motif.py` | 主题动机发展 |
| `music/arpeggiator.py` | 琶音生成 |
| `music/emotion.py` | 情绪曲线（P2 联动） |
| `music/humanize.py` | 人性化处理 |
| `effects/chain.py` | `EffectChain` 参数配置 |
| `effects/mix_assist.py` | `auto_level()` / `freq_slot_allocator()` 智能混音 |
| `export/` | WAV/OGG/FLAC 导出 |

#### 扩展（修改现有文件，增量新增字段/方法，不破坏 API）

| 模块 | 扩展内容 |
|------|----------|
| `music/pattern.py` | `MusicPattern` 新增可选 `pool_role` 字段，标记该 Pattern 在乐池中的角色 |

#### 新增（全新文件）

| 文件 | 内容 |
|------|------|
| `music/instrument_pool.py` | 核心模块：`InstrumentRole` 枚举、`PoolInstrument` dataclass、`InstrumentPool` dataclass、`PoolConfig` dataclass |
| `music/pool_generator.py` | 生成引擎：`generate_pool_tracks()` — 遍历乐池乐器，调用各生成策略产出 `MultiTrackPattern` |
| `music/pool_renderer.py` | 渲染管线：`render_pool()` — 端到端：乐池 → 分轨 → 混音 → 成品音频 |
| `music/pool_styles.py` | 风格预设：5+ 内置风格模板（battle / exploration / town / dungeon / ambient） |
| `music/pool_templates.py` | 乐池模板：5+ 预置乐器池配置 |
| `music/pool_serializer.py` | 序列化：YAML/JSON 配置的 save/load |
| `music/pool_presets/` | 预置乐池 YAML 文件目录 |

#### 无需修改

| 模块 | 原因 |
|------|------|
| `core/` 全部 | 合成引擎能力已完备 |
| `effects/` 全部 | 效果器能力已完备 |
| `gui/workstation.py` | P2 阶段再做 GUI 适配 |
| `sfx/` | 音效模块不在乐器池范围内 |

### 4.5 关键数据流

```
pool_presets/combat_quartet.yaml
         │
         ▼
  pool_serializer.load()
         │
         ▼
  InstrumentPool (内存对象)
         │
         ▼
  pool_generator.generate_pool_tracks()
    ├── melody: Piano → markov + motif → MusicPattern
    ├── chord:  String Ensemble → harmony → MusicPattern(chords)
    ├── bass:   FM Bass → bass.py → MusicPattern
    └── drum:   Electronic → euclidean → DrumPattern
         │
         ▼
  MultiTrackPattern (分轨集合)
         │
         ▼
  pool_renderer.render_pool()
    ├── 渲染各分轨 → dict[str, np.ndarray]
    ├── mix_assist.auto_level()
    ├── mix_assist.freq_slot_allocator()
    └── arrangement.render_song() → np.ndarray
         │
         ▼
  export.export_audio(成品, format="ogg")
```

---

## 5. UI 设计稿

### 5.1 CLI 交互

```bash
# 列出所有内置乐池模板
$ python -m bloodmusic pool list

  Templates:
    orchestral_small  - 管弦小编制（弦乐+木管+定音鼓）
    electronic_group  - 电子合成器组（波表+FM+电子鼓）
    jazz_trio         - 爵士三重奏（钢琴+Double Bass+鼓）
    rock_band         - 摇滚乐队（吉他+贝斯+鼓）
    ambient_pad       - 氛围环境（粒子合成+Pad+Drone）

# 查看乐池详情
$ python -m bloodmusic pool show orchestral_small

# 一键生成
$ python -m bloodmusic pool render orchestral_small \
    --style battle \
    --duration 120 \
    --key Am \
    --bpm 140 \
    --format ogg \
    --output ./output/battle_bgm.ogg

# 仅生成分轨（不混音），方便手动调优
$ python -m bloodmusic pool render my_pool.yaml --stems-only --output ./stems/

# 自定义乐池生成
$ python -m bloodmusic pool create my_pool \
    --add melody:piano \
    --add chord:strings \
    --add bass:fm_bass \
    --add drum:electronic \
    --save my_pool.yaml

# 试听乐池中某件乐器
$ python -m bloodmusic pool preview my_pool.yaml --instrument melody
```

### 5.2 YAML 配置文件格式

```yaml
# my_game_bgm.yaml
name: "森林探索 BGM"
version: "1.0"
bpm: 100
key: "C"
scale: "dorian"
style: exploration

instruments:
  - name: "主旋律"
    role: melody
    engine: wavetable
    preset: "acoustic_grand_piano"
    volume: 0.9
    pan: 0.0
    effect_chain:
      reverb_mix: 0.25
      stereo_width: 0.5

  - name: "和弦垫"
    role: chord
    engine: subtractive
    preset: "string_ensemble"
    volume: 0.6
    pan: -0.3

  - name: "Bass"
    role: bass
    engine: fm
    preset: "fm_bass"
    volume: 0.8
    pan: 0.0
    effect_chain:
      lp_filter_hz: 500

  - name: "打击乐"
    role: drum
    engine: noise
    volume: 0.7

generation:
  sections: ["intro", "verse", "chorus", "verse", "chorus", "outro"]
  section_bars: [4, 8, 8, 8, 8, 4]
  diversity: 0.3           # 生成多样性 (0=固定, 1=最大变化)
```

### 5.3 Python API

```python
from bloodmusic.music.instrument_pool import (
    InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine
)
from bloodmusic.music.pool_renderer import render_pool
from bloodmusic.export import export_audio

# 方式1: 从YAML加载
pool = InstrumentPool.from_yaml("my_pool.yaml")

# 方式2: 编程式构建
pool = InstrumentPool(
    name="Combat BGM",
    bpm=140,
    key="D",
    scale="phrygian",
    instruments=[
        PoolInstrument("Lead", role=InstrumentRole.MELODY, engine=SynthEngine.WAVETABLE,
                       preset="overdriven_guitar"),
        PoolInstrument("Chords", role=InstrumentRole.CHORD, engine=SynthEngine.FM_ADVANCED,
                       preset="string_ensemble"),
        PoolInstrument("Bass", role=InstrumentRole.BASS, engine=SynthEngine.SUBTRACTIVE,
                       preset="electric_bass_pick"),
        PoolInstrument("Drums", role=InstrumentRole.DRUM, engine=SynthEngine.NOISE),
    ]
)

# 一键渲染
audio, stems = render_pool(pool, duration_sec=120, style="battle")

# 导出
export_audio(audio, "combat_bgm.ogg", format="ogg")
for name, stem in stems.items():
    export_audio(stem, f"stems/{name}.wav", format="wav")
```

---

## 6. 待确认问题

| 编号 | 问题 | 影响范围 | 建议 |
|------|------|---------|------|
| **Q1** | 生成策略：旋律/和弦是**全自动生成**还是用户也可以在乐池中**提供音序数据**（如指定具体的和弦进行）？ | `pool_generator.py` | 建议默认全自动，同时允许 `PoolInstrument` 中可选填入 `note_sequence` 字段覆盖自动生成 |
| **Q2** | 曲式结构：Intro-Verse-Chorus 的段落划分是固定模板还是可配置？ | `pool_renderer.py` | 建议 YAML 中 `sections` 字段可配置模板名（如 `"ABAB"`），同时允许手动指定每段长度 |
| **Q3** | 每个乐器的合成引擎是否需要支持**混用**（如 melody 同时用波表 + FM 双层叠加）？ | `PoolInstrument` 设计 | 建议 v1 单引擎，P2 支持 `engine_stack` 叠加 |
| **Q4** | 自动混音的策略粒度：`mix_assist.py` 的 `auto_level` 和 `freq_slot_allocator` 是完全自动应用还是只给**建议**让用户确认？ | `pool_renderer.py` | 建议默认自动应用，同时在诊断报告中输出做了什么调整，方便用户审查 |
| **Q5** | 乐池配置文件格式偏好：YAML（人类可读）还是 TOML（更严格）？ | `pool_serializer.py` | 建议 YAML（可读性好、支持注释、Python 生态成熟） |
| **Q6** | 是否需要支持乐池的**动态切换**（如从探索→战斗时自动切换乐器和强度），类似现有 `interactive/` 的自适应音乐？ | 架构设计 | 建议 P1 不考虑，P2 阶段与 `interactive/` 模块集成 |
| **Q7** | 打击乐是否需要更丰富的合成参数（如多层叠加、力度变化），还是当前 `DrumPattern` 噪声合成足够？ | `DrumPattern` | 建议先用现有 `DrumPattern`，P2 可根据反馈增强 |

---

## 7. 技术风险评估

| 风险 | 严重度 | 缓解措施 |
|------|--------|----------|
| 自动生成的音乐"机械感"太重 | 高 | 复用 `humanize.py` 做微时间偏移+力度变化；`micro_variation.py` 做循环微变化 |
| 乐器池变大时渲染性能下降 | 中 | Python 纯计算，4-6 轨 × 120s 在 44.1kHz 下约 1-2 秒渲染时间，可接受 |
| 自动混音结果不理想（频段冲突） | 中 | `mix_assist.py` 已提供频率避让，外加用户可手动覆盖每条轨道的 effect_chain |
| 风格模板不够灵活 | 低 | 风格模板是参数预设，用户可完全覆盖或自定义 |

---

## 8. 迭代计划建议

| 阶段 | 内容 | 预计文件 |
|------|------|----------|
| **Sprint 1** | `InstrumentPool` / `PoolInstrument` / 序列化 / YAML 模板 | `instrument_pool.py` + `pool_serializer.py` + `pool_templates.py` + `pool_presets/` |
| **Sprint 2** | `pool_generator.py` — 分轨自动生成管线 | `pool_generator.py` + `pool_styles.py` |
| **Sprint 3** | `pool_renderer.py` — 端到端渲染 + CLI | `pool_renderer.py` + `cli.py` 新增命令 |
| **Sprint 4** | P1 完善（分轨导出/多样性/试听） | 增量修改上述文件 |

---

> **与现有 PRD (PRD.md) 的关系**：本 PRD 是 **v3.0 新功能 PRD**，建立在 v2.0（PRD.md + ARCHITECTURE.md 已实现的功能）之上。本系统不修改 v2.0 的任何核心 API，仅作为上层编排模块新增。
