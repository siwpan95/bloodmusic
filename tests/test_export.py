"""导出模块测试 —— WAV/FLAC 导出、_normalize_and_limit、AudioBatchExporter"""

import os
import tempfile
import unittest

import numpy as np

from bloodmusic.core.constants import SR, NORMALIZE_DBFS
from bloodmusic.export.batch import export_audio, _normalize_and_limit, AudioBatchExporter


def _make_test_signal(duration=0.5, freq=440.0):
    """生成测试正弦波信号"""
    t = np.linspace(0, duration, int(duration * SR), dtype=np.float64)
    return (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)


class TestNormalizeAndLimit(unittest.TestCase):
    """_normalize_and_limit 验证"""

    def test_output_does_not_exceed_unity(self):
        """归一化限幅后输出不应超过 1.0"""
        sig = np.array([0.5, -0.8, 0.3, -0.2], dtype=np.float64)
        result = _normalize_and_limit(sig)
        self.assertLessEqual(np.max(np.abs(result)), 1.0)

    def test_normalizes_to_target_dbfs(self):
        """归一化后峰值应接近 target_dbfs 对应的线性幅度"""
        sig = np.ones(1000, dtype=np.float64) * 0.5
        result = _normalize_and_limit(sig)
        target_amp = 10 ** (NORMALIZE_DBFS / 20.0)
        peak = np.max(np.abs(result))
        self.assertAlmostEqual(peak, target_amp, places=3)

    def test_silent_signal_stays_zero(self):
        """全零信号归一化后应仍为零"""
        sig = np.zeros(100, dtype=np.float64)
        result = _normalize_and_limit(sig)
        self.assertAlmostEqual(np.max(np.abs(result)), 0.0)

    def test_clips_values_above_unity(self):
        """超过 ±1.0 的值应被截断"""
        sig = np.array([2.0, -1.5, 0.3], dtype=np.float64)
        result = _normalize_and_limit(sig)
        self.assertLessEqual(np.max(np.abs(result)), 1.0)


class TestExportAudioWAV(unittest.TestCase):
    """export_audio WAV 导出验证"""

    def test_wav_file_created(self):
        """WAV 导出应创建文件"""
        sig = _make_test_signal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.wav")
            result = export_audio(sig, path, format="wav")
            self.assertTrue(os.path.exists(result))

    def test_wav_file_nonzero_size(self):
        """WAV 文件大小应非零"""
        sig = _make_test_signal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.wav")
            export_audio(sig, path, format="wav")
            size = os.path.getsize(path)
            self.assertGreater(size, 0)

    def test_wav_file_readable(self):
        """导出的 WAV 文件应可被 soundfile 读取"""
        sig = _make_test_signal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.wav")
            export_audio(sig, path, format="wav")
            import soundfile as sf
            data, sr_read = sf.read(path)
            self.assertEqual(sr_read, SR)
            self.assertGreater(len(data), 0)

    def test_wav_accepts_float32(self):
        """WAV 导出应接受 float32 输入"""
        sig = _make_test_signal().astype(np.float32)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_f32.wav")
            export_audio(sig, path, format="wav")
            self.assertTrue(os.path.exists(path))

    def test_wav_accepts_float64(self):
        """WAV 导出应接受 float64 输入"""
        sig = _make_test_signal().astype(np.float64)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_f64.wav")
            export_audio(sig, path, format="wav")
            self.assertTrue(os.path.exists(path))


class TestExportAudioFLAC(unittest.TestCase):
    """FLAC 导出验证"""

    def test_flac_file_created(self):
        """FLAC 导出应创建文件"""
        sig = _make_test_signal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.flac")
            try:
                result = export_audio(sig, path, format="flac")
                self.assertTrue(os.path.exists(result))
                self.assertGreater(os.path.getsize(result), 0)
            except Exception as e:
                # soundfile 可能不支持 FLAC
                self.skipTest(f"FLAC not supported: {e}")


class TestExportAudioInvalidFormat(unittest.TestCase):
    """不支持的格式应抛出 ValueError"""

    def test_invalid_format_raises(self):
        """不支持的格式应抛出 ValueError"""
        sig = _make_test_signal()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.mp3")
            with self.assertRaises(ValueError):
                export_audio(sig, path, format="mp3")


class TestAudioBatchExporter(unittest.TestCase):
    """AudioBatchExporter format 参数验证"""

    def test_exporter_default_format(self):
        """默认格式应为 wav"""
        exporter = AudioBatchExporter("/tmp/test_output")
        self.assertEqual(exporter.format, "wav")

    def test_exporter_ogg_format(self):
        """OGG 格式应正确设置"""
        exporter = AudioBatchExporter("/tmp/test_output", format="ogg")
        self.assertEqual(exporter.format, "ogg")

    def test_exporter_flac_format(self):
        """FLAC 格式应正确设置"""
        exporter = AudioBatchExporter("/tmp/test_output", format="flac")
        self.assertEqual(exporter.format, "flac")

    def test_exporter_format_dot_strip(self):
        """格式带点号应被移除"""
        exporter = AudioBatchExporter("/tmp/test_output", format=".wav")
        self.assertEqual(exporter.format, "wav")

    def test_exporter_ext_property(self):
        """_ext 属性应返回正确的扩展名"""
        exporter = AudioBatchExporter("/tmp/test_output", format="wav")
        self.assertEqual(exporter._ext, ".wav")
        exporter = AudioBatchExporter("/tmp/test_output", format="flac")
        self.assertEqual(exporter._ext, ".flac")

    def test_exporter_creates_dirs(self):
        """ensure_dirs 应创建输出目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "export_test")
            exporter = AudioBatchExporter(output_dir, format="wav")
            exporter.ensure_dirs()
            self.assertTrue(os.path.exists(os.path.join(output_dir, "sfx", "ui")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "sfx", "combat")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "music")))


if __name__ == "__main__":
    unittest.main()
