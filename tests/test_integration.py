"""集成测试 —— 完整合成→效果→导出流程 / CLI 参数 / 顶层包导入"""

import os
import tempfile
import unittest

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import OscType
from bloodmusic.core.envelope import EnvShape, ADSRParams
from bloodmusic.core.voice import SynthVoice, LFOParams, LFOTarget, synthesize_voice
from bloodmusic.core.fm_synth import FMSynthVoice, synthesize_fm_voice
from bloodmusic.effects.chain import EffectChain, process_effects
from bloodmusic.effects.dynamics import CompressorParams
from bloodmusic.effects.eq import ParametricEQParams
from bloodmusic.export.batch import export_audio
from bloodmusic.music.pattern import (
    MusicPattern, DrumSoundParams, DrumPattern,
    MultiTrackPattern, render_pattern_to_array, render_multi_track,
)
from bloodmusic.music.arpeggiator import Arpeggiator, ArpMode, generate_arpeggio
from bloodmusic.music.scale import Scale


class TestSynthEffectsExportPipeline(unittest.TestCase):
    """完整合成→效果→导出 流程"""

    def test_synth_effects_wav_export(self):
        """SynthVoice → EffectChain → WAV 导出完整流程"""
        # 1. 合成
        voice = SynthVoice(freq=440, duration=0.5, osc_type=OscType.SAW,
                           volume=0.5, env_shape=EnvShape.PERCUSSIVE)
        sig = synthesize_voice(voice).astype(np.float64)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

        # 2. 效果处理
        chain = EffectChain(
            lp_filter_hz=3000.0,
            reverb_mix=0.2,
            chorus_mix=0.3,
            eq=ParametricEQParams(mid_gain_db=3.0),
        )
        processed = process_effects(sig, chain)
        self.assertEqual(len(processed), len(sig))

        # 3. 导出
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "synth_effects.wav")
            result = export_audio(processed, path, format="wav")
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 0)


class TestFMSynthEffectsExportPipeline(unittest.TestCase):
    """FM合成→效果链→WAV导出"""

    def test_fm_synth_effects_wav_export(self):
        """FMSynthVoice → EffectChain → WAV 导出完整流程"""
        # 1. FM 合成
        voice = FMSynthVoice(
            carrier_freq=440, modulator_freq_ratio=2.0,
            fm_depth=200.0, duration=0.5,
        )
        sig = synthesize_fm_voice(voice).astype(np.float64)
        self.assertGreater(np.max(np.abs(sig)), 0.01)

        # 2. 效果处理
        chain = EffectChain(
            lp_filter_hz=5000.0,
            compressor=CompressorParams(threshold_db=-6, ratio=4.0),
            reverb_mix=0.25,
        )
        processed = process_effects(sig, chain)
        self.assertEqual(len(processed), len(sig))

        # 3. 导出
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "fm_effects.wav")
            result = export_audio(processed, path, format="wav")
            self.assertTrue(os.path.exists(result))
            self.assertGreater(os.path.getsize(result), 0)


class TestMultiTrackMusicExportPipeline(unittest.TestCase):
    """多轨音乐渲染→导出"""

    def test_multitrack_render_and_export(self):
        """多轨渲染 → WAV 导出完整流程"""
        # 1. 构建多轨模式
        melody = MusicPattern(
            name="melody",
            notes=["C4", "E4", "G4", "C5"],
            durations=[0.5, 0.5, 0.5, 0.5],
            bpm=120,
            osc_type=OscType.SINE,
            volume=0.3,
        )
        arp = Arpeggiator(mode=ArpMode.UP)
        arp_notes = generate_arpeggio(arp, ["C4", "E4", "G4"], bpm=120)

        drums = DrumPattern(
            name="drums",
            steps=4,
            bpm=120,
            tracks={"kick": [True, False, True, False]},
            sounds={"kick": DrumSoundParams(osc_type=OscType.SINE, pitch_hz=60)},
        )
        multi = MultiTrackPattern(
            name="test_multi",
            bpm=120,
            music_tracks=[melody],
            drum_track=drums,
        )

        # 2. 渲染
        sig = render_multi_track(multi, 2.0)
        self.assertGreater(np.max(np.abs(sig)), 0.0)

        # 3. 导出
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "multitrack.wav")
            result = export_audio(sig, path, format="wav")
            self.assertTrue(os.path.exists(result))


class TestCLIArgumentParsing(unittest.TestCase):
    """CLI 参数解析验证"""

    def test_batch_format_argument(self):
        """--format 参数应正确解析"""
        from bloodmusic.cli import main
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_batch = sub.add_parser("batch")
        p_batch.add_argument("--format", "-f", default="wav",
                             choices=["wav", "ogg", "flac"])
        p_batch.add_argument("--bitrate", "-b", type=int, default=128000)
        p_batch.add_argument("--output", "-o", default="./audio_output")
        p_batch.add_argument("--duration", "-d", type=float, default=30.0)

        args = parser.parse_args(["batch", "--format", "ogg"])
        self.assertEqual(args.format, "ogg")

    def test_batch_bitrate_argument(self):
        """--bitrate 参数应正确解析"""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_batch = sub.add_parser("batch")
        p_batch.add_argument("--format", "-f", default="wav",
                             choices=["wav", "ogg", "flac"])
        p_batch.add_argument("--bitrate", "-b", type=int, default=128000)
        p_batch.add_argument("--output", "-o", default="./audio_output")
        p_batch.add_argument("--duration", "-d", type=float, default=30.0)

        args = parser.parse_args(["batch", "--bitrate", "256000"])
        self.assertEqual(args.bitrate, 256000)

    def test_batch_default_format(self):
        """默认 format 应为 wav"""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_batch = sub.add_parser("batch")
        p_batch.add_argument("--format", "-f", default="wav",
                             choices=["wav", "ogg", "flac"])
        p_batch.add_argument("--bitrate", "-b", type=int, default=128000)
        p_batch.add_argument("--output", "-o", default="./audio_output")
        p_batch.add_argument("--duration", "-d", type=float, default=30.0)

        args = parser.parse_args(["batch"])
        self.assertEqual(args.format, "wav")

    def test_batch_format_choices(self):
        """format 参数只接受 wav/ogg/flac"""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_batch = sub.add_parser("batch")
        p_batch.add_argument("--format", "-f", default="wav",
                             choices=["wav", "ogg", "flac"])

        # 无效格式应触发 SystemExit
        with self.assertRaises(SystemExit):
            parser.parse_args(["batch", "--format", "mp3"])


class TestTopLevelImport(unittest.TestCase):
    """顶层 bloodmusic 包导入验证"""

    def test_import_bloodmusic(self):
        """应能导入 bloodmusic 包"""
        import bloodmusic
        self.assertEqual(bloodmusic.__version__, "2.0.0")

    def test_import_core_symbols(self):
        """应能从 bloodmusic 导入核心符号"""
        from bloodmusic import (
            SR, BPM_DEFAULT, NORMALIZE_DBFS, DEFAULT_OGG_BITRATE,
            SynthVoice, synthesize_voice,
            LFOParams, LFOTarget,
            FMSynthVoice, synthesize_fm_voice,
            OscType, EnvShape,
        )
        self.assertIsNotNone(SR)
        self.assertIsNotNone(SynthVoice)
        self.assertIsNotNone(FMSynthVoice)

    def test_import_effects_symbols(self):
        """应能从 bloodmusic 导入效果器符号"""
        from bloodmusic import (
            EffectChain, process_effects,
            apply_lowpass, apply_highpass,
            apply_bandpass, apply_notch,
            apply_schroeder_reverb,
            apply_compressor, apply_limiter, CompressorParams,
            apply_parametric_eq, ParametricEQParams,
            apply_chorus,
        )
        self.assertIsNotNone(EffectChain)
        self.assertIsNotNone(apply_bandpass)

    def test_import_music_symbols(self):
        """应能从 bloodmusic 导入音乐符号"""
        from bloodmusic import (
            MusicPattern, generate_music_wav,
            DrumSoundParams, DrumPattern,
            MultiTrackPattern, render_multi_track,
            Arpeggiator, ArpMode, generate_arpeggio,
            Scale, SCALE_INTERVALS,
            ALL_MUSIC_PATTERNS,
        )
        self.assertIsNotNone(MusicPattern)
        self.assertEqual(len(ALL_MUSIC_PATTERNS), 15)

    def test_import_export_symbols(self):
        """应能从 bloodmusic 导入导出符号"""
        from bloodmusic import AudioBatchExporter, export_audio
        self.assertIsNotNone(AudioBatchExporter)

    def test_import_sfx_symbols(self):
        """应能从 bloodmusic 导入音效符号"""
        from bloodmusic import (
            UI_FX_PRESETS, CARD_FX_PRESETS,
            COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
        )
        self.assertIsNotNone(UI_FX_PRESETS)


class TestEndToEndPresetRendering(unittest.TestCase):
    """端到端预设渲染测试"""

    def test_sfx_preset_render(self):
        """所有 SFX 预设应可合成"""
        from bloodmusic.sfx import (
            UI_FX_PRESETS, CARD_FX_PRESETS,
            COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS,
        )
        all_presets = {}
        all_presets.update(UI_FX_PRESETS)
        all_presets.update(CARD_FX_PRESETS)
        all_presets.update(COMBAT_FX_PRESETS)
        all_presets.update(SYSTEM_FX_PRESETS)

        for name, voice in all_presets.items():
            try:
                sig = synthesize_voice(voice)
                self.assertGreater(len(sig), 0,
                                    f"SFX '{name}' produced empty signal")
            except Exception as e:
                self.fail(f"SFX '{name}' failed to synthesize: {e}")

    def test_scale_to_arpeggio_to_synth(self):
        """Scale → Arpeggiator → SynthVoice 完整流程"""
        scale = Scale(root="C", scale_type="minor", octave=4)
        notes = scale.get_notes()
        self.assertGreater(len(notes), 0)

        arp = Arpeggiator(mode=ArpMode.UP, gate=0.8)
        arp_result = generate_arpeggio(arp, notes, bpm=120)
        self.assertGreater(len(arp_result), 0)

        # 合成每个音符
        for note_name, dur in arp_result:
            from bloodmusic.core.note_utils import note_to_freq
            freq = note_to_freq(note_name)
            voice = SynthVoice(freq=freq, duration=dur, osc_type=OscType.SINE)
            sig = synthesize_voice(voice)
            self.assertGreater(len(sig), 0)


if __name__ == "__main__":
    unittest.main()
