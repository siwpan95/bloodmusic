#!/usr/bin/env python3
"""P0-P2 增强功能全面验证"""

print('=== BloodMusic P0-P2 Enhancement Verification ===')
print()

# ── P0.4 Validation ──
print('P0.4:')
from bloodmusic.music.pattern import MusicPattern
try:
    MusicPattern('test', ['C4'], [0.5, 1.0], bpm=120)
    assert False
except ValueError:
    print('  Validation: OK')

# ── P0.3 Humanize ──
print('P0.3:')
from bloodmusic.music.humanize import HumanizeParams, HUMANIZE_NATURAL
from bloodmusic.music.pattern import render_pattern_to_array
hp = HUMANIZE_NATURAL
pat = MusicPattern('test', ['C4'], [0.5], bpm=120, humanize_params=hp)
audio = render_pattern_to_array(pat, 1.0)
print(f'  Humanize: OK ({len(audio)} samples)')

# ── P0.1 Instruments ──
print('P0.1:')
from bloodmusic.music.instruments import get_instrument, INSTRUMENTS, list_all_categories
inst = get_instrument('violin')
assert inst.category == 'strings'
print(f'  Instruments: OK ({len(INSTRUMENTS)} inst, {len(list_all_categories())} cats)')

# ── P0.2 MIDI I/O ──
print('P0.2:')
from bloodmusic.music.midi_io import music_pattern_to_midi
import tempfile, os
pat2 = MusicPattern('test', ['C4','E4','G4'], [0.5,0.5,1.0], bpm=120)
tmp = os.path.join(tempfile.gettempdir(), 'test_verify.mid')
music_pattern_to_midi(pat2, tmp)
assert os.path.exists(tmp)
os.remove(tmp)
print('  MIDI I/O: OK')

# ── P1.1 Acoustic Drums ──
print()
print('P1.1:')
from bloodmusic.sfx.drum_synth import (
    synthesize_tom, synthesize_crash, synthesize_shaker,
    synthesize_acoustic_snare, synthesize_acoustic_kick,
)
tom = synthesize_tom()
crash = synthesize_crash()
snare_ac = synthesize_acoustic_snare()
print(f'  Acoustic Drums: OK (tom={len(tom)},crash={len(crash)},snare={len(snare_ac)})')

# ── P1.2 TempoLane ──
print('P1.2:')
from bloodmusic.music.automation import TempoLane
tl = TempoLane.accelerando(80, 120, 5.0, 15.0)
assert 79 < tl.bpm_at(2.0) < 81
assert 110 < tl.bpm_at(12.0) < 125
print(f'  TempoLane: OK (bpm@2s={tl.bpm_at(2):.0f}, bpm@12s={tl.bpm_at(12):.0f})')

# ── P1.3 Scales ──
print('P1.3:')
from bloodmusic.music.scale import Scale, list_scales, list_progressions, CHORD_PROGRESSIONS
scales = list_scales()
assert len(scales) > 20
assert 'japanese' in scales
assert 'jazz_ii-V-I' in CHORD_PROGRESSIONS
s = Scale('D', 'blues')
chords = s.get_progression('I-IV-V-I', 'seventh')
assert len(chords) == 4
print(f'  Scales: OK ({len(scales)} scales, {len(CHORD_PROGRESSIONS)} progressions)')

# ── P2.1 Multi-Op FM ──
print()
print('P2.1:')
from bloodmusic.core.fm_advanced import MultiOpFM, create_dx7_bell
fm = create_dx7_bell()
audio_fm = fm.render(440, 0.5)
assert len(audio_fm) > 1000
print(f'  Multi-Op FM: OK ({len(audio_fm)} samples)')

# ── P2.2 Convolution Reverb ──
print('P2.2:')
from bloodmusic.effects.spatial import apply_convolution_reverb
import numpy as np
test_sig = np.random.randn(44100) * 0.3
wet = apply_convolution_reverb(test_sig, mix=0.3, ir_type='hall')
assert len(wet) == len(test_sig)
print('  Convolution Reverb: OK')

# ── P2.3 Multiband Compressor ──
print('P2.3:')
from bloodmusic.effects.dynamics import MultibandCompressorParams, apply_multiband_compressor
mbc = MultibandCompressorParams(bands=3, crossover_freqs=[250, 2000])
compressed = apply_multiband_compressor(test_sig, mbc)
assert len(compressed) == len(test_sig)
print('  Multiband Compressor: OK')

print()
print('=== ALL P0-P2 ENHANCEMENTS VERIFIED ===')
