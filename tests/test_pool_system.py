"""乐器池系统补充测试 —— 覆盖缺口 + 回归验证

覆盖范围:
  1. 枚举边界测试 (InstrumentRole, SynthEngine)
  2. PoolInstrument 边界情况
  3. PoolConfig 边界情况
  4. InstrumentPool 完整校验 + 工厂方法
  5. PoolSerializer 错误路径
  6. PoolTemplate 边界情况
  7. StylePreset 边界 + 覆盖行为
  8. PoolGenerator 角色生成 + humanize + seed
  9. PoolRenderer 边界
 10. MusicPattern.pool_role 回归
 11. CLI pool 子命令冒烟测试
 12. 模块导出验证
"""

import os
import sys
import tempfile
import unittest

import numpy as np

from bloodmusic.core.constants import SR
from bloodmusic.music.pattern import MusicPattern


# ═══════════════════════════════════════════════════════════════════════
# 1. 枚举边界测试
# ═══════════════════════════════════════════════════════════════════════

class TestInstrumentRoleEnum(unittest.TestCase):
    """InstrumentRole 枚举完整测试"""

    def test_all_roles_exist(self):
        """应包含 6 种角色"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        self.assertEqual(len(InstrumentRole), 6)

    def test_from_string_case_insensitive(self):
        """from_string 大小写不敏感"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        self.assertEqual(
            InstrumentRole.from_string("MELODY"),
            InstrumentRole.MELODY,
        )
        self.assertEqual(
            InstrumentRole.from_string("Melody"),
            InstrumentRole.MELODY,
        )
        self.assertEqual(
            InstrumentRole.from_string("  melody  "),
            InstrumentRole.MELODY,
        )

    def test_from_string_all_roles(self):
        """所有 6 种角色均支持 from_string"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        valid_values = ["melody", "chord", "bass", "drum", "pad", "fx"]
        for v in valid_values:
            role = InstrumentRole.from_string(v)
            self.assertEqual(role.value, v)

    def test_from_string_invalid_raises(self):
        """无效角色字符串应抛出 ValueError"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        with self.assertRaises(ValueError) as ctx:
            InstrumentRole.from_string("nonexistent_role")
        self.assertIn("未知的乐器角色", str(ctx.exception))

    def test_str_method(self):
        """__str__ 返回 value 字符串"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        self.assertEqual(str(InstrumentRole.MELODY), "melody")
        self.assertEqual(str(InstrumentRole.DRUM), "drum")


class TestSynthEngineEnum(unittest.TestCase):
    """SynthEngine 枚举完整测试"""

    def test_all_engines_exist(self):
        """应包含 12 种合成引擎（含 SPECTRUM 新并入的 ADDITIVE/MODAL/HYBRID/MATERIAL）"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(len(SynthEngine), 12)
    def test_from_string_case_insensitive(self):
        """from_string 大小写不敏感"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(
            SynthEngine.from_string("WAVETABLE"),
            SynthEngine.WAVETABLE,
        )
        self.assertEqual(
            SynthEngine.from_string("  fm_advanced  "),
            SynthEngine.FM_ADVANCED,
        )

    def test_from_string_all_engines(self):
        """所有引擎均支持 from_string"""
        from bloodmusic.music.instrument_pool import SynthEngine
        valid_values = [
            "subtractive", "fm", "fm_advanced", "karplus_strong",
            "granular", "wavetable", "waveguide", "noise",
        ]
        for v in valid_values:
            engine = SynthEngine.from_string(v)
            self.assertEqual(engine.value, v)

    def test_from_string_invalid_raises(self):
        """无效引擎字符串应抛出 ValueError"""
        from bloodmusic.music.instrument_pool import SynthEngine
        with self.assertRaises(ValueError) as ctx:
            SynthEngine.from_string("invalid_engine")
        self.assertIn("未知的合成引擎", str(ctx.exception))

    def test_str_method(self):
        """__str__ 返回 value 字符串"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(str(SynthEngine.FM), "fm")
        self.assertEqual(str(SynthEngine.GRANULAR), "granular")


class TestDefaultEngineMap(unittest.TestCase):
    """DEFAULT_ENGINE_MAP 和 get_default_engine 测试"""

    def test_all_roles_have_default_engine(self):
        """所有 6 种角色都有默认引擎"""
        from bloodmusic.music.instrument_pool import (
            DEFAULT_ENGINE_MAP, InstrumentRole, SynthEngine,
        )
        for role in InstrumentRole:
            self.assertIn(role, DEFAULT_ENGINE_MAP)
            self.assertIsInstance(DEFAULT_ENGINE_MAP[role], SynthEngine)

    def test_get_default_engine_known_roles(self):
        """已知角色返回正确引擎"""
        from bloodmusic.music.instrument_pool import (
            get_default_engine, InstrumentRole, SynthEngine,
        )
        self.assertEqual(
            get_default_engine(InstrumentRole.MELODY), SynthEngine.WAVETABLE,
        )
        self.assertEqual(
            get_default_engine(InstrumentRole.DRUM), SynthEngine.NOISE,
        )
        self.assertEqual(
            get_default_engine(InstrumentRole.BASS), SynthEngine.SUBTRACTIVE,
        )


# ═══════════════════════════════════════════════════════════════════════
# 2. PoolInstrument 边界测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolInstrumentEdgeCases(unittest.TestCase):
    """PoolInstrument 边界情况"""

    def test_volume_clamping_high(self):
        """volume > 2.0 应被钳制到 2.0"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", volume=5.0)
        self.assertEqual(inst.volume, 2.0)

    def test_volume_clamping_negative(self):
        """volume < 0.0 应被钳制到 0.0"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", volume=-1.0)
        self.assertEqual(inst.volume, 0.0)

    def test_volume_in_range_no_clamping(self):
        """正常 volume 不被修改"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", volume=1.5)
        self.assertEqual(inst.volume, 1.5)

    def test_pan_clamping_high(self):
        """pan > 1.0 应被钳制到 1.0"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", pan=3.0)
        self.assertEqual(inst.pan, 1.0)

    def test_pan_clamping_low(self):
        """pan < -1.0 应被钳制到 -1.0"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", pan=-5.0)
        self.assertEqual(inst.pan, -1.0)

    def test_string_role_auto_conversion(self):
        """字符串 role 自动转换为枚举"""
        from bloodmusic.music.instrument_pool import (
            PoolInstrument, InstrumentRole, SynthEngine,
        )
        inst = PoolInstrument(name="Test", role="bass")
        self.assertIsInstance(inst.role, InstrumentRole)
        self.assertEqual(inst.role, InstrumentRole.BASS)

    def test_string_engine_auto_conversion(self):
        """字符串 engine 自动转换为枚举"""
        from bloodmusic.music.instrument_pool import (
            PoolInstrument, SynthEngine,
        )
        inst = PoolInstrument(name="Test", engine="fm")
        self.assertIsInstance(inst.engine, SynthEngine)
        self.assertEqual(inst.engine, SynthEngine.FM)

    def test_to_dict_basic(self):
        """to_dict 返回正确的基本字段"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(
            name="Test", role="melody", engine="wavetable",
            volume=0.8, pan=0.2,
        )
        d = inst.to_dict()
        self.assertEqual(d["name"], "Test")
        self.assertEqual(d["role"], "melody")
        self.assertEqual(d["engine"], "wavetable")
        self.assertEqual(d["volume"], 0.8)
        self.assertEqual(d["pan"], 0.2)

    def test_to_dict_with_preset(self):
        """to_dict 包含 preset 字段（非 None 时）"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(
            name="Test", preset="acoustic_grand_piano",
        )
        d = inst.to_dict()
        self.assertEqual(d["preset"], "acoustic_grand_piano")

    def test_to_dict_without_preset(self):
        """to_dict 不包含 None preset 字段"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", preset=None)
        d = inst.to_dict()
        self.assertNotIn("preset", d)

    def test_to_dict_with_params(self):
        """to_dict 包含非空 params"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", params={"attack": 0.1})
        d = inst.to_dict()
        self.assertEqual(d["params"], {"attack": 0.1})

    def test_to_dict_without_params(self):
        """to_dict 不包含空 params"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", params={})
        d = inst.to_dict()
        self.assertNotIn("params", d)

    def test_to_dict_with_note_sequence(self):
        """to_dict 包含 note_sequence"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", note_sequence=["C4", "E4"])
        d = inst.to_dict()
        self.assertEqual(d["note_sequence"], ["C4", "E4"])

    def test_to_dict_with_octave(self):
        """to_dict 包含 octave 字段（非 None 时）"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", octave=-1)
        d = inst.to_dict()
        self.assertEqual(d["octave"], -1)

    def test_validate_empty_name(self):
        """空名称应产生警告"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="   ")
        warnings = inst.validate()
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any("name" in w.lower() for w in warnings))

    def test_validate_zero_volume(self):
        """volume=0 应产生静音警告"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="Test", volume=0.0)
        warnings = inst.validate()
        self.assertTrue(any("静音" in w for w in warnings))

    def test_validate_drum_with_note_sequence(self):
        """drum 角色 + note_sequence 应产生警告"""
        from bloodmusic.music.instrument_pool import (
            PoolInstrument, InstrumentRole,
        )
        inst = PoolInstrument(
            name="Drums", role=InstrumentRole.DRUM,
            note_sequence=["C4"],
        )
        warnings = inst.validate()
        self.assertTrue(
            any("drum" in w.lower() and "note_sequence" in w.lower()
                for w in warnings),
            f"Expected drum+note_sequence warning, got: {warnings}",
        )


# ═══════════════════════════════════════════════════════════════════════
# 3. PoolConfig 边界测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolConfigEdgeCases(unittest.TestCase):
    """PoolConfig 边界情况"""

    def test_diversity_clamping_high(self):
        """diversity > 1.0 应被钳制"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(diversity=5.0)
        self.assertEqual(config.diversity, 1.0)

    def test_diversity_clamping_low(self):
        """diversity < 0.0 应被钳制"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(diversity=-1.0)
        self.assertEqual(config.diversity, 0.0)

    def test_section_mismatch_warning(self):
        """sections 和 section_bars 数量不匹配应产生警告"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(
            sections=["intro", "verse", "chorus"],
            section_bars=[4, 8],
        )
        warnings = config.validate()
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any("不匹配" in w for w in warnings))

    def test_section_match_no_warning(self):
        """sections 和 section_bars 匹配时无警告"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(
            sections=["intro", "verse"],
            section_bars=[4, 8],
        )
        warnings = config.validate()
        self.assertEqual(len(warnings), 0)

    def test_empty_sections_no_warning(self):
        """空 sections 无 section_bars 不触发警告"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(sections=[], section_bars=[])
        warnings = config.validate()
        self.assertEqual(len(warnings), 0)

    def test_to_dict_basic(self):
        """to_dict 基本字段"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig(diversity=0.5, humanize=False, seed=42)
        d = config.to_dict()
        self.assertEqual(d["diversity"], 0.5)
        self.assertEqual(d["humanize"], False)
        self.assertEqual(d["seed"], 42)

    def test_to_dict_omits_empty_defaults(self):
        """to_dict 不包含空的默认字段"""
        from bloodmusic.music.instrument_pool import PoolConfig
        config = PoolConfig()
        d = config.to_dict()
        self.assertNotIn("sections", d)
        self.assertNotIn("section_bars", d)
        self.assertNotIn("seed", d)


# ═══════════════════════════════════════════════════════════════════════
# 4. InstrumentPool 完整校验 + 工厂方法
# ═══════════════════════════════════════════════════════════════════════

class TestInstrumentPoolComplete(unittest.TestCase):
    """InstrumentPool 完整验证"""

    def setUp(self):
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        self.valid_pool = InstrumentPool(
            name="Full Band",
            bpm=120,
            key="C",
            scale="major",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.8,
                ),
                PoolInstrument(
                    name="Chords", role=InstrumentRole.CHORD,
                    engine=SynthEngine.FM_ADVANCED, volume=0.6,
                ),
                PoolInstrument(
                    name="Bass", role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE, volume=0.9,
                ),
                PoolInstrument(
                    name="Drums", role=InstrumentRole.DRUM,
                    engine=SynthEngine.NOISE, volume=0.7,
                ),
            ],
        )

    def test_validate_full_band(self):
        """完整 band 配置校验应通过或仅有轻微警告"""
        warnings = self.valid_pool.validate()
        # 全乐队应有 drum 和 bass，无结构性警告
        structural = [
            w for w in warnings
            if "drum" in w.lower() or "bass" in w.lower()
        ]
        self.assertEqual(len(structural), 0)

    def test_validate_missing_drum(self):
        """缺少 drum 应产生警告"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole,
        )
        pool = InstrumentPool(name="No Drums", instruments=[
            PoolInstrument("Melody", role=InstrumentRole.MELODY),
        ])
        warnings = pool.validate()
        self.assertTrue(any("drum" in w.lower() for w in warnings))

    def test_validate_missing_bass(self):
        """缺少 bass 应产生警告"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole,
        )
        pool = InstrumentPool(name="No Bass", instruments=[
            PoolInstrument("Melody", role=InstrumentRole.MELODY),
            PoolInstrument("Drums", role=InstrumentRole.DRUM),
        ])
        warnings = pool.validate()
        self.assertTrue(any("bass" in w.lower() for w in warnings))

    def test_validate_empty_name(self):
        """空名称应产生警告"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="   ")
        warnings = pool.validate()
        self.assertTrue(any("name" in w.lower() for w in warnings))

    def test_validate_invalid_bpm(self):
        """无效 bpm 应产生警告"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test", bpm=0)
        warnings = pool.validate()
        self.assertTrue(any("bpm" in w.lower() for w in warnings))

    def test_validate_high_global_volume(self):
        """global_volume > 1.0 应产生削波警告"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test", global_volume=2.0)
        warnings = pool.validate()
        self.assertTrue(any("削波" in w for w in warnings))

    def test_validate_zero_global_volume(self):
        """global_volume = 0 应产生静音警告"""
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test", global_volume=0.0)
        warnings = pool.validate()
        self.assertTrue(any("静音" in w for w in warnings))

    def test_has_role_positive(self):
        """has_role 对存在的角色返回 True"""
        self.assertTrue(
            self.valid_pool.has_role(
                self.valid_pool.instruments[0].role,
            )
        )

    def test_has_role_negative(self):
        """has_role 对缺失的角色返回 False"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        self.assertFalse(self.valid_pool.has_role(InstrumentRole.PAD))

    def test_get_by_role_string(self):
        """get_by_role 支持字符串参数"""
        melodies = self.valid_pool.get_by_role("melody")
        self.assertEqual(len(melodies), 1)
        self.assertEqual(melodies[0].name, "Melody")

    def test_repr_format(self):
        """__repr__ 包含关键信息"""
        r = repr(self.valid_pool)
        self.assertIn("InstrumentPool", r)
        self.assertIn("Full Band", r)
        self.assertIn("bpm=120", r)

    def test_to_dict_structure(self):
        """to_dict 返回正确的顶层键"""
        d = self.valid_pool.to_dict()
        expected_keys = [
            "name", "version", "bpm", "key", "scale",
            "global_volume", "instruments", "generation",
        ]
        for key in expected_keys:
            self.assertIn(key, d, f"Missing key: {key}")


class TestInstrumentPoolFactoryMethods(unittest.TestCase):
    """InstrumentPool 工厂方法测试"""

    def setUp(self):
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        self.pool = InstrumentPool(
            name="Factory Test",
            bpm=100,
            key="D",
            instruments=[
                PoolInstrument(
                    name="Lead", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.8,
                ),
                PoolInstrument(
                    name="Drums", role=InstrumentRole.DRUM,
                    engine=SynthEngine.NOISE, volume=0.7,
                ),
            ],
        )

    def test_yaml_factory_roundtrip(self):
        """from_yaml 工厂方法完整往返"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            self.pool.to_yaml(tmp_path)
            from bloodmusic.music.instrument_pool import InstrumentPool
            loaded = InstrumentPool.from_yaml(tmp_path)
            self.assertEqual(loaded.name, "Factory Test")
            self.assertEqual(loaded.bpm, 100)
            self.assertEqual(loaded.key, "D")
            self.assertEqual(len(loaded.instruments), 2)
        finally:
            os.unlink(tmp_path)

    def test_json_factory_roundtrip(self):
        """from_json 工厂方法完整往返"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            self.pool.to_json(tmp_path)
            from bloodmusic.music.instrument_pool import InstrumentPool
            loaded = InstrumentPool.from_json(tmp_path)
            self.assertEqual(loaded.name, "Factory Test")
            self.assertEqual(loaded.bpm, 100)
            self.assertEqual(len(loaded.instruments), 2)
        finally:
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════
# 5. PoolSerializer 错误路径测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolSerializerErrors(unittest.TestCase):
    """PoolSerializer 错误处理测试"""

    def test_load_yaml_nonexistent_file(self):
        """加载不存在的 YAML 文件应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        with self.assertRaises(PoolSerializationError) as ctx:
            PoolSerializer.load_yaml(
                "/nonexistent/path/to/file.yaml",
            )
        self.assertIn("不存在", str(ctx.exception))

    def test_load_json_nonexistent_file(self):
        """加载不存在的 JSON 文件应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        with self.assertRaises(PoolSerializationError) as ctx:
            PoolSerializer.load_json(
                "/nonexistent/path/to/file.json",
            )
        self.assertIn("不存在", str(ctx.exception))

    def test_load_yaml_invalid_content(self):
        """加载无效 YAML 应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp.write("not: a: valid: yaml: [unclosed")
        tmp_path = tmp.name
        tmp.close()

        try:
            with self.assertRaises(PoolSerializationError) as ctx:
                PoolSerializer.load_yaml(tmp_path)
            self.assertIn("YAML", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_load_json_invalid_content(self):
        """加载无效 JSON 应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8",
        )
        tmp.write("{invalid json content}")
        tmp_path = tmp.name
        tmp.close()

        try:
            with self.assertRaises(PoolSerializationError) as ctx:
                PoolSerializer.load_json(tmp_path)
            self.assertIn("JSON", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_load_yaml_non_dict(self):
        """YAML 文件内容非 dict 应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp.write("- list item 1\n- list item 2\n")
        tmp_path = tmp.name
        tmp.close()

        try:
            with self.assertRaises(PoolSerializationError) as ctx:
                PoolSerializer.load_yaml(tmp_path)
            self.assertIn("dict", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_load_yaml_empty_file(self):
        """空 YAML 文件应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".yaml", mode="w", delete=False, encoding="utf-8",
        )
        tmp_path = tmp.name
        tmp.close()

        try:
            with self.assertRaises(PoolSerializationError) as ctx:
                PoolSerializer.load_yaml(tmp_path)
            self.assertIn("空", str(ctx.exception))
        finally:
            os.unlink(tmp_path)

    def test_load_preset_nonexistent(self):
        """加载不存在的预设应抛出 PoolSerializationError"""
        from bloodmusic.music.pool_serializer import (
            PoolSerializer, PoolSerializationError,
        )
        with self.assertRaises(PoolSerializationError) as ctx:
            PoolSerializer.load_preset("nonexistent_preset_xyz")
        self.assertIn("不存在", str(ctx.exception))

    def test_list_presets_returns_list(self):
        """list_presets 返回列表"""
        from bloodmusic.music.pool_serializer import PoolSerializer
        presets = PoolSerializer.list_presets()
        self.assertIsInstance(presets, list)

    def test_list_presets_has_expected(self):
        """list_presets 应包含预期的 5 个预设"""
        from bloodmusic.music.pool_serializer import PoolSerializer
        presets = PoolSerializer.list_presets()
        expected = [
            "ambient_pad", "electronic_group", "jazz_trio",
            "orchestral_small", "rock_band",
        ]
        for name in expected:
            self.assertIn(name, presets, f"Missing preset: {name}")


# ═══════════════════════════════════════════════════════════════════════
# 6. PoolTemplate 边界测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolTemplateEdgeCases(unittest.TestCase):
    """PoolTemplate 边界情况"""

    def test_get_template_known(self):
        """get_template 返回正确的模板"""
        from bloodmusic.music.pool_templates import get_template
        tmpl = get_template("orchestral_small")
        self.assertEqual(tmpl.name, "orchestral_small")
        self.assertEqual(tmpl.bpm, 100)

    def test_get_template_case_insensitive(self):
        """get_template 大小写不敏感"""
        from bloodmusic.music.pool_templates import get_template
        tmpl = get_template("ORCHESTRAL_SMALL")
        self.assertEqual(tmpl.name, "orchestral_small")

    def test_get_template_unknown(self):
        """get_template 对未知模板抛出 KeyError"""
        from bloodmusic.music.pool_templates import get_template
        with self.assertRaises(KeyError) as ctx:
            get_template("nonexistent")
        self.assertIn("未知模板", str(ctx.exception))

    def test_list_templates(self):
        """list_templates 返回 3 个模板名"""
        from bloodmusic.music.pool_templates import list_templates
        tmpls = list_templates()
        self.assertEqual(len(tmpls), 3)
        self.assertIn("orchestral_small", tmpls)
        self.assertIn("electronic_group", tmpls)
        self.assertIn("jazz_trio", tmpls)

    def test_to_pool_basic(self):
        """to_pool 返回合法 InstrumentPool"""
        from bloodmusic.music.pool_templates import POOL_TEMPLATES
        tmpl = POOL_TEMPLATES["jazz_trio"]
        pool = tmpl.to_pool()
        from bloodmusic.music.instrument_pool import InstrumentPool
        self.assertIsInstance(pool, InstrumentPool)
        self.assertGreater(len(pool.instruments), 0)

    def test_to_pool_with_style(self):
        """to_pool(style="battle") 设置 style 字段"""
        from bloodmusic.music.pool_templates import POOL_TEMPLATES
        tmpl = POOL_TEMPLATES["electronic_group"]
        pool = tmpl.to_pool(style="battle")
        self.assertEqual(pool.style, "battle")

    def test_to_pool_name_formatting(self):
        """to_pool 自动格式化名称为 Title Case"""
        from bloodmusic.music.pool_templates import POOL_TEMPLATES
        tmpl = POOL_TEMPLATES["orchestral_small"]
        pool = tmpl.to_pool()
        self.assertEqual(pool.name, "Orchestral Small")


# ═══════════════════════════════════════════════════════════════════════
# 7. StylePreset 边界 + 覆盖行为
# ═══════════════════════════════════════════════════════════════════════

class TestStylePresetEdgeCases(unittest.TestCase):
    """StylePreset 边界情况"""

    def test_get_style_known(self):
        """get_style 返回正确的风格"""
        from bloodmusic.music.pool_styles import get_style
        style = get_style("battle")
        self.assertEqual(style.name, "battle")
        self.assertTrue(len(style.description) > 0)
        self.assertIsNotNone(style.role_params)

    def test_get_style_case_insensitive(self):
        """get_style 大小写不敏感"""
        from bloodmusic.music.pool_styles import get_style
        style = get_style("AMBIENT")
        self.assertEqual(style.name, "ambient")

    def test_get_style_unknown(self):
        """get_style 对未知风格抛出 KeyError"""
        from bloodmusic.music.pool_styles import get_style
        with self.assertRaises(KeyError) as ctx:
            get_style("nonexistent_style")
        self.assertIn("未知风格", str(ctx.exception))

    def test_list_styles(self):
        """list_styles 返回 12 个风格名"""
        from bloodmusic.music.pool_styles import list_styles
        styles = list_styles()
        self.assertEqual(len(styles), 12)
        for name in [
            "exploration", "battle", "town", "dungeon", "ambient",
            "classical", "jazz", "electronic", "cinematic", "lofi",
            "meditation", "folk",
        ]:
            self.assertIn(name, styles, f"Missing style: {name}")

    def test_all_styles_exist(self):
        """全部 12 个风格均可通过 get_style 正确获取"""
        from bloodmusic.music.pool_styles import get_style, STYLES
        expected_names = [
            "exploration", "battle", "town", "dungeon", "ambient",
            "classical", "jazz", "electronic", "cinematic", "lofi",
            "meditation", "folk",
        ]
        self.assertEqual(len(STYLES), 12)
        for name in expected_names:
            style = get_style(name)
            self.assertEqual(
                style.name, name,
                f"get_style('{name}') returned style '{style.name}'",
            )
            self.assertTrue(len(style.description) > 0)
            self.assertIsNotNone(style.role_params)
            self.assertIsNotNone(style.mix_params)
            self.assertIsNotNone(style.config_overrides)
            self.assertIsNotNone(style.arrangement_template)

    def test_apply_config_overrides(self):
        """apply_to 应用 config_overrides"""
        from bloodmusic.music.pool_styles import get_style
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test")
        style = get_style("battle")
        new_pool = style.apply_to(pool)
        # battle style overrides diversity to 0.25
        self.assertEqual(new_pool.config.diversity, 0.25)
        self.assertTrue(new_pool.config.humanize)

    def test_apply_sets_arrangement_sections(self):
        """apply_to 设置 arrangement sections（当 pool 未显式设置时）"""
        from bloodmusic.music.pool_styles import get_style
        from bloodmusic.music.instrument_pool import InstrumentPool
        pool = InstrumentPool(name="Test")
        style = get_style("exploration")
        new_pool = style.apply_to(pool)
        # exploration uses "ambient" arrangement template
        self.assertGreater(len(new_pool.config.sections), 0)

    def test_apply_preserves_explicit_sections(self):
        """apply_to 保留 pool 显式设置的 sections"""
        from bloodmusic.music.pool_styles import get_style
        from bloodmusic.music.instrument_pool import InstrumentPool, PoolConfig
        pool = InstrumentPool(
            name="Test",
            config=PoolConfig(sections=["my_intro", "my_verse"]),
        )
        style = get_style("battle")
        new_pool = style.apply_to(pool)
        self.assertEqual(new_pool.config.sections, ["my_intro", "my_verse"])

    def test_all_styles_have_role_params(self):
        """所有风格都有 role_params"""
        from bloodmusic.music.pool_styles import STYLES
        for name, style in STYLES.items():
            self.assertIsNotNone(
                style.role_params,
                f"Style '{name}' has no role_params",
            )

    def test_all_styles_have_mix_params(self):
        """所有风格都有 mix_params"""
        from bloodmusic.music.pool_styles import STYLES
        for name, style in STYLES.items():
            self.assertIsNotNone(
                style.mix_params,
                f"Style '{name}' has no mix_params",
            )


# ═══════════════════════════════════════════════════════════════════════
# 8. PoolGenerator 角色生成 + humanize + seed
# ═══════════════════════════════════════════════════════════════════════

class TestPoolGeneratorComprehensive(unittest.TestCase):
    """PoolGenerator 完整测试"""

    def _make_pool(self, role_name, role):
        """创建仅含单个角色的测试乐器池"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument,
        )
        return InstrumentPool(
            name=f"{role_name} Pool",
            bpm=100,
            key="C",
            scale="major",
            instruments=[
                PoolInstrument(
                    name=role_name,
                    role=role,
                    volume=0.7,
                ),
            ],
        )

    def test_generate_melody_nonempty(self):
        """generate_melody 返回非空 MusicPattern"""
        from bloodmusic.music.instrument_pool import InstrumentRole, SynthEngine
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("Melody", InstrumentRole.MELODY)
        gen = PoolGenerator(pool)
        pattern = gen.generate_melody(pool.instruments[0], target_bars=8)
        self.assertGreater(len(pattern.notes), 0)
        self.assertGreater(len(pattern.durations), 0)

    def test_generate_chord_nonempty(self):
        """generate_chord 返回含 chords 的 MusicPattern"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("Chords", InstrumentRole.CHORD)
        gen = PoolGenerator(pool)
        pattern = gen.generate_chord(pool.instruments[0], target_bars=8)
        self.assertIsNotNone(pattern.chords)
        self.assertGreater(len(pattern.chords), 0)

    def test_generate_bass_nonempty(self):
        """generate_bass 返回非空 MusicPattern"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("Bass", InstrumentRole.BASS)
        gen = PoolGenerator(pool)
        pattern = gen.generate_bass(pool.instruments[0], target_bars=8)
        self.assertGreater(len(pattern.notes), 0)
        self.assertGreater(len(pattern.durations), 0)

    def test_generate_drum_nonempty(self):
        """generate_drum 返回含 tracks 的 DrumPattern"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("Drums", InstrumentRole.DRUM)
        gen = PoolGenerator(pool)
        pattern = gen.generate_drum(pool.instruments[0], target_bars=8)
        self.assertGreater(len(pattern.tracks), 0)

    def test_generate_pad_nonempty(self):
        """generate_pad 返回非空 MusicPattern"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("Pad", InstrumentRole.PAD)
        gen = PoolGenerator(pool)
        pattern = gen.generate_pad(pool.instruments[0], target_bars=8)
        self.assertGreater(len(pattern.notes), 0)
        self.assertGreater(len(pattern.durations), 0)

    def test_generate_fx_disabled(self):
        """FX 被禁用时应返回静音模式"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        pool = self._make_pool("FX", InstrumentRole.FX)
        gen = PoolGenerator(pool)  # no style → fx disabled
        pattern = gen.generate_fx(pool.instruments[0], target_bars=8)
        # 静音模式: notes 只有 None，volume=0
        self.assertTrue(all(n is None for n in pattern.notes))
        self.assertEqual(pattern.volume, 0.0)

    def test_generate_fx_enabled_with_style(self):
        """FX 在 battle 风格（enabled=True）下应生成非静音"""
        from bloodmusic.music.instrument_pool import InstrumentRole
        from bloodmusic.music.pool_generator import PoolGenerator
        from bloodmusic.music.pool_styles import get_style
        pool = self._make_pool("FX", InstrumentRole.FX)
        style = get_style("battle")  # battle has FX enabled=True
        gen = PoolGenerator(pool, style=style)
        pattern = gen.generate_fx(pool.instruments[0], target_bars=8)
        # FX enabled: 应生成至少一个有效音符
        self.assertGreater(len(pattern.notes), 0)
        self.assertGreater(pattern.volume, 0.0)

    def test_generate_all_with_seed_deterministic(self):
        """固定 seed 产生确定性输出"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        def make_pool():
            return InstrumentPool(
                name="Seed Test", bpm=120, key="C",
                instruments=[
                    PoolInstrument(
                        name="Melody", role=InstrumentRole.MELODY,
                        engine=SynthEngine.WAVETABLE, volume=0.8,
                    ),
                ],
                config=__import__(
                    "bloodmusic.music.instrument_pool", fromlist=["PoolConfig"]
                ).PoolConfig(seed=42, diversity=0.3),
            )

        from bloodmusic.music.instrument_pool import PoolConfig

        pool1 = InstrumentPool(
            name="Seed Test", bpm=120, key="C",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.8,
                ),
            ],
            config=PoolConfig(seed=42, diversity=0.3),
        )
        pool2 = InstrumentPool(
            name="Seed Test", bpm=120, key="C",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.8,
                ),
            ],
            config=PoolConfig(seed=42, diversity=0.3),
        )

        gen1 = PoolGenerator(pool1)
        gen2 = PoolGenerator(pool2)
        multi1 = gen1.generate_all(target_bars=4)
        multi2 = gen2.generate_all(target_bars=4)

        # 相同种子应产生相同输出
        self.assertEqual(
            multi1.music_tracks[0].notes,
            multi2.music_tracks[0].notes,
        )

    def test_humanize_off_no_params(self):
        """humanize=False 不设置 humanize_params"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, PoolConfig,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        pool = InstrumentPool(
            name="No Humanize", bpm=100, key="C",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY, volume=0.8,
                ),
            ],
            config=PoolConfig(humanize=False),
        )
        gen = PoolGenerator(pool)
        pattern = gen.generate_melody(pool.instruments[0], target_bars=4)
        self.assertIsNone(pattern.humanize_params)

    def test_humanize_on_has_params(self):
        """humanize=True（默认）设置 humanize_params"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, PoolConfig,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        pool = InstrumentPool(
            name="Humanize", bpm=100, key="C",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY, volume=0.8,
                ),
            ],
            config=PoolConfig(humanize=True),
        )
        gen = PoolGenerator(pool)
        pattern = gen.generate_melody(pool.instruments[0], target_bars=4)
        self.assertIsNotNone(pattern.humanize_params)

    def test_style_affects_parameters(self):
        """风格参数影响生成器行为"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole,
        )
        from bloodmusic.music.pool_generator import PoolGenerator
        from bloodmusic.music.pool_styles import get_style

        pool = InstrumentPool(
            name="Style Pool", bpm=100, key="C",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY, volume=0.8,
                ),
            ],
        )
        # with battle style (note_density=2.5)
        style = get_style("battle")
        gen = PoolGenerator(pool, style=style)
        pattern = gen.generate_melody(pool.instruments[0], target_bars=4)
        # 应有非空输出
        self.assertGreater(len(pattern.notes), 0)


# ═══════════════════════════════════════════════════════════════════════
# 9. PoolRenderer 边界测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolRendererEdgeCases(unittest.TestCase):
    """PoolRenderer 边界情况"""

    def test_constructor_with_style_name(self):
        """构造时传入 style_name"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        pool = InstrumentPool(
            name="Render Test", bpm=120, key="C",
            instruments=[
                PoolInstrument(
                    name="Tone", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.5,
                    note_sequence=["C4", "E4"],
                ),
            ],
        )
        renderer = PoolRenderer(pool, duration_sec=2.0, style_name="battle")
        self.assertEqual(renderer.style_name, "battle")
        self.assertIsNotNone(renderer._style)

    def test_constructor_with_unknown_style(self):
        """构造时传入未知风格应优雅处理"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        pool = InstrumentPool(
            name="Render Test", bpm=120, key="C",
            instruments=[
                PoolInstrument(
                    name="Tone", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.5,
                    note_sequence=["C4"],
                ),
            ],
        )
        # 不应崩溃
        renderer = PoolRenderer(
            pool, duration_sec=1.0, style_name="unknown_style_xyz",
        )
        self.assertIsNone(renderer._style)
        # render 应正常完成
        final, stems = renderer.render()
        self.assertGreater(np.max(np.abs(final)), 0.0)

    def test_constructor_uses_pool_style(self):
        """构造时不传 style_name，使用 pool.style"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.music.pool_renderer import PoolRenderer

        pool = InstrumentPool(
            name="Styled", bpm=120, key="C", style="battle",
            instruments=[
                PoolInstrument(
                    name="Tone", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE, volume=0.5,
                    note_sequence=["C4", "E4"],
                ),
            ],
        )
        renderer = PoolRenderer(pool, duration_sec=2.0)
        self.assertEqual(renderer.style_name, "battle")
        self.assertIsNotNone(renderer._style)


# ═══════════════════════════════════════════════════════════════════════
# 10. MusicPattern.pool_role 回归测试
# ═══════════════════════════════════════════════════════════════════════

class TestMusicPatternPoolRole(unittest.TestCase):
    """MusicPattern.pool_role 字段回归测试"""

    def test_pool_role_default_none(self):
        """pool_role 默认为 None"""
        pattern = MusicPattern(
            name="test",
            notes=["C4", "D4"],
            durations=[1.0, 1.0],
        )
        self.assertIsNone(pattern.pool_role)

    def test_pool_role_settable(self):
        """pool_role 可以显式设置"""
        pattern = MusicPattern(
            name="test",
            notes=["C4", "D4"],
            durations=[1.0, 1.0],
        )
        pattern.pool_role = "melody"
        self.assertEqual(pattern.pool_role, "melody")

    def test_pool_role_does_not_break_validation(self):
        """pool_role 不影响现有校验逻辑"""
        # MusicPattern.__post_init__ 应正常工作
        pattern = MusicPattern(
            name="test",
            notes=["C4", "D4", "E4"],
            durations=[1.0, 1.0, 1.0],
        )
        pattern.pool_role = "bass"
        self.assertEqual(pattern.pool_role, "bass")
        self.assertEqual(len(pattern.notes), 3)
        self.assertEqual(len(pattern.durations), 3)

    def test_pool_role_not_in_mismatch_check(self):
        """pool_role 不参与 notes/durations 匹配检查"""
        # 如果 pool_role 被误当成 notes 或 durations，不应报错
        pattern = MusicPattern(
            name="test",
            notes=["C4"],
            durations=[1.0],
        )
        pattern.pool_role = "melody"
        # 不应抛出异常
        self.assertEqual(pattern.notes, ["C4"])

    def test_multitrack_pool_role_rendering(self):
        """带 pool_role 的 pattern 正常渲染"""
        from bloodmusic.music.pattern import MultiTrackPattern, render_multi_track

        pattern = MusicPattern(
            name="test",
            notes=["C4", "E4", "G4"],
            durations=[1.0, 1.0, 1.0],
            bpm=120,
        )
        pattern.pool_role = "melody"

        multi = MultiTrackPattern(
            name="test_multi", bpm=120,
            music_tracks=[pattern],
        )
        sig = render_multi_track(multi, 2.0)
        self.assertGreater(np.max(np.abs(sig)), 0.01)


# ═══════════════════════════════════════════════════════════════════════
# 11. 模块导出验证
# ═══════════════════════════════════════════════════════════════════════

class TestModuleExports(unittest.TestCase):
    """验证 music.__init__.py 正确导出所有 pool 相关符号"""

    def test_instrument_pool_exports(self):
        """instrument_pool 符号全部可导入"""
        from bloodmusic.music import (
            InstrumentPool, PoolInstrument, PoolConfig,
            InstrumentRole, SynthEngine,
            DEFAULT_ENGINE_MAP, get_default_engine,
        )
        self.assertIsNotNone(InstrumentPool)
        self.assertIsNotNone(PoolInstrument)
        self.assertIsNotNone(PoolConfig)
        self.assertIsNotNone(InstrumentRole)
        self.assertIsNotNone(SynthEngine)
        self.assertIsNotNone(DEFAULT_ENGINE_MAP)
        self.assertTrue(callable(get_default_engine))

    def test_serializer_exports(self):
        """pool_serializer 符号全部可导入"""
        from bloodmusic.music import PoolSerializer, PoolSerializationError
        self.assertIsNotNone(PoolSerializer)
        self.assertIsNotNone(PoolSerializationError)

    def test_styles_exports(self):
        """pool_styles 符号全部可导入"""
        from bloodmusic.music import (
            StylePreset, STYLES, get_style, list_styles,
        )
        self.assertIsNotNone(StylePreset)
        self.assertIsInstance(STYLES, dict)
        self.assertTrue(callable(get_style))
        self.assertTrue(callable(list_styles))

    def test_templates_exports(self):
        """pool_templates 符号全部可导入"""
        from bloodmusic.music import (
            PoolTemplate, POOL_TEMPLATES, get_template, list_templates,
        )
        self.assertIsNotNone(PoolTemplate)
        self.assertIsInstance(POOL_TEMPLATES, dict)
        self.assertTrue(callable(get_template))
        self.assertTrue(callable(list_templates))

    def test_generator_renderer_exports(self):
        """PoolGenerator 和 PoolRenderer 可导入"""
        from bloodmusic.music import PoolGenerator, PoolRenderer
        self.assertIsNotNone(PoolGenerator)
        self.assertIsNotNone(PoolRenderer)


# ═══════════════════════════════════════════════════════════════════════
# 12. 序列化特殊字段测试
# ═══════════════════════════════════════════════════════════════════════

class TestSerializationSpecialFields(unittest.TestCase):
    """EffectChain 序列化 + master_chain 序列化"""

    def test_effect_chain_serialization(self):
        """PoolInstrument with effect_chain 往返序列化"""
        from bloodmusic.music.instrument_pool import (
            PoolInstrument, InstrumentPool, InstrumentRole, SynthEngine,
        )
        from bloodmusic.effects.chain import EffectChain
        from bloodmusic.effects.dynamics import CompressorParams
        from bloodmusic.music.pool_serializer import PoolSerializer

        inst = PoolInstrument(
            name="FX Instrument",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.WAVETABLE,
            volume=0.8,
            effect_chain=EffectChain(
                reverb_mix=0.3,
                lp_filter_hz=4000.0,
                compressor=CompressorParams(
                    threshold_db=-15.0, ratio=3.0,
                ),
            ),
        )

        pool = InstrumentPool(
            name="Chain Test", instruments=[inst],
        )
        d = pool.to_dict()
        inst_dict = d["instruments"][0]
        self.assertIn("effect_chain", inst_dict)
        self.assertEqual(inst_dict["effect_chain"]["reverb_mix"], 0.3)
        self.assertEqual(inst_dict["effect_chain"]["lp_filter_hz"], 4000.0)

    def test_master_chain_serialization(self):
        """InstrumentPool with master_chain 序列化"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, PoolInstrument, InstrumentRole, SynthEngine,
        )
        from bloodmusic.effects.chain import EffectChain

        pool = InstrumentPool(
            name="Master Chain Pool",
            instruments=[
                PoolInstrument(
                    name="Melody", role=InstrumentRole.MELODY,
                    engine=SynthEngine.WAVETABLE,
                ),
                PoolInstrument(
                    name="Drums", role=InstrumentRole.DRUM,
                    engine=SynthEngine.NOISE,
                ),
            ],
            master_chain=EffectChain(
                reverb_mix=0.1,
                lp_filter_hz=16000.0,
            ),
        )
        d = pool.to_dict()
        self.assertIn("master_chain", d)
        self.assertEqual(d["master_chain"]["reverb_mix"], 0.1)


if __name__ == "__main__":
    unittest.main()
