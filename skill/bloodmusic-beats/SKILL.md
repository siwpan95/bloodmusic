---
name: bloodmusic-beats
description: >
  This skill should be used when the user wants to produce beats, drum patterns, or instrumental music
  using the BloodMusic programmatic audio synthesis engine at this repository root.
  Triggers include: "make a beat", "create a drum pattern", "produce music with code",
  "generate 808 beats", "make trap/boom-bap/lo-fi/EDM beats", "create game music with drums",
  "compose a song", "make a complete track", "add bass line", "add harmony", "automate filter",
  or any request to programmatically generate WAV audio files with drum rhythms and melodies.
  Supports 7 beat styles: Trap, Boom Bap, Lo-Fi, Battle, Drum-Only, EDM, and Ambient.
  Also supports full song arrangement, effect chains, automation, bass synthesis, harmony, and automation lanes.
  Supports InstrumentPool (乐器池) for YAML-driven multi-instrument composition,
  album generation with --pool mode, and 10 preset album-style YAML configurations.
  Triggers include: "build an instrument pool", "generate music from instrument pool",
  "album with pool", "pool render", "create instrument pool", "generate album with pool",
  "使用乐器池", "乐池生成", "InstrumentPool".
---

# BloodMusic Beats

## Overview

Use the BloodMusic engine (in this repository) to programmatically synthesize beats, drum patterns, full music arrangements, and complete songs. Generate WAV audio files by combining 808 drum synthesis, Euclidean rhythms, music presets, custom patterns, bass synthesis, harmony generation, effects chains, and automation lanes.

The engine also includes the **InstrumentPool** system — define a multi-instrument ensemble via YAML, pick a StylePreset, and render a complete arrangement with one call. Use the `album_maker` subpackage (`python -m bloodmusic.album_maker.cli make`) to generate a multi-style album from pool presets. The legacy root-level `album_generator.py` script has been removed from the repo (historical versions remain in git history); use `album_maker` instead.

## Quick Start — Generate All Beat Styles

Execute the bundled script to produce all 7 beat styles at once:

```bash
python scripts/make_beats.py
```

Output files appear in `./output_beats/` (with timestamps to avoid overwrites):
- `trap_beat_YYYYMMDD_HHMMSS.wav` — Dark 808 rhythms at 140 BPM (~3.4 min)
- `boom_bap_beat_YYYYMMDD_HHMMSS.wav` — Classic 90s hip-hop swing at 92 BPM (~3.5 min)
- `lofi_beat_YYYYMMDD_HHMMSS.wav` — Relaxed jazz-chord grooves at 78 BPM (~3.7 min)
- `battle_beat_YYYYMMDD_HHMMSS.wav` — Boss fight music + intense drums at 145 BPM (~3.5 min)
- `drum_only_beat_YYYYMMDD_HHMMSS.wav` — Acapella-ready drum loop at 95 BPM (~3.5 min)
- `edm_beat_YYYYMMDD_HHMMSS.wav` — Four-on-the-floor dance beat at 128 BPM (~3.5 min)
- `ambient_beat_YYYYMMDD_HHMMSS.wav` — Dungeon atmosphere + sparse percussion at 70 BPM (~3.7 min)

## Environment Setup

Before using BloodMusic, ensure it is installed:

```bash
cd <PATH>
pip install -e .
```

If `from bloodmusic import ...` fails, check the repo's `pyproject.toml`:
- `[tool.setuptools].packages` must include `"bloodmusic"`
- `[tool.setuptools.package-dir]` must include `bloodmusic = "."`

Required dependencies: `numpy`, `scipy`, `sounddevice`, `soundfile`.

## Beat Creation Workflows

### Workflow 1: Manual 808 Beat (Trap / Boom Bap style)

Use `bloodmusic.sfx.drum_synth` for precise control over each hit placement:

1. Synthesize drum one-shots with `synthesize_808_kick()`, `synthesize_808_snare()`, `synthesize_808_hihat()`
2. Calculate `beat_dur = 60.0 / bpm` to convert beats to sample positions
3. Place each hit at its beat position: `result[pos:pos+len(hit)] += hit`
4. Normalize and export with `scipy.io.wavfile.write()`

Key parameters for tuning 808 character:
- Kick: `freq_start`/`freq_end` (pitch sweep), `distortion` (aggression), `click_level` (attack)
- Snare: `tone_freq` (pitch), `noise_decay` (sizzle length)
- Hihat: `osc_freq` (brightness), `decay` (open/closed)

### Workflow 2: DrumPattern (Step Sequencer style)

Use `DrumPattern` for grid-based programming (like a drum machine):

1. Define `DrumSoundParams` for each drum voice (kick, snare, hihat)
2. Create `DrumPattern` with 16-step boolean tracks
3. Each step = one 16th note; `True` triggers the sound
4. Render with `render_drum_pattern(drum, duration_seconds)`

### Workflow 3: MultiTrackPattern (Full Arrangement)

Combine drums with music presets or custom melodies:

1. Import a `MusicPattern` preset from `bloodmusic.music.presets`
2. Or create a custom `MusicPattern` with chords, notes, and effects
3. Wrap in `MultiTrackPattern` with a `DrumPattern`
4. Render with `render_multi_track(multi, duration_seconds)`

Available music presets: `BOSS_FIGHT_MUSIC`, `DUNGEON_MUSIC`, `PLATFORMER_MUSIC`, `TAVERN_MUSIC`, `MENU_MUSIC`, `BATTLE_HIGH_MUSIC`, `BATTLE_LOW_MUSIC`.

**Important**: `env_shape` must use the `EnvShape` string enum, not integers:
```python
from bloodmusic.core.envelope import EnvShape
env_shape=EnvShape.PAD        # slow attack, sustained
env_shape=EnvShape.PERCUSSIVE # fast attack, quick decay
```

### Workflow 4: Euclidean Rhythms

Use algorithmic rhythm generation for complex, organic-sounding patterns:

```python
from bloodmusic.music.euclidean import get_euclidean_tracks
tracks = get_euclidean_tracks("combat_intense")  # or: combat_heavy, boss_epic, stealth, chase, ambient_drums
```

## Advanced Composition Workflows

### Workflow 5: SongArrangement (Structural Composition)

Build complete songs with intro/verse/chorus/bridge/outro sections using `SongArrangement`:

```python
from bloodmusic.music.arrangement import (
    SongArrangement, Section, Transition, render_song,
    TrackChannel, MixBus, SongMixer, create_song_template,
)

# Quick template-based creation
arrangement = create_song_template("pop")  # pop, edm, ambient, trap, cinematic

# Or build manually:
intro = Section(name="intro", start_time=0, duration=8)
chorus = Section(name="chorus", start_time=8, duration=16)
transition = Transition(from_section="intro", to_section="chorus",
                        start_time=7.5, duration=1.0, type_="crossfade")

arrangement = SongArrangement(
    name="my_song",
    bpm=120,
    sections=[intro, chorus],
    transitions=[transition],
)

# Route tracks through mix buses for grouped processing
arrangement.track_channels = [
    TrackChannel(track_name="drums", bus="rhythm", volume=0.9, pan=0.0),
    TrackChannel(track_name="bass", bus="low_end", volume=0.8, pan=0.0),
]

# Apply bus-level mixing (EQ, compression per bus)
arrangement.mixer = SongMixer(buses={
    "rhythm": MixBus(eq={"low_shelf": (100, 1.5)}, compressor={"threshold": -12}),
    "low_end": MixBus(eq={"high_cut": 5000}),
})

audio = render_song(arrangement)
```

**5 built-in templates**: `pop`, `edm`, `ambient`, `trap`, `cinematic` — each pre-configured with sections, track routing, and mix buses.

### Workflow 6: EffectChain (Per-Track Effects)

Apply professional effects chains to any audio:

```python
from bloodmusic.effects.chain import EffectChain

chain = EffectChain(
    # EQ
    eq_low_shelf=(100, -3),       # (freq_hz, db_gain)
    eq_high_shelf=(8000, 2),
    eq_peaking=[(2500, -2, 1.0)],  # (freq, gain, Q)

    # Dynamics
    compressor_threshold=-18,
    compressor_ratio=4,
    compressor_makeup=3,

    # Modulation
    flanger_mix=0.3,
    flanger_rate=0.5,
    flanger_depth=0.004,
    phaser_mix=0.2,
    phaser_rate=0.3,
    chorus_mix=0.25,

    # Time-based
    delay_mix=0.3,
    delay_time=0.25,
    delay_feedback=0.4,
    reverb_mix=0.35,
    reverb_decay=1.5,
)

processed = chain.process_effects(audio)
```

**Effect pipeline order**: Filters → EQ → Compressor → Distortion → Flanger/Phaser → Chorus → Delay → Reverb → Stereo

**Resonant filters** (2-pole biquad with Q control):
```python
from bloodmusic.effects.filters import apply_resonant_lpf, apply_resonant_hpf

# Sweeping resonant low-pass (Q=0.707 = Butterworth; Q>1 = resonant peak)
audio = apply_resonant_lpf(audio, cutoff_hz=2000, q=2.5)
audio = apply_resonant_hpf(audio, cutoff_hz=200, q=0.707)
```

### Workflow 7: Automation (Dynamic Parameter Control)

Create evolving sounds with time-based parameter automation:

```python
from bloodmusic.music.automation import (
    AutomationLane, AutomationPoint, AutomationTrack,
    apply_filter_sweep, apply_volume_automation, apply_pan_automation,
)

# Filter sweep (e.g., build-up)
lane = AutomationLane(
    parameter="lp_filter_hz",
    points=[
        AutomationPoint(time=0.0, value=200),
        AutomationPoint(time=8.0, value=8000, interpolation="smooth"),
    ],
)
swept = apply_filter_sweep(audio, lane, q=1.5)

# Volume fade in/out
vol_lane = AutomationLane(
    parameter="volume",
    points=[
        AutomationPoint(time=0.0, value=0.0),
        AutomationPoint(time=2.0, value=1.0, interpolation="smooth"),
        AutomationPoint(time=28.0, value=1.0),
        AutomationPoint(time=30.0, value=0.0, interpolation="smooth"),
    ],
)
automated = apply_volume_automation(audio, vol_lane)

# Auto-pan (LFO-style)
pan_lane = AutomationLane(
    parameter="pan",
    points=[
        AutomationPoint(time=0.0, value=-0.8),
        AutomationPoint(time=1.0, value=0.8, interpolation="smooth"),
        AutomationPoint(time=2.0, value=-0.8, interpolation="smooth"),
    ],
)

# Preset automation patterns:
from bloodmusic.music.automation import build_up_lowpass, fade_in_out, auto_pan_sine, drop_filter_resonance
```

**Interpolation modes**: `"linear"` (default), `"smooth"` (cosine easing), `"step"` (instant change)

### Workflow 8: BassSynth (Dedicated Bass Synthesis)

Generate bass lines with specialized synthesis models:

```python
from bloodmusic.music.bass import BassSynth, render_bass_pattern

# Preset bass types
sub = BassSynth.preset("sub")     # Deep sine + harmonics
fm = BassSynth.preset("fm")       # DX7-style FM bass
acid = BassSynth.preset("acid")   # TB-303 style (saw + resonant LPF + distortion)
pluck = BassSynth.preset("pluck") # Fast-decay triangle for plucky bass

# Custom bass
my_bass = BassSynth(
    osc_type=OscType.SAW,
    cutoff_hz=800,
    resonance=2.0,
    distortion=0.3,
    envelope_shape=EnvShape.PERCUSSIVE,
    volume=0.75,
)

# Render a bass pattern (notes with per-note BassSynth)
from bloodmusic.music import MusicPattern
pattern = MusicPattern(
    notes=["C2", "C2", "G2", "G2", "A2", "A2", "F2", "F2"],
    durations=[0.5] * 8,
    bpm=120,
    osc_type=OscType.SAW,
)
bass_audio = render_bass_pattern(pattern, duration_seconds=8.0)
```

### Workflow 9: Harmony (Multi-Voice Arrangement)

Generate harmonies and arrange voices for richer melodies:

```python
from bloodmusic.music.harmony import (
    generate_parallel_harmony, generate_diatonic_harmony,
    generate_chordal_harmony, voice_leading, render_harmony_tracks,
)

# Generate harmony voices from a melody
melody_notes = ["C4", "E4", "G4", "A4", "C5", "D5", "E5", "G5"]
melody_durs = [0.5] * 8

# Parallel harmony (fixed interval)
harmony = generate_parallel_harmony(melody_notes, interval=3)  # 3rd above

# Diatonic harmony (stays in key)
harmony = generate_diatonic_harmony(melody_notes, key="C", interval=3)

# Chordal harmony (from chord progression)
chords = [["C4","E4","G4"], ["F4","A4","C5"], ["G4","B4","D5"], ["C4","E4","G4"]]
harmony = generate_chordal_harmony(melody_notes, chords)

# SATB-style voice leading (minimize voice movement)
voices = voice_leading(melody_notes, harmony_voices=[harmony])

# Render all voices to audio
tracks = render_harmony_tracks(voices, melody_durs, bpm=120)
```

### Workflow 10: InstrumentPool (端到端乐器池系统)

一键从乐器池配置生成完整纯音乐 — 声明乐器、选风格、出成品。

**核心概念**：
- **InstrumentPool** — 乐器池：定义用哪些乐器、什么角色、BPM/调性/音阶
- **StylePreset** — 风格预设：5 种内置风格 (exploration, battle, town, dungeon, ambient)
- **PoolRenderer** — 渲染管线：乐池 → 分轨生成 → 混音辅助 → 母带 → 成品音频

**快速开始 — 从 YAML 到 WAV**：

```python
from bloodmusic.music.instrument_pool import InstrumentPool
from bloodmusic.music.pool_renderer import PoolRenderer

# 方式1: 从 YAML 加载预置乐池
pool = InstrumentPool.from_yaml("music/pool_presets/orchestral_small.yaml")

# 方式2: 使用内置模板
from bloodmusic.music.pool_templates import POOL_TEMPLATES
pool = POOL_TEMPLATES["electronic_group"].to_pool(style="battle")

# 方式3: 纯代码构建
from bloodmusic.music.instrument_pool import InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine
pool = InstrumentPool(name="自定义BGM", bpm=120, key="C", scale="dorian")
pool.instruments.append(PoolInstrument("主旋律", role=InstrumentRole.MELODY,
    engine=SynthEngine.WAVETABLE, preset="acoustic_grand_piano", volume=0.9))
pool.instruments.append(PoolInstrument("和弦", role=InstrumentRole.CHORD,
    engine=SynthEngine.SUBTRACTIVE, preset="string_ensemble", volume=0.6))

# 一键渲染: 乐池 → 分轨 → 混音 → 成品 (float32 ndarray)
renderer = PoolRenderer(pool, duration_sec=120.0, style_name="battle")
final_audio, stems = renderer.render()

# final_audio: np.ndarray (float32, 44100Hz) — 可直接保存
# stems: Dict[str, np.ndarray] — {乐器名: 分轨音频}

# 仅导出分轨（跳过混音）
stems = renderer.render_stems_only()

# 导出为 WAV
from scipy.io import wavfile
wavfile.write("output.wav", 44100, (final_audio * 32767).astype(np.int16))
```

**5 个内置 StylePreset**：

| 风格 | 名称 | 描述 | BPM 范围 | arrangement_template |
|------|------|------|----------|---------------------|
| exploration | 探索/漫游 | 宽广、明亮的旋律 | 70-100 | ambient |
| battle | 战斗 | 激烈、快速、压迫感 | 130-180 | pop |
| town | 城镇/村庄 | 温暖、舒缓、亲切 | 80-110 | lo-fi |
| dungeon | 地下城 | 阴暗、紧张、沉重 | 60-90 | ambient |
| ambient | 氛围/环境 | 空灵、缓慢、空间感 | 40-80 | ambient |

**5 个内置 PoolTemplate**：

| 模板 | 描述 | 乐器配置 |
|------|------|----------|
| orchestral_small | 管弦小编制 | Violin(melody) + Strings(chord) + Cello(bass) + Timpani(drum) |
| electronic_group | 电子合成器组 | Square Lead(melody) + Saw Pad(chord) + FM Bass + Noise Drum |
| jazz_trio | 爵士三重奏 | Trumpet(melody) + Piano(chord) + Acoustic Bass + Brush Drum |
| rock_band | 摇滚乐队 | Dist Guitar(melody) + Clean Guitar(chord) + Pick Bass + Rock Drum |
| ambient_pad | 氛围环境 | Sine Pad(melody) + Granular Pad + Sub Bass (无鼓) |

**生成整张专辑（10 首多风格纯音乐）**：

```bash
cd <PATH>

# 专辑模式（album_maker 子包，替代已移除的 album_generator.py）
python -m bloodmusic.album_maker.cli make --demo

# 自定义 YAML 专辑配置
python -m bloodmusic.album_maker.cli make -c configs/custom_album.yaml

# 快速单曲 / 指定风格
python -m bloodmusic.album_maker.cli quick
python -m bloodmusic.album_maker.cli style jazz

```

Pool 模式会遍历 `music/pool_presets/album_*.yaml` 中的 10 个风格配置，
调用 `InstrumentPool.from_yaml()` → `StylePreset.apply_to()` → `PoolRenderer.render()`
为每种风格生成一首完整曲目，输出到 `album_output_pool/`。

**自定义乐池 YAML 格式**：

```yaml
name: "我的自定义 BGM"
version: "1.0"
bpm: 120
key: "C"
scale: "dorian"
style: exploration          # 关联 StylePreset

instruments:
  - name: "主旋律"
    role: melody
    engine: wavetable
    preset: "acoustic_grand_piano"
    volume: 0.9
    pan: 0.0
    effect_chain:
      reverb_mix: 0.3
      reverb_decay: 1.5
      lp_filter_hz: 4500

  - name: "和弦"
    role: chord
    engine: subtractive
    preset: "string_ensemble"
    volume: 0.6
    pan: -0.2
    effect_chain:
      reverb_mix: 0.4
      reverb_decay: 2.0

  - name: "Bass"
    role: bass
    engine: fm
    preset: "fm_bass"
    volume: 0.8
    octave: -1
    effect_chain:
      lp_filter_hz: 800

  - name: "鼓"
    role: drum
    engine: noise
    volume: 0.7

generation:
  diversity: 0.3
  humanize: true
  chord_progression: "dreamy"
  # sections: ["intro", "verse", "chorus", "outro"]   # 可选，不填走 StylePreset 默认
  # section_bars: [4, 8, 8, 4]
```

**关键字段说明**：

| 字段层级 | 字段 | 类型 | 必填 | 说明 |
|----------|------|------|------|------|
| 顶层 | name | str | ✅ | 乐池名称 |
| 顶层 | bpm | int | ✅ | 速度 |
| 顶层 | key | str | ✅ | 调性 ("C", "Am", "D", ...) |
| 顶层 | scale | str | ✅ | 音阶 ("major", "minor", "dorian", "pentatonic", ...) |
| 顶层 | style | str | ❌ | 风格预设名，PoolRenderer 自动应用 |
| 顶层 | global_volume | float | ❌ | 全局音量 (默认 0.9) |
| instruments[] | name | str | ✅ | 乐器显示名 |
| instruments[] | role | str | ✅ | melody/chord/bass/drum/pad/fx |
| instruments[] | engine | str | ✅ | wavetable/subtractive/fm/fm_advanced/karplus_strong/granular/waveguide/noise |
| instruments[] | preset | str | ❌ | instruments.py 预设名 |
| instruments[] | volume | float | ❌ | 相对音量 (默认 1.0) |
| instruments[] | pan | float | ❌ | 声像 (-1.0 ~ 1.0, 默认 0.0) |
| instruments[] | octave | int | ❌ | 八度偏移 (bass 常用 -1) |
| instruments[] | effect_chain | dict | ❌ | 效果链参数 |
| instruments[].effect_chain | reverb_mix | float | ❌ | 混响混合量 |
| instruments[].effect_chain | reverb_decay | float | ❌ | 混响衰减时间 |
| instruments[].effect_chain | lp_filter_hz | float | ❌ | 低通滤波截止频率 |
| generation | diversity | float | ❌ | 多样性 (0.0~1.0, 默认 0.3) |
| generation | humanize | bool | ❌ | 人性化处理 (默认 true) |
| generation | chord_progression | str | ❌ | 和弦进行 (dreamy/epic/folk/ambient/pop_verse/heroic) |
| generation | sections | list | ❌ | 段落名称列表 |
| generation | section_bars | list | ❌ | 各段小节数 |

**InstrumentRole 枚举值**：
- `melody` — 主旋律 (使用 Markov 链生成)
- `chord` — 和弦/和声 (使用 harmony.py)
- `bass` — 低音线 (使用 bass.py)
- `drum` — 打击乐 (使用 euclidean.py)
- `pad` — 铺底/氛围 (harmony + arpeggiator)
- `fx` — 特殊效果

**SynthEngine 枚举值**：
- `wavetable` — 波表合成 (钢琴、弦乐、吉他等)
- `subtractive` — 减法合成 (铺底、正弦波)
- `fm` — 2-op FM 合成 (金属音色、铃音)
- `fm_advanced` — 多 op FM (DX7 风格)
- `karplus_strong` — 物理建模拨弦
- `granular` — 粒子合成
- `waveguide` — 波导物理建模
- `noise` — 噪声合成 (鼓专用)

**相关 Python API**：
```python
# 风格预设
from bloodmusic.music.pool_styles import STYLES, get_style, list_styles
battle = get_style("battle")

# 模板
from bloodmusic.music.pool_templates import POOL_TEMPLATES, get_template, list_templates
orch = get_template("orchestral_small")

# 序列化
from bloodmusic.music.pool_serializer import PoolSerializer
pools = PoolSerializer.list_presets()  # 列出所有 YAML 预置
```

## Creating Custom Beats

To create a new beat style:

1. Read `references/bloodmusic_api.md` for the complete API reference
2. Choose a beat creation workflow from above (Workflows 1-4 for beats, 5-10 for composition)
3. Set BPM, bar count, and drum sound parameters
4. Define hit positions or step patterns
5. Optionally add a `MusicPattern` for melody/chords
6. Apply effects via `EffectChain` for professional sound
7. Use `AutomationLane` for dynamic filter sweeps or volume changes
8. Export to WAV with normalization

## Resources

### scripts/make_beats.py
The complete beat-making script producing 7 styles (3-5 minutes each, with timestamped filenames). Execute directly or read for reference patterns and API usage examples.

### references/bloodmusic_api.md
Comprehensive API reference covering all classes, parameters, and code examples for:
- Drum synthesis (808 kick, snare, hihat)
- DrumPattern and DrumSoundParams
- MusicPattern and MultiTrackPattern
- Euclidean rhythm presets
- Music presets (battle, dungeon, platformer, etc.)
- SongArrangement and Section/Transition
- EffectChain with delay, flanger, phaser, resonant filters
- AutomationLane and AutomationTrack
- BassSynth (sub, FM, acid, pluck presets)
- Harmony (parallel, diatonic, chordal, voice leading)
- Export and normalization utilities

### music/pool_presets/album_*.yaml
10 个专辑风格乐池 YAML 配置文件，对应《血音幻境》专辑的 10 首曲目：
- `album_dawn_overture.yaml` — 01 晨曦序曲 (古典/钢琴, exploration)
- `album_lost_in_cosmos.yaml` — 02 星海迷途 (新世纪, ambient)
- `album_deep_sea.yaml` — 03 深海絮语 (氛围, ambient)
- `album_midnight_jazz.yaml` — 04 午夜爵士 (爵士, town)
- `album_neon_pulse.yaml` — 05 霓虹脉冲 (电子, battle)
- `album_heros_journey.yaml` — 06 英雄远征 (影视史诗, battle)
- `album_nostalgia.yaml` — 07 旧日时光 (Lo-Fi, town)
- `album_birds_mountains.yaml` — 08 空山鸟语 (冥想, ambient)
- `album_pastoral_tune.yaml` — 09 田园小调 (民谣, exploration)
- `album_finale_rebirth.yaml` — 10 终章·重生 (史诗终章, battle)

每个 YAML 文件包含该曲目的乐器组合、BPM、调性、音阶、效果链和生成参数。
与 `album_maker` 子包配合使用。

### docs/PRD-instrument-pool.md
InstrumentPool 系统的产品需求文档，包含完整的功能规格、用户故事和使用场景。
