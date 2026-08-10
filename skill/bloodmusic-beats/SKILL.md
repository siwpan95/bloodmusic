---
name: bloodmusic-beats
description: >
  This skill should be used when the user wants to produce beats, drum patterns, or instrumental music
  using the BloodMusic programmatic audio synthesis engine located at G:/tools/bloodmusic.
  Triggers include: "make a beat", "create a drum pattern", "produce music with code",
  "generate 808 beats", "make trap/boom-bap/lo-fi/EDM beats", "create game music with drums",
  "compose a song", "make a complete track", "add bass line", "add harmony", "automate filter",
  or any request to programmatically generate WAV audio files with drum rhythms and melodies.
  Supports 7 beat styles: Trap, Boom Bap, Lo-Fi, Battle, Drum-Only, EDM, and Ambient.
  Also supports full song arrangement, effect chains, automation, bass synthesis, harmony, and sampling.
---

# BloodMusic Beats

## Overview

Use the BloodMusic engine (at `G:\tools\bloodmusic`) to programmatically synthesize beats, drum patterns, full music arrangements, and complete songs. Generate WAV audio files by combining 808 drum synthesis, Euclidean rhythms, music presets, custom patterns, bass synthesis, harmony generation, effects chains, and automation lanes.

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
cd G:\tools\bloodmusic
pip install -e .
```

If `from bloodmusic import ...` fails, check `pyproject.toml` at `G:\tools\bloodmusic\pyproject.toml`:
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

### Workflow 10: SamplePad (WAV Sample Playback)

Load and trigger external WAV samples like an MPC:

```python
from bloodmusic.music.sampler import (
    Sample, load_sample, play_sample,
    SamplePad, PadSlot, render_pad_sequence, render_sampler_pattern,
)

# Load a sample (supports 8/16/24/32-bit WAV, mono/stereo → mono)
sample = load_sample("kick.wav")

# Pitch-shifted playback (0.5 = octave down, 2.0 = octave up)
audio = play_sample(sample, pitch=1.5, volume=0.8)

# MPC-style pad setup
pad = SamplePad()
pad.assign("pad1", PadSlot(sample=load_sample("kick.wav"), volume=0.9))
pad.assign("pad2", PadSlot(sample=load_sample("snare.wav"), volume=0.75, pitch=1.2))
pad.assign("pad3", PadSlot(sample=load_sample("hihat.wav"), volume=0.5))

# Trigger sequence: (time_seconds, pad_name)
pattern = [
    (0.0, "pad1"), (0.25, "pad3"), (0.5, "pad2"), (0.75, "pad3"),
    (1.0, "pad1"), (1.25, "pad3"), (1.5, "pad1"), (1.75, "pad3"),
]
audio = render_pad_sequence(pad, pattern, bpm=120, duration=4.0)
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
- SamplePad and WAV sample playback
- Export and normalization utilities
