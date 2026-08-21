"""效果器模块测试 —— 滤波器 / 混响 / 动态 / EQ / Chorus / 效果链"""

import unittest

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.core.oscillator import oscillator, OscType
from bloodmusic.effects.filters import (
    apply_lowpass, apply_highpass, apply_bandpass, apply_notch,
)
from bloodmusic.effects.spatial import (
    apply_simple_reverb, apply_schroeder_reverb,
)
from bloodmusic.effects.dynamics import (
    CompressorParams, apply_compressor, apply_limiter,
)
from bloodmusic.effects.eq import ParametricEQParams, apply_parametric_eq
from bloodmusic.effects.modulation import apply_chorus
from bloodmusic.effects.chain import EffectChain, process_effects


def _make_sine(freq=440.0, duration=0.5, sr=SR):
    """生成正弦波测试信号"""
    t = np.linspace(0, duration, int(duration * sr), dtype=np.float64)
    return np.sin(2 * np.pi * freq * t)


def _make_sweep(duration=1.0, sr=SR):
    """生成从 100Hz 到 10000Hz 的扫频信号"""
    t = np.linspace(0, duration, int(duration * sr), dtype=np.float64)
    freqs = np.linspace(100, 10000, len(t))
    phase = np.cumsum(2 * np.pi * freqs / sr)
    return np.sin(phase)


class TestLowpassFilter(unittest.TestCase):
    """低通滤波器测试"""

    def test_lowpass_reduces_high_freq(self):
        """低通滤波应衰减高频分量"""
        sig = _make_sweep()
        filtered = apply_lowpass(sig, 1000.0)
        # 高频部分的能量应减少
        # 比较后半段（高频）的 RMS
        half = len(sig) // 2
        rms_orig = np.sqrt(np.mean(sig[half:] ** 2))
        rms_filt = np.sqrt(np.mean(filtered[half:] ** 2))
        self.assertLess(rms_filt, rms_orig)

    def test_lowpass_preserves_length(self):
        """低通滤波后信号长度不变"""
        sig = _make_sine()
        filtered = apply_lowpass(sig, 2000.0)
        self.assertEqual(len(filtered), len(sig))

    def test_lowpass_zero_cutoff_returns_original(self):
        """截止频率 <= 0 时返回原信号"""
        sig = _make_sine()
        filtered = apply_lowpass(sig, 0.0)
        self.assertTrue(np.array_equal(sig, filtered))

    def test_lowpass_above_nyquist_returns_original(self):
        """截止频率 >= Nyquist 时返回原信号"""
        sig = _make_sine()
        filtered = apply_lowpass(sig, SR / 2.0)
        self.assertTrue(np.array_equal(sig, filtered))


class TestHighpassFilter(unittest.TestCase):
    """高通滤波器测试"""

    def test_highpass_reduces_low_freq(self):
        """高通滤波应衰减低频分量"""
        sig = _make_sweep()
        filtered = apply_highpass(sig, 5000.0)
        # 低频部分的能量应减少
        quarter = len(sig) // 4
        rms_orig = np.sqrt(np.mean(sig[:quarter] ** 2))
        rms_filt = np.sqrt(np.mean(filtered[:quarter] ** 2))
        self.assertLess(rms_filt, rms_orig)

    def test_highpass_preserves_length(self):
        """高通滤波后信号长度不变"""
        sig = _make_sine()
        filtered = apply_highpass(sig, 2000.0)
        self.assertEqual(len(filtered), len(sig))

    def test_highpass_zero_cutoff_returns_original(self):
        """截止频率 <= 0 时返回原信号"""
        sig = _make_sine()
        filtered = apply_highpass(sig, 0.0)
        self.assertTrue(np.array_equal(sig, filtered))


class TestBandpassFilter(unittest.TestCase):
    """带通滤波器测试"""

    def test_bandpass_output_nonzero(self):
        """带通滤波应产生非零输出"""
        sig = _make_sweep()
        filtered = apply_bandpass(sig, 1000.0, q=1.0)
        self.assertGreater(np.max(np.abs(filtered)), 0.01)

    def test_bandpass_preserves_length(self):
        """带通滤波后信号长度不变"""
        sig = _make_sine()
        filtered = apply_bandpass(sig, 1000.0)
        self.assertEqual(len(filtered), len(sig))

    def test_bandpass_zero_center_returns_original(self):
        """中心频率 <= 0 时返回原信号"""
        sig = _make_sine()
        filtered = apply_bandpass(sig, 0.0)
        self.assertTrue(np.array_equal(sig, filtered))

    def test_bandpass_with_q(self):
        """不同 Q 值应产生不同输出"""
        sig = _make_sweep()
        filtered_low_q = apply_bandpass(sig, 1000.0, q=0.5)
        filtered_high_q = apply_bandpass(sig, 1000.0, q=10.0)
        self.assertFalse(np.allclose(filtered_low_q, filtered_high_q, atol=1e-6))


class TestNotchFilter(unittest.TestCase):
    """陷波滤波器测试"""

    def test_notch_output_nonzero(self):
        """陷波滤波应产生非零输出"""
        sig = _make_sweep()
        filtered = apply_notch(sig, 1000.0, q=1.0)
        self.assertGreater(np.max(np.abs(filtered)), 0.01)

    def test_notch_preserves_length(self):
        """陷波滤波后信号长度不变"""
        sig = _make_sine()
        filtered = apply_notch(sig, 1000.0)
        self.assertEqual(len(filtered), len(sig))

    def test_notch_zero_freq_returns_original(self):
        """陷波频率 <= 0 时返回原信号"""
        sig = _make_sine()
        filtered = apply_notch(sig, 0.0)
        self.assertTrue(np.array_equal(sig, filtered))

    def test_notch_reduces_target_freq(self):
        """陷波应衰减目标频率附近的能量"""
        # 生成纯 1000Hz 正弦波
        sig = _make_sine(freq=1000.0)
        filtered = apply_notch(sig, 1000.0, q=5.0)
        # 陷波后 RMS 应显著降低
        rms_orig = np.sqrt(np.mean(sig ** 2))
        rms_filt = np.sqrt(np.mean(filtered ** 2))
        self.assertLess(rms_filt, rms_orig * 0.9)


class TestSchroederReverb(unittest.TestCase):
    """Schroeder 混响测试"""

    def test_schroeder_preserves_length(self):
        """Schroeder 混响后信号长度不变"""
        sig = _make_sine(duration=0.5)
        result = apply_schroeder_reverb(sig, mix=0.3)
        self.assertEqual(len(result), len(sig))

    def test_schroeder_mix_parameter(self):
        """不同 mix 参数应产生不同输出"""
        sig = _make_sine(duration=0.5)
        result_low = apply_schroeder_reverb(sig, mix=0.1)
        result_high = apply_schroeder_reverb(sig, mix=0.5)
        self.assertFalse(np.allclose(result_low, result_high, atol=1e-4))

    def test_schroeder_zero_mix_returns_original(self):
        """mix=0 时应返回原信号"""
        sig = _make_sine(duration=0.3)
        result = apply_schroeder_reverb(sig, mix=0.0)
        self.assertTrue(np.allclose(sig, result, atol=1e-6))

    def test_schroeder_output_nonzero(self):
        """Schroeder 混响输出应非零"""
        sig = _make_sine(duration=0.5)
        result = apply_schroeder_reverb(sig, mix=0.3)
        self.assertGreater(np.max(np.abs(result)), 0.01)

    def test_schroeder_no_clipping(self):
        """Schroeder 混响输出不应爆音"""
        sig = _make_sine(duration=0.5)
        result = apply_schroeder_reverb(sig, mix=0.5)
        self.assertLessEqual(np.max(np.abs(result)), 1.01)


class TestCompressor(unittest.TestCase):
    """压缩器测试"""

    def test_compressor_params_defaults(self):
        """CompressorParams 默认值验证"""
        params = CompressorParams()
        self.assertAlmostEqual(params.threshold_db, -12.0)
        self.assertAlmostEqual(params.ratio, 4.0)
        self.assertAlmostEqual(params.attack_ms, 10.0)
        self.assertAlmostEqual(params.release_ms, 100.0)
        self.assertAlmostEqual(params.makeup_db, 0.0)

    def test_compressor_reduces_peak(self):
        """压缩器应降低峰值"""
        # 生成一个有峰值的信号
        sig = _make_sine(freq=440, duration=0.5) * 0.9
        # 添加一个峰值
        sig[len(sig) // 2] = 1.0
        params = CompressorParams(threshold_db=-6, ratio=4.0)
        compressed = apply_compressor(sig, params)
        # 压缩后峰值应比原信号峰值低
        self.assertLess(np.max(np.abs(compressed)), np.max(np.abs(sig)))

    def test_compressor_preserves_length(self):
        """压缩后信号长度不变"""
        sig = _make_sine()
        params = CompressorParams()
        compressed = apply_compressor(sig, params)
        self.assertEqual(len(compressed), len(sig))

    def test_compressor_zero_threshold_passthrough(self):
        """阈值为 0dB 时应直接通过（不压缩）"""
        sig = _make_sine()
        params = CompressorParams(threshold_db=0.0)
        compressed = apply_compressor(sig, params)
        self.assertTrue(np.allclose(sig, compressed, atol=1e-6))

    def test_compressor_makeup_gain(self):
        """压缩器 makeup gain 应增加输出幅度"""
        sig = _make_sine(freq=440, duration=0.5) * 0.5
        params_no_gain = CompressorParams(threshold_db=-12, makeup_db=0.0)
        params_with_gain = CompressorParams(threshold_db=-12, makeup_db=6.0)
        sig_no = apply_compressor(sig, params_no_gain)
        sig_with = apply_compressor(sig, params_with_gain)
        self.assertGreater(np.max(np.abs(sig_with)), np.max(np.abs(sig_no)))


class TestLimiter(unittest.TestCase):
    """限幅器测试"""

    def test_limiter_output_within_threshold(self):
        """限幅器输出不应超过阈值"""
        sig = _make_sine() * 2.0  # 超幅信号
        threshold_db = -3.0
        limited = apply_limiter(sig, threshold_db=threshold_db)
        threshold_lin = 10 ** (threshold_db / 20.0)
        self.assertLessEqual(np.max(np.abs(limited)), threshold_lin + 1e-10)

    def test_limiter_preserves_length(self):
        """限幅后信号长度不变"""
        sig = _make_sine()
        limited = apply_limiter(sig)
        self.assertEqual(len(limited), len(sig))

    def test_limiter_default_threshold(self):
        """默认阈值 -1dB 下输出应不超过 ~0.8913"""
        sig = _make_sine() * 2.0
        limited = apply_limiter(sig)
        expected_threshold = 10 ** (-1.0 / 20.0)
        self.assertLessEqual(np.max(np.abs(limited)), expected_threshold + 1e-10)


class TestParametricEQ(unittest.TestCase):
    """参量 EQ 测试"""

    def test_eq_params_defaults(self):
        """ParametricEQParams 默认值验证"""
        params = ParametricEQParams()
        self.assertAlmostEqual(params.low_freq, 200.0)
        self.assertAlmostEqual(params.low_gain_db, 0.0)
        self.assertAlmostEqual(params.mid_freq, 1000.0)
        self.assertAlmostEqual(params.mid_gain_db, 0.0)
        self.assertAlmostEqual(params.high_freq, 4000.0)
        self.assertAlmostEqual(params.high_gain_db, 0.0)

    def test_eq_zero_gain_passthrough(self):
        """所有增益为 0dB 时应接近原信号"""
        sig = _make_sine()
        params = ParametricEQParams()
        result = apply_parametric_eq(sig, params)
        # 0dB 增益近似直通（可能有微小滤波器误差）
        self.assertTrue(np.allclose(sig, result, atol=0.05))

    def test_eq_boost_changes_signal(self):
        """增益提升应改变信号"""
        sig = _make_sine()
        params = ParametricEQParams(mid_gain_db=6.0)
        result = apply_parametric_eq(sig, params)
        self.assertFalse(np.allclose(sig, result, atol=1e-4))

    def test_eq_preserves_length(self):
        """EQ 后信号长度不变"""
        sig = _make_sine()
        params = ParametricEQParams(low_gain_db=3.0, mid_gain_db=-3.0, high_gain_db=6.0)
        result = apply_parametric_eq(sig, params)
        self.assertEqual(len(result), len(sig))


class TestChorus(unittest.TestCase):
    """Chorus 效果测试"""

    def test_chorus_preserves_length(self):
        """Chorus 后信号长度不变"""
        sig = _make_sine(duration=0.5)
        result = apply_chorus(sig, mix=0.5)
        self.assertEqual(len(result), len(sig))

    def test_chorus_output_nonzero(self):
        """Chorus 应产生非零输出"""
        sig = _make_sine(duration=0.5)
        result = apply_chorus(sig, mix=0.5)
        self.assertGreater(np.max(np.abs(result)), 0.01)

    def test_chorus_zero_mix_returns_original(self):
        """mix=0 时应返回原信号"""
        sig = _make_sine(duration=0.3)
        result = apply_chorus(sig, mix=0.0)
        self.assertTrue(np.allclose(sig, result, atol=1e-6))

    def test_chorus_different_voices(self):
        """不同声部数应产生不同输出"""
        sig = _make_sine(duration=0.3)
        result_2 = apply_chorus(sig, mix=0.5, n_voices=2)
        result_5 = apply_chorus(sig, mix=0.5, n_voices=5)
        self.assertFalse(np.allclose(result_2, result_5, atol=1e-4))

    def test_chorus_no_clipping(self):
        """Chorus 输出不应爆音"""
        sig = _make_sine(duration=0.5)
        result = apply_chorus(sig, mix=0.7)
        self.assertLessEqual(np.max(np.abs(result)), 1.01)


class TestEffectChain(unittest.TestCase):
    """EffectChain 新字段验证"""

    def test_effect_chain_defaults(self):
        """EffectChain 所有新字段默认值验证"""
        chain = EffectChain()
        self.assertIsNone(chain.lp_filter_hz)
        self.assertIsNone(chain.hp_filter_hz)
        self.assertAlmostEqual(chain.distortion, 0.0)
        self.assertIsNone(chain.bit_crush)
        self.assertAlmostEqual(chain.reverb_mix, 0.0)
        self.assertAlmostEqual(chain.reverb_decay, 0.5)
        self.assertAlmostEqual(chain.reverb_delay_ms, 40.0)
        self.assertAlmostEqual(chain.stereo_width, 0.0)
        # 新增字段
        self.assertIsNone(chain.bp_center_hz)
        self.assertIsNone(chain.bp_q)
        self.assertIsNone(chain.notch_hz)
        self.assertIsNone(chain.notch_q)
        self.assertFalse(chain.reverb_schroeder)
        self.assertIsNone(chain.compressor)
        self.assertIsNone(chain.eq)
        self.assertAlmostEqual(chain.chorus_mix, 0.0)
        self.assertAlmostEqual(chain.chorus_rate, 0.5)
        self.assertAlmostEqual(chain.chorus_depth, 0.002)

    def test_effect_chain_custom_values(self):
        """EffectChain 自定义值验证"""
        chain = EffectChain(
            lp_filter_hz=2000.0,
            bp_center_hz=1000.0,
            bp_q=5.0,
            notch_hz=60.0,
            reverb_schroeder=True,
            chorus_mix=0.3,
        )
        self.assertAlmostEqual(chain.lp_filter_hz, 2000.0)
        self.assertAlmostEqual(chain.bp_center_hz, 1000.0)
        self.assertTrue(chain.reverb_schroeder)
        self.assertAlmostEqual(chain.chorus_mix, 0.3)


class TestProcessEffects(unittest.TestCase):
    """process_effects 完整链路测试"""

    def test_process_empty_chain(self):
        """空效果链应返回近似原信号"""
        sig = _make_sine()
        chain = EffectChain()
        result = process_effects(sig, chain)
        self.assertTrue(np.allclose(sig, result, atol=1e-6))

    def test_process_with_lowpass(self):
        """效果链含低通滤波应正常工作"""
        sig = _make_sweep()
        chain = EffectChain(lp_filter_hz=2000.0)
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))

    def test_process_with_compressor(self):
        """效果链含压缩器应正常工作"""
        sig = _make_sine() * 0.9
        chain = EffectChain(compressor=CompressorParams(threshold_db=-6, ratio=4.0))
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))

    def test_process_with_eq(self):
        """效果链含 EQ 应正常工作"""
        sig = _make_sine()
        chain = EffectChain(eq=ParametricEQParams(mid_gain_db=6.0))
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))

    def test_process_with_chorus(self):
        """效果链含 Chorus 应正常工作"""
        sig = _make_sine(duration=0.5)
        chain = EffectChain(chorus_mix=0.5)
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))

    def test_process_schroeder_reverb(self):
        """效果链 Schroeder 混响应正常工作"""
        sig = _make_sine(duration=0.5)
        chain = EffectChain(reverb_mix=0.3, reverb_schroeder=True)
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))

    def test_process_full_chain(self):
        """完整效果链应正常工作"""
        sig = _make_sine(duration=0.5)
        chain = EffectChain(
            lp_filter_hz=5000.0,
            hp_filter_hz=100.0,
            eq=ParametricEQParams(mid_gain_db=3.0),
            compressor=CompressorParams(threshold_db=-10, ratio=4.0),
            chorus_mix=0.3,
            reverb_mix=0.2,
        )
        result = process_effects(sig, chain)
        self.assertEqual(len(result), len(sig))
        self.assertGreater(np.max(np.abs(result)), 0.01)

    def test_process_preserves_dtype(self):
        """process_effects 应返回 float64 数组"""
        sig = _make_sine()
        chain = EffectChain(lp_filter_hz=2000.0)
        result = process_effects(sig, chain)
        self.assertEqual(result.dtype, np.float64)


if __name__ == "__main__":
    unittest.main()
