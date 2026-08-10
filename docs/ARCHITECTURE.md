# BloodMusic 全面增强 — 系统架构设计

> 架构师: 高见远 (Gao)  
> 版本: v2.0  
> 日期: 2025-07

---

## Part A: 系统设计

### 1. 实现方案与框架选型

#### 1.1 核心技术挑战

| 挑战 | 说明 | 解决思路 |
|------|------|----------|
| **滤波器性能** | 现有一阶 IIR 使用 Python for 循环，极慢 | 使用 `scipy.signal.butter` + `scipy.signal.lfilter` 向量化替换 |
| **混响质量** | comb-filter 混响音质差，金属感重 | 实现 Schroeder 混响：4×并行 comb + 2×串联 allpass |
| **LFO 调制架构** | 现有 SynthVoice 无 LFO | 在 `synthesize_voice()` 中增加 LFO 调制路径，新增 `LFOParams` dataclass |
| **FM 合成** | 现有只有减法合成 | 新增 `FMSynthVoice`，双算子 (carrier + modulator)，不修改原 SynthVoice |
| **多轨/和弦/鼓点** | MusicPattern 只支持单音序列 | 新增 `DrumPattern` + `MultiTrackPattern`，MusicPattern 增加和弦字段 |
| **导出归一化** | 现有只做简单限幅 | 在 `batch.py` 和 `pattern.py` 中增加 -1dBFS 归一化 + 硬限幅 |
| **OGG/FLAC 导出** | 仅支持 WAV | 新增 `soundfile` 依赖，在导出层统一处理格式 |

#### 1.2 框架与库选型

| 库 | 版本 | 用途 | 选择理由 |
|----|------|------|----------|
| `numpy` | 已有 | 数组计算 | 已有依赖，无需更改 |
| `scipy` | 已有 | 信号处理 | 已有依赖，`signal.butter/lfilter` 替换 for 循环 |
| `sounddevice` | 已有 | 实时播放 | 已有依赖 |
| `tkinter` | 标准库 | GUI | 已有依赖，保持不变 |
| `soundfile` | ^0.12 | OGG/FLAC 导出 | 轻量、支持 OGG Vorbis + FLAC + WAV，比 pydub 无需 ffmpeg |

#### 1.3 架构模式

- **增量增强**：所有新功能通过新增字段（默认值=None/0）和新增类实现，不破坏现有 API
- **分层架构**：`core → effects → music/sfx → export → playback → gui`
- **策略模式**：LFO 调制目标通过 `LFOTarget` 枚举选择策略
- **组合模式**：`MultiTrackPattern` 组合多个 `MusicPattern` / `DrumPattern`

---

### 2. 文件列表

> `[新建]` = 全新文件，`[修改]` = 修改现有文件

```
bloodmusic/
├── core/
│   ├── constants.py            [修改] 新增 NORMALIZE_DBFS 常量
│   ├── note_utils.py           [修改] 修复 freq_to_midi bug
│   ├── oscillator.py           [不变]
│   ├── envelope.py             [不变]
│   ├── voice.py                [修改] 新增 LFOParams, SynthVoice 增加 LFO 字段, synthesize_voice 增加 LFO 调制
│   └── fm_synth.py             [新建] FMSynthVoice + synthesize_fm_voice
├── effects/
│   ├── __init__.py             [修改] 导出新函数
│   ├── chain.py                [修改] EffectChain 新增 bandpass/notch/EQ/compressor/chorus 字段, process_effects 增加新效果步骤
│   ├── filters.py              [修改] 用 scipy.signal 重写 lowpass/highpass, 新增 bandpass/notch, 用 lfilter 向量化
│   ├── spatial.py              [修改] 新增 Schroeder 混响, 保留 apply_simple_reverb 向后兼容
│   ├── dynamics.py             [新建] 压缩器/限幅器 (Compressor, Limiter)
│   ├── eq.py                   [新建] 三段参量 EQ (ParametricEQ)
│   └── modulation.py           [新建] Chorus 效果
├── music/
│   ├── __init__.py             [修改] 导出新类和新预设
│   ├── pattern.py              [修改] MusicPattern 新增 chords 字段, 新增 DrumPattern, MultiTrackPattern, 多轨混合渲染
│   ├── presets.py              [修改] 6→15+ 预设, 新增 RPG/平台跳跃风格
│   ├── arpeggiator.py          [新建] 琶音器 (Arpeggiator)
│   └── scale.py                [新建] 音阶/调式系统 (Scale 类)
├── sfx/
│   └── presets.py              [不变] 现有 40 个预设无需修改
├── export/
│   ├── __init__.py             [修改] 导出新导出函数
│   └── batch.py                [修改] 新增归一化/限幅, OGG/FLAC 导出, WAV 元数据
├── playback/
│   └── player.py              [不变]
├── gui/
│   └── workstation.py          [修改] 新增 DrumPattern/多轨/FM 预览, 格式选择, 新预设显示
├── __init__.py                 [修改] 导出新 API (FMSynthVoice, DrumPattern 等)
├── cli.py                      [修改] 新增 --format 参数
└── main.py                     [不变]
```

---

### 3. 数据结构与接口

```mermaid
classDiagram
    direction TB

    class LFOParams {
        +float rate = 0.0
        +float depth = 0.0
        +LFOTarget target = AMPLITUDE
    }

    class LFOTarget {
        <<enumeration>>
        AMPLITUDE
        FILTER_CUTOFF
        PITCH
    }

    class SynthVoice {
        +float freq = 440.0
        +OscType osc_type = SINE
        +float duration = 0.15
        +float volume = 1.0
        +EnvShape env_shape = PERCUSSIVE
        +ADSRParams adsr = None
        +EffectChain effect_chain = None
        +float pitch_mod = 0.0
        +float vibrato_rate = 0.0
        +float vibrato_depth = 0.0
        +float detune = 0.0
        +List~Tuple~ harmonics
        +LFOParams lfo = None          ← 新增
    }

    class FMSynthVoice {
        +float carrier_freq = 440.0
        +OscType carrier_type = SINE
        +float modulator_freq_ratio = 1.0
        +OscType modulator_type = SINE
        +float fm_depth = 100.0
        +float duration = 0.3
        +float volume = 1.0
        +EnvShape env_shape = PERCUSSIVE
        +ADSRParams adsr = None
        +EffectChain effect_chain = None
        +LFOParams lfo = None
    }

    class EffectChain {
        +Optional~float~ lp_filter_hz = None
        +Optional~float~ hp_filter_hz = None
        +Optional~float~ bp_center_hz = None      ← 新增
        +Optional~float~ bp_q = None               ← 新增
        +Optional~float~ notch_hz = None           ← 新增
        +Optional~float~ notch_q = None            ← 新增
        +float distortion = 0.0
        +Optional~int~ bit_crush = None
        +float reverb_mix = 0.0
        +float reverb_decay = 0.5
        +float reverb_delay_ms = 40.0
        +bool reverb_schroeder = False             ← 新增
        +float stereo_width = 0.0
        +Optional~CompressorParams~ compressor = None  ← 新增
        +Optional~ParametricEQParams~ eq = None        ← 新增
        +float chorus_mix = 0.0                      ← 新增
        +float chorus_rate = 0.5                      ← 新增
        +float chorus_depth = 0.002                   ← 新增
    }

    class CompressorParams {
        +float threshold_db = -12.0
        +float ratio = 4.0
        +float attack_ms = 10.0
        +float release_ms = 100.0
        +float makeup_db = 0.0
    }

    class ParametricEQParams {
        +float low_freq = 200.0
        +float low_gain_db = 0.0
        +float low_q = 1.0
        +float mid_freq = 1000.0
        +float mid_gain_db = 0.0
        +float mid_q = 1.0
        +float high_freq = 4000.0
        +float high_gain_db = 0.0
        +float high_q = 1.0
    }

    class MusicPattern {
        +str name
        +List~Optional~str~~ notes
        +List~float~ durations
        +Optional~List~int~~ octave_shifts = None
        +int bpm = 120
        +bool loop = True
        +OscType osc_type = SINE
        +float volume = 0.18
        +EnvShape env_shape = PAD
        +List~Tuple~ harmonics
        +float vibrato_rate = 0.0
        +float vibrato_depth = 0.0
        +float reverb_mix = 0.15
        +float reverb_decay = 0.8
        +float stereo_width = 0.3
        +Optional~float~ lp_filter_hz = None
        +Optional~List~List~str~~~ chords = None    ← 新增
    }

    class DrumPattern {
        +str name
        +int steps = 16
        +int bpm = 120
        +Dict~str~List~bool~~ tracks
        +Dict~str~DrumSoundParams~ sounds
        +bool loop = True
    }

    class DrumSoundParams {
        +OscType osc_type = NOISE_BROWN
        +float pitch_hz = 100.0
        +float decay = 0.15
        +float volume = 0.6
        +float hp_hz = 0.0
        +float lp_hz = 0.0
    }

    class MultiTrackPattern {
        +str name
        +int bpm = 120
        +bool loop = True
        +List~MusicPattern~ music_tracks
        +Optional~DrumPattern~ drum_track = None
    }

    class Scale {
        +str name
        +List~int~ intervals
        +root_note: str = "C"
        +octave: int = 4
        +get_notes() List~str~
        +get_freqs() List~float~
        +get_chord(degree: int, quality: str) List~str~
    }

    class Arpeggiator {
        +ArpMode mode = UP
        +int octaves = 1
        +float gate = 0.8
        +generate(notes, bpm, durations) List~Tuple~
    }

    class ArpMode {
        <<enumeration>>
        UP
        DOWN
        UP_DOWN
        RANDOM
    }

    SynthVoice --> LFOParams : lfo
    FMSynthVoice --> LFOParams : lfo
    EffectChain --> CompressorParams : compressor
    EffectChain --> ParametricEQParams : eq
    DrumPattern --> DrumSoundParams : sounds
    MultiTrackPattern --> MusicPattern : music_tracks
    MultiTrackPattern --> DrumPattern : drum_track
    Arpeggiator --> ArpMode : mode
    MusicPattern ..> Arpeggiator : uses
```

---

### 4. 程序调用流程

#### 4.1 FM 合成流程

```mermaid
sequenceDiagram
    participant Caller
    participant fm_synth as fm_synth.py
    participant osc as oscillator.py
    participant env as envelope.py
    participant chain as effects/chain.py

    Caller->>fm_synth: synthesize_fm_voice(voice: FMSynthVoice)
    fm_synth->>fm_synth: 计算 n_samples, t 数组
    fm_synth->>osc: oscillator(t, carrier_freq * ratio, modulator_type)
    osc-->>fm_synth: modulator_sig
    fm_synth->>fm_synth: modulated_freq = carrier_freq + fm_depth * modulator_sig
    fm_synth->>osc: oscillator(t, modulated_freq, carrier_type)
    osc-->>fm_synth: carrier_sig
    fm_synth->>fm_synth: LFO 调制 (如 lfo != None)
    fm_synth->>env: make_envelope(n_samples, env_shape, adsr)
    env-->>fm_synth: envelope
    fm_synth->>fm_synth: sig = carrier_sig * envelope * volume
    alt effect_chain != None
        fm_synth->>chain: process_effects(sig, chain)
        chain-->>fm_synth: processed_sig
    end
    fm_synth->>fm_synth: 归一化 + 限幅
    fm_synth-->>Caller: float32 波形
```

#### 4.2 多轨混合渲染流程

```mermaid
sequenceDiagram
    participant Caller
    participant pattern as pattern.py
    participant drum as DrumPattern
    participant multi as MultiTrackPattern
    participant effects as effects/chain.py
    participant export as export/batch.py

    Caller->>multi: render_multi_track(mtp: MultiTrackPattern, duration_sec)
    multi->>multi: 计算总时长, 生成时间轴
    loop 每个 MusicPattern 轨道
        multi->>pattern: render_pattern_to_array(pat)
        pattern-->>multi: track_sig (mono float64)
        multi->>multi: 累加到 mix_buffer
    end
    opt drum_track != None
        multi->>drum: render_drum_pattern(drum_track, duration)
        drum-->>multi: drum_sig (mono float64)
        multi->>multi: 累加 drum_sig 到 mix_buffer
    end
    multi->>multi: 归一化 (-1dBFS) + 硬限幅
    multi-->>Caller: mix_buffer (float32)
    Caller->>export: export_audio(mix_buffer, path, format)
    export->>export: normalize_and_limit(sig)
    export->>export: 按 format 写文件 (WAV/OGG/FLAC)
    export-->>Caller: 文件路径
```

#### 4.3 效果链处理流程（增强后）

```mermaid
sequenceDiagram
    participant Caller
    participant chain as chain.py
    participant filters as filters.py
    participant eq as eq.py
    participant dynamics as dynamics.py
    participant distortion as distortion.py
    participant modulation as modulation.py
    participant spatial as spatial.py

    Caller->>chain: process_effects(sig, chain)
    Note over chain: 1. 滤波器
    alt lp_filter_hz != None
        chain->>filters: apply_lowpass(sig, cutoff)
    end
    alt hp_filter_hz != None
        chain->>filters: apply_highpass(sig, cutoff)
    end
    alt bp_center_hz != None
        chain->>filters: apply_bandpass(sig, center, q)
    end
    alt notch_hz != None
        chain->>filters: apply_notch(sig, freq, q)
    end
    Note over chain: 2. EQ
    alt eq != None
        chain->>eq: apply_parametric_eq(sig, eq_params)
    end
    Note over chain: 3. 压缩器
    alt compressor != None
        chain->>dynamics: apply_compressor(sig, comp_params)
    end
    Note over chain: 4. 失真
    alt distortion > 0
        chain->>distortion: apply_distortion(sig, amount)
    end
    alt bit_crush != None
        chain->>distortion: apply_bit_crush(sig, depth)
    end
    Note over chain: 5. Chorus
    alt chorus_mix > 0
        chain->>modulation: apply_chorus(sig, mix, rate, depth)
    end
    Note over chain: 6. 混响
    alt reverb_mix > 0
        alt reverb_schroeder == True
            chain->>spatial: apply_schroeder_reverb(sig, mix, decay, sr)
        else
            chain->>spatial: apply_simple_reverb(sig, mix, decay, delay_ms, sr)
        end
    end
    Note over chain: 7. 立体声
    alt stereo_width > 0
        chain->>spatial: apply_stereo(sig, width, sr)
    end
    chain-->>Caller: processed_sig
```

---

### 5. 待明确事项

| 编号 | 问题 | 当前假设 | 备注 |
|------|------|----------|------|
| Q1 | OGG 编码模式 | 默认 128kbps CBR | soundfile 支持设置 bitrate |
| Q2 | 鼓点合成方式 | 纯合成 + 噪声塑形 | 无采样依赖，保持程序化 |
| Q3 | FM 算子级联 | 双算子 (2-op) | carrier + 1 modulator，后续可扩展 |
| Q4 | GUI 框架 | 保持 Tkinter | 不迁移 pygame-ce |
| Q5 | 新增预设风格 | RPG 探索 + 平台跳跃 | 新增约 9 个预设 |
| Q6 | 和弦表示法 | 同时支持 List[str] 和 str+quality | `chords=[["C4","E4","G4"]]` 或 `chord_names=["C_maj"]` |

---

## Part B: 任务分解

### 6. 依赖包列表

```
# 新增依赖
soundfile>=0.12.1         # OGG/FLAC/WAV 多格式导出 (替代部分 scipy.io.wavfile 用法)

# 已有依赖 (无需变更)
numpy                     # 数组计算
scipy                     # 信号处理 (butter, lfilter, sosfilt)
sounddevice               # 实时播放
```

---

### 7. 任务列表

#### T01: Bug 修复 + 核心基础设施增强
**优先级**: P0 | **复杂度**: S  
**依赖**: 无  
**说明**: 修复 freq_to_midi bug；增强常量定义；为 SynthVoice 添加 LFO 支持；新增 FMSynthVoice；导出层添加归一化/限幅

| 文件 | 操作 | 内容 |
|------|------|------|
| `core/note_utils.py` | 修改 | 修复 `freq_to_midi`：`(freq / _A4_FREQ).bit_length()` → `12 * math.log2(freq / _A4_FREQ)` |
| `core/constants.py` | 修改 | 新增 `NORMALIZE_DBFS = -1.0`，`DEFAULT_OGG_BITRATE = 128000` |
| `core/voice.py` | 修改 | 新增 `LFOParams` dataclass + `LFOTarget` 枚举；`SynthVoice` 新增 `lfo: Optional[LFOParams] = None`；`synthesize_voice()` 增加 LFO 调制路径 |
| `core/fm_synth.py` | 新建 | `FMSynthVoice` dataclass + `synthesize_fm_voice()` 函数 |
| `export/batch.py` | 修改 | 新增 `_normalize_and_limit(sig, target_dbfs)` 函数，导出前调用 |
| `music/pattern.py` | 修改 | `generate_music_wav()` 写入前调用归一化/限幅 |
| `core/__init__.py` | 修改 | 导出 `LFOParams`, `LFOTarget`, `FMSynthVoice`, `synthesize_fm_voice` |

#### T02: 效果器全面升级（滤波器 + 混响 + 新效果）
**优先级**: P0 | **复杂度**: L  
**依赖**: T01 (需要 LFOParams 定义)  
**说明**: scipy.signal 重写滤波器；新增 bandpass/notch；Schroeder 混响；压缩器；参量 EQ；Chorus；EffectChain 扩展

| 文件 | 操作 | 内容 |
|------|------|------|
| `effects/filters.py` | 修改 | 用 `scipy.signal.butter` + `sosfilt` 重写 `apply_lowpass`/`apply_highpass`；新增 `apply_bandpass(sig, center_hz, q)` / `apply_notch(sig, freq_hz, q)` |
| `effects/spatial.py` | 修改 | 新增 `apply_schroeder_reverb(sig, mix, decay, sr)` — 4×comb + 2×allpass；保留 `apply_simple_reverb` 向后兼容 |
| `effects/dynamics.py` | 新建 | `CompressorParams` dataclass + `apply_compressor(sig, params)` + `apply_limiter(sig, threshold_db)` |
| `effects/eq.py` | 新建 | `ParametricEQParams` dataclass + `apply_parametric_eq(sig, params)` — 三段参量均衡 |
| `effects/modulation.py` | 新建 | `apply_chorus(sig, mix, rate, depth, sr)` — 延迟线 + LFO 调制 |
| `effects/chain.py` | 修改 | `EffectChain` 新增 `bp_center_hz`/`bp_q`/`notch_hz`/`notch_q`/`reverb_schroeder`/`compressor`/`eq`/`chorus_mix`/`chorus_rate`/`chorus_depth` 字段；`process_effects()` 按新顺序处理全部效果 |
| `effects/__init__.py` | 修改 | 导出新增函数 |

#### T03: 音乐系统增强（和弦 + 鼓点 + 多轨 + 琶音 + 音阶）
**优先级**: P0 | **复杂度**: L  
**依赖**: T01, T02 (依赖效果器升级)  
**说明**: MusicPattern 支持和弦；新增 DrumPattern 步进序列器；MultiTrackPattern 多轨混合渲染；琶音器；音阶系统

| 文件 | 操作 | 内容 |
|------|------|------|
| `music/pattern.py` | 修改 | `MusicPattern` 新增 `chords: Optional[List[List[str]]] = None`；新增 `DrumPattern` dataclass + `DrumSoundParams` + `render_drum_pattern()`；新增 `MultiTrackPattern` dataclass + `render_multi_track()`；`generate_music_wav()` 增加和弦渲染逻辑 |
| `music/arpeggiator.py` | 新建 | `ArpMode` 枚举 (UP/DOWN/UP_DOWN/RANDOM) + `Arpeggiator` dataclass + `generate_arpeggio()` |
| `music/scale.py` | 新建 | `Scale` 类，预定义大调/小调/五声/蓝调等音阶，`get_notes()` / `get_freqs()` / `get_chord()` 方法 |
| `music/presets.py` | 修改 | 6→15+ 预设，新增 RPG 探索/平台跳跃/地下城/商店/标题画面等风格 |
| `music/__init__.py` | 修改 | 导出 `DrumPattern`, `DrumSoundParams`, `MultiTrackPattern`, `render_drum_pattern`, `render_multi_track`, `Arpeggiator`, `ArpMode`, `Scale` 及新增预设 |

#### T04: 导出增强 + CLI + 顶层集成
**优先级**: P1 | **复杂度**: M  
**依赖**: T01, T02, T03 (依赖所有功能模块完成)  
**说明**: OGG/FLAC 导出；WAV 元数据；CLI 新增 --format 参数；`__init__.py` 顶层导出新 API

| 文件 | 操作 | 内容 |
|------|------|------|
| `export/batch.py` | 修改 | 新增 `export_audio(sig, path, format="wav", bitrate=128000, metadata=None)` 统一导出函数，支持 WAV/OGG/FLAC；`AudioBatchExporter` 新增 `format` 参数和 `metadata` 参数；使用 `soundfile` 写 OGG/FLAC；WAV 写入 `soundfile` 以支持元数据 |
| `export/__init__.py` | 修改 | 导出 `export_audio` |
| `cli.py` | 修改 | `batch` 子命令新增 `--format` (wav/ogg/flac) 和 `--bitrate` 参数 |
| `__init__.py` | 修改 | 顶层导出所有新增 API (FMSynthVoice, synthesize_fm_voice, LFOParams, LFOTarget, DrumPattern, MultiTrackPattern, Scale, Arpeggiator, apply_bandpass, apply_notch, apply_schroeder_reverb, apply_compressor, apply_parametric_eq, apply_chorus, CompressorParams, ParametricEQParams 等) |

#### T05: GUI 更新
**优先级**: P1 | **复杂度**: M  
**依赖**: T03, T04 (依赖新功能模块和导出能力)  
**说明**: GUI 适配新增的 DrumPattern/MultiTrackPattern/FM 合成预览；新增格式选择；展示新预设

| 文件 | 操作 | 内容 |
|------|------|------|
| `gui/workstation.py` | 修改 | 左侧列表新增 DrumPattern / MultiTrackPattern / FMSynthVoice 分类；预览逻辑适配新类型；导出区新增格式下拉框 (WAV/OGG/FLAC)；预设列表展示新增的 15+ 音乐预设 |

---

### 8. 共享知识

```
1. 采样率常量: 所有模块统一使用 core.constants.SR (44100)，不硬编码
2. 归一化标准: 导出前统一调用 _normalize_and_limit(sig, target_dbfs=-1.0)
   - 目标: 峰值 -1dBFS = 10^(-1/20) ≈ 0.8913
   - 硬限幅: np.clip(sig, -1.0, 1.0)
3. 新增字段默认值: 所有新增 Optional 字段默认 None，数值字段默认 0.0，确保向后兼容
4. 函数签名: 现有函数签名不变，新参数通过可选参数追加在末尾
5. 类型注解: 使用 Python 3.10+ 语法 (Optional[X], list[X], dict[K,V])
6. 信号流: mono float64 在效果链内部流转，最终输出 float32
7. 效果链顺序: 滤波器 → EQ → 压缩器 → 失真 → Chorus → 混响 → 立体声
8. scipy 滤波器: 统一使用 sos (second-order sections) 格式，数值更稳定
9. 命名规范: apply_xxx 效果函数，synthesize_xxx 合成函数，render_xxx 渲染函数
10. 导出格式: WAV (默认, 16bit PCM), OGG (Vorbis, 默认 128kbps CBR), FLAC (lossless)
```

---

### 9. 任务依赖图

```mermaid
graph TD
    T01[T01: Bug修复+核心增强<br/>P0 / S]
    T02[T02: 效果器全面升级<br/>P0 / L]
    T03[T03: 音乐系统增强<br/>P0 / L]
    T04[T04: 导出增强+CLI+集成<br/>P1 / M]
    T05[T05: GUI更新<br/>P1 / M]

    T01 --> T02
    T01 --> T03
    T02 --> T03
    T03 --> T04
    T02 --> T04
    T04 --> T05
    T03 --> T05
```

**关键路径**: T01 → T02 → T03 → T04 → T05

**并行机会**: T02 和 T03 之间 T02 必须先完成（音乐渲染依赖效果器），但 T01 完成后 T02 可立即开始，不需要等 T03。
