# BloodMusic 乐器池系统集成 — 增量 PRD

> 产品经理: Alice · 版本: 1.0 · 日期: 2025-08
> 父文档: PRD-instrument-pool.md (v1.0)

---

## 1. 变更范围

### 1.1 修改文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `album_generator.py` | **修改** | 新增 pool-based 模式、CLI `--pool` 参数；保留 10 首 legacy 函数不变 |
| `skill/bloodmusic-beats/SKILL.md` | **修改** | 新增 Workflow 11: InstrumentPool 端到端工作流 |
| `music/__init__.py` | **可能修改** | 如 pool 模块尚未导出则补充导出 |

### 1.2 新增文件

| 文件 | 说明 |
|------|------|
| `music/pool_presets/album_classical.yaml` | 古典/钢琴 风格乐池配置 |
| `music/pool_presets/album_newage.yaml` | 新世纪 风格乐池配置 |
| `music/pool_presets/album_ambient.yaml` | 氛围音乐 风格乐池配置 |
| `music/pool_presets/album_jazz.yaml` | 爵士 风格乐池配置 |
| `music/pool_presets/album_electronic.yaml` | 电子/EDM 风格乐池配置 |
| `music/pool_presets/album_cinematic.yaml` | 影视史诗 风格乐池配置 |
| `music/pool_presets/album_lofi.yaml` | Lo-Fi 风格乐池配置 |
| `music/pool_presets/album_meditation.yaml` | 冥想/自然 风格乐池配置 |
| `music/pool_presets/album_folk.yaml` | 民谣/世界音乐 风格乐池配置 |
| `music/pool_presets/album_finale.yaml` | 史诗终章 风格乐池配置 |

### 1.3 无需修改

| 文件/模块 | 原因 |
|-----------|------|
| `music/instrument_pool.py` | 数据模型已完备 |
| `music/pool_renderer.py` | 渲染管线已完备 |
| `music/pool_generator.py` | 生成引擎已完备 |
| `music/pool_styles.py` | 5 种 StylePreset 可直接复用 |
| `music/pool_templates.py` | 5 种 PoolTemplate 可直接复用 |
| `music/pool_serializer.py` | YAML 序列化已完备 |
| `core/`、`effects/` | 底层引擎无需变动 |

---

## 2. album_generator.py 改造方案

### 2.1 改造原则

- **向后兼容**：原有 10 个 `track_xx_xxx()` 函数保留不动，`main()` 默认行为不变
- **增量扩展**：新增 pool-based 模式通过 CLI 参数 `--pool` 触发
- **配置驱动**：10 种风格各对应一个 YAML pool 配置文件

### 2.2 架构变化

```
album_generator.py (改造后)
├── 原有 10 个 track_xx_xxx() 函数            ← legacy 模式 (不变)
├── 原有 main() 函数                           ← 默认行为 (不变)
│
├── [新增] ALBUM_STYLE_POOLS: Dict[str, str]  ← 风格→YAML 映射表
├── [新增] generate_album_with_pool()          ← pool-based 专辑生成
├── [新增] cli_main()                          ← argparse CLI 入口
│
└── [新增] if __name__ == "__main__": cli_main()
```

### 2.3 核心新增函数

#### `generate_album_with_pool()`

```python
def generate_album_with_pool(
    pool_dir: str = "music/pool_presets",
    output_dir: str = "album_output_pool",
    duration_sec: float = 120.0,
    seed: Optional[int] = None,
) -> list:
    """使用 InstrumentPool + PoolRenderer 批量生成专辑。

    遍历 ALBUM_STYLE_POOLS 中定义的 10 个风格→YAML 映射，
    对每个风格执行：
      1. InstrumentPool.from_yaml(pool_yaml)
      2. PoolRenderer(pool, duration_sec, style_name).render()
      3. _fade_edges + _normalize + save_wav

    Args:
        pool_dir: 乐池 YAML 配置文件目录
        output_dir: 输出目录
        duration_sec: 每首曲目目标时长（秒）
        seed: 随机种子（None=自动生成）

    Returns:
        生成的 WAV 文件路径列表
    """
```

#### `ALBUM_STYLE_POOLS` 映射表

```python
ALBUM_STYLE_POOLS = {
    "01_晨曦序曲":      ("album_classical.yaml",   "exploration"),
    "02_星海迷途":      ("album_newage.yaml",      "ambient"),
    "03_深海絮语":      ("album_ambient.yaml",     "ambient"),
    "04_午夜爵士":      ("album_jazz.yaml",       "town"),
    "05_霓虹脉冲":      ("album_electronic.yaml",  "battle"),
    "06_英雄远征":      ("album_cinematic.yaml",   "battle"),
    "07_旧日时光":      ("album_lofi.yaml",        "ambient"),
    "08_空山鸟语":      ("album_meditation.yaml",  "exploration"),
    "09_田园小调":      ("album_folk.yaml",        "town"),
    "10_终章·重生":     ("album_finale.yaml",       "battle"),
}
```

### 2.4 CLI 设计

```bash
# Legacy 模式（默认，不变）
python album_generator.py
# → 使用原始 10 个 track_xx_xxx() 函数生成，输出到 album_output/

# Pool-based 模式（新增）
python album_generator.py --pool
# → 使用 InstrumentPool + PoolRenderer 生成，输出到 album_output_pool/

python album_generator.py --pool --duration 180 --seed 42
# → 每首 3 分钟，固定种子

python album_generator.py --pool --output ./my_album
# → 自定义输出目录

# 兼容：同时生成两种模式（对比用）
python album_generator.py --pool --legacy
# → 同时运行 legacy 和 pool 模式
```

### 2.5 10 个 YAML 乐池配置设计

每份 YAML 的 `style` 字段关联 `ALBUM_STYLE_POOLS` 中对应的 StylePreset，确保 PoolRenderer 自动应用风格参数覆盖。

| 序号 | 曲名 | YAML 文件 | StylePreset | 核心乐器配置 |
|------|------|-----------|-------------|-------------|
| 01 | 晨曦序曲 | `album_classical.yaml` | exploration | 钢琴旋律(melody) + 弦乐垫底(chord) + 低音弦乐(bass)，无鼓 |
| 02 | 星海迷途 | `album_newage.yaml` | ambient | FM 钟声(melody) + 太空铺底(pad) + 轻柔打击(drum) |
| 03 | 深海絮语 | `album_ambient.yaml` | ambient | 正弦波垫底(pad) + 漂浮旋律(melody) + 高频闪烁(fx) |
| 04 | 午夜爵士 | `album_jazz.yaml` | town | 爵士旋律(melody) + 七和弦(chord) + 行走Bass(bass) + 轻刷鼓(drum) |
| 05 | 霓虹脉冲 | `album_electronic.yaml` | battle | 方波Lead(melody) + 电子Pad(chord) + Acid Bass(bass) + EDM鼓(drum) |
| 06 | 英雄远征 | `album_cinematic.yaml` | battle | 英雄主题(melody) + 和声层(chord) + FM Bass(bass) + 战斗鼓(drum) |
| 07 | 旧日时光 | `album_lofi.yaml` | ambient | 七和弦垫(chord) + Lo-Fi旋律(melody) + Sub Bass(bass) + 稀疏鼓(drum) |
| 08 | 空山鸟语 | `album_meditation.yaml` | exploration | 五声音阶垫(pad) + 鸟鸣旋律(melody) + 低频共鸣(pad) |
| 09 | 田园小调 | `album_folk.yaml` | town | 民谣旋律(melody) + 三度和声(chord) + Pluck Bass(bass) + 手鼓(drum) |
| 10 | 终章·重生 | `album_finale.yaml` | battle | 宏大主题(melody) + 第二旋律(chord) + FM Bass(bass) + 史诗鼓(drum) |

每份 YAML 的结构（以 `album_classical.yaml` 为例）：

```yaml
name: "晨曦序曲 - 古典钢琴"
version: "1.0"
bpm: 72
key: "C"
scale: "major"
style: exploration      # 关联 StylePreset，PoolRenderer 自动应用

instruments:
  - name: "piano_melody"
    role: melody
    engine: wavetable
    preset: "acoustic_grand_piano"
    volume: 0.85
    pan: 0.0
    effect_chain:
      reverb_mix: 0.3
      reverb_decay: 1.5
      lp_filter_hz: 4500

  - name: "strings_pad"
    role: chord
    engine: subtractive
    preset: "string_ensemble"
    volume: 0.55
    pan: -0.2
    effect_chain:
      reverb_mix: 0.4
      reverb_decay: 2.0

  - name: "cello_bass"
    role: bass
    engine: subtractive
    preset: "cello"
    volume: 0.65
    octave: -1
    effect_chain:
      reverb_mix: 0.25
      lp_filter_hz: 800

generation:
  diversity: 0.3
  humanize: true
  chord_progression: "dreamy"
```

> **注意**：pool-based 模式产出的音乐侧重"自动生成"体验，与 legacy 模式手写音符的 10 首曲目在听感上会不同——这是设计意图：两种模式互补，而非替代。

### 2.6 兼容性保障

- `main()` 函数保持不变，默认执行 legacy 模式
- `track_xx_xxx()` 函数一行不改
- 新增代码集中在文件尾部，用注释分隔
- 导入 `pool_renderer` 和 `instrument_pool` 采用 lazy import（仅在 pool 模式下加载），避免影响 legacy 启动速度

---

## 3. SKILL.md 更新方案

### 3.1 修改点

在 Workflow 10 (SamplePad) 之后、Creating Custom Beats 之前，插入新 Workflow。

### 3.2 新增内容：Workflow 11 — InstrumentPool

```markdown
### Workflow 11: InstrumentPool (端到端乐器池系统)

一键从乐器池配置生成完整纯音乐——声明乐器、选风格、出成品。

```python
from bloodmusic.music.instrument_pool import InstrumentPool
from bloodmusic.music.pool_renderer import PoolRenderer

# 方式1: 从 YAML 加载预置乐池
pool = InstrumentPool.from_yaml("music/pool_presets/orchestral_small.yaml")

# 方式2: 使用内置模板
from bloodmusic.music.pool_templates import POOL_TEMPLATES
pool = POOL_TEMPLATES["electronic_group"].to_pool(style="battle")

# 一键渲染: 乐池 → 分轨 → 混音 → 成品
renderer = PoolRenderer(pool, duration_sec=120.0, style_name="battle")
final_audio, stems = renderer.render()

# 仅导出分轨（跳过混音）
stems = renderer.render_stems_only()

# 导出为 WAV
from scipy.io import wavfile
wavfile.write("output.wav", 44100, (final_audio * 32767).astype(np.int16))
```

**5 个内置 StylePreset**：`exploration`, `battle`, `town`, `dungeon`, `ambient`

**5 个内置 PoolTemplate**：`orchestral_small`, `electronic_group`, `jazz_trio`, `rock_band`, `ambient_pad`

**生成整张专辑（10 首多风格纯音乐）**：

```bash
cd G:\tools\bloodmusic
python album_generator.py --pool
```

这会使用 `album_generator.py` 的 pool-based 模式，调用 InstrumentPool + PoolRenderer
为 10 种音乐风格各生成一首完整曲目，输出到 `album_output_pool/`。

**自定义乐池 YAML 格式**：

```yaml
name: "我的自定义 BGM"
version: "1.0"
bpm: 120
key: "C"
scale: "dorian"
style: exploration

instruments:
  - name: "主旋律"
    role: melody
    engine: wavetable
    preset: "acoustic_grand_piano"
    volume: 0.9

  - name: "和弦"
    role: chord
    engine: subtractive
    preset: "string_ensemble"
    volume: 0.6

  - name: "Bass"
    role: bass
    engine: fm
    volume: 0.8
    octave: -1

  - name: "鼓"
    role: drum
    engine: noise
    volume: 0.7

generation:
  sections: ["intro", "verse", "chorus", "outro"]
  section_bars: [4, 8, 8, 4]
  diversity: 0.3
  humanize: true
```
```

### 3.3 其他 SKILL.md 微调

| 位置 | 修改内容 |
|------|----------|
| `description` frontmatter 字段 | 新增触发词：`"create instrument pool"`, `"generate album with pool"`, `"使用乐器池"` |
| Overview 段 | 末尾新增一句，提及 InstrumentPool 端到端系统 |
| Resrouces 段 | 新增 `music/pool_presets/album_*.yaml` — 10 个专辑风格乐池 YAML 配置 |

---

## 4. 待确认问题处理

以下逐条确认 PRD-instrument-pool.md 第 6 节的 Q1-Q7 处理方式：

### Q1：生成策略 — 全自动 vs 用户提供音序数据

**PM 建议**：默认全自动生成，同时允许 `PoolInstrument.note_sequence` 字段覆盖自动生成。

**当前状态**：✅ 已实现。`PoolInstrument` 已有 `note_sequence: Optional[List[Optional[str]]]` 字段。`pool_generator.py` 的 `PoolGenerator` 在生成 melody 角色时检查 `note_sequence`——若为 None 则自动生成，若指定则直接使用用户提供的音符序列。

**本次增量**：10 个 album YAML 的 melody 角色**不设置** `note_sequence`，全部走自动生成。用户如需覆盖，可自行编辑 YAML 添加 `note_sequence` 字段。

### Q2：曲式结构 — 固定模板 vs 可配置

**PM 建议**：YAML 中 `sections` 字段可配置模板名，同时允许手动指定每段长度。

**当前状态**：✅ 已实现。`PoolConfig` 有 `sections` 和 `section_bars` 两个字段，用户可在 YAML 的 `generation` 段自定义。`pool_generator.py` 已支持读取 `config.sections` 并用 `config.section_bars` 控制各段小节数。

**本次增量**：每个 album YAML 可按需指定 `sections`/`section_bars`，不指定则走 StylePreset 默认曲式。

### Q3：合成引擎混用 — 单引擎 vs 引擎栈

**PM 建议**：v1 单引擎，P2 支持 `engine_stack` 叠加。

**当前状态**：✅ 已按建议实现。`PoolInstrument.engine` 为单一 `SynthEngine` 枚举值，当前不支持引擎栈叠加。

**本次增量**：无需变更。10 个 album YAML 的每件乐器使用单一 `engine` 字段。P2 阶段若引入 `engine_stack`，需同时修改 `PoolInstrument` 数据模型和 `pool_generator.py` 的生成逻辑。

### Q4：自动混音策略 — 自动应用 vs 建议确认

**PM 建议**：默认自动应用 `mix_assist` + 诊断日志。

**当前状态**：✅ 已实现。`PoolRenderer._apply_mix_assist()` 方法自动调用 `auto_level()` 和 `freq_slot_allocator()`，并通过 `logging` 输出诊断信息。

**本次增量**：无需变更。`generate_album_with_pool()` 使用 `PoolRenderer.render()` 即自动获得 mix_assist 处理。通过 Python logging 级别控制诊断输出详细程度。

### Q5：配置文件格式 — YAML

**PM 建议**：YAML（可读性好、支持注释）。

**当前状态**：✅ 已实现。`pool_serializer.py` 提供 `PoolSerializer.save_yaml()` / `load_yaml()`，`pool_presets/` 下均为 `.yaml` 文件。

**本次增量**：10 个 album YAML 配置文件均为 `.yaml` 格式，与现有 `pool_presets/` 保持一致。

### Q6：动态切换 — P1 不考虑

**PM 建议**：P1 不考虑动态切换（如探索→战斗），P2 阶段与 `interactive/` 模块集成。

**当前状态**：✅ 已按建议处理。当前未实现动态切换，`pool_renderer.py` 为一次性渲染管线。

**本次增量**：无需变更。album_generator.py 的 pool-based 模式为一次性生成 10 首独立曲目，不涉及动态场景切换。

### Q7：打击乐合成参数 — 先用现有 DrumPattern

**PM 建议**：先用现有 `DrumPattern`，P2 可根据反馈增强。

**当前状态**：✅ 已按建议处理。`pool_generator.py` 中的 drum 角色使用 `euclidean.py` + `DrumPattern` 生成节奏轨。

**本次增量**：无需变更。10 个 album YAML 的 drum 角色使用默认噪声合成 + 欧几里得节奏生成。P2 阶段如需更丰富的打击乐参数（多层叠加、力度变化），可在 `PoolInstrument.params` 中扩展。

---

## 5. 用户故事

1. **作为独立游戏开发者**，我想用 `album_generator.py --pool` 一条命令生成 10 首不同风格的纯音乐专辑，这样我不需要手写任何音符就能快速试听多种风格搭配，确定项目的音乐方向。

2. **作为独立游戏开发者**，我想修改 `album_presets/` 下的 YAML 配置文件来调整某首曲目的乐器配置（如把钢琴换成吉他），然后重新运行 `--pool` 看效果，这样我能用配置文件驱动的方式快速迭代音乐风格，而不需要改 Python 代码。

3. **作为独立游戏开发者**，我想在 SKILL.md 中看到 InstrumentPool 的完整使用范例（从 YAML 加载到一键渲染），这样我能快速学会这个新系统并把它集成到我的自动构建流程中。

---

## 6. 技术注意事项

1. **PoolRenderer 回退策略**：当 `PoolRenderer._generate_tracks()` 失败（如 YAML 格式错误），`generate_album_with_pool()` 应 catch 异常、打印诊断信息、跳过该曲目继续处理下一首，而非整体崩溃。

2. **时长截断一致性**：`PoolRenderer.render()` 已在内部做了 `duration_sec` 截断处理，`generate_album_with_pool()` 无需额外截断。

3. **Legacy 模式零回归**：`album_generator.py` 修改仅新增代码，不移动或修改任何现有函数和导入行。

4. **Lazy Import**：pool 相关模块（`instrument_pool`、`pool_renderer`）在 `--pool` 开关触发后才 import，避免 legacy 模式加载不必要的依赖。

5. **album YAML 目录约定**：10 个 album YAML 放在 `music/pool_presets/` 下与现有 5 个 YAML 同目录，文件名以 `album_` 前缀区分。

---

> **与父 PRD (PRD-instrument-pool.md) 的关系**：本增量 PRD 建立在乐器池系统已实现并测试通过的基础上，聚焦于将乐器池能力集成到 `album_generator.py` 和 `SKILL.md` 两个面向用户的入口。
