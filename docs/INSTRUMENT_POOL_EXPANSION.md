# BloodMusic 乐器池扩充可行性调研

> 调研时间：2026-08-22 ｜ 视角：音频工程师（GameAudioEngineer）
> 结论：**乐器池可以且应当继续扩充**，分「内容 / 类别 / 引擎」三层，成本递增、接口已解耦。

---

## 一、当前基线（代码实测）

| 维度 | 现状 | 位置 |
|---|---|---|
| 合成引擎 `SynthEngine` | **12 个**：SUBTRACTIVE / FM / FM_ADVANCED / KARPLUS_STRONG / GRANULAR / WAVETABLE / WAVEGUIDE / NOISE / **ADDITIVE** / **MODAL** / **HYBRID** / **MATERIAL** | `music/instrument_pool.py:70` |
| 乐器角色 `InstrumentRole` | **6 个**：MELODY / CHORD / BASS / DRUM / PAD / FX | `music/instrument_pool.py:36` |
| 乐器类别 `category` | 实际用到 **8 类**：piano / strings / brass / woodwind / guitar / percussion / synth / bass | `music/instruments.py` |
| 注册乐器 `INSTRUMENTS` | **30 件**（piano×5、strings×5、brass×2、woodwind×3、guitar×4、percussion×4、synth×4、bass×3） | `music/instruments.py` |
| 对照标准 | GM2 = 16 旋律族 / 256 音色 | 外部 |
| 覆盖率 | 乐器 ≈ 12% (30/256)，类别 = 50% (8/16) | — |

---

## 二、三层扩展点（在哪里加、改什么）

### ① 加乐器（内容扩充）— 零引擎改动，约 8–10 行/件
`music/instruments.py` 内定义 `InstrumentPreset(...)` 并注册进 `INSTRUMENTS` 字典即可。
已验证：现有 30 件全部是这种纯参数映射，只描述 `osc_type / harmonics / env_shape / volume / vibrato / reverb / lp_hp_filter / stereo_width`，由 `InstrumentPreset.apply_to()` 套用到 `MusicPattern`。
> 注意：`extra_instruments` 既支持引用 `INSTRUMENTS` 注册名，也支持 **raw dict 直接写 `engine` + `engine_params`**（如《SPECTRUM》专辑即以此并入 8 件新引擎乐器，无需注册名）。但 raw dict 的 `engine_params` 必须被正确透传（见 P3-b 修正），否则 preset 会丢失。

### ② 加类别 / 角色（类别扩充）— 中等成本
- `category` 是自由字符串，加第 9 类（如 `organ`、`ethnic`、`sfx`）只需在 `InstrumentPreset` 填新值。
- 加**新角色**（如 `ARP`、`DRONE`、`TEXTURE`）需在 `music/instrument_pool.py` 扩展 `InstrumentRole` 枚举，并在 `music/pool_generator.py` 增加 `generate_<role>()` + 在 `_generate_for_instrument()` 加 dispatch 分支。

### ③ 加合成引擎（技术代际扩充）— 中高成本，但接口已解耦
`music/instrument_pool.py` 的 `SynthEngine` 枚举 + `pool_generator._ENGINE_OSC_MAP` 是统一入口；`MusicPattern` 已用 `engine` + `engine_params` 解耦。新增引擎 = 在 `core/` 加模块（如 `additive.py`、`modal.py`）并接入枚举与映射，上层生成逻辑无需重写。

---

## 三、联网调研：业界可扩充方向

### 3.1 合成技术代际缺口（对照 Blackout Audio / Uniphonic / Gearnews 综述）
- **已覆盖**：减法、FM/FM-Advanced、Karplus-Strong（弦物理）、Granular（粒子）、Waveguide（管物理）、噪声、**加法合成 Additive**（P1，glass/bell/metal 非谐分音）、**模态合成 Modal**（P1，bar/membrane/tubular/bowl/gong 共振体）、**混合声部 Hybrid**（P2，additive+modal+tone+noise+fm 多层融合）、**Material-aware 撞击 MATERIAL**（P2 定义模块 `sfx/material.py`；P3 已接成乐器池 drum 角色的 `SynthEngine.MATERIAL`，由 `pool_generator._generate_material_drum` 分派、kick/snare/hihat 各自映射 wood/metal/ceramic 等材质，concrete/wood/metal/gravel/glass/stone/ice/ceramic/water/sand 参数化撞击）。
- **未来方向（重 / 待定）**：
  - **Neural / DDSP**（WaveNet / RAVE / Engel 2020）：数据驱动，与零采样理念冲突，仅远景。
  - **Spatial（HRTF / Ambisonics）**：当前仅 `stereo_width`，无 HRTF/环绕。
- **延伸（重，标未来）**：
  - **Neural / DDSP**（WaveNet / RAVE / Engel 2020）：数据驱动，但与本项目「零外部采样」理念冲突，仅作远景。
  - **空间音频 Spatial**（HRTF / Ambisonics）：当前仅 `stereo_width`，无 HRTF/环绕。

### 3.2 乐器类别缺口（对照 GM2 的 16 旋律族）
| 已覆盖族 | 缺失/薄弱族（可立即补） |
|---|---|
| piano(5) | **organ 族全缺**：drawbar / church / reed / accordion / harmonica |
| strings(5) | — |
| brass(2) | 缺 trombone / tuba / french horn / muted trumpet |
| woodwind(3) | 缺 oboe / bassoon / english horn / piccolo / recorder / pan flute / shakuhachi / whistle / ocarina / soprano&tenor&baritone sax |
| guitar(4) | — |
| percussion(4) | 缺 glockenspiel / xylophone / dulcimer |
| synth(4) | 缺 fantasia / space voice / metal / halo / sweep / crystal / goblin 等 GM2 变体 |
| bass(3) | — |
| — | **ethnic/world 薄弱**：仅 koto / banjo → 缺 sitar / shamisen / kalimba / bagpipe / fiddle / shanai |
| — | **Sound Effects 全缺**：seashore / rain / wind / bird / machinery（游戏音效床） |

### 3.3 游戏音频专用扩充（对照 SFX Engine / Wwise·FMOD 文献）
- **Material-aware 程序化 SFX**：footstep = impact burst + granular 表面纹理 + debris + surface EQ（concrete/wood/metal/gravel 共振频率不同）。`sfx/drum_synth.py` 已有雏形，可系统化为参数化材质系统。
- **自适应垂直分层 stem**：按强度（explore→combat_low→combat_high→victory）提供可叠加 stem——zhuangtaiji FSM 已验证分层，可产品化。
- **参数驱动环境音床**：风/雨/海浪用 granular + 噪声调制，替代静态采样。

---

## 四、推荐优先级路线图（音频工程师视角）

| 优先级 | 动作 | 成本 | 收益 |
|---|---|---|---|
| **P0** ✅ | 补 GM2 主要族乐器（organ/brass/woodwind/strings/ethnic/percussion/synth 变体）→ 30 → 68 件 | 低（纯参数） | **已完成 2026-08-22**，端到端渲染验证通过 |
| **P1** ✅ | 加 **Additive** + **Modal** 两个引擎 + 8 件真实合成乐器 → 68 → 76 件 | 中 | **已完成 2026-08-22**，端到端渲染验证通过 |
| **P2** ✅ | **Hybrid 声部**(additive+modal+tone+noise+fm 多层) + **Material-aware SFX**(10 材质) + 3 件 HYBRID 乐器 → 76 → 79 件 | 中高 | **已完成 2026-08-22**，专辑流程试产 demo 通过 |
| **P3（部分完成）** | **Spatial(HRTF) ✅** 已落地（`effects/spatial.py` + EffectChain 集成，零采样合成）；Ambisonics、Neural/DDSP 仍为未来方向 | 高 | 空间化已可用，数据驱动音色需权衡零采样理念 |

---

## 五、实施示意

### 加一件乐器（P0，零引擎改动）
```python
# music/instruments.py
DRAWBAR_ORGAN = InstrumentPreset(
    name="Drawbar Organ", gm_program=16, category="organ",
    osc_type=OscType.SAW, volume=0.18, env_shape=EnvShape.PAD,
    harmonics=[(1.0,1.0),(2.0,0.6),(3.0,0.4),(4.0,0.25),(5.0,0.15)],
    vibrato_rate=6.0, vibrato_depth=0.8,
    reverb_mix=0.2, reverb_decay=0.8, lp_filter_hz=4000, stereo_width=0.6,
)
INSTRUMENTS["drawbar_organ"] = DRAWBAR_ORGAN
```

### 加一个引擎（P1，扩展枚举 + 接入）
> **接入点说明（实测）**：FM/FM_ADVANCED/WAVETABLE/KARPLUS_STRONG/WAVEGUIDE/GRANULAR 已有专属渲染方法；而 ADDITIVE/MODAL/HYBRID 的**真正接入点是 `music/pattern.py` 的 `_render_note_signal()` 调度函数**（它按 `pattern.engine` 分发到 `core.additive` / `core.modal` / `core.hybrid`，否则回退振荡器链路）。PoolRenderer 的 ADDITIVE/MODAL/HYBRID 分支委托 `render_pattern_to_array`，经此路径生效，故渲染层始终消费 `engine` 字段。`pool_generator._ENGINE_OSC_MAP` 仅用于选 osc_type 装饰，非渲染入口。

```python
# music/instrument_pool.py —— SynthEngine 枚举追加
ADDITIVE = "additive"    # 加法合成（分音叠加 / 玻璃·钟·金属）
MODAL    = "modal"       # 模态合成（谐振体建模 / 棒·膜·钵·管钟）

# core/additive.py / core/modal.py —— 新增引擎，实现 engine_params 接口
#   ADDITIVE: partials / preset(glass|bell|metal|glass_pad|organ|saw|triangle) / inharmonicity / partial_decay
#   MODAL:    modes / preset(bar|membrane|tubular|bowl|gong) / base_decay / attack

# music/pattern.py —— _render_note_signal() 内按 pattern.engine 分发（真实接入点）
if engine == SynthEngine.ADDITIVE: return additive_synth(...)
if engine == SynthEngine.MODAL:    return modal_synth(...)

# music/instruments.py —— InstrumentPreset 新增 engine / engine_params 字段，
#   apply_to() / make_pattern() 透传；乐器声明 engine=SynthEngine.XXX 即生效。
```

---

## P0 执行记录（2026-08-22 已完成）

在 `music/instruments.py` 新增 **38 件**乐器预设（纯参数映射，零引擎改动），注册总数由 30 → **68 件**，类别由 8 → **10**（新增 `organ`、`ethnic`）。

新增明细：

- **organ ×5**：drawbar_organ / church_organ / reed_organ / accordion / harmonica
- **brass ×4**：trombone / tuba / muted_trumpet / french_horn
- **woodwind ×12**：oboe / english_horn / bassoon / soprano_sax / tenor_sax / baritone_sax / piccolo / recorder / pan_flute / shakuhachi / whistle / ocarina
- **strings ×2**：contrabass / tremolo_strings
- **ethnic ×6**：sitar / shamisen / kalimba / bagpipe / fiddle / shanai
- **percussion ×3**：glockenspiel / xylophone / dulcimer
- **synth ×6**：polysynth_pad / space_voice_pad / metal_pad / halo_pad / sweep_pad / charang_lead

验证：

- 模块导入 + `get_instrument()` 解析全部新键名通过（`count=68`，`cats` 含 organ/ethnic）。
- 真实渲染冒烟测试（sitar / trombone / metal_pad / drawbar_organ / kalimba / oboe / french_horn 各 2s）RMS 均 > 0，合成链路端到端可用。
- 自动键名取自 `name` 小写（如 `Metal Pad` → `metal_pad`），album_maker 的 `extra_instruments` 现可直接引用这些新键名。
- 未做项：SFX 床（rain/wind/seashore 等）留待 P2 Material-aware SFX 系统，不在本次纯参数 P0 范围。

> 数据模型已用 `engine` + `engine_params` 解耦，新增引擎不需改上层生成逻辑。

## P1 执行记录（2026-08-22 已完成）

在 `music/instrument_pool.py` 的 `SynthEngine` 枚举新增 **ADDITIVE / MODAL** 两个引擎值（10 个）；新增两个真实合成引擎模块，并通过 `music/pattern.py:_render_note_signal()` 接入渲染调度（原 8 个引擎枚举值此前从未被消费，本次一并让 ADDITIVE/MODAL 真正生效，且默认 `engine=None` 回退原振荡器链路，**对旧 68 件乐器零回归**）。

新增模块：

- `core/additive.py`：`additive_synth()` + `ADDITIVE_PRESETS`（glass / bell / metal / glass_pad / organ / saw / triangle）。逐分音正弦叠加，支持非谐拉伸 `inharmonicity` 与逐分音衰减 `partial_decay`（营造敲击瞬态）。
- `core/modal.py`：`modal_synth()` + `MODAL_PRESETS`（bar / membrane / tubular / bowl / gong）。把谐振体建模为一组指数衰减正弦模态（ratio / amp / decay_scale），物理衰减即包络（不再叠加 ADSR），低频模态长、高频模态短，正是 marimba / tubular bell / singing bowl 的物理本质。
- `core/__init__.py`：导出上述函数与预设。

`music/instruments.py`：`InstrumentPreset` 新增 `engine: Optional[SynthEngine]` 与 `engine_params: Dict` 字段，`apply_to()` / `make_pattern()` 透传；新增 **8 件**真实合成乐器并注册（68 → **76 件**）：

- **ADDITIVE ×4**：glass_bell（glass）、metal_bell（bell）、metal_plate（metal）、glass_pad（glass_pad，含轻颤音）
- **MODAL ×4**：marimba_bar（bar）、tubular_bell_modal（tubular）、singing_bowl（bowl，长衰减 ethnic）、gong_modal（gong）

验证（`_validate_p1.py`，venv 跑通）：

- 枚举 `ADDITIVE`/`MODAL` 存在；`INSTRUMENTS` 总数 = **76**（68+8）。
- 8 件新乐器逐件 `make_pattern()` → `generate_music_wav()` 渲染，读回 WAV 计算 RMS 均 > 0（glass_bell≈4391 / metal_bell≈2647 / metal_plate≈2985 / glass_pad≈5546 / marimba_bar≈7385 / tubular_bell_modal≈8451 / singing_bowl≈6129 / gong_modal≈7222），合成链路端到端可用。
- 回归：旧 68 件中抽 5 件（含带颤音的 glockenspiel / space_voice_pad）走原振荡器回退链路渲染正常，确认无未定义变量等回归。
- 未做项：原始 8 个引擎（SUBTRACTIVE/FM/…）仍仅为枚举占位未接渲染；Hybrid 声部与 Material-aware SFX 留待 P2。

## P2 执行记录（2026-08-22 已完成）

### P2-a 混合声部 Hybrid 引擎
- `SynthEngine` 枚举新增 **HYBRID**（11 个）；新增 `core/hybrid.py`：`hybrid_synth()` + `HYBRID_PRESETS`（bell_metal / glass_strike / hybrid_pad / metal_strike / wood_hybrid）。
- 设计：单个声部内融合 **additive + modal + tone(减法谐波) + noise(瞬态) + fm** 多层，每层独立 gain/detune/params；软限幅防叠加爆音。这是 Serum/Vital 式「同一声部多层合成」的程序化落地。
- 接入点双保险：`music/pattern.py:_render_note_signal()` 与 `music/pool_renderer.py:_render_pattern_with_engine()` 均新增 HYBRID 分支。`core/__init__.py` 导出 `hybrid_synth / HYBRID_PRESETS`。
- `music/instruments.py` 新增 **3 件** HYBRID 乐器（hybrid_bell_metal / hybrid_glass_strike / hybrid_shimmer_pad）并注册，76 → **79 件**。

### P2-b Material-aware 程序化 SFX
- 新增 `sfx/material.py`：`synthesize_material_impact(material, velocity, duration)` + `MATERIAL_PRESETS`（10 材质：wood / concrete / metal / gravel / glass / stone / ice / ceramic / water / sand）。
- 设计：撞击 = impact tone（指数音高下沉）+ noise burst（明亮度高通）+ resonant body（并行带通着色材质共振峰）+ debris（granular 碎屑）+ surface lowpass，全部由材质参数驱动——一套合成器替代每件材质一个采样。
- `sfx/__init__.py` 导出。

### P2-c 专辑流程新引擎接入说明（复核修订）
- 经本轮复核：`_render_pattern_with_engine()` 的 ADDITIVE/MODAL/HYBRID 分支委托 `render_pattern_to_array`，而后者经 `music/pattern.py:_render_note_signal()` **真实消费 `engine`**（ADDITIVE→`core.additive`、MODAL→`core.modal`、HYBRID→`core.hybrid`），故渲染层**从未沉默 fallback 成基础振荡器**。
- 该分支自 P1 接入 `_render_note_signal` 起即有效。验证：glass_bell 等经此路径渲染与纯正弦频谱差异显著，新引擎在专辑流程真正生效。
- **真正阻断新引擎「以正确音色可闻并入」的缺陷在别处**（见下方「P3 执行记录 / P3-b」），并非渲染层。

### 验证（venv 跑通，ALL PASS）
- 枚举 HYBRID 存在；INSTRUMENTS = 79。
- 11 件新引擎乐器（ADDITIVE×4 / MODAL×4 / HYBRID×3）逐件 `generate_music_wav` 渲染 RMS 均 > 0。
- pool_renderer 路径 3 件（glass_bell / singing_bowl / hybrid_bell_metal）RMS>0 且 corr_vs_sine<0.95。
- Material-aware SFX 10 材质 RMS 均 > 0。
- 回归 3 件旧乐器（含颤音 glockenspiel / space_voice_pad）正常。

### P2-d 专辑流程试产 demo
- 脚本 `AlbumMaker` 完整管线（PoolGenerator → PoolRenderer → 编排 → 母带）渲染 2 曲（「钟璃幻境」96BPM/C、「金属仪式」120BPM/Em），乐池以 **8 件新引擎乐器**（玻璃钟/金属钟/金属板/玻璃铺底/马林巴棒/管钟/颂钵/锣）+ 标准 bass/drum 兜底节奏构成。
- 输出 `D:\bloodmusic\album_new_engines_demo`：2 曲 ×（_sources 独立分轨 / stems / song_final.wav），2/2 成功，总时长 18s，RMS≈5000。8 件新引擎乐器均独立分轨落盘，确认专辑流程端到端产出真实新引擎音色。
- 环境警告（ffmpeg / audio_pipeline 的 `sampler` 导入）为可选 pipeline 依赖缺失，核心合成路径不受影响，非阻塞。

### 未做项
- 原始 8 个引擎（SUBTRACTIVE/FM/…）中 FM/FM_ADVANCED/WAVETABLE/KARPLUS_STRONG/WAVEGUIDE/GRANULAR 已有专属渲染方法，ADDITIVE/MODAL/HYBRID 经 `_render_note_signal` 接入；Neural/DDSP 仍为 P3 未来方向。
- （历史）Material-aware SFX 已接为乐器池 drum 角色的 `SynthEngine.MATERIAL`（见 P3 执行记录 #29）。

---

## P3 执行记录（2026-08-22 复核 + 落地）

### P3-a HRTF 双耳空间化（Spatial）
- 新增 `effects/spatial.py`：纯合成（零采样）HRTF 模型 `apply_hrtf(azimuth, elevation, distance, ...)`：
  - ITD（Woodworth 近似 + 分数延迟插值）、ILD（高频头部阴影低通 + 增益衰减）、pinna notch（`iirnotch`，仰角驱动）、距离衰减（1/r + 空气吸收低通）。
  - 另提供卷积变体 `apply_hrtf_convolution` / `synthesize_hrir`（合成 HRIR，FFT 卷积）。
- `effects/chain.py`：`EffectChain` 新增 `spatial_enabled / spatial_azimuth / spatial_elevation / spatial_distance`，在立体声步之后调用 `apply_hrtf`。
- `effects/__init__.py` 导出 `apply_hrtf / synthesize_hrir / apply_hrtf_convolution`。
- 验证（`_validate_hrtf.py`，ALL PASS）：形状 (n,2)；ITD 符号正确（az=+60 → 左耳峰值晚 27 样本，az=-60 早 27）；ILD（az=+60 右耳 RMS≈0.066 > 左耳≈0.025）；pinna notch（elev45/elev0 频段能量比 0.33）；距离（d=1→0.98，d=5→0.32）；卷积变体形状 (44100,2)；EffectChain 集成形状 (44100,2)。

### P3-b 复核发现的真实缺陷与修正（#30 真实落地关键）
> 此前 P1/P2 文档称「新引擎已端到端渲染验证通过」，但本轮实测发现两处**真实阻断缺陷**，导致 8 件新引擎乐器在《SPECTRUM》专辑中并未真正以正确音色出现：

1. **`extra_instruments` 的 `engine_params` 在 `album_maker/track.py:_build_pool_for_track()` 被丢弃**（只传了 name/role/engine/preset/volume/pan/note_sequence，未传 `engine_params`/`params`/`automation`/`octave`）。后果：8 件新引擎的 `preset`（glass/bowl/tubular/bar/gong/metal）全部丢失，模态乐器退化成默认 `bar`、加法乐器退化成默认 `glass`，音色与配置不符。
   - **修正**：补齐 `engine_params=inst_data.get("engine_params") or {}` 等字段透传。

2. **`fx` 角色 + 风格 FX 关闭（默认）→ 静音 pattern**。8 件新引擎中 5 件被配为 `role: fx`（玻璃铃/管钟/马林巴/金属板/锣），而 `pool_generator.generate_fx()` 在 FX 风格未启用时返回 `notes=[None], volume=0.0` 的静音 pattern。后果：这 5 件在专辑中完全不发声——与「并入专辑生产」相悖。
   - **修正**：`generate_fx()` 对携带真实音高引擎（ADDITIVE/MODAL/HYBRID）的乐器，即便 FX 风格关闭也渲染一段可闻 drone（八度 4、音量 `instrument.volume*0.5`、适度颤音与高截止），普通 fx 乐器维持原静音行为不变。

> 说明：PoolRenderer 的 ADDITIVE/MODAL/HYBRID 分支本就委托 `render_pattern_to_array`，而后者经 `pattern.py:_render_note_signal()` 真实消费 `engine`，故**渲染层从未沉默 fallback**；上述两处才是阻断新引擎「以正确音色可闻并入」的真正缺陷。

### P3-c 《SPECTRUM 频谱万象》8 件新引擎并入（#30 真实落地）
- 配置 `configs/spectrum_album.yaml` 的 `extra_instruments` 将 8 件新引擎逐曲织入（玻璃铃/金属铃/金属板/玻璃铺/马林巴/管钟/颂钵/锣，engine=additive/modal）。
- 经 P3-b 两处修正后，全 12 曲渲染验证通过（见 `logs/spectrum_render_v4.log`）：pad 角色（玻璃铺/颂钵）以**正确 preset** 发声；fx 角色（玻璃铃/管钟/马林巴/金属板/锣）由静音修正为**可闻 drone**，且全部经真实 additive/modal 合成（非沉默 fallback）。
- 验证脚本：`_validate_p1_wiring.py`（单元：三引擎真实合成、preset 区分、形状一致）、`_validate_album_integration.py`（集成：真实配置→pool→生成→渲染走真实新引擎合成）。
