"""
分轨生成引擎 —— 按角色分派到不同生成策略
==========================================

遍历 InstrumentPool 中的每件乐器，按 InstrumentRole 分派到对应的生成器：
  - melody → markov.py（马尔可夫旋律生成）
  - chord  → harmony.py（和弦进行 + 声部排列）
  - bass   → bass.py（低音合成器）
  - drum   → euclidean.py（欧几里得节奏）
  - pad    → harmony.py + arpeggiator.py（铺底/琶音）
  - fx     → 特殊效果处理

核心方法: generate_all() 返回 MultiTrackPattern。

用法:
    >>> from bloodmusic.music.pool_generator import PoolGenerator
    >>> gen = PoolGenerator(pool, style=some_style)
    >>> multi_track = gen.generate_all(target_bars=32)
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, TYPE_CHECKING

from ..core.oscillator import OscType
from ..core.envelope import EnvShape
from .instrument_pool import InstrumentRole, PoolInstrument, SynthEngine
from .pattern import (
    DrumPattern,
    DrumSoundParams,
    MusicPattern,
    MultiTrackPattern,
)
from .humanize import HumanizeParams

if TYPE_CHECKING:
    from .instrument_pool import InstrumentPool
    from .pool_styles import StylePreset

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# 引擎 → OscType 映射
# ═══════════════════════════════════════════════════════════════════════

_ENGINE_OSC_MAP: Dict[SynthEngine, OscType] = {
    SynthEngine.SUBTRACTIVE: OscType.SAW,
    SynthEngine.FM: OscType.SINE,
    SynthEngine.FM_ADVANCED: OscType.SINE,
    SynthEngine.KARPLUS_STRONG: OscType.TRIANGLE,
    SynthEngine.GRANULAR: OscType.SINE,
    SynthEngine.WAVETABLE: OscType.TRIANGLE,
    SynthEngine.WAVEGUIDE: OscType.SQUARE,
    SynthEngine.NOISE: OscType.NOISE_BROWN,
}


def _get_osc_type(engine: SynthEngine) -> OscType:
    """合成引擎 → 基础振荡器类型。"""
    return _ENGINE_OSC_MAP.get(engine, OscType.SINE)


# ═══════════════════════════════════════════════════════════════════════
# 鼓声预设映射
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_DRUM_SOUNDS: Dict[str, DrumSoundParams] = {
    "kick": DrumSoundParams(
        osc_type=OscType.SINE, pitch_hz=55.0, decay=0.25, volume=0.8,
    ),
    "snare": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=200.0, decay=0.12,
        volume=0.5, hp_hz=800.0,
    ),
    "hihat": DrumSoundParams(
        osc_type=OscType.NOISE_WHITE, pitch_hz=8000.0, decay=0.06,
        volume=0.3, hp_hz=5000.0,
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# PoolGenerator
# ═══════════════════════════════════════════════════════════════════════

class PoolGenerator:
    """分轨生成引擎。

    遍历乐器池中的每件乐器，按其 role 调用对应的生成策略。

    Args:
        pool: 乐器池定义
        style: 风格预设（可选）
    """

    def __init__(
        self,
        pool: "InstrumentPool",
        style: Optional["StylePreset"] = None,
    ):
        self.pool = pool
        self.style = style

        # 设置随机种子
        if pool.config.seed is not None:
            random.seed(pool.config.seed)

    # ── 主入口 ──

    def generate_all(self, target_bars: Optional[int] = None) -> MultiTrackPattern:
        """为乐器池中所有乐器生成分轨。

        Args:
            target_bars: 目标小节数，None=使用 pool.config.target_bars 或 32

        Returns:
            MultiTrackPattern 包含所有生成的分轨
        """
        bars = target_bars or self.pool.config.target_bars or 32
        multi = MultiTrackPattern(
            name=self.pool.name,
            bpm=self.pool.bpm,
        )

        logger.info(
            f"PoolGenerator: 开始生成 {len(self.pool.instruments)} 件乐器, "
            f"{bars} 小节, BPM={self.pool.bpm}"
        )

        for instrument in self.pool.instruments:
            try:
                # 如果 instrument 没有自己的 automation，使用 pool 级别的
                if instrument.automation is None and self.pool.automation is not None:
                    instrument.automation = self.pool.automation
                pattern = self._generate_for_instrument(instrument, bars)
                if pattern is not None:
                    if isinstance(pattern, DrumPattern):
                        multi.drum_track = pattern
                        logger.info(f"  ✅ drum: {instrument.name}")
                    else:
                        pattern.pool_role = instrument.role.value
                        multi.music_tracks.append(pattern)
                        logger.info(
                            f"  ✅ {instrument.role.value}: {instrument.name}"
                        )
            except Exception as e:
                logger.warning(
                    f"  ⚠️ 跳过 {instrument.name} ({instrument.role.value}): {e}",
                    exc_info=True,
                )

        logger.info(
            f"PoolGenerator: 完成 — "
            f"{len(multi.music_tracks)} 旋律轨 + "
            f"{'1' if multi.drum_track else '0'} 鼓轨"
        )
        return multi

    def _generate_for_instrument(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ):
        """按角色分派到具体生成器。"""
        role = instrument.role
        if role == InstrumentRole.MELODY:
            return self.generate_melody(instrument, target_bars)
        elif role == InstrumentRole.CHORD:
            return self.generate_chord(instrument, target_bars)
        elif role == InstrumentRole.BASS:
            return self.generate_bass(instrument, target_bars)
        elif role == InstrumentRole.DRUM:
            return self.generate_drum(instrument, target_bars)
        elif role == InstrumentRole.PAD:
            return self.generate_pad(instrument, target_bars)
        elif role == InstrumentRole.FX:
            return self.generate_fx(instrument, target_bars)
        else:
            logger.warning(f"未知角色: {role}")
            return None

    # ── 角色生成器 ──

    def generate_melody(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> MusicPattern:
        """为 melody 角色生成旋律 MusicPattern。

        使用 markov.py 的马尔可夫链生成旋律线。
        如果 instrument.note_sequence 有值，则使用用户指定的序列。
        """
        style_params = self._resolve_style_params(InstrumentRole.MELODY)

        # 使用现有马尔可夫链生成旋律
        from .markov import (
            MarkovChain,
            MelodyGenerator,
            MelodyGeneratorConfig,
            melody_from_note_string,
            SAMPLE_MELODIES,
        )

        # 构建训练链
        chain = MarkovChain(order=2)
        melodies = [
            melody_from_note_string(s, name=f"sample_{i}")
            for i, s in enumerate(SAMPLE_MELODIES)
        ]
        chain.train_from_melodies(melodies)

        # 配置生成器
        temperature = style_params.get("temperature", 0.8)
        note_density = style_params.get("note_density", 2.0)

        config = MelodyGeneratorConfig(
            markov_order=2,
            temperature=temperature,
            avoid_repeat=2,
            target_bars=target_bars,
            note_density=note_density,
            rest_probability=style_params.get("rest_probability", 0.05),
            min_octave=style_params.get("min_octave", 3),
            max_octave=style_params.get("max_octave", 5),
        )

        # 选择起始音
        from .scale import Scale
        scale_obj = Scale(root=self.pool.key, scale_type=self.pool.scale, octave=4)
        scale_notes = scale_obj.get_notes()
        start_note = scale_notes[0] if scale_notes else "C4"

        # 生成旋律
        gen = MelodyGenerator(chain, config)
        melody = gen.generate(
            start_note=start_note,
            bars=target_bars,
            temperature=temperature,
            seed=self.pool.config.seed,
        )

        # MelodyNote → MusicPattern
        notes: List[Optional[str]] = []
        durations: List[float] = []
        for mn in melody.notes:
            if mn.rest:
                notes.append(None)
            else:
                notes.append(mn.pitch)
            durations.append(mn.duration)

        # 使用 instrument.note_sequence 覆盖（如果有）
        if instrument.note_sequence is not None:
            notes = list(instrument.note_sequence)
            # 确保 durations 匹配
            if len(durations) != len(notes):
                durations = [0.5] * len(notes)

        pattern = MusicPattern(
            name=instrument.name,
            notes=notes,
            durations=durations,
            bpm=self.pool.bpm,
            osc_type=_get_osc_type(instrument.engine),
            volume=instrument.volume * 0.18,
            env_shape=EnvShape.PAD,
            engine=instrument.engine,
            engine_params=instrument.engine_params,
            automation=instrument.automation,
        )

        # 应用乐器预设
        self._apply_preset(pattern, instrument)

        # 应用人性化
        self._apply_humanize(pattern, style_params)

        return pattern

    def generate_chord(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> MusicPattern:
        """为 chord 角色生成和弦 MusicPattern。

        使用 harmony.py 生成和弦进行 + 声部排列。
        """
        style_params = self._resolve_style_params(InstrumentRole.CHORD)

        from .scale import Scale
        scale_obj = Scale(root=self.pool.key, scale_type=self.pool.scale, octave=3)

        # 选择和弦进行
        progression_name = (
            self.pool.config.chord_progression
            or style_params.get("chord_progression", "I-IV-V-I")
        )
        try:
            chords = scale_obj.get_progression(progression_name)
        except Exception:
            chords = scale_obj.get_progression("I-IV-V-I")

        # 生成和弦音符序列
        beats_per_chord = 2
        chord_notes_list: List[List[str]] = []
        flat_notes: List[Optional[str]] = []
        durations: List[float] = []

        total_beats = target_bars * 4
        while sum(durations) < total_beats:
            for chord_notes in chords:
                chord_notes_list.append(chord_notes)
                flat_notes.append(None)  # chord pattern: notes 为空, chords 非空
                durations.append(beats_per_chord)
                if sum(durations) >= total_beats:
                    break

        pattern = MusicPattern(
            name=instrument.name,
            notes=flat_notes,
            durations=durations,
            bpm=self.pool.bpm,
            osc_type=_get_osc_type(instrument.engine),
            volume=instrument.volume * 0.12,
            env_shape=EnvShape.SWELL,
            chords=chord_notes_list[:len(flat_notes)],
            reverb_mix=0.25,
            engine=instrument.engine,
            engine_params=instrument.engine_params,
            automation=instrument.automation,
        )

        self._apply_preset(pattern, instrument)
        self._apply_humanize(pattern, style_params)
        return pattern

    def generate_bass(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> MusicPattern:
        """为 bass 角色生成低音 MusicPattern。

        使用 bass.py 生成低音线。
        """
        style_params = self._resolve_style_params(InstrumentRole.BASS)

        from .scale import Scale
        scale_obj = Scale(root=self.pool.key, scale_type=self.pool.scale, octave=2)
        root_note = scale_obj.get_notes()[0] if scale_obj.get_notes() else "C2"

        # 生成简单的 bass line（基于音阶根音 + 第五音）
        bass_notes: List[Optional[str]] = []
        durations: List[float] = []
        total_beats = target_bars * 4
        beat = 0
        while beat < total_beats:
            # 基本节奏：每拍一个小节
            if beat % 4 == 0:
                bass_notes.append(root_note)  # 根音
            elif beat % 4 == 2:
                # 第五音（尝试）
                try:
                    fifth = scale_obj.get_notes()[
                        min(4, len(scale_obj.get_notes()) - 1)
                    ]
                    bass_notes.append(fifth)
                except Exception:
                    bass_notes.append(root_note)
            else:
                bass_notes.append(root_note)
            durations.append(0.5)
            beat += 0.5

        pattern = MusicPattern(
            name=instrument.name,
            notes=bass_notes,
            durations=durations,
            bpm=self.pool.bpm,
            osc_type=_get_osc_type(instrument.engine),
            volume=instrument.volume * 0.22,
            env_shape=EnvShape.PERCUSSIVE,
            lp_filter_hz=500.0,
            reverb_mix=0.05,
            stereo_width=0.1,
            engine=instrument.engine,
            engine_params=instrument.engine_params,
            automation=instrument.automation,
        )

        # 八度偏移
        if instrument.octave is not None:
            pattern.octave_shifts = [instrument.octave] * len(bass_notes)

        self._apply_preset(pattern, instrument)
        self._apply_humanize(pattern, style_params)
        return pattern

    def generate_drum(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> DrumPattern:
        """为 drum 角色生成打击乐 DrumPattern。

        使用 euclidean.py 生成欧几里得节奏。
        """
        style_params = self._resolve_style_params(InstrumentRole.DRUM)

        from .euclidean import euclidean_rhythm

        # 从风格参数获取节奏预设
        preset_name = style_params.get("preset_name", "four_on_floor")
        pulse_density = style_params.get("pulse_density", 0.5)
        bpm_range = style_params.get("bpm_range", (100, 140))

        # 根据密度计算脉冲数
        steps = 16
        kick_pulses = min(steps, max(1, int(steps * pulse_density * 0.7)))
        snare_pulses = min(steps, max(1, int(steps * pulse_density * 0.5)))
        hihat_pulses = min(steps, max(1, int(steps * pulse_density * 1.2)))

        kick_pattern = euclidean_rhythm(kick_pulses, steps, 0)
        snare_pattern = euclidean_rhythm(snare_pulses, steps, 4)
        hihat_pattern = euclidean_rhythm(hihat_pulses, steps, 0)

        drum = DrumPattern(
            name=instrument.name,
            steps=steps,
            bpm=self.pool.bpm,
            tracks={
                "kick": kick_pattern,
                "snare": snare_pattern,
                "hihat": hihat_pattern,
            },
            sounds={
                "kick": DrumSoundParams(
                    osc_type=OscType.SINE,
                    pitch_hz=55.0,
                    decay=0.2,
                    volume=instrument.volume * 0.8,
                ),
                "snare": DrumSoundParams(
                    osc_type=OscType.NOISE_WHITE,
                    pitch_hz=200.0,
                    decay=0.12,
                    volume=instrument.volume * 0.5,
                    hp_hz=800.0,
                ),
                "hihat": DrumSoundParams(
                    osc_type=OscType.NOISE_WHITE,
                    pitch_hz=8000.0,
                    decay=0.06,
                    volume=instrument.volume * 0.3,
                    hp_hz=5000.0,
                ),
            },
        )
        return drum

    def generate_pad(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> MusicPattern:
        """为 pad 角色生成铺底 MusicPattern。

        使用 harmony.py + arpeggiator.py 生成长时域铺底/琶音。
        """
        style_params = self._resolve_style_params(InstrumentRole.PAD)

        from .scale import Scale
        from .arpeggiator import Arpeggiator, ArpMode, generate_arpeggio

        scale_obj = Scale(root=self.pool.key, scale_type=self.pool.scale, octave=3)
        scale_notes = scale_obj.get_notes()

        # 取音阶前几个音符作为和弦
        chord_notes = scale_notes[:min(3, len(scale_notes))]

        # 琶音模式
        arp_mode_str = style_params.get("arpeggio_mode", "up_down")
        arp_mode_map = {
            "up": ArpMode.UP,
            "down": ArpMode.DOWN,
            "up_down": ArpMode.UP_DOWN,
            "random": ArpMode.RANDOM,
        }
        arp_mode = arp_mode_map.get(arp_mode_str, ArpMode.UP_DOWN)

        octaves = style_params.get("octaves", 1)

        arp = Arpeggiator(mode=arp_mode, octaves=octaves, gate=0.9)
        arpeggio = generate_arpeggio(arp, chord_notes, bpm=self.pool.bpm)

        pad_notes: List[Optional[str]] = []
        durations: List[float] = []
        for note, dur_beats in arpeggio:
            pad_notes.append(note)
            durations.append(dur_beats / (60.0 / self.pool.bpm))

        # 循环到目标小节数
        total_beats = target_bars * 4
        while sum(durations) < total_beats:
            pad_notes.extend(pad_notes[:len(arpeggio)])
            for _, dur_beats in arpeggio:
                durations.append(dur_beats / (60.0 / self.pool.bpm))

        volume_mult = style_params.get("volume_mult", 0.5)

        pattern = MusicPattern(
            name=instrument.name,
            notes=pad_notes,
            durations=durations,
            bpm=self.pool.bpm,
            osc_type=_get_osc_type(instrument.engine),
            volume=instrument.volume * 0.08 * volume_mult,
            env_shape=EnvShape.SWELL,
            reverb_mix=style_params.get("reverb_mix", 0.5),
            reverb_decay=2.0,
            lp_filter_hz=4000.0,
            stereo_width=0.8,
            engine=instrument.engine,
            engine_params=instrument.engine_params,
            automation=instrument.automation,
        )

        self._apply_preset(pattern, instrument)
        self._apply_humanize(pattern, style_params)
        return pattern

    def generate_fx(
        self,
        instrument: PoolInstrument,
        target_bars: int,
    ) -> MusicPattern:
        """为 fx 角色生成特效 MusicPattern。

        生成简单的氛围音或低频 drone。
        """
        style_params = self._resolve_style_params(InstrumentRole.FX)
        if not style_params.get("enabled", False):
            # FX 被禁用，返回静音模式
            return MusicPattern(
                name=instrument.name,
                notes=[None],
                durations=[float(target_bars * 4)],
                bpm=self.pool.bpm,
                osc_type=OscType.SINE,
                volume=0.0,
                env_shape=EnvShape.PAD,
                engine=instrument.engine,
                engine_params=instrument.engine_params,
                automation=instrument.automation,
            )

        from .scale import Scale
        scale_obj = Scale(root=self.pool.key, scale_type=self.pool.scale, octave=2)
        root_note = scale_obj.get_notes()[0] if scale_obj.get_notes() else "C2"

        # 生成长音 drone
        fx_notes = [root_note]
        durations = [float(target_bars * 4)]

        pattern = MusicPattern(
            name=instrument.name,
            notes=fx_notes,
            durations=durations,
            bpm=self.pool.bpm,
            osc_type=OscType.SINE,
            volume=instrument.volume * 0.06,
            env_shape=EnvShape.SWELL,
            reverb_mix=0.7,
            reverb_decay=3.0,
            lp_filter_hz=2000.0,
            stereo_width=0.9,
            vibrato_rate=0.5,
            vibrato_depth=1.0,
            engine=instrument.engine,
            engine_params=instrument.engine_params,
            automation=instrument.automation,
        )

        self._apply_preset(pattern, instrument)
        self._apply_humanize(pattern, style_params)
        return pattern

    # ── 风格参数解析 ──

    def _resolve_style_params(self, role: InstrumentRole) -> dict:
        """按角色查找风格参数覆盖。

        Args:
            role: 乐器角色

        Returns:
            合并了 style 覆盖的参数字典
        """
        params: dict = {}

        if self.style is not None and self.style.role_params:
            role_key = role.value
            if role_key in self.style.role_params:
                params.update(self.style.role_params[role_key])

        # diversity 影响 temperature
        if "temperature" in params:
            base_temp = params["temperature"]
            diversity = self.pool.config.diversity
            # diversity 0=保守(temp低), 0.5=默认, 1=最大随机(temp高)
            adjusted = base_temp + (diversity - 0.5) * 2.0
            params["temperature"] = max(0.1, min(3.0, adjusted))

        return params

    # ── 辅助方法 ──

    def _apply_preset(
        self,
        pattern: MusicPattern,
        instrument: PoolInstrument,
    ) -> None:
        """将 instruments.py 中的预设应用到 MusicPattern。"""
        if instrument.preset is None:
            return
        try:
            from .instruments import get_instrument
            preset = get_instrument(instrument.preset)
            preset.apply_to(pattern)
            # 保持 pool instrument 的 volume
            pattern.volume = preset.volume * instrument.volume
            logger.debug(f"  应用预设: {instrument.preset} → {instrument.name}")
        except (KeyError, Exception) as e:
            logger.warning(
                f"  预设 '{instrument.preset}' 应用失败: {e}，使用默认音色"
            )

    def _apply_humanize(
        self,
        pattern: MusicPattern,
        style_params: dict,
    ) -> None:
        """根据配置和风格参数应用人性化。"""
        if not self.pool.config.humanize:
            return

        humanize_level = style_params.get("humanize_level", "subtle")
        humanize_map = {
            "none": HumanizeParams.none(),
            "subtle": HumanizeParams.subtle(),
            "natural": HumanizeParams.natural(),
            "groovy": HumanizeParams.groovy(),
            "human": HumanizeParams.human(),
        }
        hp = humanize_map.get(humanize_level, HumanizeParams.subtle())
        if self.pool.config.seed is not None:
            hp.seed = self.pool.config.seed
        pattern.humanize_params = hp
