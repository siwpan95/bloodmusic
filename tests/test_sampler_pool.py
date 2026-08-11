"""SAMPLER 引擎 Pool 系统测试

覆盖范围:
  1. SynthEngine.SAMPLER 枚举值 + from_string
  2. PoolInstrument sample_path 字段 + to_dict
  3. YAML 序列化/反序列化 roundtrip
  4. PoolGenerator.generate_all() 对 SAMPLER 乐器不抛异常
  5. album_maker 集成 (TrackHandler 含 sampler 乐器可正常完成)

运行:
    F:/Python314/python.exe -m pytest tests/test_sampler_pool.py -v
"""

import os
import sys
import tempfile
import unittest
import wave
import struct

import numpy as np

# ── 辅助函数 ──

def _create_test_wav(path: str, duration: float = 0.5, sr: int = 44100,
                     freq: float = 440.0) -> str:
    """创建一段简单的正弦波 WAV 作为假采样。

    Args:
        path: 输出路径
        duration: 时长（秒）
        sr: 采样率
        freq: 频率 (Hz)

    Returns:
        创建的文件路径
    """
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    data = (np.sin(2 * np.pi * freq * t) * 0.5 * 32767).astype(np.int16)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())
    return path


# ═══════════════════════════════════════════════════════════════════════
# 1. SynthEngine.SAMPLER 枚举测试
# ═══════════════════════════════════════════════════════════════════════

class TestSamplerSynthEngine(unittest.TestCase):
    """SynthEngine.SAMPLER 枚举专项测试"""

    def test_sampler_engine_exists(self):
        """SAMPLER 应存在于 SynthEngine 枚举中"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertTrue(hasattr(SynthEngine, "SAMPLER"))

    def test_sampler_engine_value(self):
        """SAMPLER.value 应为 'sampler'"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(SynthEngine.SAMPLER.value, "sampler")

    def test_from_string_sampler(self):
        """from_string('sampler') 应返回 SynthEngine.SAMPLER"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(
            SynthEngine.from_string("sampler"),
            SynthEngine.SAMPLER,
        )

    def test_from_string_sampler_case_insensitive(self):
        """from_string 对 'SAMPLER' 大小写不敏感"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(
            SynthEngine.from_string("SAMPLER"),
            SynthEngine.SAMPLER,
        )
        self.assertEqual(
            SynthEngine.from_string("  Sampler  "),
            SynthEngine.SAMPLER,
        )

    def test_total_engines_count(self):
        """添加 SAMPLER 后引擎总数应至少为 9"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertGreaterEqual(len(SynthEngine), 9)

    def test_str_method(self):
        """__str__ 返回 'sampler'"""
        from bloodmusic.music.instrument_pool import SynthEngine
        self.assertEqual(str(SynthEngine.SAMPLER), "sampler")


# ═══════════════════════════════════════════════════════════════════════
# 2. PoolInstrument sample_path 字段测试
# ═══════════════════════════════════════════════════════════════════════

class TestPoolInstrumentSamplePath(unittest.TestCase):
    """PoolInstrument sample_path 字段测试"""

    def test_default_sample_path_empty(self):
        """默认 sample_path 应为空字符串"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(name="test")
        self.assertEqual(inst.sample_path, "")

    def test_sample_path_settable(self):
        """sample_path 应可设置"""
        from bloodmusic.music.instrument_pool import PoolInstrument
        inst = PoolInstrument(
            name="test",
            engine="sampler",
            sample_path="G:/samples/piano.wav",
        )
        self.assertEqual(inst.sample_path, "G:/samples/piano.wav")

    def test_to_dict_includes_sample_path_when_nonempty(self):
        """to_dict() 应在 sample_path 非空时包含该字段"""
        from bloodmusic.music.instrument_pool import (
            InstrumentRole, PoolInstrument, SynthEngine,
        )
        inst = PoolInstrument(
            name="钢琴采样",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.SAMPLER,
            sample_path="G:/radio_music_stems/song_01/piano.wav",
            volume=0.85,
            pan=0.0,
        )
        d = inst.to_dict()
        self.assertIn("sample_path", d)
        self.assertEqual(
            d["sample_path"],
            "G:/radio_music_stems/song_01/piano.wav",
        )
        self.assertEqual(d["engine"], "sampler")
        self.assertEqual(d["volume"], 0.85)

    def test_to_dict_excludes_sample_path_when_empty(self):
        """to_dict() 应在 sample_path 为空时不包含该字段（向后兼容）"""
        from bloodmusic.music.instrument_pool import (
            PoolInstrument, SynthEngine,
        )
        inst = PoolInstrument(
            name="合成器钢琴",
            engine=SynthEngine.WAVETABLE,
        )
        d = inst.to_dict()
        self.assertNotIn("sample_path", d)

    def test_sampler_with_note_sequence(self):
        """SAMPLER 乐器可携带 note_sequence"""
        from bloodmusic.music.instrument_pool import (
            InstrumentRole, PoolInstrument, SynthEngine,
        )
        inst = PoolInstrument(
            name="旋律采样",
            role=InstrumentRole.MELODY,
            engine=SynthEngine.SAMPLER,
            sample_path="/tmp/test.wav",
            note_sequence=["C4", "D4", "E4", None, "G4"],
        )
        self.assertEqual(len(inst.note_sequence), 5)
        self.assertEqual(inst.note_sequence[0], "C4")
        self.assertIsNone(inst.note_sequence[3])


# ═══════════════════════════════════════════════════════════════════════
# 3. YAML 序列化/反序列化 roundtrip
# ═══════════════════════════════════════════════════════════════════════

class TestSamplerSerialization(unittest.TestCase):
    """SAMPLER 乐器 YAML 序列化 roundtrip 测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bloodmusic_sampler_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _build_sampler_pool(self):
        """构建含 SAMPLER 乐器的 InstrumentPool"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )
        return InstrumentPool(
            name="Sampler Test Pool",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="真实钢琴采样",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.SAMPLER,
                    sample_path="G:/radio_music_stems/song_01/piano.wav",
                    volume=0.85,
                    pan=0.0,
                ),
                PoolInstrument(
                    name="合成器贝斯",
                    role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE,
                    volume=0.9,
                ),
            ],
            config=PoolConfig(
                sections=["intro", "verse"],
                section_bars=[4, 8],
            ),
        )

    def test_yaml_roundtrip_preserves_sample_path(self):
        """YAML 保存→加载应保留 sample_path"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        pool = self._build_sampler_pool()
        yaml_path = os.path.join(self.tmpdir, "sampler_pool.yaml")

        # 保存
        PoolSerializer.save_yaml(pool, yaml_path)
        self.assertTrue(os.path.isfile(yaml_path))

        # 加载
        loaded = PoolSerializer.load_yaml(yaml_path)

        # 验证 SAMPLER 乐器
        sampler_insts = [
            i for i in loaded.instruments
            if i.engine.value == "sampler"
        ]
        self.assertEqual(len(sampler_insts), 1)
        sampler = sampler_insts[0]
        self.assertEqual(sampler.name, "真实钢琴采样")
        self.assertEqual(
            sampler.sample_path,
            "G:/radio_music_stems/song_01/piano.wav",
        )
        self.assertEqual(sampler.volume, 0.85)
        self.assertEqual(sampler.pan, 0.0)

        # 验证 synth 乐器不受影响
        synth_insts = [
            i for i in loaded.instruments
            if i.engine.value != "sampler"
        ]
        self.assertEqual(len(synth_insts), 1)
        self.assertEqual(synth_insts[0].name, "合成器贝斯")
        self.assertEqual(synth_insts[0].engine.value, "subtractive")

    def test_json_roundtrip_preserves_sample_path(self):
        """JSON 保存→加载应保留 sample_path"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        pool = self._build_sampler_pool()
        json_path = os.path.join(self.tmpdir, "sampler_pool.json")

        PoolSerializer.save_json(pool, json_path)
        self.assertTrue(os.path.isfile(json_path))

        loaded = PoolSerializer.load_json(json_path)

        sampler_insts = [
            i for i in loaded.instruments
            if i.engine.value == "sampler"
        ]
        self.assertEqual(len(sampler_insts), 1)
        self.assertEqual(
            sampler_insts[0].sample_path,
            "G:/radio_music_stems/song_01/piano.wav",
        )

    def test_dict_construction_sample_path(self):
        """从 dict 直接构造 PoolInstrument 应正确设置 sample_path"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        data = {
            "name": "dict 采样",
            "role": "melody",
            "engine": "sampler",
            "sample_path": "/tmp/dict_test.wav",
            "volume": 0.75,
        }
        inst = PoolSerializer._dict_to_instrument(data)
        self.assertEqual(inst.sample_path, "/tmp/dict_test.wav")
        self.assertEqual(inst.engine.value, "sampler")

    def test_dict_construction_no_sample_path(self):
        """从 dict 构造（无 sample_path）默认空字符串"""
        from bloodmusic.music.pool_serializer import PoolSerializer

        data = {
            "name": "无采样路径",
            "role": "melody",
            "engine": "wavetable",
        }
        inst = PoolSerializer._dict_to_instrument(data)
        self.assertEqual(inst.sample_path, "")


# ═══════════════════════════════════════════════════════════════════════
# 4. PoolGenerator 对 SAMPLER 的处理
# ═══════════════════════════════════════════════════════════════════════

class TestPoolGeneratorSamplerSkip(unittest.TestCase):
    """PoolGenerator.generate_all() SAMPLER 跳过测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bloodmusic_gen_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_generate_all_skips_sampler_no_exception(self):
        """generate_all() 对 SAMPLER 乐器应跳过且不抛异常"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        # 创建 WAV 采样（PoolGenerator 不加载它，只是需要 sample_path 存在）
        wav_path = os.path.join(self.tmpdir, "test_sample.wav")
        _create_test_wav(wav_path, duration=0.3)

        pool = InstrumentPool(
            name="Sampler Skip Test",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="采样器钢琴",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.SAMPLER,
                    sample_path=wav_path,
                    volume=0.85,
                ),
                PoolInstrument(
                    name="合成器贝斯",
                    role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE,
                    volume=0.9,
                ),
            ],
            config=PoolConfig(seed=42),
        )

        gen = PoolGenerator(pool)
        # 不应抛异常
        multi = gen.generate_all(target_bars=4)

        # SAMPLER 不应出现在 music_tracks 中
        sampler_names = [
            t.name for t in multi.music_tracks
            if hasattr(t, "name")
        ]
        self.assertNotIn("采样器钢琴", sampler_names)

        # synth 乐器应正常生成
        self.assertGreaterEqual(len(multi.music_tracks), 1)
        synth_names = [t.name for t in multi.music_tracks]
        self.assertIn("合成器贝斯", synth_names)

    def test_pure_sampler_pool_does_not_crash(self):
        """纯 SAMPLER 乐器池 generate_all() 不应崩溃"""
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )
        from bloodmusic.music.pool_generator import PoolGenerator

        wav_path = os.path.join(self.tmpdir, "pure_sample.wav")
        _create_test_wav(wav_path, duration=0.3)

        pool = InstrumentPool(
            name="Pure Sampler",
            bpm=100,
            key="Am",
            instruments=[
                PoolInstrument(
                    name="采样器1",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.SAMPLER,
                    sample_path=wav_path,
                ),
                PoolInstrument(
                    name="采样器2",
                    role=InstrumentRole.CHORD,
                    engine=SynthEngine.SAMPLER,
                    sample_path=wav_path,
                ),
            ],
            config=PoolConfig(seed=123),
        )

        gen = PoolGenerator(pool)
        multi = gen.generate_all(target_bars=8)

        # 应该返回空的 MultiTrackPattern（无 music_tracks，无 drum_track）
        self.assertEqual(len(multi.music_tracks), 0)
        self.assertIsNone(multi.drum_track)


# ═══════════════════════════════════════════════════════════════════════
# 5. album_maker TrackHandler SAMPLER 集成测试
# ═══════════════════════════════════════════════════════════════════════

class TestAlbumMakerSamplerIntegration(unittest.TestCase):
    """album_maker TrackHandler 含 SAMPLER 乐器的集成测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bloodmusic_album_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_track_spec_extra_instruments_sampler(self):
        """TrackSpec.extra_instruments 中的 SAMPLER 应正确解析 sample_path"""
        from bloodmusic.album_maker.config import TrackSpec

        spec = TrackSpec(
            title="采样器测试曲",
            bpm=100,
            bars=8,
            key="C",
            seed=42,
            extra_instruments=[
                {
                    "name": "钢琴采样",
                    "role": "melody",
                    "engine": "sampler",
                    "sample_path": "G:/samples/piano.wav",
                    "volume": 0.85,
                },
            ],
        )
        self.assertEqual(len(spec.extra_instruments), 1)
        self.assertEqual(
            spec.extra_instruments[0]["sample_path"],
            "G:/samples/piano.wav",
        )

    def test_build_pool_for_track_includes_sample_path(self):
        """_build_pool_for_track() 应传递 sample_path 到 PoolInstrument"""
        from bloodmusic.album_maker.config import TrackSpec
        from bloodmusic.album_maker.track import TrackHandler
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )

        # 构造基础 pool
        base_pool = InstrumentPool(
            name="Test Base",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="基础贝斯",
                    role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE,
                ),
            ],
            config=PoolConfig(seed=42),
        )

        spec = TrackSpec(
            title="采样器测试",
            bpm=100,
            bars=8,
            key="Am",
            seed=99,
            extra_instruments=[
                {
                    "name": "额外采样器",
                    "role": "melody",
                    "engine": "sampler",
                    "sample_path": "G:/test_extra.wav",
                    "volume": 0.7,
                },
            ],
        )

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw={},
        )

        track_pool = handler._build_pool_for_track()

        # 检查 sampler 乐器
        sampler_insts = [
            i for i in track_pool.instruments
            if i.engine == SynthEngine.SAMPLER
        ]
        self.assertEqual(len(sampler_insts), 1)
        self.assertEqual(sampler_insts[0].name, "额外采样器")
        self.assertEqual(sampler_insts[0].sample_path, "G:/test_extra.wav")
        self.assertEqual(sampler_insts[0].volume, 0.7)

        # 检查原有 synth 乐器
        self.assertIn("基础贝斯", [i.name for i in track_pool.instruments])

    def test_process_with_sampler_instrument(self):
        """process() 含 SAMPLER 乐器的专辑应正常生成"""
        from bloodmusic.album_maker.config import TrackSpec
        from bloodmusic.album_maker.track import TrackHandler
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )

        # 创建测试 WAV
        wav_path = os.path.join(self.tmpdir, "test_sampler.wav")
        _create_test_wav(wav_path, duration=1.0, freq=261.63)  # C4

        # 基础 pool（含 synth 和 sampler）
        base_pool = InstrumentPool(
            name="Integration Test Pool",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="合成器贝斯",
                    role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE,
                    volume=0.8,
                ),
                PoolInstrument(
                    name="钢琴采样",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.SAMPLER,
                    sample_path=wav_path,
                    volume=0.85,
                    note_sequence=["C4", "D4", "E4", "C4"],
                ),
            ],
            config=PoolConfig(seed=42),
        )

        spec = TrackSpec(
            title="集成测试曲",
            bpm=100,
            bars=4,
            key="C",
            seed=42,
        )

        handler = TrackHandler(
            spec=spec,
            pool=base_pool,
            mix_config_raw={
                "compress": False,
                "normalize_mode": "none",
                "clip_mode": "soft",
            },
        )

        work_dir = os.path.join(self.tmpdir, "track_output")
        result = handler.process(work_dir)

        # 基本验证
        self.assertTrue(result.success, f"Track 失败: {result.error}")
        self.assertEqual(result.title, "集成测试曲")
        self.assertIsNotNone(result.song_path)

        # 验证 stems 目录存在（synth + sampler）
        stems_dir = os.path.join(work_dir, "stems")
        self.assertTrue(os.path.isdir(stems_dir))

        # 检查 sampler stem 是否存在
        stem_files = os.listdir(stems_dir)
        sampler_stem = [f for f in stem_files if "钢琴采样" in f]
        self.assertEqual(len(sampler_stem), 1,
                         f"未找到 sampler stem，现有文件: {stem_files}")

        # 检查 synth stem
        synth_stem = [f for f in stem_files if "合成器贝斯" in f]
        self.assertEqual(len(synth_stem), 1,
                         f"未找到 synth stem，现有文件: {stem_files}")

    def test_process_sampler_without_sample_path_warns(self):
        """SAMPLER 乐器缺少 sample_path 不应崩溃"""
        from bloodmusic.album_maker.config import TrackSpec
        from bloodmusic.album_maker.track import TrackHandler
        from bloodmusic.music.instrument_pool import (
            InstrumentPool, InstrumentRole, PoolConfig, PoolInstrument,
            SynthEngine,
        )

        base_pool = InstrumentPool(
            name="Missing Sample Path Pool",
            bpm=120,
            key="C",
            instruments=[
                PoolInstrument(
                    name="缺失路径采样器",
                    role=InstrumentRole.MELODY,
                    engine=SynthEngine.SAMPLER,
                    sample_path="",  # 空路径
                ),
                PoolInstrument(
                    name="合成器",
                    role=InstrumentRole.BASS,
                    engine=SynthEngine.SUBTRACTIVE,
                ),
            ],
            config=PoolConfig(seed=42),
        )

        spec = TrackSpec(title="空路径测试", bpm=100, bars=4, key="C", seed=1)
        handler = TrackHandler(spec=spec, pool=base_pool, mix_config_raw={})
        work_dir = os.path.join(self.tmpdir, "missing_sample_output")
        result = handler.process(work_dir)

        # 不应崩溃；synth 乐器应正常渲染
        self.assertTrue(result.success,
                        f"含缺失 sample_path 的 sampler 不应导致崩溃: {result.error}")


# ═══════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
