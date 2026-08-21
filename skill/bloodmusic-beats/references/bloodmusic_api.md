# BloodMusic API 参考

## 项目概述

BloodMusic 是一个纯 Python 的程序化音频合成引擎，支持零依赖（仅需 numpy/scipy）生成音乐和音效。适用于游戏配乐、beat 制作、音效设计、完整歌曲编曲。

## 安装

```bash
cd G:\tools\audio\bloodmusic
pip install -e .
```

**注意**: 需要先修复 `pyproject.toml`，在 `[tool.setuptools]` 的 `packages` 列表中添加 `"bloodmusic"`，并在 `[tool.setuptools.package-dir]` 中添加 `bloodmusic = "."`。

## 核心常量

```python
from bloodmusic import SR  # 44100 Hz 采样率
```

---

## 鼓合成 (bloodmusic.sfx.drum_synth)

### 808 底鼓

```python
from bloodmusic.sfx.drum_synth import synthesize_808_kick, Kick808Params

kick = synthesize_808_kick(Kick808Params(
    freq_start=150.0,   # 起始频率 Hz
    freq_end=40.0,      # 结束频率 Hz
    duration=0.4,       # 时长 秒
    freq_decay=0.05,    # 频率衰减速度
    amp_decay=0.2,      # 振幅衰减速度
    click_level=0.35,   # 点击/attack 音量
    distortion=0.2,     # 失真量
    volume=0.88,        # 整体音量
))
```

### 808 军鼓

```python
from bloodmusic.sfx.drum_synth import synthesize_808_snare, Snare808Params

snare = synthesize_808_snare(Snare808Params(
    tone_freq=180,       # 音调频率
    tone_decay=0.1,      # 音调衰减
    noise_decay=0.15,    # 噪声衰减
    duration=0.25,       # 时长
    volume=0.75,         # 音量
))
```

### 808 踩镲

```python
from bloodmusic.sfx.drum_synth import synthesize_808_hihat, Hihat808Params

hihat = synthesize_808_hihat(Hihat808Params(
    osc_freq=8000,      # 振荡频率 (越高越亮)
    decay=0.06,         # 衰减
    duration=0.1,       # 时长
    volume=0.45,        # 音量
))

# 开镲 (更长衰减)
open_hat = synthesize_808_hihat(Hihat808Params(
    osc_freq=8000, decay=0.25, duration=0.3, volume=0.35,
))
```

---

## 鼓 Pattern 系统 (bloodmusic.music)

### DrumSoundParams - 鼓音色参数

```python
from bloodmusic.music import DrumSoundParams
from bloodmusic import OscType

sound = DrumSoundParams(
    osc_type=OscType.SINE,      # 振荡器类型: SINE, SQUARE, SAW, TRIANGLE, NOISE_WHITE, NOISE_PINK, NOISE_BROWN
    pitch_hz=55,                # 音高 Hz (底鼓 40-80, 军鼓 150-250, 踩镲 5000-10000)
    decay=0.22,                 # 衰减时间 秒
    volume=0.7,                 # 音量 0-1
    hp_hz=200,                  # 高通滤波器 Hz (用于去除非低频噪声)
    lp_hz=8000,                 # 低通滤波器 Hz
    body_hz=100,                # 体共振频率
    noise_mix=0.3,              # 噪声混合比例
)
```

### DrumPattern - 鼓 Pattern 定义

```python
from bloodmusic.music import DrumPattern

drum = DrumPattern(
    name="my_drums",
    steps=16,           # 每 Pattern 步数 (通常 16 = 1 小节 4/4)
    bpm=120,            # 速度
    tracks={            # 每轨: 16 个 bool 值，True=触发
        "kick":  [True, False, False, False, True, False, False, False,
                  True, False, False, False, True, False, False, False],
        "snare": [False, False, False, False, True, False, False, False,
                  False, False, False, False, True, False, False, False],
        "hihat": [True, False, True, False, True, False, True, False,
                  True, False, True, False, True, False, True, False],
    },
    sounds={            # 每轨音色
        "kick":  DrumSoundParams(...),
        "snare": DrumSoundParams(...),
        "hihat": DrumSoundParams(...),
    },
)
```

### MusicPattern - 音乐 Pattern

```python
from bloodmusic.music import MusicPattern
from bloodmusic import OscType
from bloodmusic.core.envelope import EnvShape

melody = MusicPattern(
    name="my_melody",
    chords=[              # 和弦 (每个元素是音符名列表)
        ["A4", "C5", "E5", "G5"],   # Am7
        ["D4", "F5", "A5", "C6"],   # Dm7
    ],
    notes=[None, "E5", None, "D5"],  # 单音旋律 (None=无)
    durations=[1.0, 0.5, 0.5, 1.0], # 每音符/和弦时长 拍
    bpm=120,
    loop=True,
    osc_type=OscType.SINE,  # 波形
    volume=0.3,
    env_shape=EnvShape.PAD,         # 必须使用 EnvShape 枚举:
                                     #   EnvShape.PERCUSSIVE - 快速衰减
                                     #   EnvShape.PAD        - 慢起慢落
                                     #   EnvShape.SUSTAINED  - 保持型
    harmonics=[(1.0, 1.0), (2.0, 0.3)],  # 谐波: (频率倍率, 振幅)
    vibrato_rate=5.0,       # 颤音频率
    vibrato_depth=0.2,      # 颤音深度
    reverb_mix=0.3,         # 混响混合 0-1
    reverb_decay=1.5,       # 混响衰减 (建议 ≤2.0)
    stereo_width=0.5,       # 立体声宽度 0-1
    lp_filter_hz=4000,      # 低通滤波
    hp_filter_hz=80,        # 高通滤波
)
```

**重要**: `env_shape` 必须使用 `EnvShape` 字符串枚举，**不能**使用整数。错误示例: `env_shape=1` → 会导致静音。

### MultiTrackPattern - 多轨组合

```python
from bloodmusic.music import MultiTrackPattern, render_multi_track

multi = MultiTrackPattern(
    name="full_arrangement",
    bpm=120,
    loop=True,
    music_tracks=[melody1, melody2],  # MusicPattern 列表
    drum_track=drum,                   # 单个 DrumPattern
    mix_volumes=[0.8, 0.6],           # 可选: 各轨独立音量
)

audio = render_multi_track(multi, duration_seconds=30.0)
```

---

## 预设 (bloodmusic.music.presets)

```python
from bloodmusic.music.presets import (
    BATTLE_HIGH_MUSIC,   # 战斗高音轨
    BATTLE_LOW_MUSIC,    # 战斗低音轨
    BOSS_FIGHT_MUSIC,    # Boss 战斗音乐
    DUNGEON_MUSIC,       # 地下城氛围
    MENU_MUSIC,          # 菜单音乐
    TAVERN_MUSIC,        # 酒馆音乐
    PLATFORMER_MUSIC,    # 平台跳跃音乐
)
```

---

## 欧几里得节奏 (bloodmusic.music.euclidean)

```python
from bloodmusic.music.euclidean import get_euclidean_tracks

# 预设节奏风格:
# "combat_intense" - 激烈战斗
# "combat_heavy"   - 重击战斗
# "boss_epic"      - 史诗 Boss
# "stealth"        - 潜行
# "chase"          - 追逐
# "ambient_drums"  - 氛围鼓点

tracks = get_euclidean_tracks("combat_intense")
# 返回: {"kick": [...], "snare": [...], "hihat": [...]}
```

---

## 歌曲编曲 (bloodmusic.music.arrangement)

构建完整歌曲结构，支持段落、过渡、音轨路由、总线混音。

### SongArrangement - 歌曲编排

```python
from bloodmusic.music.arrangement import (
    SongArrangement, Section, Transition, render_song,
    TrackChannel, MixBus, SongMixer, create_song_template,
)

# 定义段落
intro = Section(name="intro", start_time=0, duration=8)
verse = Section(name="verse", start_time=8, duration=16)
chorus = Section(name="chorus", start_time=24, duration=16)
bridge = Section(name="bridge", start_time=40, duration=8)
outro = Section(name="outro", start_time=48, duration=8)

# 定义过渡
transitions = [
    Transition(from_section="intro", to_section="verse",
               start_time=7.5, duration=1.0, type_="crossfade"),
    Transition(from_section="verse", to_section="chorus",
               start_time=23.5, duration=0.5, type_="build"),
    Transition(from_section="bridge", to_section="outro",
               start_time=47.5, duration=1.0, type_="fade"),
]

# Track routing (将音轨路由到混音总线)
track_channels = [
    TrackChannel(track_name="drums", bus="rhythm", volume=0.9, pan=0.0),
    TrackChannel(track_name="bass", bus="low_end", volume=0.8, pan=0.0),
    TrackChannel(track_name="melody", bus="mid", volume=0.75, pan=0.2),
    TrackChannel(track_name="pad", bus="mid", volume=0.6, pan=-0.3),
]

# Bus-level mixing (每条总线独立的 EQ / 压缩)
mixer = SongMixer(buses={
    "rhythm":  MixBus(eq={"low_shelf": (100, 2), "high_shelf": (10000, -2)},
                       compressor={"threshold": -12, "ratio": 4}),
    "low_end": MixBus(eq={"high_cut": 5000}),
    "mid":     MixBus(eq={"peaking": [(2500, -2, 1.0)]}),
})

arrangement = SongArrangement(
    name="my_song",
    bpm=120,
    sections=[intro, verse, chorus, bridge, outro],
    transitions=transitions,
    track_channels=track_channels,
    mixer=mixer,
)

audio = render_song(arrangement)
```

### create_song_template - 快速模板

```python
# 5 种内置模板:
arrangement = create_song_template("pop")       # 流行歌: intro→verse→chorus→verse→chorus→bridge→chorus→outro
arrangement = create_song_template("edm")       # EDM: intro→buildup→drop→breakdown→buildup→drop→outro
arrangement = create_song_template("ambient")   # 氛围: intro→pad→texture→climax→outro
arrangement = create_song_template("trap")      # Trap: intro→verse→hook→verse→hook→bridge→hook→outro
arrangement = create_song_template("cinematic") # 影视: intro→theme→conflict→resolution→finale
```

### Transition 类型

- `"crossfade"` — 交叉淡入淡出
- `"build"` — 渐强过渡
- `"fade"` — 淡出再淡入
- `"hard"` — 硬切

---

## 效果链 (bloodmusic.effects.chain)

完整的效果处理链，支持 EQ、压缩、失真、调制效果、延迟、混响。

### EffectChain - 效果链

```python
from bloodmusic.effects.chain import EffectChain

chain = EffectChain(
    # EQ (3 段参数均衡器)
    eq_low_shelf=(100, -3),         # 低频搁架: (freq_hz, db_gain)
    eq_high_shelf=(8000, 2),        # 高频搁架: (freq_hz, db_gain)
    eq_peaking=[(2500, -2, 1.0)],   # 参量均衡: [(freq, gain_db, Q)]

    # 压缩器
    compressor_threshold=-18,        # dB
    compressor_ratio=4,              # 压缩比
    compressor_attack=0.005,         # 启动时间 秒
    compressor_release=0.1,          # 释放时间 秒
    compressor_makeup=3,             # 补偿增益 dB

    # 失真
    distortion_drive=0.0,            # 0=纯净, 1=重失真
    distortion_mix=0.0,

    # Flanger
    flanger_mix=0.3,                 # 混合比例
    flanger_rate=0.5,                # LFO 频率 Hz
    flanger_depth=0.004,             # 深度 (延迟时间偏移 秒)
    flanger_feedback=0.3,            # 反馈量

    # Phaser
    phaser_mix=0.2,
    phaser_rate=0.3,                 # LFO 频率 Hz
    phaser_depth=0.7,                # 深度
    phaser_stages=4,                 # 全通滤波器级数
    phaser_feedback=0.5,

    # Chorus
    chorus_mix=0.25,
    chorus_rate=1.2,
    chorus_depth=0.005,
    chorus_voices=3,

    # Delay
    delay_mix=0.3,                   # 干湿混合
    delay_time=0.25,                 # 延迟时间 秒 (或使用拍数)
    delay_feedback=0.4,              # 反馈量
    delay_pingpong=True,             # 乒乓延迟 (立体声)
    delay_multitap=False,            # 多拍延迟

    # Reverb
    reverb_mix=0.35,                 # 0-1, 建议 ≤0.5
    reverb_decay=1.5,                # 衰减时间, 建议 ≤2.0
    reverb_damping=0.5,              # 高频阻尼
)

processed = chain.process_effects(audio)
```

**效果处理管道顺序**: Filters → EQ → Compressor → Distortion → Flanger/Phaser → Chorus → Delay → Reverb → Stereo

### 谐振滤波器 (bloodmusic.effects.filters)

```python
from bloodmusic.effects.filters import apply_resonant_lpf, apply_resonant_hpf

# 2-pole 双二阶滤波器, 支持 Q 控制
audio = apply_resonant_lpf(audio, cutoff_hz=2000, q=2.5)   # Q=2.5 → 明显谐振峰
audio = apply_resonant_lpf(audio, cutoff_hz=2000, q=0.707) # Q=0.707 → Butterworth (平坦)
audio = apply_resonant_hpf(audio, cutoff_hz=200,  q=0.707) # 高通, 切除低频轰鸣
```

---

## 自动化 (bloodmusic.music.automation)

基于时间线的参数自动化控制，支持滤波器扫频、音量渐变、声像移动。

### AutomationLane - 自动化轨道

```python
from bloodmusic.music.automation import (
    AutomationLane, AutomationPoint, AutomationTrack,
    apply_filter_sweep, apply_volume_automation, apply_pan_automation,
)

# 自动化点
points = [
    AutomationPoint(time=0.0, value=200),
    AutomationPoint(time=4.0, value=800),
    AutomationPoint(time=8.0, value=8000, interpolation="smooth"),
]

lane = AutomationLane(parameter="lp_filter_hz", points=points)

# interpolation 模式:
#   "linear" - 线性插值 (默认)
#   "smooth" - 余弦缓动
#   "step"   - 阶跃 (瞬间跳变)

# 应用滤波器扫频
audio = apply_filter_sweep(audio, lane, q=1.5)

# 应用音量自动化
vol_lane = AutomationLane(parameter="volume", points=[
    AutomationPoint(time=0.0, value=0.0),
    AutomationPoint(time=2.0, value=1.0, interpolation="smooth"),
    AutomationPoint(time=28.0, value=1.0),
    AutomationPoint(time=30.0, value=0.0, interpolation="smooth"),
])
audio = apply_volume_automation(audio, vol_lane)

# 应用声像自动化
pan_lane = AutomationLane(parameter="pan", points=[
    AutomationPoint(time=0.0, value=-0.8),
    AutomationPoint(time=1.0, value=0.8, interpolation="smooth"),
    AutomationPoint(time=2.0, value=-0.8, interpolation="smooth"),
])
audio = apply_pan_automation(audio, pan_lane)
```

### 自动化预设

```python
from bloodmusic.music.automation import (
    build_up_lowpass,         # 渐开低通: 200→8000 Hz (上升感)
    fade_in_out,              # 淡入淡出: 0→1→0
    auto_pan_sine,            # 正弦自动声像: L↔R 摆动
    drop_filter_resonance,    # 滤波器共鸣下降 (drop 效果)
)
```

---

## Bass 合成 (bloodmusic.music.bass)

专用低频合成器，4 种预置风格。

### BassSynth - Bass 合成器

```python
from bloodmusic.music.bass import BassSynth, render_bass_pattern
from bloodmusic.core.envelope import EnvShape
from bloodmusic.core.oscillator import OscType

# 4 种预置:
sub  = BassSynth.preset("sub")    # Sub: 纯正弦 + 谐波叠加, 深沉有力
fm   = BassSynth.preset("fm")     # FM: DX7 风格频率调制, 金属质感
acid = BassSynth.preset("acid")   # Acid: 锯齿波 + 谐振 LPF + 失真, TB-303 风格
pluck= BassSynth.preset("pluck")  # Pluck: 三角波快速衰减, 弹拨感

# 自定义 Bass
my_bass = BassSynth(
    osc_type=OscType.SAW,          # 波形
    cutoff_hz=800,                  # 滤波器截止频率
    resonance=2.0,                  # 谐振 Q 值 (1-10)
    distortion=0.3,                 # 失真量 (0-1)
    envelope_shape=EnvShape.PERCUSSIVE,
    volume=0.75,
    fm_amount=0.0,                  # FM 调制量 (仅 FM 预置)
    fm_ratio=2.0,                   # FM 频率比
)

# 渲染 Bass pattern
from bloodmusic.music import MusicPattern
pattern = MusicPattern(
    notes=["C2", "C2", "G2", "G2", "A2", "A2", "F2", "F2"],
    durations=[0.5] * 8,
    bpm=120,
)
bass_audio = render_bass_pattern(pattern, duration_seconds=8.0)
```

---

## 和声系统 (bloodmusic.music.harmony)

多声部和声生成与声部编排。

### 和声生成

```python
from bloodmusic.music.harmony import (
    generate_parallel_harmony,    # 平行和声 (固定音程)
    generate_diatonic_harmony,    # 自然音阶和声 (保持调性)
    generate_chordal_harmony,     # 和弦式和声 (从和弦进行推导)
    voice_leading,                # SATB 声部进行 (最小移动)
    render_harmony_tracks,        # 渲染所有声部为音频
    HarmonyVoice,
)

melody_notes = ["C4", "E4", "G4", "A4", "C5", "D5", "E5", "G5"]
melody_durs = [0.5] * 8

# 平行和声 (上方 3 度)
harmony = generate_parallel_harmony(melody_notes, interval=3)

# 自然音阶和声 (C 大调, 3 度)
harmony = generate_diatonic_harmony(melody_notes, key="C", interval=3)

# 和弦式和声
chords = [["C4","E4","G4"], ["F4","A4","C5"], ["G4","B4","D5"], ["C4","E4","G4"]]
harmony = generate_chordal_harmony(melody_notes, chords)

# 声部进行 — 最小化声部移动
voices = voice_leading(melody_notes, harmony_voices=[harmony])

# 渲染所有声部
tracks = render_harmony_tracks(voices, melody_durs, bpm=120)
```

---


## 导出

```python
from bloodmusic.export import export_wav, AudioConfig

export_wav(audio, "output.wav", config=AudioConfig(normalize=True))

# 或直接使用 scipy
from scipy.io import wavfile
import numpy as np

audio_norm = audio / np.max(np.abs(audio)) * 0.95
wavfile.write("output.wav", 44100, (audio_norm * 32767).astype(np.int16))
```

---

## 手动 808 beat 编排模板

```python
def manual_808_beat(bpm, bars, kick_hits, snare_hits, hihat_subdiv=2):
    beat_dur = 60.0 / bpm
    total_dur = bars * 4.0 * beat_dur
    result = np.zeros(int(total_dur * SR))

    kick = synthesize_808_kick(Kick808Params(freq_start=150, freq_end=45, ...))
    snare = synthesize_808_snare(Snare808Params(...))
    hihat = synthesize_808_hihat(Hihat808Params(...))

    def place_hit(audio_hit, position_beats):
        pos = int(position_beats * beat_dur * SR)
        end = min(pos + len(audio_hit), len(result))
        result[pos:end] += audio_hit[:end - pos]

    for pos in kick_hits:
        place_hit(kick, pos)
    for pos in snare_hits:
        place_hit(snare, pos)
    for i in range(int(total_dur / (beat_dur / hihat_subdiv))):
        place_hit(hihat, i / hihat_subdiv)

    return np.clip(result / max(np.max(np.abs(result)), 1e-8), -1, 1)
```
