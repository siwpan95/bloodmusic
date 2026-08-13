"""核心模块测试 —— freq_to_midi 修复、LFO、FM 合成、常量"""

import math
import unittest

import numpy as np

from bloodmusic.core.note_utils import freq_to_midi, midi_to_freq, note_to_freq
from bloodmusic.core.constants import (
    SR, BPM_DEFAULT, NORMALIZE_DBFS, DEFAULT_OGG_BITRATE,
)
from bloodmusic.core.voice import (
    SynthVoice, synthesize_voice, LFOParams, LFOTarget,
)
from bloodmusic.core.fm_synth import FMSynthVoice, synthesize_fm_voice
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape, ADSRParams


class TestFreqToMidi(unittest.TestCase):
    """freq_to_midi bug 修复验证（bit_length -> math.log2）"""

    def test_a4_440hz_midi_69(self):
        """440Hz 应映射到 MIDI 69"""
        self.assertEqual(freq_to_midi(440.0), 69)

    def test_a5_880hz_midi_81(self):
        """880Hz（比 A4 高一个八度）应映射到 MIDI 81"""
        self.assertEqual(freq_to_midi(880.0), 81)

    def test_a3_220hz_midi_57(self):
        """220Hz（比 A4 低一个八度）应映射到 MIDI 57"""
        self.assertEqual(freq_to_midi(220.0), 57)

    def test_c4_261hz_midi_60(self):
        """C4 (261.63Hz) 应映射到 MIDI 60（中央 C）"""
        self.assertEqual(freq_to_midi(261.63), 60)

    def test_midi_to_freq_roundtrip(self):
        """midi_to_freq 与 freq_to_midi 应互为逆运算（四舍五入内）"""
        for midi in [0, 21, 60, 69, 108, 127]:
            freq = midi_to_freq(midi)
            self.assertEqual(freq_to_midi(freq), midi,
                             f"Roundtrip failed for MIDI {midi}")

    def test_low_frequency_boundary(self):
        """极低频率应返回合理 MIDI 值"""
        midi = freq_to_midi(20.0)
        self.assertLess(midi, 40)
        self.assertGreater(midi, 0)

    def test_high_frequency_boundary(self):
        """高频率应返回合理 MIDI 值"""
        midi = freq_to_midi(8000.0)
        self.assertGreater(midi, 100)

    def test_uses_log2_not_bit_length(self):
        """确认使用 math.log2（旧 bug 使用 bit_length 会产生错误结果）"""
        # 440Hz 旧 bit_length(440)=9, 69+12*9=177 — 错误
        # math.log2(440/440)=0, 69+12*0=69 — 正确
        self.assertEqual(freq_to_midi(440.0), 69)


class TestLFOParamsAndTarget(unittest.TestCase):
    """LFOParams / LFOTarget 枚举值验证"""

    def test_lfo_target_values(self):
        """LFOTarget 应包含 AMPLITUDE, PITCH, FILTER_CUTOFF"""
        self.assertEqual(LFOTarget.AMPLITUDE.value, "amplitude")
        self.assertEqual(LFOTarget.PITCH.value, "pitch")
        self.assertEqual(LFOTarget.FILTER_CUTOFF.value, "filter_cutoff")

    def test_lfo_params_defaults(self):
        """LFOParams 默认值验证"""
        params = LFOParams()
        self.assertAlmostEqual(params.rate, 0.0)
        self.assertAlmostEqual(params.depth, 0.0)
        self.assertEqual(params.target, LFOTarget.AMPLITUDE)

    def test_lfo_params_custom(self):
        """LFOParams 自定义参数"""
        params = LFOParams(rate=5.0, depth=0.3, target=LFOTarget.PITCH)
        self.assertAlmostEqual(params.rate, 5.0)
        self.assertAlmostEqual(params.depth, 0.3)
        self.assertEqual(params.target, LFOTarget.PITCH)


class TestSynthVoiceLFO(unittest.TestCase):
    """SynthVoice.lfo 字段向后兼容 + LFO 调制输出"""

    def test_synthvoice_lfo_default_none(self):
        """SynthVoice 默认 lfo=None（向后兼容）"""
        voice = SynthVoice()
        self.assertIsNone(voice.lfo)

    def test_synthvoice_lfo_set(self):
        """SynthVoice 可以设置 lfo 字段"""
        lfo = LFOParams(rate=6.0, depth=0.5, target=LFOTarget.AMPLITUDE)
        voice = SynthVoice(lfo=lfo)
        self.assertIsNotNone(voice.lfo)
        self.assertAlmostEqual(voice.lfo.rate, 6.0)

    def test_lfo_amplitude_modulation(self):
        """LFO AMPLITUDE 调制应改变输出信号包络"""
        voice_no_lfo = SynthVoice(freq=440, duration=0.5, osc_type=OscType.SINE)
        sig_no_lfo = synthesize_voice(voice_no_lfo)

        lfo = LFOParams(rate=5.0, depth=0.8, target=LFOTarget.AMPLITUDE)
        voice_lfo = SynthVoice(freq=440, duration=0.5, osc_type=OscType.SINE, lfo=lfo)
        sig_lfo = synthesize_voice(voice_lfo)

        # 两者都应产生非零输出
        self.assertGreater(np.max(np.abs(sig_no_lfo)), 0.01)
        self.assertGreater(np.max(np.abs(sig_lfo)), 0.01)
        # LFO 调制后的信号应与无 LFO 不同
        self.assertFalse(np.allclose(sig_no_lfo, sig_lfo, atol=1e-4))

    def test_lfo_pitch_modulation(self):
        """LFO PITCH 调制应改变音高"""
        voice_no_lfo = SynthVoice(freq=440, duration=0.5, osc_type=OscType.SINE)
        sig_no_lfo = synthesize_voice(voice_no_lfo)

        lfo = LFOParams(rate=5.0, depth=0.5, target=LFOTarget.PITCH)
        voice_lfo = SynthVoice(freq=440, duration=0.5, osc_type=OscType.SINE, lfo=lfo)
        sig_lfo = synthesize_voice(voice_lfo)

        # PITCH LFO 应该产生不同的信号
        self.assertFalse(np.allclose(sig_no_lfo, sig_lfo, atol=1e-4))

    def test_lfo_filter_cutoff_no_crash(self):
        """LFO FILTER_CUTOFF 目标不应崩溃（效果链中处理）"""
        lfo = LFOParams(rate=3.0, depth=0.5, target=LFOTarget.FILTER_CUTOFF)
        voice = SynthVoice(freq=440, duration=0.3, osc_type=OscType.SINE, lfo=lfo)
        sig = synthesize_voice(voice)
        self.assertEqual(len(sig), int(0.3 * SR))


class TestFMSynthVoice(unittest.TestCase):
    """FMSynthVoice 合成验证"""

    def test_fm_output_nonzero(self):
        """FM 合成输出应非零"""
        voice = FMSynthVoice(carrier_freq=440, duration=0.3)
        sig = synthesize_fm_voice(voice)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

    def test_fm_output_length(self):
        """FM 合成输出长度应正确"""
        duration = 0.5
        voice = FMSynthVoice(carrier_freq=440, duration=duration)
        sig = synthesize_fm_voice(voice)
        expected_len = int(duration * SR)
        self.assertEqual(len(sig), expected_len)

    def test_fm_with_different_ratio(self):
        """不同 modulator_freq_ratio 应产生不同声音"""
        voice1 = FMSynthVoice(carrier_freq=440, modulator_freq_ratio=1.0, duration=0.3)
        voice2 = FMSynthVoice(carrier_freq=440, modulator_freq_ratio=2.0, duration=0.3)
        sig1 = synthesize_fm_voice(voice1)
        sig2 = synthesize_fm_voice(voice2)
        self.assertFalse(np.allclose(sig1, sig2, atol=1e-4))

    def test_fm_effect_audible(self):
        """FM 深度应影响声音（fm_depth 越大变化越大）"""
        voice_shallow = FMSynthVoice(carrier_freq=440, fm_depth=10.0, duration=0.3)
        voice_deep = FMSynthVoice(carrier_freq=440, fm_depth=500.0, duration=0.3)
        sig_shallow = synthesize_fm_voice(voice_shallow)
        sig_deep = synthesize_fm_voice(voice_deep)
        # 不同 FM 深度应产生不同信号
        self.assertFalse(np.allclose(sig_shallow, sig_deep, atol=1e-4))

    def test_fm_no_clipping(self):
        """FM 合成输出不应超过 1.0（有限幅保护）"""
        voice = FMSynthVoice(carrier_freq=440, fm_depth=500.0, duration=0.3)
        sig = synthesize_fm_voice(voice)
        self.assertLessEqual(np.max(np.abs(sig)), 1.0)

    def test_fm_with_lfo(self):
        """FM 合成 + LFO 应正常工作"""
        lfo = LFOParams(rate=5.0, depth=0.5, target=LFOTarget.AMPLITUDE)
        voice = FMSynthVoice(carrier_freq=440, duration=0.3, lfo=lfo)
        sig = synthesize_fm_voice(voice)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

    def test_fm_carrier_types(self):
        """不同载波类型应产生非零输出"""
        for osc in [OscType.SINE, OscType.SAW, OscType.SQUARE, OscType.TRIANGLE]:
            voice = FMSynthVoice(carrier_freq=440, carrier_type=osc, duration=0.2)
            sig = synthesize_fm_voice(voice)
            self.assertGreater(np.max(np.abs(sig)), 0.01,
                               f"FM with {osc.value} carrier produced near-zero output")


class TestConstants(unittest.TestCase):
    """新增常量验证"""

    def test_normalize_dbfs(self):
        """NORMALIZE_DBFS 应为 -1.0"""
        self.assertAlmostEqual(NORMALIZE_DBFS, -1.0)

    def test_default_ogg_bitrate(self):
        """DEFAULT_OGG_BITRATE 应为 128000"""
        self.assertEqual(DEFAULT_OGG_BITRATE, 128000)

    def test_sr_value(self):
        """采样率应为 44100"""
        self.assertEqual(SR, 44100)

    def test_bpm_default(self):
        """默认 BPM 应为 120"""
        self.assertEqual(BPM_DEFAULT, 120)


class TestNoteUtils(unittest.TestCase):
    """note_to_freq 验证"""

    def test_a4_frequency(self):
        """A4 应映射到 440Hz"""
        self.assertAlmostEqual(note_to_freq("A4"), 440.0, places=1)

    def test_unknown_note_raises(self):
        """未知音符应显式抛出 ValueError（不再静默回退 440Hz）"""
        with self.assertRaises(ValueError):
            note_to_freq("X9")

    def test_note_with_underscore(self):
        """下划线音符名应被正确处理"""
        # Eb_4 -> Eb4
        freq = note_to_freq("Eb_4")
        self.assertGreater(freq, 300.0)
        self.assertLess(freq, 350.0)


if __name__ == "__main__":
    unittest.main()
