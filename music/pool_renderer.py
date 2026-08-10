"""
端到端渲染管线 —— 乐器池 → 分轨 → 混音 → 成品音频
==================================================

将 InstrumentPool 从定义到成品音频的完整流程串联起来：

  Phase 1: PoolGenerator  → 分轨生成 (MultiTrackPattern)
  Phase 2: Pattern 渲染   → 各轨音频数组 (np.ndarray)
  Phase 3: 混音阶段       → auto_level + freq_slot_allocator
  Phase 4: 编排渲染       → SongArrangement + render_song()
  Phase 5: 母带处理       → master_chain + normalize

用法:
    >>> from bloodmusic.music.pool_renderer import PoolRenderer
    >>> renderer = PoolRenderer(pool, duration_sec=60.0, style_name="battle")
    >>> final_audio, stems = renderer.render()
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

from ..core.constants import SR, NORMALIZE_DBFS
from ..core.note_utils import note_to_freq
from ..core.oscillator import OscType
from .pattern import (
    MusicPattern,
    DrumPattern,
    MultiTrackPattern,
    render_pattern_to_array,
    render_drum_pattern,
    render_multi_track,
)

if TYPE_CHECKING:
    from .instrument_pool import InstrumentPool, SynthEngine

logger = logging.getLogger(__name__)


class PoolRenderer:
    """端到端乐器池渲染管线。

    Args:
        pool: 乐器池定义
        duration_sec: 目标时长（秒）
        style_name: 风格名称（如 "battle", "exploration"）
        output_dir: 可选的输出目录
    """

    def __init__(
        self,
        pool: "InstrumentPool",
        duration_sec: float = 120.0,
        style_name: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        self.pool = pool
        self.duration_sec = duration_sec
        self.style_name = style_name or pool.style
        self.output_dir = output_dir

        # 解析风格预设
        self._style = None
        if self.style_name:
            try:
                from .pool_styles import get_style
                self._style = get_style(self.style_name)
                logger.info(f"PoolRenderer: 应用风格 '{self.style_name}'")
            except KeyError:
                logger.warning(
                    f"PoolRenderer: 未知风格 '{self.style_name}'，忽略"
                )

    # ── 主入口 ──

    def render(self) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """完整渲染管线：乐池 → 分轨 → 混音 → 成品。

        Returns:
            (final_audio: np.ndarray, stems: Dict[str, np.ndarray])
            final_audio 为 float32 立体声/单声道
            stems 为 {乐器名: float64 音频数组}
        """
        logger.info(f"PoolRenderer: 开始渲染 '{self.pool.name}' ({self.duration_sec}s)")

        # Phase 1: 生成分轨
        tracks = self._generate_tracks()

        # Phase 2: 渲染各分轨为音频
        stems = self._render_tracks_to_stems(tracks)

        # Phase 3: 混音辅助
        stems = self._apply_mix_assist(stems)

        # Phase 4: 编排并渲染
        mixed = self._render_arrangement(tracks, stems)

        # Phase 5: 母带
        final = self._apply_master_chain(mixed)

        # 截断到目标时长（arrangement 按曲式模板渲染可能超出 duration_sec）
        samples_needed = int(self.duration_sec * SR)
        if len(final) > samples_needed:
            final = final[:samples_needed]

        logger.info(
            f"PoolRenderer: 渲染完成 — "
            f"{len(stems)} stems, "
            f"output shape={final.shape}, "
            f"peak={np.max(np.abs(final)):.3f}"
        )

        return final, stems

    def render_stems_only(self) -> Dict[str, np.ndarray]:
        """仅渲染分轨（跳过混音和母带）。

        Returns:
            {乐器名: float64 音频数组}
        """
        logger.info(
            f"PoolRenderer: 仅渲染分轨 '{self.pool.name}' ({self.duration_sec}s)"
        )
        tracks = self._generate_tracks()
        stems = self._render_tracks_to_stems(tracks)
        stems = self._apply_mix_assist(stems)
        return stems

    # ── Phase 1: 生成分轨 ──

    def _generate_tracks(self) -> MultiTrackPattern:
        """使用 PoolGenerator 生成 MultiTrackPattern。

        Returns:
            MultiTrackPattern
        """
        from .pool_generator import PoolGenerator

        generator = PoolGenerator(self.pool, style=self._style)
        tracks = generator.generate_all()

        logger.info(
            f"  Phase 1: 分轨生成完成 — "
            f"{len(tracks.music_tracks)} music + "
            f"{'1' if tracks.drum_track else '0'} drum"
        )
        return tracks

    # ── Phase 2: 渲染分轨 ──

    def _render_tracks_to_stems(
        self,
        tracks: MultiTrackPattern,
    ) -> Dict[str, np.ndarray]:
        """将每个 MusicPattern/DrumPattern 渲染为独立音频数组。

        对每个 music track，先检查 engine 字段：
        - engine 非 None → 使用真实引擎渲染
        - engine 为 None 或 SUBTRACTIVE/NOISE → 使用 legacy render_pattern_to_array()

        渲染后应用 automation（如果 pattern.automation 有值）。

        Returns:
            {乐器名: float64 音频数组}
        """
        stems: Dict[str, np.ndarray] = {}

        for i, music_track in enumerate(tracks.music_tracks):
            try:
                # 引擎感知渲染分派
                audio = self._render_pattern_with_engine(
                    music_track, self.duration_sec
                )

                # 应用 automation（per-stem）
                audio = self._apply_automation_to_stem(audio, music_track)

                # 确保长度一致
                target_len = int(self.duration_sec * SR)
                if len(audio) < target_len:
                    audio = np.pad(audio, (0, target_len - len(audio)))
                audio = audio[:target_len]
                stems[music_track.name] = audio
            except Exception as e:
                logger.warning(f"  渲染旋律轨 '{music_track.name}' 失败: {e}")
                stems[music_track.name] = np.zeros(
                    int(self.duration_sec * SR), dtype=np.float64
                )

        if tracks.drum_track is not None:
            try:
                drum_audio = render_drum_pattern(
                    tracks.drum_track, self.duration_sec
                )
                target_len = int(self.duration_sec * SR)
                if len(drum_audio) < target_len:
                    drum_audio = np.pad(drum_audio, (0, target_len - len(drum_audio)))
                drum_audio = drum_audio[:target_len]
                stems[tracks.drum_track.name] = drum_audio
            except Exception as e:
                logger.warning(f"  渲染鼓轨失败: {e}")
                stems["drums"] = np.zeros(
                    int(self.duration_sec * SR), dtype=np.float64
                )

        logger.info(f"  Phase 2: 渲染完成 — {len(stems)} stems")
        return stems

    # ── 引擎感知渲染分派 ──

    def _render_pattern_with_engine(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """根据 pattern.engine 分派到真实引擎或 legacy 渲染。

        引擎分派规则：
        - engine=None / SUBTRACTIVE / NOISE → legacy render_pattern_to_array()
        - 和弦轨道（chords 非空且 notes 全 None）→ legacy（和弦渲染逻辑在 legacy 中）
        - 其他引擎 → 对应真实引擎渲染方法
        - 引擎渲染失败时 fallback 到 legacy 路径

        Args:
            pattern: 音乐模式（含 engine / engine_params 字段）
            duration_sec: 目标时长

        Returns:
            float64 音频数组
        """
        engine = getattr(pattern, 'engine', None)
        if engine is None:
            return render_pattern_to_array(pattern, duration_sec)

        # 导入 SynthEngine 枚举用于比较
        from .instrument_pool import SynthEngine

        if engine in (SynthEngine.SUBTRACTIVE, SynthEngine.NOISE):
            return render_pattern_to_array(pattern, duration_sec)

        # 和弦轨道（notes 全为 None，使用 chords 字段）走 legacy 渲染
        if pattern.chords is not None and all(n is None for n in pattern.notes):
            return render_pattern_to_array(pattern, duration_sec)

        try:
            if engine == SynthEngine.FM:
                return self._render_fm(pattern, duration_sec)
            elif engine == SynthEngine.FM_ADVANCED:
                return self._render_fm_advanced(pattern, duration_sec)
            elif engine == SynthEngine.WAVETABLE:
                return self._render_wavetable(pattern, duration_sec)
            elif engine == SynthEngine.KARPLUS_STRONG:
                return self._render_karplus_strong(pattern, duration_sec)
            elif engine == SynthEngine.WAVEGUIDE:
                return self._render_waveguide(pattern, duration_sec)
            elif engine == SynthEngine.GRANULAR:
                return self._render_granular(pattern, duration_sec)
            else:
                logger.warning(
                    f"  未知引擎类型 {engine}，fallback 到基础振荡器"
                )
                return render_pattern_to_array(pattern, duration_sec)
        except Exception as e:
            logger.warning(
                f"  Engine {engine} 渲染失败 ({e})，fallback 到基础振荡器"
            )
            return render_pattern_to_array(pattern, duration_sec)

    # ── FM 双算子渲染 ──

    def _render_fm(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用 FM 双算子合成器逐音符渲染。

        engine_params:
            modulator_freq_ratio: float (默认 2.0)
            fm_depth: float (默认 100.0)
        """
        from ..core.fm_synth import FMSynthVoice, synthesize_fm_voice
        from ..core.envelope import EnvShape

        params = getattr(pattern, 'engine_params', {}) or {}
        mod_ratio = params.get("modulator_freq_ratio", 2.0)
        fm_depth = params.get("fm_depth", 100.0)

        beat_dur = 60.0 / max(pattern.bpm, 1)
        total_beats = sum(pattern.durations)
        loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

        samples_list: List[np.ndarray] = []
        for _ in range(loops):
            for i, note in enumerate(pattern.notes):
                dur = pattern.durations[i] * beat_dur
                if note is None:
                    n_samp = max(1, int(dur * SR))
                    samples_list.append(np.zeros(n_samp, dtype=np.float64))
                else:
                    freq = note_to_freq(note)
                    voice = FMSynthVoice(
                        carrier_freq=freq,
                        carrier_type=OscType.SINE,
                        modulator_freq_ratio=mod_ratio,
                        modulator_type=OscType.SINE,
                        fm_depth=fm_depth,
                        duration=dur,
                        volume=0.3,
                        env_shape=EnvShape.PERCUSSIVE,
                    )
                    sig = synthesize_fm_voice(voice).astype(np.float64)
                    samples_list.append(sig)

        if not samples_list:
            return np.zeros(int(duration_sec * SR), dtype=np.float64)

        full = np.concatenate(samples_list)
        target_len = int(duration_sec * SR)
        if len(full) < target_len:
            reps = int(np.ceil(target_len / len(full)))
            full = np.tile(full, reps)
        return full[:target_len]

    # ── FM_ADVANCED 多算子渲染 ──

    # 预设名 → 创建函数映射
    _FM_ADVANCED_PRESET_MAP: Dict[str, callable] = {}

    @classmethod
    def _get_fm_advanced_preset_map(cls) -> Dict[str, callable]:
        """延迟初始化 FM_ADVANCED 预设映射（避免 import 时循环引用）。"""
        if not cls._FM_ADVANCED_PRESET_MAP:
            from ..core.fm_advanced import (
                create_dx7_bell, create_dx7_epiano, create_dx7_bass,
            )
            cls._FM_ADVANCED_PRESET_MAP = {
                "dx7_bell": create_dx7_bell,
                "dx7_epiano": create_dx7_epiano,
                "dx7_bass": create_dx7_bass,
            }
            # 扩展预设（non-standard DX7 sounds）
            cls._FM_ADVANCED_PRESET_MAP.update({
                "dx7_brass": cls._create_dx7_brass,
                "dx7_strings": cls._create_dx7_strings,
                "dx7_organ": cls._create_dx7_organ,
            })
        return cls._FM_ADVANCED_PRESET_MAP

    @staticmethod
    def _create_dx7_brass():
        """DX7 风格铜管音色。"""
        from ..core.fm_advanced import MultiOpFM, FMAlgorithm, FMOpParams
        from ..core.envelope import EnvShape
        from ..core.oscillator import OscType as _OscType
        fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.STACK)
        fm.ops = [
            FMOpParams(freq_ratio=1.0, env_shape=EnvShape.PAD, level=1.0),
            FMOpParams(freq_ratio=1.99, env_shape=EnvShape.PLUCK, level=0.7),
            FMOpParams(freq_ratio=3.01, env_shape=EnvShape.PERCUSSIVE, level=0.4),
            FMOpParams(freq_ratio=4.07, env_shape=EnvShape.PERCUSSIVE, level=0.2),
        ]
        return fm

    @staticmethod
    def _create_dx7_strings():
        """DX7 风格弦乐合奏音色。"""
        from ..core.fm_advanced import MultiOpFM, FMAlgorithm, FMOpParams
        from ..core.envelope import EnvShape
        fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.PAIR)
        fm.ops = [
            FMOpParams(freq_ratio=1.0, env_shape=EnvShape.PAD, level=1.0),
            FMOpParams(freq_ratio=1.01, env_shape=EnvShape.SWELL, level=0.6),
            FMOpParams(freq_ratio=2.0, env_shape=EnvShape.PAD, level=0.5),
            FMOpParams(freq_ratio=3.0, env_shape=EnvShape.SWELL, level=0.3),
        ]
        return fm

    @staticmethod
    def _create_dx7_organ():
        """DX7 风格管风琴音色。"""
        from ..core.fm_advanced import MultiOpFM, FMAlgorithm, FMOpParams
        from ..core.envelope import EnvShape
        fm = MultiOpFM(operators=4, algorithm=FMAlgorithm.STACK)
        fm.ops = [
            FMOpParams(freq_ratio=1.0, env_shape=EnvShape.PAD, level=1.0),
            FMOpParams(freq_ratio=2.0, env_shape=EnvShape.PAD, level=0.7),
            FMOpParams(freq_ratio=4.0, env_shape=EnvShape.PAD, level=0.4),
            FMOpParams(freq_ratio=5.33, env_shape=EnvShape.PERCUSSIVE, level=0.25),
        ]
        return fm

    def _render_fm_advanced(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用 MultiOpFM (DX7 风格) 逐音符渲染。

        engine_params:
            preset: str (默认 "dx7_epiano")
        """
        params = getattr(pattern, 'engine_params', {}) or {}
        preset_name = params.get("preset", "dx7_epiano")

        preset_map = self._get_fm_advanced_preset_map()
        create_fn = preset_map.get(preset_name, preset_map["dx7_epiano"])
        fm = create_fn()

        beat_dur = 60.0 / max(pattern.bpm, 1)
        total_beats = sum(pattern.durations)
        loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

        samples_list: List[np.ndarray] = []
        for _ in range(loops):
            for i, note in enumerate(pattern.notes):
                dur = pattern.durations[i] * beat_dur
                if note is None:
                    n_samp = max(1, int(dur * SR))
                    samples_list.append(np.zeros(n_samp, dtype=np.float64))
                else:
                    freq = note_to_freq(note)
                    sig = fm.render(freq, dur, volume=0.3)
                    samples_list.append(sig)

        if not samples_list:
            return np.zeros(int(duration_sec * SR), dtype=np.float64)

        full = np.concatenate(samples_list)
        target_len = int(duration_sec * SR)
        if len(full) < target_len:
            reps = int(np.ceil(target_len / len(full)))
            full = np.tile(full, reps)
        return full[:target_len]

    # ── WAVETABLE 波表渲染 ──

    def _render_wavetable(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用 WavetableOscillator 逐音符渲染。

        engine_params:
            preset: str (默认 "sine")
        """
        from ..core.wavetable import Wavetable, WavetableOscillator

        params = getattr(pattern, 'engine_params', {}) or {}
        preset_name = params.get("preset", "sine")

        try:
            wt = Wavetable.from_preset(preset_name)
        except ValueError:
            logger.warning(f"  波表预设 '{preset_name}' 不存在，fallback 到 sine")
            wt = Wavetable.from_preset("sine")

        beat_dur = 60.0 / max(pattern.bpm, 1)
        total_beats = sum(pattern.durations)
        loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

        samples_list: List[np.ndarray] = []
        for _ in range(loops):
            for i, note in enumerate(pattern.notes):
                dur = pattern.durations[i] * beat_dur
                if note is None:
                    n_samp = max(1, int(dur * SR))
                    samples_list.append(np.zeros(n_samp, dtype=np.float64))
                else:
                    freq = note_to_freq(note)
                    osc = WavetableOscillator(wt, freq=freq)
                    sig = osc.render(dur)
                    samples_list.append(sig)

        if not samples_list:
            return np.zeros(int(duration_sec * SR), dtype=np.float64)

        full = np.concatenate(samples_list)
        target_len = int(duration_sec * SR)
        if len(full) < target_len:
            reps = int(np.ceil(target_len / len(full)))
            full = np.tile(full, reps)
        return full[:target_len]

    # ── KARPLUS_STRONG 拨弦渲染 ──

    # 引擎参数中的预设名 → KS_PRESETS_BY_NAME 中的预设名映射
    _KS_PRESET_NAME_MAP: Dict[str, str] = {
        "nylon_guitar": "nylon_guitar",
        "steel_guitar": "steel_guitar",
        "acoustic_bass": "upright_bass",
        "harp": "harp",
        "sitar": "ethnic_lute",
        "ethnic_lute": "ethnic_lute",
    }

    def _render_karplus_strong(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用 Karplus-Strong 物理建模逐音符渲染。

        engine_params:
            preset: str (默认 "nylon_guitar")
        """
        from ..core.karplus_strong import (
            KarplusStrongSynth, KSVoice, KS_PRESETS_BY_NAME,
        )

        params = getattr(pattern, 'engine_params', {}) or {}
        preset_name = params.get("preset", "nylon_guitar")
        mapped_name = self._KS_PRESET_NAME_MAP.get(preset_name, "nylon_guitar")

        ks_synth = KarplusStrongSynth(sample_rate=SR)

        beat_dur = 60.0 / max(pattern.bpm, 1)
        total_beats = sum(pattern.durations)
        loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

        samples_list: List[np.ndarray] = []
        for _ in range(loops):
            for i, note in enumerate(pattern.notes):
                dur = pattern.durations[i] * beat_dur
                if note is None:
                    n_samp = max(1, int(dur * SR))
                    samples_list.append(np.zeros(n_samp, dtype=np.float64))
                else:
                    freq = note_to_freq(note)
                    if mapped_name in KS_PRESETS_BY_NAME:
                        voice = KS_PRESETS_BY_NAME[mapped_name].voice
                        voice.freq = freq
                        voice.duration = dur
                    else:
                        voice = KSVoice(freq=freq, duration=dur, volume=0.3)
                    sig = ks_synth.synthesize(voice).astype(np.float64)
                    samples_list.append(sig)

        if not samples_list:
            return np.zeros(int(duration_sec * SR), dtype=np.float64)

        full = np.concatenate(samples_list)
        target_len = int(duration_sec * SR)
        if len(full) < target_len:
            reps = int(np.ceil(target_len / len(full)))
            full = np.tile(full, reps)
        return full[:target_len]

    # ── WAVEGUIDE 波导管乐渲染 ──

    def _render_waveguide(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用数字波导管逐音符渲染管乐音色。

        engine_params:
            instrument: str (默认 "clarinet")
            breath: float (可选)
            embouchure: float (可选)
            bell_openness: float (可选)
            volume: float (可选)
        """
        from ..core.waveguide import WaveguideVoice, render_waveguide

        params = getattr(pattern, 'engine_params', {}) or {}
        instrument_name = params.get("instrument", "clarinet")

        beat_dur = 60.0 / max(pattern.bpm, 1)
        total_beats = sum(pattern.durations)
        loops = max(1, int(duration_sec / (total_beats * beat_dur))) if pattern.loop else 1

        samples_list: List[np.ndarray] = []
        for _ in range(loops):
            for i, note in enumerate(pattern.notes):
                dur = pattern.durations[i] * beat_dur
                if note is None:
                    n_samp = max(1, int(dur * SR))
                    samples_list.append(np.zeros(n_samp, dtype=np.float64))
                else:
                    freq = note_to_freq(note)
                    try:
                        voice = WaveguideVoice.preset(
                            instrument_name, freq, duration=dur,
                        )
                        # 允许覆盖演奏参数
                        for key in ("breath", "embouchure", "bell_openness", "volume"):
                            if key in params:
                                setattr(voice, key, params[key])
                        sig = render_waveguide(voice)
                    except ValueError:
                        logger.warning(
                            f"  波导管乐器 '{instrument_name}' 不存在，"
                            f"fallback 到 clarinet"
                        )
                        voice = WaveguideVoice.preset("clarinet", freq, duration=dur)
                        sig = render_waveguide(voice)
                    samples_list.append(sig)

        if not samples_list:
            return np.zeros(int(duration_sec * SR), dtype=np.float64)

        full = np.concatenate(samples_list)
        target_len = int(duration_sec * SR)
        if len(full) < target_len:
            reps = int(np.ceil(target_len / len(full)))
            full = np.tile(full, reps)
        return full[:target_len]

    # ── GRANULAR 粒子合成渲染 ──

    # 引擎参数中的预设名 → GRAIN_PRESETS_BY_NAME 中的预设名映射
    _GRANULAR_PRESET_NAME_MAP: Dict[str, str] = {
        "ethereal_pad": "ethereal_pad",
        "wind_ambient": "wind_ambient",
        "water_texture": "water_texture",
        "sci_fi": "sci_fi_drone",
        "magical_chime": "magic_sparkle",
        "fire_crackle": "fire_crackle",
    }

    def _render_granular(
        self,
        pattern: MusicPattern,
        duration_sec: float,
    ) -> np.ndarray:
        """使用粒子合成器整轨渲染（纹理合成，非逐音符）。

        engine_params:
            preset: str (默认 "ethereal_pad")
            density: float (可选)
            pitch_shift: float (可选)
        """
        from ..core.granular import (
            GranularSynth, GrainCloud, GRAIN_PRESETS_BY_NAME,
        )

        params = getattr(pattern, 'engine_params', {}) or {}
        preset_name = params.get("preset", "ethereal_pad")
        mapped_name = self._GRANULAR_PRESET_NAME_MAP.get(
            preset_name, "ethereal_pad"
        )

        if mapped_name in GRAIN_PRESETS_BY_NAME:
            cloud = GRAIN_PRESETS_BY_NAME[mapped_name].cloud
            # 允许覆盖关键参数
            if "density" in params:
                cloud.density = params["density"]
            if "pitch_shift" in params:
                cloud.pitch_shift = params["pitch_shift"]
        else:
            logger.warning(
                f"  粒子预设 '{mapped_name}' 不存在，使用默认 GrainCloud"
            )
            cloud = GrainCloud()

        gs = GranularSynth(sample_rate=SR)
        return gs.synthesize(cloud, duration_sec)

    # ── Automation 应用 ──

    def _apply_automation_to_stem(
        self,
        audio: np.ndarray,
        pattern: MusicPattern,
    ) -> np.ndarray:
        """对单个 stem 应用 automation 配置。

        支持:
            filter_sweep: 滤波器扫频效果
            volume_curve: 音量包络自动化

        Args:
            audio: 渲染后的音频数组
            pattern: 对应的 MusicPattern（含 automation 字段）

        Returns:
            自动化处理后的音频数组
        """
        automation_config = getattr(pattern, 'automation', None)
        if not automation_config:
            return audio

        try:
            from ..music.automation import (
                AutomationLane, apply_filter_sweep, apply_volume_automation,
            )

            duration = len(audio) / SR
            result = audio.copy()

            # Filter sweep
            if 'filter_sweep' in automation_config:
                fs = automation_config['filter_sweep']
                start_hz = fs.get('start_hz', 20000)
                end_hz = fs.get('end_hz', 400)
                mid_hz = fs.get('mid_hz', start_hz)
                mid_time_ratio = fs.get('mid_time_ratio', 0.5)
                interpolate = fs.get('interpolate', 'smooth')

                sweep = AutomationLane("cutoff", [
                    (0.0, start_hz),
                    (duration * mid_time_ratio, mid_hz),
                    (duration, end_hz),
                ], interpolate=interpolate)

                result = apply_filter_sweep(
                    result,
                    sweep,
                    filter_type=fs.get('type', 'lowpass'),
                    q=fs.get('q', 1.0),
                )
                logger.debug(
                    f"  应用 filter_sweep: {start_hz}Hz → {mid_hz}Hz → {end_hz}Hz "
                    f"(q={fs.get('q', 1.0)})"
                )

            # Volume curve
            if 'volume_curve' in automation_config:
                vc = automation_config['volume_curve']
                lane = AutomationLane(
                    "volume",
                    vc['points'],
                    interpolate=vc.get('interpolate', 'smooth'),
                )
                result = apply_volume_automation(result, lane)
                logger.debug("  应用 volume_curve")

            return result
        except Exception as e:
            logger.warning(f"  Automation 应用失败: {e}")
            return audio

    # ── Phase 3: 混音辅助 ──

    def _apply_mix_assist(
        self,
        stems: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """应用 auto_level 和 freq_slot_allocator。

        Args:
            stems: 原始分轨

        Returns:
            混音辅助后的分轨
        """
        if not stems:
            return stems

        try:
            from ..effects.mix_assist import auto_level, freq_slot_allocator

            # 自动电平平衡
            target_rms = -18.0
            if self._style and self._style.mix_params:
                target_rms = self._style.mix_params.get(
                    "target_rms_db", -18.0
                )

            stems = auto_level(stems, target_rms_db=target_rms)

            # 频率避让建议（仅记录日志，不做硬修改以保留可听性）
            suggestions = freq_slot_allocator(stems)
            if suggestions:
                logger.info(f"  Phase 3: 频率避让建议 — {len(suggestions)} 条")
                for track_name, eq_slots in suggestions.items():
                    for freq, gain, q in eq_slots:
                        logger.debug(
                            f"    {track_name}: {freq:.0f}Hz {gain:+.1f}dB Q={q:.1f}"
                        )
        except Exception as e:
            logger.warning(f"  混音辅助失败: {e}")

        return stems

    # ── Phase 4: 编排渲染 ──

    def _render_arrangement(
        self,
        tracks: MultiTrackPattern,
        stems: Dict[str, np.ndarray],
    ) -> np.ndarray:
        """使用 SongArrangement + SongMixer 进行编排渲染。

        如果乐器池有 drum 轨，也加入 stems。

        Returns:
            float64 混音数组
        """
        try:
            arrangement = self._build_arrangement(tracks)
            mixer = self._build_mixer(tracks, stems)
            arrangement.mixer = mixer
            from .arrangement import render_song
            return render_song(arrangement)
        except Exception as e:
            logger.warning(f"  编排渲染失败，回退到直接混合: {e}")
            return self._fallback_mix(stems)

    def _build_arrangement(self, tracks: MultiTrackPattern):
        """将 MultiTrackPattern 转为 SongArrangement。"""
        from .arrangement import SongArrangement, Section

        # 确定曲式
        template_name = "pop"
        if self._style and self._style.arrangement_template:
            template_name = self._style.arrangement_template

        arrangement = SongArrangement(
            name=self.pool.name,
            bpm=self.pool.bpm,
            key=self.pool.key,
            global_volume=self.pool.global_volume,
        )

        # 确定 sections / bars
        if self.pool.config.sections:
            section_names = self.pool.config.sections
            section_bars = (
                self.pool.config.section_bars
                or [8] * len(section_names)
            )
        else:
            from .arrangement import create_song_template
            template = create_song_template(template_name)
            section_names = [s.name for s in template.sections]
            section_bars = [s.bars for s in template.sections]

        # 为每个 section 分配 music patterns
        music_patterns = list(tracks.music_tracks)
        drum_pattern = tracks.drum_track

        for i, (name, bars) in enumerate(zip(section_names, section_bars)):
            arrangement.add_section(
                name=name,
                bars=bars,
                music_patterns=music_patterns,
                drum_pattern=drum_pattern,
            )

        if self.pool.master_chain is not None:
            arrangement.master_chain = self.pool.master_chain

        return arrangement

    def _build_mixer(
        self,
        tracks: MultiTrackPattern,
        stems: Dict[str, np.ndarray],
    ):
        """构建按角色分 Bus 的 SongMixer。"""
        from .arrangement import SongMixer
        from ..effects.chain import EffectChain

        mixer = SongMixer(master_volume=self.pool.global_volume)

        # 按角色分组
        drum_indices: List[int] = []
        bass_indices: List[int] = []
        melody_indices: List[int] = []
        other_indices: List[int] = []

        for i, track in enumerate(tracks.music_tracks):
            role = getattr(track, "pool_role", None)
            if role == "bass":
                bass_indices.append(i)
            elif role in ("melody", "chord", "pad", "fx"):
                melody_indices.append(i)
            else:
                other_indices.append(i)

        # 如果 drum 存在，作为最后 track
        drum_track_idx = len(tracks.music_tracks)
        if tracks.drum_track is not None:
            drum_indices.append(drum_track_idx)

        # 创建 Bus
        if drum_indices:
            mixer.add_bus(
                "DrumBus",
                drum_indices,
                volume=0.9,
                effect_chain=EffectChain(lp_filter_hz=12000.0),
            )
        if bass_indices:
            mixer.add_bus(
                "BassBus",
                bass_indices,
                volume=0.85,
                effect_chain=EffectChain(lp_filter_hz=500.0),
            )
        if melody_indices:
            reverb_mix = 0.2
            if self._style and self._style.mix_params:
                reverb_mix = self._style.mix_params.get("reverb_mix", 0.2)
            mixer.add_bus(
                "MelodyBus",
                melody_indices,
                volume=0.8,
                effect_chain=EffectChain(reverb_mix=reverb_mix),
            )

        if self._style and self._style.mix_params:
            compression_ratio = self._style.mix_params.get("compression_ratio", 2.0)
            from ..effects.dynamics import CompressorParams
            mixer.master_chain = EffectChain(
                compressor=CompressorParams(
                    threshold_db=-20.0,
                    ratio=compression_ratio,
                    attack_ms=5.0,
                    release_ms=100.0,
                    makeup_db=2.0,
                ),
            )

        return mixer

    # ── 回退混合 ──

    def _fallback_mix(self, stems: Dict[str, np.ndarray]) -> np.ndarray:
        """简单直接混合（当编排渲染失败时使用）。"""
        target_len = int(self.duration_sec * SR)
        mix_buffer = np.zeros(target_len, dtype=np.float64)

        for name, audio in stems.items():
            min_len = min(len(audio), target_len)
            mix_buffer[:min_len] += audio[:min_len]

        peak = np.max(np.abs(mix_buffer))
        if peak > 0:
            mix_buffer = mix_buffer / peak * 0.95
        mix_buffer = np.clip(mix_buffer, -1.0, 1.0)
        return mix_buffer.astype(np.float32)

    # ── Phase 5: 母带 ──

    def _apply_master_chain(self, audio: np.ndarray) -> np.ndarray:
        """应用母带效果链 + 归一化。

        Args:
            audio: 混音后音频

        Returns:
            float32 母带后音频
        """
        result = audio.astype(np.float64)

        # 全局音量
        result *= self.pool.global_volume

        # Pool 级别的 master_chain
        if self.pool.master_chain is not None:
            try:
                from ..effects.chain import process_effects
                result = process_effects(result, self.pool.master_chain)
            except Exception as e:
                logger.warning(f"  母带处理失败: {e}")

        # 归一化到目标 dBFS
        target_amp = 10 ** (NORMALIZE_DBFS / 20.0)
        peak = np.max(np.abs(result))
        if peak > 0:
            result = result * (target_amp / peak)
        result = np.clip(result, -1.0, 1.0)

        # NaN/Inf 检查
        result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)

        return result.astype(np.float32)
