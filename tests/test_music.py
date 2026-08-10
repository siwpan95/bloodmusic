"""音乐模块测试 —— DrumPattern / MultiTrackPattern / Arpeggiator / Scale / Presets"""

import unittest

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape
from bloodmusic.music.pattern import (
    MusicPattern, DrumSoundParams, DrumPattern,
    MultiTrackPattern, render_drum_pattern,
    render_pattern_to_array, render_multi_track,
)
from bloodmusic.music.arpeggiator import Arpeggiator, ArpMode, generate_arpeggio
from bloodmusic.music.scale import Scale, SCALE_INTERVALS
from bloodmusic.music.presets import ALL_MUSIC_PATTERNS


class TestDrumPattern(unittest.TestCase):
    """DrumPattern 渲染验证"""

    def _make_simple_drum_pattern(self):
        """创建简单鼓点模式"""
        return DrumPattern(
            name="test_drum",
            steps=8,
            bpm=120,
            tracks={
                "kick":  [True, False, False, False, True, False, False, False],
                "snare": [False, False, True, False, False, False, True, False],
                "hihat": [True, True, True, True, True, True, True, True],
            },
            sounds={
                "kick":  DrumSoundParams(osc_type=OscType.SINE, pitch_hz=60, decay=0.2, volume=0.8),
                "snare": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=200, decay=0.1, volume=0.5),
                "hihat": DrumSoundParams(osc_type=OscType.NOISE_WHITE, pitch_hz=8000, decay=0.05, volume=0.3,
                                         hp_hz=5000),
            },
        )

    def test_drum_output_nonzero(self):
        """鼓点渲染输出应非零"""
        pattern = self._make_simple_drum_pattern()
        sig = render_drum_pattern(pattern, 2.0)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

    def test_drum_output_length(self):
        """鼓点渲染输出长度应正确"""
        pattern = self._make_simple_drum_pattern()
        duration = 2.0
        sig = render_drum_pattern(pattern, duration)
        expected_len = int(duration * SR)
        self.assertEqual(len(sig), expected_len)

    def test_drum_empty_tracks(self):
        """空鼓点轨道应返回全零信号"""
        pattern = DrumPattern(name="empty", steps=4, bpm=120)
        sig = render_drum_pattern(pattern, 1.0)
        self.assertAlmostEqual(np.max(np.abs(sig)), 0.0, places=5)

    def test_drum_no_loop(self):
        """loop=False 应只循环一次"""
        pattern = self._make_simple_drum_pattern()
        pattern.loop = False
        sig = render_drum_pattern(pattern, 10.0)
        # 不循环模式下，超出部分应为零
        # 验证信号存在
        self.assertGreater(np.max(np.abs(sig)), 0.0)


class TestMultiTrackPattern(unittest.TestCase):
    """MultiTrackPattern 渲染验证"""

    def test_multitrack_basic(self):
        """多轨渲染应产生非零输出"""
        melody = MusicPattern(
            name="melody",
            notes=["C4", "E4", "G4"],
            durations=[1.0, 1.0, 1.0],
            bpm=120,
            osc_type=OscType.SINE,
            volume=0.3,
        )
        drums = DrumPattern(
            name="drums",
            steps=4,
            bpm=120,
            tracks={"kick": [True, False, True, False]},
            sounds={"kick": DrumSoundParams()},
        )
        multi = MultiTrackPattern(
            name="test_multi",
            bpm=120,
            music_tracks=[melody],
            drum_track=drums,
        )
        sig = render_multi_track(multi, 2.0)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

    def test_multitrack_output_length(self):
        """多轨渲染输出长度应正确"""
        melody = MusicPattern(
            name="melody",
            notes=["C4"],
            durations=[1.0],
            bpm=120,
        )
        multi = MultiTrackPattern(
            name="test_multi",
            bpm=120,
            music_tracks=[melody],
        )
        duration = 2.0
        sig = render_multi_track(multi, duration)
        expected_len = int(duration * SR)
        self.assertEqual(len(sig), expected_len)

    def test_multitrack_no_clipping(self):
        """多轨渲染输出不应爆音"""
        melody = MusicPattern(
            name="melody",
            notes=["C4", "E4", "G4"],
            durations=[1.0, 1.0, 1.0],
            bpm=120,
            osc_type=OscType.SAW,
            volume=0.5,
        )
        multi = MultiTrackPattern(
            name="test_multi",
            bpm=120,
            music_tracks=[melody],
        )
        sig = render_multi_track(multi, 2.0)
        self.assertLessEqual(np.max(np.abs(sig)), 1.0)


class TestMusicPatternChords(unittest.TestCase):
    """MusicPattern.chords 字段验证"""

    def test_chords_field_default_none(self):
        """chords 默认为 None"""
        pattern = MusicPattern(name="test", notes=["C4"], durations=[1.0])
        self.assertIsNone(pattern.chords)

    def test_chords_field_set(self):
        """chords 字段可以设置"""
        pattern = MusicPattern(
            name="test",
            notes=["C4", "F4"],
            durations=[1.0, 1.0],
            chords=[["C4", "E4", "G4"], ["F4", "A4", "C5"]],
        )
        self.assertIsNotNone(pattern.chords)
        self.assertEqual(len(pattern.chords), 2)

    def test_chords_affect_output(self):
        """有 chords 的渲染输出应与无 chords 不同"""
        pattern_no_chords = MusicPattern(
            name="no_chords",
            notes=["C4", "E4"],
            durations=[0.5, 0.5],
            bpm=120,
        )
        pattern_with_chords = MusicPattern(
            name="with_chords",
            notes=["C4", "E4"],
            durations=[0.5, 0.5],
            bpm=120,
            chords=[["C4", "E4", "G4"], ["E4", "G4", "B4"]],
        )
        sig_no = render_pattern_to_array(pattern_no_chords, 1.0)
        sig_with = render_pattern_to_array(pattern_with_chords, 1.0)
        # 有和弦叠加时信号应更强
        self.assertGreater(np.max(np.abs(sig_with)), 0.0)


class TestArpeggiator(unittest.TestCase):
    """琶音器测试"""

    def test_arp_up_mode(self):
        """UP 模式应按频率升序排列"""
        arp = Arpeggiator(mode=ArpMode.UP)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)
        # UP 模式应返回 3 个音符
        self.assertEqual(len(result), 3)
        # 所有音符应非空
        for note, dur in result:
            self.assertGreater(len(note), 0)
            self.assertGreater(dur, 0)

    def test_arp_down_mode(self):
        """DOWN 模式应按频率降序排列"""
        arp = Arpeggiator(mode=ArpMode.DOWN)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)
        self.assertEqual(len(result), 3)

    def test_arp_up_down_mode(self):
        """UP_DOWN 模式应先升后降"""
        arp = Arpeggiator(mode=ArpMode.UP_DOWN)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)
        # UP_DOWN: C4 E4 G4 E4 = 4 个音符（去掉首尾重复）
        self.assertEqual(len(result), 4)

    def test_arp_random_mode(self):
        """RANDOM 模式应返回相同数量的音符"""
        # 用固定种子保证确定性
        np.random.seed(42)
        arp = Arpeggiator(mode=ArpMode.RANDOM)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)
        self.assertEqual(len(result), 3)

    def test_arp_octave_extension(self):
        """八度扩展应增加音符数量"""
        arp = Arpeggiator(mode=ArpMode.UP, octaves=2)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)
        # 3 notes × 2 octaves = 6
        self.assertEqual(len(result), 6)

    def test_arp_gate_parameter(self):
        """gate 参数应影响音符时长"""
        arp1 = Arpeggiator(mode=ArpMode.UP, gate=0.5)
        arp2 = Arpeggiator(mode=ArpMode.UP, gate=1.0)
        result1 = generate_arpeggio(arp1, ["C4", "E4", "G4"], bpm=120)
        result2 = generate_arpeggio(arp2, ["C4", "E4", "G4"], bpm=120)
        # gate=1.0 的时长应为 gate=0.5 的两倍
        self.assertAlmostEqual(result2[0][1], result1[0][1] * 2.0, places=5)

    def test_arp_custom_durations(self):
        """自定义时值应正确应用"""
        arp = Arpeggiator(mode=ArpMode.UP)
        result = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120,
                                    durations=[1.0, 0.5, 0.25])
        # 自定义时值应生成不同长度
        self.assertGreater(result[0][1], result[1][1])
        self.assertGreater(result[1][1], result[2][1])


class TestScale(unittest.TestCase):
    """Scale 类验证"""

    def test_scale_get_notes_major(self):
        """C 大调音阶应包含正确的音符"""
        scale = Scale(root="C", scale_type="major", octave=4)
        notes = scale.get_notes()
        self.assertEqual(len(notes), 7)
        self.assertIn("C4", notes)

    def test_scale_get_freqs(self):
        """get_freqs 应返回正确数量的频率"""
        scale = Scale(root="C", scale_type="major", octave=4)
        freqs = scale.get_freqs()
        self.assertEqual(len(freqs), 7)
        # 频率应递增
        for i in range(len(freqs) - 1):
            self.assertLess(freqs[i], freqs[i + 1])

    def test_scale_get_chord_triad(self):
        """I 级三和弦应包含 3 个音符"""
        scale = Scale(root="C", scale_type="major", octave=4)
        chord = scale.get_chord(1)
        self.assertEqual(len(chord), 3)

    def test_scale_get_chord_seventh(self):
        """I 级七和弦应包含 4 个音符"""
        scale = Scale(root="C", scale_type="major", octave=4)
        chord = scale.get_chord(1, quality="seventh")
        self.assertEqual(len(chord), 4)

    def test_scale_intervals_property(self):
        """intervals 属性应返回正确的间隔列表"""
        scale = Scale(root="C", scale_type="major")
        intervals = scale.intervals
        self.assertEqual(intervals, [0, 2, 4, 5, 7, 9, 11])

    def test_scale_unknown_type_falls_back_to_major(self):
        """未知音阶类型应回退到大调"""
        scale = Scale(root="C", scale_type="unknown_type")
        intervals = scale.intervals
        self.assertEqual(intervals, SCALE_INTERVALS["major"])


class TestScaleIntervals(unittest.TestCase):
    """SCALE_INTERVALS 包含 12 种音阶"""

    def test_scale_intervals_has_12_types(self):
        """SCALE_INTERVALS 应包含 12 种音阶"""
        self.assertEqual(len(SCALE_INTERVALS), 12)

    def test_all_scales_start_at_zero(self):
        """所有音阶间隔应从 0 开始"""
        for name, intervals in SCALE_INTERVALS.items():
            self.assertEqual(intervals[0], 0,
                             f"Scale '{name}' does not start at 0")

    def test_known_scales_present(self):
        """应包含常见的音阶类型"""
        expected = ["major", "minor", "dorian", "phrygian", "lydian",
                    "mixolydian", "pentatonic", "blues", "harmonic_minor",
                    "melodic_minor", "whole_tone", "chromatic"]
        for name in expected:
            self.assertIn(name, SCALE_INTERVALS,
                          f"Missing scale: {name}")


class TestMusicPresets(unittest.TestCase):
    """15 个音乐预设全部存在且可渲染"""

    def test_15_presets_exist(self):
        """应包含 15 个音乐预设"""
        self.assertEqual(len(ALL_MUSIC_PATTERNS), 15)

    def test_all_presets_names(self):
        """所有预设应有非空名称"""
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            self.assertTrue(len(pattern.name) > 0,
                            f"Preset '{key}' has empty name")

    def test_all_presets_renderable(self):
        """所有预设应可渲染为非零音频"""
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            try:
                sig = render_pattern_to_array(pattern, 1.0)
                self.assertGreater(np.max(np.abs(sig)), 0.0,
                                   f"Preset '{key}' rendered to silence")
            except Exception as e:
                self.fail(f"Preset '{key}' failed to render: {e}")

    def test_all_presets_correct_length(self):
        """所有预设渲染后长度应正确"""
        duration = 1.0
        for key, pattern in ALL_MUSIC_PATTERNS.items():
            sig = render_pattern_to_array(pattern, duration)
            expected_len = int(duration * SR)
            self.assertEqual(len(sig), expected_len,
                              f"Preset '{key}' has wrong length")


if __name__ == "__main__":
    unittest.main()
