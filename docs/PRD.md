# BloodMusic 全面增强 — 产品需求文档 (PRD)

> 版本: 1.0 · 日期: 2025-07 · 作者: 产品经理 Alice

---

## 1. 项目信息

| 字段 | 值 |
|------|------|
| 项目名称 | bloodmusic_enhance |
| 编程语言 | Python 3.10+ / numpy / scipy |
| 原始需求 | 对 BloodMusic 程序化游戏音频合成引擎进行全面增量增强，解决音频引擎、音乐生成、音色设计、导出能力、代码质量、GUI 六大不足 |
| 技术栈约束 | Python + numpy + scipy，保持与现有架构兼容 |
| 目标用户 | 独立开发者（一人团队，功能驱动，快速出活） |

---

## 2. 产品定义

### 产品目标

**让独立游戏开发者用纯 Python 就能生成专业级游戏音频——从音效到多轨配乐，一条命令搞定。**

核心指标：

1. **音色丰富度 ×10**：从当前 7 种波形 + 5 种包络 → 支持 FM 合成、LFO 调制、多阶滤波、和弦/多轨，可合成音色覆盖 80% 以上常见游戏音频场景
2. **音乐生成能力从单音→多轨**：从仅支持单音旋律 → 支持和弦层叠 + 鼓点 + 琶音 + 多音阶/调式，音乐预设从 6 个扩展到 15+
3. **导出就绪率 100%**：所有导出音频自带归一化 + 峰值限制 + 元数据，直接可用，无需二次处理

### 用户故事

1. **作为独立开发者**，我想用 FM 合成 + LFO 生成科幻武器音效，这样不用手动叠加几十层振荡器就能得到有动态变化的音色
2. **作为独立开发者**，我想生成包含和弦伴奏 + 鼓点的多轨 BGM，这样游戏不用只有单音旋律的"极简风"配乐
3. **作为独立开发者**，我想批量导出归一化 + 带元数据的 OGG 音频，这样导出即可直接集成到游戏引擎，不用再开 Audacity 转换
4. **作为独立开发者**，我想在 GUI 里实时调参数并立刻听到变化，这样调音效率从"改代码→运行→听"的分钟级缩短到秒级
5. **作为独立开发者**，我想选择不同音阶/调式生成旋律，这样同一组音符在不同调式下能产出风格迥异的音乐（如 Dorian 战斗、Lydian 奇幻）

---

## 3. 需求池

### P0 — 必做（核心价值，不做等于没增强）

| 编号 | 需求 | 做什么 | 为什么 |
|------|------|--------|--------|
| P0-1 | 二阶滤波器升级 | 将现有 `apply_lowpass`/`apply_highpass` 从一阶 IIR 升级为 scipy.signal.butter 二阶巴特沃斯；新增 `apply_bandpass`/`apply_notch` | 一阶 IIR 频率响应极差（-6dB/oct），无法做出有音乐性的滤波效果；带通/陷波是合成音色的基本工具 |
| P0-2 | 混响升级 | 用 Schroeder 混响（4×comb + 2×allpass）替换现有 comb-filter 混响 | 现有 comb 混响有金属尾音，听感廉价；Schroeder 是游戏音频最低可接受标准 |
| P0-3 | LFO 调制系统 | 在 `SynthVoice` 中新增 LFO 参数（rate/depth/target），支持调制振幅/滤波截止频率/音高 | LFO 是音色运动感的核心来源（颤音、wah-wah、tremolo），没有 LFO 的合成器音色"死板" |
| P0-4 | FM 合成 | 新增 `FMSynthVoice`，包含 carrier + modulator 振荡器 + FM 深度参数 | FM 合成用极少的参数就能产生极丰富的频谱（金属钟声、科幻音效），性价比最高 |
| P0-5 | 和弦/多轨音乐 | `MusicPattern` 支持和弦（多个音符同时发声）+ 多轨道层叠（旋律层 + 和弦垫 + 低音线）| 单音旋律是当前最大短板，没有和弦的游戏 BGM 听起来不完整 |
| P0-6 | 鼓点/打击轨 | 新增 `DrumPattern`（kick/snare/hihat 步进序列器）+ 与 `MusicPattern` 多轨混合渲染 | 鼓点是游戏 BGM 的节奏骨架，没有鼓点的战斗/菜单音乐缺乏驱动力 |
| P0-7 | freq_to_midi Bug 修复 | 修复 `note_utils.freq_to_midi` 中误用 `.bit_length()` 的 bug，改为 `math.log2()` 计算 | 现有代码对任何频率都返回 69 附近，完全不可用 |
| P0-8 | 导出归一化 + 峰值限制 | `AudioBatchExporter` 导出前自动归一化到 -1dBFS + 硬限幅 | 防止导出音频削波或音量不一致，直接可用 |

### P1 — 应做（显著提升体验）

| 编号 | 需求 | 做什么 | 为什么 |
|------|------|--------|--------|
| P1-1 | 压缩器/限幅器 | 新增 `apply_compressor`（阈值/比率/起音/释放）和 `apply_limiter` | 动态范围控制是音频后期基本操作，让战斗 SFX 和 BGM 在混音中不互相打架 |
| P1-2 | 三段参量 EQ | 新增 `apply_eq`（低/中/高三段，每段增益+频率+Q 值）| 音色塑形的标配工具，比低通/高通更精确 |
| P1-3 | Chorus 效果 | 新增 `apply_chorus`（延迟调制 + 多声部）| Chorus 是给单声源增加"厚度"和"空间感"的最有效手段，对弦乐/Pad 尤为重要 |
| P1-4 | 琶音器 | 新增 `Arpeggiator`（上行/下行/随机模式 + 速率控制）| 琶音器可以将和弦自动拆解为旋律线，是电子音乐和游戏 BGM 的常用工具 |
| P1-5 | 音阶/调式系统 | 新增 `Scale` 类（Major/Minor/Dorian/Phrygian/Lydian/Mixolydian/Pentatonic 等），提供 `get_scale_notes()` 和量化音符到音阶 | 让开发者用音阶约束旋律生成，不同调式天然适配不同游戏场景 |
| P1-6 | 音乐预设扩展 | 从 6 个扩展到 15+，新增：boss_fight / dungeon / tavern / forest / puzzle / title_screen / game_over / credits 等 | 预设少意味着开发者需要从零编写大部分 BGM，增加预设降低使用门槛 |
| P1-7 | OGG/FLAC 导出 | 导出支持 OGG Vorbis（游戏标准格式）和 FLAC（无损） | WAV 体积大，OGG 是游戏引擎的事实标准格式 |
| P1-8 | WAV 元数据写入 | 导出 WAV 时写入 INFO chunk（项目名/生成时间/参数摘要） | 便于资产管理，知道每个音频是怎么生成的 |
| P1-9 | 滤波器向量化 | 将 `filters.py` 中 Python for 循环替换为 scipy.signal.lfilter | for 循环处理滤波在长音频时极慢（~100x 差距），是性能瓶颈 |

### P2 — 可做（锦上添花）

| 编号 | 需求 | 做什么 | 为什么 |
|------|------|--------|--------|
| P2-1 | 波表合成 | 新增 `WavetableOsc`（用户自定义波形表 + 线性插值扫描）| 提供更复杂的周期波形，但对独立开发者使用频率较低 |
| P2-2 | 子振荡器 | `SynthVoice` 支持 sub-osc（-1 oct 固定振幅叠加）| 增加低频"厚度"，但可以用 detune 近似替代 |
| P2-3 | Flanger/Phaser 效果 | 新增 `apply_flanger`/`apply_phaser` | 特殊音色效果，使用场景有限 |
| P2-4 | GUI 波形可视化 | 在预览面板显示波形图（matplotlib 嵌入 Tkinter）| 视觉反馈好，但核心音频功能优先 |
| P2-5 | GUI 实时参数调节 | 添加滑块控件实时调节 SynthVoice 参数 | 体验提升大但开发量也大，先保证 CLI/API 好用 |
| P2-6 | 钢琴卷帘/音序器 UI | 在 GUI 中添加步进音序器界面 | 功能价值高但开发量极大，适合后续版本 |
| P2-7 | 噪声生成向量化 | 将 `_pink_noise_kernel` 中 Python for 循环替换为 numpy 向量化 | 粉红/棕噪声目前只在 SFX 中使用，性能影响有限 |
| P2-8 | 自定义 ADSR 全面生效 | 使 `ADSRParams` 在所有 `EnvShape` 下生效（当前仅 PERCUSSIVE） | 更灵活的包络控制，但 5 种预设包络已覆盖大部分场景 |

---

## 4. 技术规范概要

### 架构原则

- **增量改进**：在现有 7 模块结构上扩展，不重写核心接口
- **向后兼容**：现有 `SynthVoice` / `EffectChain` / `MusicPattern` 的 API 签名不变，新功能通过新增字段（默认值=None/0）和新增类实现
- **性能优先路径**：用 scipy.signal 替换 Python 循环的滤波/混响实现，保持实时预览可行

### 模块影响范围

| 模块 | 主要变更 |
|------|---------|
| `core/` | 新增 FMSynthVoice、LFO 参数、Scale 类；修复 freq_to_midi；滤波器升级到 scipy |
| `effects/` | 新增 bandpass/notch/EQ/compressor/limiter/chorus；混响升级 Schroeder；滤波器向量化 |
| `music/` | MusicPattern 支持和弦/多轨；新增 DrumPattern + Arpeggiator；扩展预设 |
| `sfx/` | 利用 FM/LFO/新效果重写部分预设，提升音质 |
| `export/` | 新增 OGG/FLAC 格式、归一化、峰值限制、元数据 |
| `gui/` | P2 阶段：波形可视化 + 参数滑块 |

### 依赖变更

- **新增**：`soundfile`（OGG/FLAC 编码）、`soundfile` 依赖 `libsndfile`
- **已有**：`numpy`、`scipy`（滤波器/混响升级后深度使用 `scipy.signal`）
- **不变**：`sounddevice`（实时预览）、`tkinter`（GUI）

---

## 5. 待确认问题

| 编号 | 问题 | 影响范围 | 建议 |
|------|------|---------|------|
| Q1 | OGG 导出是否需要可变比特率（VBR）控制？ | export | 默认 128kbps CBR 足够游戏使用，VBR 可作为 P2 |
| Q2 | 鼓点合成是否需要真实采样（sample-based）还是继续纯合成？ | music/sfx | 纯合成保持零依赖哲学，但听感不如采样；建议纯合成 + 噪声塑形模拟 |
| Q3 | FM 合成是否需要支持多调制器级联（operator stack）？ | core | 先做双算子（carrier + 1 modulator），级联留 P2 |
| Q4 | GUI 增强是否需要迁移到 pygame-ce（与用户其他项目统一）？ | gui | Tkinter 现有 GUI 可继续维护；若用户倾向统一可后续迁移，但增加工作量 |
| Q5 | 音乐预设扩展的目标游戏类型偏好？ | music | 当前预设偏暗黑/卡牌风；是否需要增加明快/RPG/平台跳跃风格？ |
| Q6 | 和弦表示法：采用字符串标记（如 "Cm7"）还是列表标记（如 ["C4","Eb4","G4","Bb4"]）？ | music | 列表更灵活但冗长，字符串需要解析器；建议两种都支持 |
