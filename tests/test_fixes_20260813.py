"""2026-08-13 修复回归测试

覆盖本次评估修复的缺陷:
  - 严重1: 粉红噪声向量化正确性 (core/oscillator.py)
  - 严重2: 实时引擎节奏门控真正生效 (interactive/engine.py)
  - 中等4: main.py _PROJECT_ROOT 指向包目录自身
  - 中等5: note_to_freq 非法输入防御 + 振荡器相位稳定
"""

import unittest

import numpy as np

from bloodmusic.core.oscillator import (
    osc_noise_pink, osc_saw, osc_square, osc_triangle, _phase_fraction,
)
from bloodmusic.core.note_utils import note_to_freq
from bloodmusic.interactive.engine import RealtimeMusicEngine
from bloodmusic.interactive.layer_mixer import MusicLayer, LayerRole


class TestPinkNoiseFix(unittest.TestCase):
    """严重1: 粉红噪声应无 NaN/Inf、长度正确、且具备真实能量。"""

    def test_no_nan_or_inf(self):
        out = osc_noise_pink(20000)
        self.assertEqual(len(out), 20000)
        self.assertFalse(np.any(np.isnan(out)), "粉红噪声不应含 NaN")
        self.assertFalse(np.any(np.isinf(out)), "粉红噪声不应含 Inf")

    def test_finite_energy(self):
        out = osc_noise_pink(50000)
        rms = float(np.sqrt(np.mean(out ** 2)))
        # 归一化后应有合理幅度（不为全零、也不爆音）
        self.assertGreater(rms, 1e-4)
        self.assertLess(rms, 1.0)

    def test_deterministic_with_seed(self):
        a = osc_noise_pink(1000, rng=np.random.default_rng(42))
        b = osc_noise_pink(1000, rng=np.random.default_rng(42))
        np.testing.assert_array_equal(a, b, "相同 seed 应可复现")


class TestNoteToFreqDefense(unittest.TestCase):
    """中等5: 非法音符必须显式报错，而非静默回退 440Hz。"""

    def test_valid_note(self):
        self.assertAlmostEqual(note_to_freq("A4"), 440.0, places=2)
        self.assertAlmostEqual(note_to_freq("C#4"), 277.18, places=1)

    def test_underscore_normalization(self):
        self.assertEqual(note_to_freq("Eb_4"), note_to_freq("Eb4"))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            note_to_freq("")

    def test_missing_octave_raises(self):
        with self.assertRaises(ValueError):
            note_to_freq("C")

    def test_unknown_pitch_raises(self):
        with self.assertRaises(ValueError):
            note_to_freq("H4")


class TestPhaseStability(unittest.TestCase):
    """中等5: 长音频下相位计算不应崩溃或产生 NaN。"""

    def test_phase_fraction_in_range(self):
        t = np.linspace(0, 1000, 50000)  # 长音频
        ph = _phase_fraction(t, 440.0)
        self.assertTrue(np.all((ph >= 0.0) & (ph < 1.0)))

    def test_saw_no_nan_long_audio(self):
        t = np.linspace(0, 3000, 100000)
        out = osc_saw(t, 55.0)
        self.assertFalse(np.any(np.isnan(out)))

    def test_square_duty_clamped(self):
        t = np.linspace(0, 1, 1000)
        # duty 被钳制到 [0,1]，越界不应报错，且整段取同相
        # duty 钳制到 1.0 -> phase<1.0 恒真 -> 整段 1.0
        out = osc_square(t, 220.0, duty=1.5)
        self.assertEqual(out.min(), 1.0)
        self.assertEqual(out.max(), 1.0)
        # duty 钳制到 0.0 -> phase<0.0 恒假 -> 整段 -1.0
        out2 = osc_square(t, 220.0, duty=-0.5)
        self.assertEqual(out2.min(), -1.0)
        self.assertEqual(out2.max(), -1.0)

    def test_triangle_finite(self):
        t = np.linspace(0, 500, 20000)
        out = osc_triangle(t, 330.0)
        self.assertFalse(np.any(np.isnan(out)))


class TestMainPathRoot(unittest.TestCase):
    """中等4: _PROJECT_ROOT 应指向包目录 bloodmusic 自身。"""

    def test_project_root_is_package_dir(self):
        import importlib.util
        from pathlib import Path

        # 直接载入包根下的 main.py，避免依赖 sys.path 配置
        main_path = Path(__file__).resolve().parents[1] / "main.py"
        spec = importlib.util.spec_from_file_location("_bm_main_under_test", main_path)
        _m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_m)

        expected = main_path.resolve().parent  # bloodmusic/ 包目录
        self.assertEqual(_m._PROJECT_ROOT, expected)
        # 不应再向上跳一级到 bloodmusic 的父目录
        self.assertNotEqual(_m._PROJECT_ROOT, expected.parent)


class TestRealtimeGateFix(unittest.TestCase):
    """严重2: rhythm_pattern 必须在实时合成中真正调制层增益。"""

    def _engine_with_layer(self, layer: MusicLayer) -> RealtimeMusicEngine:
        engine = RealtimeMusicEngine()
        engine._active_mappings = {"bpm": 120, "filter_openness": 1.0}
        engine._t = 0.0
        # 直接替换混音器层集合以便单测 _synthesize_layer
        engine.mixer._layers = [layer]
        return engine

    def test_gate_changes_output_by_beat_phase(self):
        """强拍与弱拍相位合成出的 RMS 应明显不同（门控生效）。"""
        layer = MusicLayer(
            role=LayerRole.MELODY, name="lead",
            osc_type="saw", base_octave=4,
            notes=["Eb", "G"],
            # 两段：前 0.5 拍强、后 0.5 拍弱
            rhythm_pattern=[0.5, 0.5],
        )
        sr = 44100
        n = sr // 4  # 0.25s (半拍)

        # 强拍段起点 (t=0, 落在段0 -> 增益 1.0)
        engine_on = self._engine_with_layer(layer)
        engine_on._t = 0.0
        out_on = engine_on._synthesize_layer(layer, 1.0, n, sr)

        # 弱拍段起点 (t=0.25 拍, 落在段1 -> 增益 0.5)
        engine_off = self._engine_with_layer(layer)
        engine_off._t = (60.0 / 120.0) * 0.5
        out_off = engine_off._synthesize_layer(layer, 1.0, n, sr)

        rms_on = float(np.sqrt(np.mean(out_on ** 2)))
        rms_off = float(np.sqrt(np.mean(out_off ** 2)))
        # 弱拍增益应为强拍的大约一半 -> RMS 显著更小
        self.assertGreater(rms_on, 0.0)
        ratio = rms_off / rms_on
        self.assertTrue(0.2 < ratio < 0.8,
                        f"弱拍/强拍 RMS 比值应为 ~0.5，实际 {ratio:.3f}")

    def test_no_pattern_keeps_full_gain(self):
        """无 rhythm_pattern 时不应被门控衰减（增益恒为 1.0）。"""
        layer = MusicLayer(
            role=LayerRole.MELODY, name="lead",
            osc_type="saw", base_octave=4,
            notes=["G"],
            rhythm_pattern=[],
        )
        sr = 44100
        n = sr // 4
        engine = self._engine_with_layer(layer)
        engine._t = (60.0 / 120.0) * 0.5  # 任意弱拍相位
        out = engine._synthesize_layer(layer, 1.0, n, sr)
        # 无 pattern 时整段应保留正常幅度（不应被削到一半）
        rms = float(np.sqrt(np.mean(out ** 2)))
        self.assertGreater(rms, 0.1)


if __name__ == "__main__":
    unittest.main()
