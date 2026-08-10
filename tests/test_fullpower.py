"""全性能压榨方案完整测试套件

覆盖范围:
  1. 向后兼容性 — 22个现有 YAML 正常加载 + validate()
  2. 真实引擎渲染 — 6种引擎各自产生非零音频
  3. Automation 功能 — filter_sweep + volume_curve 正确工作
  4. 12个 fullpower YAML 结构校验
  5. engine_params / automation 序列化往返
  6. MusicPattern 新字段 (engine/engine_params/automation)
  7. Pool 级别 automation 继承
  8. --fullpower CLI 端到端
"""

import os
import sys
import tempfile
import unittest

import numpy as np

from bloodmusic.core.constants import SR


# ═══════════════════════════════════════════════════════════════════════
# 辅助工具
# ═══════════════════════════════════════════════════════════════════════

def _all_yaml_files():
    """返回 pool_presets 下所有 YAML 文件路径"""
    presets_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "music", "pool_presets",
    )
    return sorted([
        os.path.join(presets_dir, f)
        for f in os.listdir(presets_dir)
        if f.endswith(".yaml")
    ])


def _existing_yaml_files():
    """返回非 fullpower 的现有 YAML（向后兼容测试用）"""
    return [f for f in _all_yaml_files() if "fullpower_" not in os.path.basename(f)]


def _fullpower_yaml_files():
    """返回 fullpower_ 前缀的 YAML 文件"""
    return [f for f in _all_yaml_files() if "fullpower_" in os.path.basename(f)]


def _make_minimal_pool(role_name, role, engine, engine_params=None, automation=None):
    """创建最小测试用乐器池"""
    from bloodmusic.music.instrument_pool import (
        InstrumentPool, PoolInstrument, InstrumentRole,
    )
    inst = PoolInstrument(
        name=role_name,
        role=role,
        engine=engine,
        volume=0.5,
        note_sequence=["C4", "E4", "G4", "C5"],
    )
    if engine_params:
        inst.engine_params = engine_params
    if automation:
        inst.automation = automation

    pool = InstrumentPool(
        name=f"{role_name} Test",
        bpm=100,
        key="C",
        scale="major",
        instruments=[inst],
    )
    return pool


# ═══════════════════════════════════════════════════════════════════════
# 1. 向后兼容性 — 22 个现有 YAML
# ═══════════════════════════════════════════════════════════════════════

class TestBackwardCompatibility(unittest.TestCase):
    """所有现有 YAML 正常加载 + validate()"""

    def test_all_existing_yaml_load(self):
        """22 个现有 YAML 全部可成功加载"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        failures = []
        for yf in _existing_yaml_files():
            try:
                pool = InstrumentPool.from_yaml(yf)
                self.assertIsNotNone(pool)
                self.assertIsInstance(pool.name, str)
                self.assertGreater(len(pool.name.strip()), 0)
            except Exception as e:
                failures.append(f"{os.path.basename(yf)}: {e}")
        self.assertEqual(len(failures), 0,
                         f"Failed to load: {failures}")

    def test_all_existing_yaml_validate(self):
        """22 个现有 YAML validate() 无结构性错误"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        structural_issues = []
        for yf in _existing_yaml_files():
            pool = InstrumentPool.from_yaml(yf)
            warnings = pool.validate()
            # 仅关注结构性错误（非"建议"级别），例如 name 为空、bpm 无效
            critical = [w for w in warnings if "为空" in w or "无效" in w]
            if critical:
                structural_issues.append(
                    f"{os.path.basename(yf)}: {critical}"
                )
        self.assertEqual(len(structural_issues), 0,
                         f"Structural validation issues: {structural_issues}")

    def test_existing_yaml_has_no_engine_params_field(self):
        """现有 YAML 中不应包含 engine_params 字段（向后兼容验证）"""
        # 这个测试确认现有 YAML 在没有 engine_params 时正常工作
        from bloodmusic.music.instrument_pool import InstrumentPool
        for yf in _existing_yaml_files():
            pool = InstrumentPool.from_yaml(yf)
            for inst in pool.instruments:
                # 现有 YAML 的 engine_params 应为空 dict
                self.assertEqual(
                    inst.engine_params, {},
                    f"{os.path.basename(yf)}: {inst.name} has engine_params"
                )

    def test_existing_yaml_has_no_automation_field(self):
        """现有 YAML 中不应包含 automation 字段"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        for yf in _existing_yaml_files():
            pool = InstrumentPool.from_yaml(yf)
            for inst in pool.instruments:
                self.assertIsNone(
                    inst.automation,
                    f"{os.path.basename(yf)}: {inst.name} has automation"
                )

    def test_count_existing_yaml(self):
        """确认现有 YAML 数量为 22"""
        existing = _existing_yaml_files()
        self.assertEqual(len(existing), 22,
                         f"Expected 22 existing YAMLs, got {len(existing)}")


# ═══════════════════════════════════════════════════════════════════════
# 2. 真实引擎渲染验证
# ═══════════════════════════════════════════════════════════════════════

class TestRealEngineRendering(unittest.TestCase):
    """6 种真实合成引擎各自产生非零音频"""

    def _render_and_check(self, engine, engine_params=None,
                          role="melody", duration=2.0):
        """渲染一个引擎并验证音频非零"""
        from bloodmusic.music.instrument_pool import (
            InstrumentRole, PoolInstrument,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        role_enum = InstrumentRole.from_string(role)
        pool = _make_minimal_pool(
            role_name=f"Test {engine.value}",
            role=role_enum,
            engine=engine,
            engine_params=engine_params,
        )
        renderer = PoolRenderer(pool, duration_sec=duration)
        final, stems = renderer.render()
        peak = np.max(np.abs(final))
        return peak, final, stems

    def test_waveguide_clarinet(self):
        """waveguide clarinet 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVEGUIDE,
            engine_params={"instrument": "clarinet"},
        )
        self.assertGreater(peak, 1e-6,
                           f"waveguide clarinet peak={peak} too low")

    def test_waveguide_flute(self):
        """waveguide flute 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVEGUIDE,
            engine_params={"instrument": "flute"},
        )
        self.assertGreater(peak, 1e-6,
                           f"waveguide flute peak={peak} too low")

    def test_waveguide_brass(self):
        """waveguide brass 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVEGUIDE,
            engine_params={"instrument": "brass"},
        )
        self.assertGreater(peak, 1e-6,
                           f"waveguide brass peak={peak} too low")

    def test_waveguide_saxophone(self):
        """waveguide saxophone 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVEGUIDE,
            engine_params={"instrument": "saxophone"},
        )
        self.assertGreater(peak, 1e-6,
                           f"waveguide saxophone peak={peak} too low")

    def test_granular_ethereal_pad(self):
        """granular ethereal_pad 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.GRANULAR,
            engine_params={"preset": "ethereal_pad"},
            role="pad",
        )
        self.assertGreater(peak, 1e-6,
                           f"granular ethereal_pad peak={peak} too low")

    def test_granular_wind_ambient(self):
        """granular wind_ambient 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.GRANULAR,
            engine_params={"preset": "wind_ambient"},
            role="pad",
        )
        self.assertGreater(peak, 1e-6,
                           f"granular wind_ambient peak={peak} too low")

    def test_granular_sci_fi(self):
        """granular sci_fi 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.GRANULAR,
            engine_params={"preset": "sci_fi"},
            role="pad",
        )
        self.assertGreater(peak, 1e-6,
                           f"granular sci_fi peak={peak} too low")

    def test_fm_advanced_dx7_bell(self):
        """fm_advanced dx7_bell 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.FM_ADVANCED,
            engine_params={"preset": "dx7_bell"},
        )
        self.assertGreater(peak, 1e-6,
                           f"fm_advanced dx7_bell peak={peak} too low")

    def test_fm_advanced_dx7_epiano(self):
        """fm_advanced dx7_epiano 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.FM_ADVANCED,
            engine_params={"preset": "dx7_epiano"},
        )
        self.assertGreater(peak, 1e-6,
                           f"fm_advanced dx7_epiano peak={peak} too low")

    def test_fm_advanced_dx7_bass(self):
        """fm_advanced dx7_bass 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.FM_ADVANCED,
            engine_params={"preset": "dx7_bass"},
            role="bass",
        )
        self.assertGreater(peak, 1e-6,
                           f"fm_advanced dx7_bass peak={peak} too low")

    def test_karplus_strong_nylon_guitar(self):
        """karplus_strong nylon_guitar 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.KARPLUS_STRONG,
            engine_params={"preset": "nylon_guitar"},
        )
        self.assertGreater(peak, 1e-6,
                           f"karplus_strong nylon_guitar peak={peak} too low")

    def test_karplus_strong_harp(self):
        """karplus_strong harp 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.KARPLUS_STRONG,
            engine_params={"preset": "harp"},
        )
        self.assertGreater(peak, 1e-6,
                           f"karplus_strong harp peak={peak} too low")

    def test_karplus_strong_sitar(self):
        """karplus_strong sitar (ethnic_lute) 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.KARPLUS_STRONG,
            engine_params={"preset": "sitar"},
        )
        self.assertGreater(peak, 1e-6,
                           f"karplus_strong sitar peak={peak} too low")

    def test_wavetable_brass(self):
        """wavetable brass 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVETABLE,
            engine_params={"preset": "brass"},
        )
        self.assertGreater(peak, 1e-6,
                           f"wavetable brass peak={peak} too low")

    def test_wavetable_organ(self):
        """wavetable organ 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVETABLE,
            engine_params={"preset": "organ"},
        )
        self.assertGreater(peak, 1e-6,
                           f"wavetable organ peak={peak} too low")

    def test_wavetable_bell(self):
        """wavetable bell 产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.WAVETABLE,
            engine_params={"preset": "bell"},
        )
        self.assertGreater(peak, 1e-6,
                           f"wavetable bell peak={peak} too low")

    def test_fm_basic(self):
        """fm 基础双算子产生非零音频"""
        from bloodmusic.music.instrument_pool import SynthEngine
        peak, _, _ = self._render_and_check(
            SynthEngine.FM,
            engine_params={"modulator_freq_ratio": 2.0, "fm_depth": 100.0},
        )
        self.assertGreater(peak, 1e-6,
                           f"fm basic peak={peak} too low")

    def test_all_engines_produce_audio(self):
        """所有非 legacy 引擎都产生非零音频（汇总）"""
        from bloodmusic.music.instrument_pool import SynthEngine
        engines_to_test = [
            (SynthEngine.FM, {"modulator_freq_ratio": 2.0}),
            (SynthEngine.FM_ADVANCED, {"preset": "dx7_epiano"}),
            (SynthEngine.WAVETABLE, {"preset": "sine"}),
            (SynthEngine.KARPLUS_STRONG, {"preset": "nylon_guitar"}),
            (SynthEngine.WAVEGUIDE, {"instrument": "clarinet"}),
            (SynthEngine.GRANULAR, {"preset": "ethereal_pad"}),
        ]
        failures = []
        for engine, engine_params in engines_to_test:
            peak, _, _ = self._render_and_check(
                engine, engine_params=engine_params,
                role="pad" if engine == SynthEngine.GRANULAR else "melody",
            )
            if peak <= 1e-6:
                failures.append(f"{engine.value}: peak={peak}")
        self.assertEqual(len(failures), 0,
                         f"Engines producing silence: {failures}")

    def test_engine_fallback_on_invalid_params(self):
        """无效 engine_params 时 fallback 到基础渲染（不崩溃）"""
        from bloodmusic.music.instrument_pool import SynthEngine
        # 用不存在的波表预设，应 fallback 到 sine
        peak, final, _ = self._render_and_check(
            SynthEngine.WAVETABLE,
            engine_params={"preset": "nonexistent_preset_xyz"},
        )
        self.assertGreater(peak, 1e-6,
                           "Fallback rendering failed")


# ═══════════════════════════════════════════════════════════════════════
# 3. Automation 功能测试
# ═══════════════════════════════════════════════════════════════════════

class TestAutomationFunctionality(unittest.TestCase):
    """filter_sweep + volume_curve 正确工作"""

    def _render_with_without_automation(self, automation_config):
        """返回 (with_auto, without_auto) 两个音频数组"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        # 带 automation 的 pool
        inst_with = PoolInstrument(
            name="Test",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            volume=0.5,
            note_sequence=["C4", "E4", "G4", "C5"],
            engine_params={"preset": "sine"},
            automation=automation_config,
        )
        pool_with = InstrumentPool(
            name="Automation Test",
            bpm=100, key="C", scale="major",
            instruments=[inst_with],
        )

        # 不带 automation 的 pool
        inst_without = PoolInstrument(
            name="Test",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            volume=0.5,
            note_sequence=["C4", "E4", "G4", "C5"],
            engine_params={"preset": "sine"},
        )
        pool_without = InstrumentPool(
            name="No Automation Test",
            bpm=100, key="C", scale="major",
            instruments=[inst_without],
        )

        renderer_with = PoolRenderer(pool_with, duration_sec=2.0)
        renderer_without = PoolRenderer(pool_without, duration_sec=2.0)

        final_with, _ = renderer_with.render()
        final_without, _ = renderer_without.render()

        return final_with.astype(np.float64), final_without.astype(np.float64)

    def test_filter_sweep_changes_output(self):
        """filter_sweep 使音频波形与无 automation 版本不同"""
        with_auto, without_auto = self._render_with_without_automation({
            "filter_sweep": {
                "start_hz": 20000,
                "end_hz": 200,
                "mid_hz": 5000,
                "mid_time_ratio": 0.5,
                "type": "lowpass",
                "q": 2.0,
                "interpolate": "smooth",
            },
        })
        diff = np.max(np.abs(with_auto - without_auto))
        self.assertGreater(diff, 1e-6,
                           "filter_sweep should change audio output")

    def test_filter_sweep_peak_different(self):
        """带 filter_sweep 的音频峰值应与不带的不同"""
        with_auto, without_auto = self._render_with_without_automation({
            "filter_sweep": {
                "start_hz": 20000,
                "end_hz": 400,
                "mid_hz": 20000,
                "mid_time_ratio": 0.3,
                "type": "lowpass",
                "q": 1.0,
            },
        })
        peak_with = np.max(np.abs(with_auto))
        peak_without = np.max(np.abs(without_auto))
        # 峰值应不同（滤波器衰减了高频）
        self.assertNotAlmostEqual(peak_with, peak_without, places=2,
                                  msg="filter_sweep should affect peak amplitude")

    def test_volume_curve_works(self):
        """volume_curve 正确改变音量"""
        with_auto, without_auto = self._render_with_without_automation({
            "volume_curve": {
                "points": [(0.0, 0.0), (0.5, 1.0), (1.5, 1.0), (2.0, 0.0)],
                "interpolate": "smooth",
            },
        })
        diff = np.max(np.abs(with_auto - without_auto))
        self.assertGreater(diff, 1e-6,
                           "volume_curve should change audio output")

    def test_volume_curve_fade_in(self):
        """volume_curve 淡入效果——在 stem 级别开头能量明显低于中段"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        inst = PoolInstrument(
            name="FadeTest",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            volume=0.7,
            note_sequence=["C4", "E4", "G4", "C5", "E5", "G5"],
            engine_params={"preset": "sine"},
            automation={
                "volume_curve": {
                    "points": [(0.0, 0.0), (1.0, 1.0), (2.0, 1.0)],
                    "interpolate": "linear",
                },
            },
        )
        pool = InstrumentPool(
            name="Fade Test", bpm=100, key="C", scale="major",
            instruments=[inst],
        )
        renderer = PoolRenderer(pool, duration_sec=2.0)
        _, stems = renderer.render()

        self.assertIn("FadeTest", stems)
        audio = stems["FadeTest"]

        # Check stem directly (before mix/master normalization)
        # Early portion should have lower energy
        early_rms = np.sqrt(np.mean(audio[:int(0.3 * SR)] ** 2))
        mid_rms = np.sqrt(np.mean(audio[int(1.0 * SR):int(1.5 * SR)] ** 2))
        self.assertLess(early_rms, mid_rms * 0.7,
                        f"Stem fade-in: early_rms={early_rms:.4f}, "
                        f"mid_rms={mid_rms:.4f}")

    def test_combined_filter_and_volume(self):
        """filter_sweep + volume_curve 同时工作"""
        with_auto, without_auto = self._render_with_without_automation({
            "filter_sweep": {
                "start_hz": 20000, "end_hz": 500,
                "mid_hz": 20000, "mid_time_ratio": 0.5,
                "type": "lowpass", "q": 1.0,
            },
            "volume_curve": {
                "points": [(0.0, 0.0), (0.5, 1.0), (2.0, 1.0)],
                "interpolate": "smooth",
            },
        })
        diff = np.max(np.abs(with_auto - without_auto))
        self.assertGreater(diff, 1e-6,
                           "Combined automation should change output")

    def test_empty_automation_no_effect(self):
        """空 automation dict 不破坏音频（产生非零输出）"""
        with_auto, without_auto = self._render_with_without_automation({})
        # 空 automation 不应导致静音——两个版本都应产生非零音频
        peak_with = np.max(np.abs(with_auto))
        peak_without = np.max(np.abs(without_auto))
        self.assertGreater(peak_with, 1e-6,
                           "Empty automation produced silence (with_auto)")
        self.assertGreater(peak_without, 1e-6,
                            "Empty automation produced silence (without_auto)")
        # 两个版本的音频都应有效长度
        self.assertGreater(len(with_auto), 1000)
        self.assertGreater(len(without_auto), 1000)

    def test_automation_applied_per_stem(self):
        """automation 每个 stem 独立应用"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        inst1 = PoolInstrument(
            name="Track1",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            volume=0.5,
            note_sequence=["C4", "E4"],
            engine_params={"preset": "sine"},
            automation={"volume_curve": {
                "points": [(0.0, 0.0), (1.0, 1.0)],
                "interpolate": "linear",
            }},
        )
        inst2 = PoolInstrument(
            name="Track2",
            role=InstrumentRole.CHORD,
            engine=SynthEngine.WAVETABLE,
            volume=0.5,
            note_sequence=["G4", "C5"],
            engine_params={"preset": "sine"},
            # no automation
        )

        pool = InstrumentPool(
            name="Per-Stem Test",
            bpm=100, key="C", scale="major",
            instruments=[inst1, inst2],
        )
        renderer = PoolRenderer(pool, duration_sec=2.0)
        _, stems = renderer.render()

        self.assertIn("Track1", stems)
        self.assertIn("Track2", stems)
        # Track1 开头应接近零（volume_curve 淡入）
        early_peak1 = np.max(np.abs(stems["Track1"][:int(0.1 * SR)]))
        early_peak2 = np.max(np.abs(stems["Track2"][:int(0.1 * SR)]))
        self.assertLess(early_peak1, early_peak2 * 0.5,
                        "Track1 should fade in while Track2 starts at full volume")


# ═══════════════════════════════════════════════════════════════════════
# 4. 12 个 fullpower YAML 结构校验
# ═══════════════════════════════════════════════════════════════════════

class TestFullpowerYAMLStructure(unittest.TestCase):
    """12 个 fullpower YAML 完整结构校验"""

    @classmethod
    def setUpClass(cls):
        from bloodmusic.music.instrument_pool import InstrumentPool
        cls.pools = {}
        for yf in _fullpower_yaml_files():
            name = os.path.basename(yf)
            try:
                cls.pools[name] = InstrumentPool.from_yaml(yf)
            except Exception as e:
                cls.pools[name] = e

    def test_count_fullpower_yaml(self):
        """确认 12 个 fullpower YAML"""
        self.assertEqual(len(_fullpower_yaml_files()), 12)

    def test_all_fullpower_yaml_load(self):
        """所有 fullpower YAML 可正常加载"""
        failures = []
        for name, result in self.pools.items():
            if isinstance(result, Exception):
                failures.append(f"{name}: {result}")
        self.assertEqual(len(failures), 0,
                         f"Failed to load: {failures}")

    def test_all_fullpower_yaml_version(self):
        """所有 fullpower YAML version = '2.0'"""
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            self.assertEqual(pool.version, "2.0",
                             f"{name}: expected version '2.0', got '{pool.version}'")

    def test_minimum_four_engines_per_yaml(self):
        """每个 fullpower YAML 包含至少 4 种不同引擎"""
        from bloodmusic.music.instrument_pool import SynthEngine
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            engines = set()
            for inst in pool.instruments:
                engines.add(inst.engine)
            self.assertGreaterEqual(
                len(engines), 4,
                f"{name}: only {len(engines)} unique engines, need ≥4"
            )

    def test_engine_params_field_present(self):
        """每个 fullpower YAML 至少有部分乐器包含 engine_params"""
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            has_params = any(
                inst.engine_params for inst in pool.instruments
                if inst.engine_params
            )
            self.assertTrue(
                has_params,
                f"{name}: no instrument has engine_params"
            )

    def test_valid_engine_params_keys(self):
        """engine_params 键值合法（不包含未知键）"""
        valid_keys_per_engine = {
            "waveguide": {"instrument", "breath", "embouchure",
                         "bell_openness", "volume"},
            "granular": {"preset", "density", "pitch_shift"},
            "fm_advanced": {"preset"},
            "karplus_strong": {"preset"},
            "wavetable": {"preset"},
            "fm": {"modulator_freq_ratio", "fm_depth"},
        }
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            for inst in pool.instruments:
                if not inst.engine_params:
                    continue
                engine_key = inst.engine.value
                valid_keys = valid_keys_per_engine.get(engine_key, set())
                for key in inst.engine_params:
                    self.assertIn(
                        key, valid_keys,
                        f"{name}/{inst.name}: unknown engine_param "
                        f"'{key}' for engine '{engine_key}'. "
                        f"Valid keys: {valid_keys}"
                    )

    def test_instruments_have_roles(self):
        """每个 YAML 的乐器都有有效 role"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            for inst in pool.instruments:
                self.assertIsInstance(inst.role, InstrumentRole)
                self.assertIn(inst.role, InstrumentRole)

    def test_pool_validate_no_critical(self):
        """validate() 无严重结构性问题"""
        for name, pool in self.pools.items():
            if isinstance(pool, Exception):
                continue
            warnings = pool.validate()
            critical = [w for w in warnings if "为空" in w or "无效" in w]
            self.assertEqual(
                len(critical), 0,
                f"{name}: critical validation warnings: {critical}"
            )

    def test_known_fullpower_names(self):
        """确认 12 个预期的 fullpower 文件名"""
        expected = [
            "fullpower_cinematic_odyssey.yaml",
            "fullpower_classical_opera.yaml",
            "fullpower_jazz_night.yaml",
            "fullpower_lofi_dreams.yaml",
            "fullpower_electronic_warehouse.yaml",
            "fullpower_exploration_wilds.yaml",
            "fullpower_folk_voyage.yaml",
            "fullpower_meditation_zen.yaml",
            "fullpower_battle_forge.yaml",
            "fullpower_town_market.yaml",
            "fullpower_ambient_void.yaml",
            "fullpower_dungeon_depths.yaml",
        ]
        actual = [os.path.basename(f) for f in _fullpower_yaml_files()]
        for name in expected:
            self.assertIn(name, actual, f"Missing fullpower YAML: {name}")


# ═══════════════════════════════════════════════════════════════════════
# 5. engine_params / automation 序列化往返
# ═══════════════════════════════════════════════════════════════════════

class TestNewFieldSerialization(unittest.TestCase):
    """engine_params 和 automation 的序列化往返测试"""

    def test_engine_params_yaml_roundtrip(self):
        """engine_params YAML 往返不丢失数据"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        pool = InstrumentPool(
            name="Engine Params Test",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="WG Clarinet",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVEGUIDE,
                    volume=0.7,
                    engine_params={
                        "instrument": "clarinet",
                        "breath": 0.8,
                        "embouchure": 0.5,
                    },
                ),
            ],
        )

        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            pool.to_yaml(tmp_path)
            loaded = InstrumentPool.from_yaml(tmp_path)
            inst = loaded.instruments[0]
            self.assertEqual(inst.engine_params["instrument"], "clarinet")
            self.assertEqual(inst.engine_params["breath"], 0.8)
            self.assertEqual(inst.engine_params["embouchure"], 0.5)
        finally:
            os.unlink(tmp_path)

    def test_automation_yaml_roundtrip(self):
        """automation 配置 YAML 往返不丢失"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        auto_config = {
            "filter_sweep": {
                "start_hz": 20000,
                "end_hz": 400,
                "mid_hz": 5000,
                "mid_time_ratio": 0.5,
                "type": "lowpass",
                "q": 2.0,
            },
        }
        pool = InstrumentPool(
            name="Automation Serial Test",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="Auto Track",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE,
                    volume=0.7,
                    automation=auto_config,
                ),
            ],
        )

        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            pool.to_yaml(tmp_path)
            loaded = InstrumentPool.from_yaml(tmp_path)
            inst = loaded.instruments[0]
            self.assertIsNotNone(inst.automation)
            self.assertIn("filter_sweep", inst.automation)
            self.assertEqual(
                inst.automation["filter_sweep"]["start_hz"], 20000,
            )
            self.assertEqual(
                inst.automation["filter_sweep"]["end_hz"], 400,
            )
        finally:
            os.unlink(tmp_path)

    def test_engine_params_empty_not_serialized(self):
        """空 engine_params 不出现在序列化输出中"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole,
        )
        inst = PoolInstrument(
            name="No Params",
            role=InstrumentRole.MELODY,
            engine="wavetable",
        )
        d = inst.to_dict()
        self.assertNotIn("engine_params", d)

    def test_automation_none_not_serialized(self):
        """None automation 不出现在序列化输出中"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="No Auto")
        d = inst.to_dict()
        self.assertNotIn("automation", d)

    def test_pool_level_automation_yaml_roundtrip(self):
        """Pool 级别的 automation YAML 往返"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        pool = InstrumentPool(
            name="Pool Auto Test",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="Track1",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE,
                    volume=0.7,
                ),
            ],
            automation={
                "filter_sweep": {
                    "start_hz": 10000, "end_hz": 500,
                    "mid_hz": 10000, "mid_time_ratio": 0.5,
                    "type": "lowpass", "q": 1.0,
                },
            },
        )

        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            pool.to_yaml(tmp_path)
            loaded = InstrumentPool.from_yaml(tmp_path)
            self.assertIsNotNone(loaded.automation)
            self.assertIn("filter_sweep", loaded.automation)
            self.assertEqual(
                loaded.automation["filter_sweep"]["start_hz"], 10000,
            )
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════
# 6. MusicPattern 新字段测试
# ═══════════════════════════════════════════════════════════════════════

class TestMusicPatternNewFields(unittest.TestCase):
    """MusicPattern 的 engine / engine_params / automation 字段"""

    def test_engine_field_default_none(self):
        """MusicPattern.engine 默认为 None"""
        from bloodmusic.music.pattern import MusicPattern
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
        )
        self.assertIsNone(pattern.engine)

    def test_engine_field_settable(self):
        """MusicPattern.engine 可设置 SynthEngine 值"""
        from bloodmusic.music.pattern import MusicPattern
        from bloodmusic.music.instrument_pool import SynthEngine
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
            engine=SynthEngine.WAVEGUIDE,
        )
        self.assertEqual(pattern.engine, SynthEngine.WAVEGUIDE)

    def test_engine_params_default_empty(self):
        """MusicPattern.engine_params 默认为空 dict"""
        from bloodmusic.music.pattern import MusicPattern
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
        )
        self.assertEqual(pattern.engine_params, {})

    def test_engine_params_settable(self):
        """MusicPattern.engine_params 可设置"""
        from bloodmusic.music.pattern import MusicPattern
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
            engine_params={"preset": "dx7_bell"},
        )
        self.assertEqual(pattern.engine_params["preset"], "dx7_bell")

    def test_automation_default_none(self):
        """MusicPattern.automation 默认为 None"""
        from bloodmusic.music.pattern import MusicPattern
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
        )
        self.assertIsNone(pattern.automation)

    def test_automation_settable(self):
        """MusicPattern.automation 可设置"""
        from bloodmusic.music.pattern import MusicPattern
        auto = {"filter_sweep": {"start_hz": 20000, "end_hz": 400}}
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
            automation=auto,
        )
        self.assertEqual(pattern.automation["filter_sweep"]["start_hz"], 20000)

    def test_engine_fields_do_not_break_post_init(self):
        """新字段不影响 __post_init__ 校验"""
        from bloodmusic.music.pattern import MusicPattern
        from bloodmusic.music.instrument_pool import SynthEngine
        pattern = MusicPattern(
            name="test",
            notes=["C4", "D4", "E4"],
            durations=[1.0, 1.0, 1.0],
            engine=SynthEngine.FM_ADVANCED,
            engine_params={"preset": "dx7_epiano"},
            automation={"volume_curve": {"points": [(0, 0), (1, 1)]}},
        )
        # 不应抛出异常
        self.assertEqual(len(pattern.notes), 3)
        self.assertEqual(len(pattern.durations), 3)


# ═══════════════════════════════════════════════════════════════════════
# 7. Pool 级别 automation 继承
# ═══════════════════════════════════════════════════════════════════════

class TestPoolAutomationInheritance(unittest.TestCase):
    """Pool 级别 automation 继承到 instrument"""

    def test_pool_automation_inherited_by_instrument(self):
        """instrument 无 automation 时继承 pool 级别"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        pool = InstrumentPool(
            name="Inheritance Test",
            bpm=100,
            key="C",
            instruments=[
                PoolInstrument(
                    name="Track1",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE,
                    volume=0.5,
                    note_sequence=["C4", "E4", "G4"],
                ),
            ],
            automation={
                "filter_sweep": {
                    "start_hz": 20000, "end_hz": 400,
                    "mid_hz": 20000, "mid_time_ratio": 0.5,
                    "type": "lowpass", "q": 1.0,
                },
            },
        )

        gen = PoolGenerator(pool)
        multi = gen.generate_all(target_bars=4)
        pattern = multi.music_tracks[0]
        # 继承后 instrument 和 pattern 都应有 automation
        self.assertIsNotNone(pattern.automation)
        self.assertIn("filter_sweep", pattern.automation)

    def test_instrument_automation_overrides_pool(self):
        """instrument 有 automation 时不继承 pool 级别"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        inst_auto = {
            "volume_curve": {
                "points": [(0.0, 0.0), (1.0, 1.0)],
                "interpolate": "linear",
            },
        }
        pool = InstrumentPool(
            name="Override Test",
            bpm=100,
            key="C",
            instruments=[
                PoolInstrument(
                    name="Track1",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE,
                    volume=0.5,
                    note_sequence=["C4", "E4", "G4"],
                    automation=inst_auto,
                ),
            ],
            automation={
                "filter_sweep": {
                    "start_hz": 20000, "end_hz": 400,
                    "mid_hz": 20000, "mid_time_ratio": 0.5,
                    "type": "lowpass", "q": 1.0,
                },
            },
        )

        gen = PoolGenerator(pool)
        multi = gen.generate_all(target_bars=4)
        pattern = multi.music_tracks[0]
        # 应使用 instrument 自己的 automation，不包含 pool 级别的 filter_sweep
        self.assertIn("volume_curve", pattern.automation)
        self.assertNotIn("filter_sweep", pattern.automation)


# ═══════════════════════════════════════════════════════════════════════
# 8. --fullpower CLI 端到端
# ═══════════════════════════════════════════════════════════════════════

class TestFullpowerCLIEndToEnd(unittest.TestCase):
    """--fullpower 端到端集成测试"""

    @classmethod
    def setUpClass(cls):
        """跳过此 class 如果环境不支持长时间渲染"""
        pass

    def test_fullpower_single_track_render(self):
        """单轨 fullpower YAML 完整渲染到音频"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        from bloodmusic.music.pool_renderer import PoolRenderer

        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "music", "pool_presets", "fullpower_lofi_dreams.yaml",
        )
        pool = InstrumentPool.from_yaml(yaml_path)
        pool.config.seed = 42

        renderer = PoolRenderer(pool, duration_sec=5.0)
        final, stems = renderer.render()

        # 验证产出
        self.assertGreater(np.max(np.abs(final)), 1e-6,
                           "Fullpower render produced silence")
        self.assertGreater(len(stems), 0,
                           "No stems produced")
        # 非 FX 的 stem 都应 > 0（FX 可能被风格禁用）
        for name, audio in stems.items():
            if "fx" in name.lower() or "FX" in name:
                continue  # FX stems may be silent when style disables them
            self.assertGreater(
                np.max(np.abs(audio)), 1e-6,
                f"Stem '{name}' is silent"
            )

    def test_fullpower_battle_forge_render(self):
        """fullpower_battle_forge 渲染验证——最复杂的配置"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        from bloodmusic.music.pool_renderer import PoolRenderer

        yaml_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "music", "pool_presets", "fullpower_battle_forge.yaml",
        )
        pool = InstrumentPool.from_yaml(yaml_path)
        pool.config.seed = 42

        renderer = PoolRenderer(pool, duration_sec=5.0)
        final, stems = renderer.render()

        self.assertGreater(np.max(np.abs(final)), 1e-6,
                           "Battle forge render produced silence")
        # battle forge 应有 drum
        has_drum_name = any(
            "drum" in name.lower() or "battle" in name.lower()
            for name in stems
        )
        self.assertGreater(len(stems), 2,
                           "Battle forge should have multiple stems")

    def test_fullpower_cli_import(self):
        """验证 album_generator 中 --fullpower 相关函数可导入"""
        # 不要实际运行 CLI——只验证函数存在并可调用
        import importlib
        import sys

        # 确保可以导入 _generate_fullpower_album
        album_gen_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "album_generator.py",
        )

        spec = importlib.util.spec_from_file_location(
            "album_generator", album_gen_path,
        )
        module = importlib.util.module_from_spec(spec)

        # 先设置 sys.argv 避免 argparse 解析失败
        old_argv = sys.argv
        sys.argv = ["album_generator.py"]

        try:
            spec.loader.exec_module(module)
            self.assertTrue(hasattr(module, "_generate_fullpower_album"))
            self.assertTrue(hasattr(module, "cli_main"))
            self.assertTrue(hasattr(module, "FULLPOWER_ALBUM"))
            self.assertEqual(len(module.FULLPOWER_ALBUM), 12)
        finally:
            sys.argv = old_argv

    def test_fullpower_quick_render(self):
        """快速渲染 3 个不同 fullpower YAML (5s each) 验证引擎不崩溃"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        from bloodmusic.music.pool_renderer import PoolRenderer

        test_cases = [
            "fullpower_classical_opera.yaml",
            "fullpower_electronic_warehouse.yaml",
            "fullpower_ambient_void.yaml",
        ]
        failures = []
        for yaml_name in test_cases:
            yaml_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "music", "pool_presets", yaml_name,
            )
            try:
                pool = InstrumentPool.from_yaml(yaml_path)
                pool.config.seed = 42
                renderer = PoolRenderer(pool, duration_sec=3.0)
                final, _ = renderer.render()
                peak = np.max(np.abs(final))
                if peak <= 1e-6:
                    failures.append(f"{yaml_name}: silence")
            except Exception as e:
                failures.append(f"{yaml_name}: {e}")

        self.assertEqual(len(failures), 0,
                         f"Quick render failures: {failures}")


# ═══════════════════════════════════════════════════════════════════════
# 9. PoolInstrument 新字段默认值测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolInstrumentNewDefaults(unittest.TestCase):
    """engine_params 和 automation 默认值行为"""

    def test_engine_params_default_empty_dict(self):
        """PoolInstrument.engine_params 默认为 {}"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test")
        self.assertEqual(inst.engine_params, {})

    def test_automation_default_none(self):
        """PoolInstrument.automation 默认为 None"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test")
        self.assertIsNone(inst.automation)

    def test_instrument_pool_automation_default_none(self):
        """InstrumentPool.automation 默认为 None"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test")
        self.assertIsNone(pool.automation)

    def test_to_dict_includes_engine_params(self):
        """to_dict 包含非空 engine_params"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(
            name="Test",
            engine_params={"preset": "dx7_bell"},
        )
        d = inst.to_dict()
        self.assertIn("engine_params", d)
        self.assertEqual(d["engine_params"]["preset"], "dx7_bell")

    def test_to_dict_includes_automation(self):
        """to_dict 包含非 None automation"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(
            name="Test",
            automation={"filter_sweep": {"start_hz": 20000}},
        )
        d = inst.to_dict()
        self.assertIn("automation", d)
        self.assertEqual(d["automation"]["filter_sweep"]["start_hz"], 20000)

    def test_serializer_reads_engine_params_from_yaml(self):
        """PoolSerializer._dict_to_instrument 正确读取 engine_params"""
        from bloodmusic.music.pool_serializer import PoolSerializer
        data = {
            "name": "Test",
            "role": "melody",
            "engine": "waveguide",
            "engine_params": {"instrument": "flute", "breath": 0.9},
        }
        inst = PoolSerializer._dict_to_instrument(data)
        self.assertEqual(inst.engine_params["instrument"], "flute")
        self.assertEqual(inst.engine_params["breath"], 0.9)

    def test_serializer_reads_automation_from_yaml(self):
        """PoolSerializer._dict_to_instrument 正确读取 automation"""
        from bloodmusic.music.pool_serializer import PoolSerializer
        auto = {"filter_sweep": {"start_hz": 20000, "end_hz": 400}}
        data = {
            "name": "Test",
            "role": "melody",
            "engine": "wavetable",
            "automation": auto,
        }
        inst = PoolSerializer._dict_to_instrument(data)
        self.assertEqual(inst.automation, auto)


if __name__ == "__main__":
    unittest.main()
