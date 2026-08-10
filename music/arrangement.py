"""
歌曲编排系统 —— SongArrangement + 段落管理 + 完整渲染管线
===========================================================

将多个 MusicPattern / DrumPattern 变体按时间线组织为完整歌曲：
  Intro → Verse → Chorus → Bridge → Outro

核心能力:
  - Section: 独立段落，可指定不同的旋律/鼓点/BPM/效果
  - Transition: 段落间过渡（crossfade / fill / silence）
  - SongArrangement: 声明式整曲定义
  - render_song(): 完整渲染管线
  - TrackChannel: 音轨级别的独立效果链 + 声像 + 音量

用法:
  >>> from bloodmusic.music.arrangement import SongArrangement, Section, render_song
  >>> song = SongArrangement(name="my_song", bpm=120)
  >>> song.add_section("intro", 4, [melody_intro], drum_intro)
  >>> song.add_section("verse", 8, [melody_verse], drum_verse)
  >>> song.add_section("chorus", 8, [melody_chorus, bass], drum_chorus)
  >>> audio = render_song(song)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Callable

from ..core.constants import SR
from ..effects.chain import EffectChain, process_effects
from .pattern import (
    MusicPattern, DrumPattern, render_pattern_to_array, render_drum_pattern,
)
from .automation import TempoLane  # P1


# ═══════════════════════════════════════════════════════════════════════
# Track Channel — 单轨独立效果链
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TrackChannel:
    """单个音频轨道的独立混音参数。

    每条轨道（旋律/贝斯/鼓等）可以有独立的效果链、音量和声像。
    在 SongArrangement 中，每个 Section 的每条轨道可覆盖默认值。
    """
    volume: float = 1.0
    pan: float = 0.0           # -1.0 (左) ~ 1.0 (右)
    effect_chain: Optional[EffectChain] = None
    mute: bool = False

    def apply(self, audio: np.ndarray) -> np.ndarray:
        """对音频应用通道处理"""
        if self.mute:
            return np.zeros_like(audio)
        result = audio.astype(np.float64) * self.volume
        if self.effect_chain is not None:
            result = process_effects(result, self.effect_chain)
        return result


# ═══════════════════════════════════════════════════════════════════════
# Section — 歌曲段落
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Section:
    """歌曲的一个结构段落。

    Args:
        name: 段落名 ("intro", "verse", "chorus", "bridge", "outro" 等)
        bars: 小节数 (4/4 拍下, 1 小节 = 4 拍)
        music_patterns: 该段落使用的旋律/和声轨道列表
        drum_pattern: 该段落使用的鼓点模式
        bpm: 该段落的 BPM (None = 使用歌曲默认 BPM)
        track_channels: 按轨道索引指定的独立混音参数
                        例: {0: TrackChannel(volume=0.8, effect_chain=...)}
        master_lp_cutoff: 全段落低通滤波截止频率 (用于 build-up 闷声等)
        volume: 段落级主音量覆盖
    """
    name: str
    bars: int
    music_patterns: List[MusicPattern] = field(default_factory=list)
    drum_pattern: Optional[DrumPattern] = None
    bpm: Optional[int] = None
    track_channels: Dict[int, TrackChannel] = field(default_factory=dict)
    master_lp_cutoff: Optional[float] = None
    volume: float = 1.0


# ═══════════════════════════════════════════════════════════════════════
# Transition — 段落间过渡
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Transition:
    """段落间过渡定义。

    type 可选:
        "immediate"  — 直接切换 (默认)
        "crossfade"  — X 小节的交叉淡化
        "fill"       — 鼓花过渡 (需要 fill_pattern)
        "silence"    — 静音间隔
    """
    type: str = "immediate"
    bars: float = 0.5               # 过渡时长 (小节)
    fill_pattern: Optional[DrumPattern] = None  # "fill" 类型使用
    extra_drum_hits: List[Tuple[str, float, float]] = field(default_factory=list)
    # [(track_name, beat_position, velocity), ...] — 过渡加花


# ═══════════════════════════════════════════════════════════════════════
# SongArrangement — 完整歌曲定义
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SongArrangement:
    """完整歌曲的声明式编排。

    Args:
        name: 歌曲名
        bpm: 默认 BPM (各 Section 可覆盖)
        key: 调性标注 (C, Am 等，当前仅作说明)
        time_signature: 拍号 (当前仅支持 4/4)
        sections: 段落列表
        transitions: 段落间过渡列表 (None = 全部 immediate)
        track_channels: 全局默认轨道混音通道
        master_chain: 母带效果链 (应用在整个渲染结果上)
        global_volume: 全局音量
    """
    name: str
    bpm: int = 120
    key: str = "C"
    time_signature: Tuple[int, int] = (4, 4)
    sections: List[Section] = field(default_factory=list)
    transitions: Optional[List[Optional[Transition]]] = None
    track_channels: Dict[int, TrackChannel] = field(default_factory=dict)
    master_chain: Optional[EffectChain] = None
    mixer: Optional["SongMixer"] = None   # 总线混音器 (可选)
    tempo_lane: Optional["TempoLane"] = None  # BPM 自动化曲线 (P1)
    global_volume: float = 0.9

    def add_section(
        self,
        name: str,
        bars: int,
        music_patterns: List[MusicPattern] = None,
        drum_pattern: Optional[DrumPattern] = None,
        bpm: Optional[int] = None,
        transition: Optional[Transition] = None,
        track_channels: Optional[Dict[int, TrackChannel]] = None,
        master_lp_cutoff: Optional[float] = None,
        volume: float = 1.0,
    ):
        """便捷方法：向歌曲添加一个段落"""
        section = Section(
            name=name,
            bars=bars,
            music_patterns=music_patterns or [],
            drum_pattern=drum_pattern,
            bpm=bpm,
            track_channels=track_channels or {},
            master_lp_cutoff=master_lp_cutoff,
            volume=volume,
        )
        if self.transitions is None:
            self.transitions = []
        self.transitions.append(transition)
        self.sections.append(section)
        return self

    @property
    def total_duration_sec(self) -> float:
        """预估总时长 (秒) — 支持 TempoLane"""
        if self.tempo_lane is not None:
            # 使用 TempoLane 计算总时长
            total_beats = sum(sec.bars * 4.0 for sec in self.sections)
            return self.tempo_lane.beats_to_time(total_beats)

        total = 0.0
        for i, sec in enumerate(self.sections):
            bpm = sec.bpm if sec.bpm is not None else self.bpm
            beat_dur = 60.0 / bpm
            total += sec.bars * 4.0 * beat_dur
            if self.transitions and i < len(self.transitions) and self.transitions[i]:
                trans = self.transitions[i]
                if trans.type in ("crossfade", "fill"):
                    total += trans.bars * 4.0 * beat_dur
                elif trans.type == "silence":
                    total += trans.bars * 4.0 * beat_dur
        return total


# ═══════════════════════════════════════════════════════════════════════
# 核心渲染函数
# ═══════════════════════════════════════════════════════════════════════

def render_song(
    arrangement: SongArrangement,
    master_sr: int = SR,
) -> np.ndarray:
    """渲染完整歌曲为音频数组。

    渲染管线:
      1. 对每个 Section: 渲染所有 melody track + drum track
      2. 应用每轨的 TrackChannel (独立效果链 / 音量 / 声像)
      3. 应用段落级过滤 (master_lp_cutoff)
      4. 拼接所有段落，处理 Transition
      5. 应用母带效果链 (master_chain)
      6. 归一化 + 限幅

    Args:
        arrangement: 歌曲编排定义
        master_sr: 采样率

    Returns:
        渲染完成的立体声音频 (2, n_samples) 或 mono (n_samples,)
    """
    if not arrangement.sections:
        raise ValueError("SongArrangement 至少需要一个 Section")

    # 收集所有轨道的最大数量
    max_tracks = max(
        len(sec.music_patterns) + (1 if sec.drum_pattern else 0)
        for sec in arrangement.sections
    )
    # 检查是否有需要立体声处理的轨道
    has_stereo = _check_stereo_needed(arrangement)

    # 渲染每个段落为独立音频段
    rendered_sections: List[np.ndarray] = []
    section_info: List[dict] = []  # [(start_sample, duration_samples), ...]

    for s_idx, section in enumerate(arrangement.sections):
        # BPM 计算: 优先 TempoLane > section.bpm > arrangement.bpm
        if arrangement.tempo_lane is not None:
            # 计算当前 section 开始时的累计节拍
            beats_before = sum(
                arrangement.sections[i].bars * 4.0 for i in range(s_idx)
            )
            start_time = arrangement.tempo_lane.beats_to_time(beats_before)
            end_beats = beats_before + section.bars * 4.0
            section_dur = arrangement.tempo_lane.beats_to_time(end_beats) - start_time
            sec_bpm = section.bpm if section.bpm is not None else arrangement.bpm
        else:
            sec_bpm = section.bpm if section.bpm is not None else arrangement.bpm
            beat_dur = 60.0 / sec_bpm
            section_dur = section.bars * 4.0 * beat_dur

        beat_dur = 60.0 / sec_bpm
        n_samples = int(section_dur * master_sr)

        sec_audio = np.zeros(n_samples, dtype=np.float64)

        # 如果配置了总线混音器，收集各轨音频用 mixer 混合
        if arrangement.mixer is not None and arrangement.mixer.buses:
            track_dict: Dict[int, np.ndarray] = {}

            for t_idx, pattern in enumerate(section.music_patterns):
                track_audio = render_pattern_to_array(pattern, section_dur)
                channel = section.track_channels.get(
                    t_idx,
                    arrangement.track_channels.get(t_idx, TrackChannel()),
                )
                track_audio = channel.apply(track_audio)
                if has_stereo and channel.pan != 0.0:
                    track_audio = _apply_pan(track_audio, channel.pan)
                track_dict[t_idx] = track_audio

            if section.drum_pattern is not None:
                drum_track_idx = len(section.music_patterns)
                drum_audio = render_drum_pattern(section.drum_pattern, section_dur)
                channel = section.track_channels.get(
                    drum_track_idx,
                    arrangement.track_channels.get(drum_track_idx, TrackChannel()),
                )
                drum_audio = channel.apply(drum_audio)
                if has_stereo and channel.pan != 0.0:
                    drum_audio = _apply_pan(drum_audio, channel.pan)
                track_dict[drum_track_idx] = drum_audio

            sec_audio = arrangement.mixer.mix(track_dict, target_len=n_samples)

        else:
            # 渲染每个旋律轨道
            for t_idx, pattern in enumerate(section.music_patterns):
                track_audio = render_pattern_to_array(pattern, section_dur)

                # 获取轨道通道参数
                channel = section.track_channels.get(
                    t_idx,
                    arrangement.track_channels.get(t_idx, TrackChannel()),
                )
                track_audio = channel.apply(track_audio)

                # 声像处理
                if has_stereo and channel.pan != 0.0:
                    track_audio = _apply_pan(track_audio, channel.pan)

                min_len = min(len(track_audio), n_samples)
                sec_audio[:min_len] += track_audio[:min_len]

            # 渲染鼓点轨道
            if section.drum_pattern is not None:
                drum_track_idx = len(section.music_patterns)
                drum_audio = render_drum_pattern(section.drum_pattern, section_dur)

                channel = section.track_channels.get(
                    drum_track_idx,
                    arrangement.track_channels.get(drum_track_idx, TrackChannel()),
                )
                drum_audio = channel.apply(drum_audio)

                if has_stereo and channel.pan != 0.0:
                    drum_audio = _apply_pan(drum_audio, channel.pan)

                min_len = min(len(drum_audio), n_samples)
                sec_audio[:min_len] += drum_audio[:min_len]

        # 段落级过滤
        if section.master_lp_cutoff is not None:
            from ..effects.filters import apply_lowpass
            sec_audio = apply_lowpass(sec_audio, section.master_lp_cutoff, master_sr)

        # 段落级音量
        sec_audio *= section.volume

        # 检查 NaN/Inf
        sec_audio = np.nan_to_num(sec_audio, nan=0.0, posinf=1.0, neginf=-1.0)

        rendered_sections.append(sec_audio)

    # 处理段落间过渡
    output_chunks = []
    for i, sec_audio in enumerate(rendered_sections):
        transition = (
            arrangement.transitions[i]
            if arrangement.transitions and i < len(arrangement.transitions)
            else None
        )

        if i > 0 and transition is not None:
            prev = rendered_sections[i - 1]
            sec_bpm = (arrangement.sections[i].bpm
                       if arrangement.sections[i].bpm is not None
                       else arrangement.bpm)
            trans_dur_sec = transition.bars * 4.0 * (60.0 / sec_bpm)
            trans_samples = int(trans_dur_sec * master_sr)

            if transition.type == "crossfade":
                # 交叉淡化
                if trans_samples > 0:
                    sec_audio = _apply_crossfade(prev, sec_audio, trans_samples)
                output_chunks.pop()  # 移除上一个已添加的
                output_chunks.append(sec_audio)

            elif transition.type == "fill":
                # 鼓花过渡
                if transition.fill_pattern is not None:
                    fill_audio = render_drum_pattern(
                        transition.fill_pattern, trans_dur_sec
                    )
                    if len(fill_audio) > trans_samples:
                        fill_audio = fill_audio[:trans_samples]
                    elif len(fill_audio) < trans_samples:
                        fill_audio = np.pad(fill_audio, (0, trans_samples - len(fill_audio)))
                    # 合并：前一段尾部 + fill + 后一段
                    tail_len = min(trans_samples, len(prev))
                    prev_tail = prev[-tail_len:] * np.linspace(0.3, 0, tail_len)
                    sec_start = sec_audio[:trans_samples] * np.linspace(0, 1, trans_samples)
                    transition_chunk = np.zeros(trans_samples * 2, dtype=np.float64)
                    transition_chunk[:tail_len] += prev_tail
                    transition_chunk[trans_samples:trans_samples + trans_samples] += sec_start
                    transition_chunk[trans_samples:min(trans_samples * 2, trans_samples + len(fill_audio))] += fill_audio
                    output_chunks.pop()
                    output_chunks.append(transition_chunk)
                output_chunks.append(sec_audio[trans_samples:])

            elif transition.type == "silence":
                silence = np.zeros(trans_samples, dtype=np.float64)
                output_chunks.append(silence)
                output_chunks.append(sec_audio)

            else:  # immediate
                output_chunks.append(sec_audio)
        else:
            output_chunks.append(sec_audio)

    # 拼接所有段落
    full_audio = np.concatenate(output_chunks) if output_chunks else np.zeros(1)

    # 应用母带效果链
    if arrangement.master_chain is not None:
        full_audio = process_effects(full_audio, arrangement.master_chain, master_sr)

    # 归一化 + 限幅
    full_audio *= arrangement.global_volume
    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak * 0.95
    full_audio = np.clip(full_audio, -1.0, 1.0)

    # 检查 NaN
    full_audio = np.nan_to_num(full_audio, nan=0.0, posinf=1.0, neginf=-1.0)

    return full_audio.astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════

def _check_stereo_needed(arrangement: SongArrangement) -> bool:
    """检查是否有轨道需要立体声处理"""
    for sec in arrangement.sections:
        for ch in sec.track_channels.values():
            if ch.pan != 0.0:
                return True
    for ch in arrangement.track_channels.values():
        if ch.pan != 0.0:
            return True
    return False


def _apply_pan(audio: np.ndarray, pan: float) -> np.ndarray:
    """-1 dB 声像法则：单声道 → 带声像的立体声"""
    if pan == 0.0:
        return audio
    pan = np.clip(pan, -1.0, 1.0)
    left_gain = np.cos((pan + 1.0) * np.pi / 4.0)
    right_gain = np.sin((pan + 1.0) * np.pi / 4.0)
    return np.column_stack([audio * left_gain, audio * right_gain])


def _apply_crossfade(
    prev_section: np.ndarray,
    next_section: np.ndarray,
    fade_samples: int,
) -> np.ndarray:
    """在 prev 的尾部和 next 的首部之间做交叉淡化"""
    fade_samples = min(fade_samples, len(prev_section), len(next_section))
    if fade_samples <= 0:
        full = np.concatenate([prev_section, next_section])
        return full

    # 渐变曲线 (等功率 crossfade)
    t = np.linspace(0, np.pi / 2, fade_samples)
    fade_out = np.cos(t)
    fade_in = np.sin(t)

    prev_tail = prev_section[-fade_samples:] * fade_out
    next_head = next_section[:fade_samples] * fade_in

    # 拼接
    result = np.concatenate([
        prev_section[:-fade_samples],
        prev_tail + next_head,
        next_section[fade_samples:],
    ])
    return result


# ═══════════════════════════════════════════════════════════════════════
# Bus 混音系统
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MixBus:
    """混音总线 — 一组轨道分组，独立总处理。

    类似 DAW 中的 Bus/Group 概念：
      - DrumBus: 所有鼓轨道 → 压缩器 → 总输出
      - SynthBus: 所有合成器 → EQ → Chorus → 总输出
    """
    name: str
    track_indices: List[int]       # 该 Bus 包含的轨道索引
    volume: float = 1.0
    effect_chain: Optional[EffectChain] = None

    def process(self, tracks: Dict[int, np.ndarray]) -> np.ndarray:
        """合并该 Bus 的所有轨道并处理"""
        bus_mix = np.zeros(
            max(len(t) for t in tracks.values()) if tracks else 1,
            dtype=np.float64,
        )
        for idx in self.track_indices:
            if idx in tracks:
                min_len = min(len(tracks[idx]), len(bus_mix))
                bus_mix[:min_len] += tracks[idx][:min_len]
        bus_mix *= self.volume
        if self.effect_chain is not None:
            bus_mix = process_effects(bus_mix, self.effect_chain)
        return bus_mix


@dataclass
class SongMixer:
    """完整混音器 — Bus 分组 + 总输出处理。

    用法:
        >>> mixer = SongMixer()
        >>> mixer.add_bus("drums", [0], effect_chain=drum_compressor)
        >>> mixer.add_bus("synths", [1, 2, 3], effect_chain=eq_chain)
        >>> output = mixer.mix(track_dict)
    """
    buses: List[MixBus] = field(default_factory=list)
    master_volume: float = 0.9
    master_chain: Optional[EffectChain] = None

    def add_bus(self, name: str, track_indices: List[int],
                volume: float = 1.0,
                effect_chain: Optional[EffectChain] = None):
        self.buses.append(MixBus(
            name=name,
            track_indices=track_indices,
            volume=volume,
            effect_chain=effect_chain,
        ))
        return self

    def mix(self, tracks: Dict[int, np.ndarray],
            target_len: Optional[int] = None) -> np.ndarray:
        """混合所有轨道。

        Args:
            tracks: {轨道索引: 音频数组}
            target_len: 目标长度 (None = 自动取最长轨)

        Returns:
            混合后的音频
        """
        if target_len is None:
            target_len = max(len(t) for t in tracks.values()) if tracks else 1

        # 处理已分配的 bus
        bused_indices = set()
        master_mix = np.zeros(target_len, dtype=np.float64)

        for bus in self.buses:
            bus_out = bus.process(tracks)
            min_len = min(len(bus_out), target_len)
            master_mix[:min_len] += bus_out[:min_len]
            bused_indices.update(bus.track_indices)

        # 未分配的轨道直接混合
        for idx, track in tracks.items():
            if idx not in bused_indices:
                min_len = min(len(track), target_len)
                master_mix[:min_len] += track[:min_len]

        master_mix *= self.master_volume
        if self.master_chain is not None:
            master_mix = process_effects(master_mix, self.master_chain)

        # 归一化
        peak = np.max(np.abs(master_mix))
        if peak > 0:
            master_mix = master_mix / peak * 0.95
        master_mix = np.clip(master_mix, -1.0, 1.0)

        return master_mix.astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════
# 歌曲模板
# ═══════════════════════════════════════════════════════════════════════

def create_song_template(template_name: str) -> SongArrangement:
    """创建常用歌曲结构模板。

    支持模板:
        "pop"      — Intro → Verse → Chorus → Verse → Chorus → Bridge → Chorus → Outro
        "electronic" — Intro → Build-up → Drop → Break → Build-up → Drop → Outro
        "ambient"  — Intro → Body → Climax → Resolution → Outro
        "lo-fi"    — Intro → Verse → Chorus → Verse → Outro
        "hip-hop"  — Intro → Verse(16) → Hook(8) → Verse(16) → Hook(8) → Outro
    """
    templates = {
        "pop": [("intro", 4), ("verse", 8), ("chorus", 8), ("verse", 8),
                ("chorus", 8), ("bridge", 4), ("chorus", 8), ("outro", 4)],
        "electronic": [("intro", 8), ("build_up", 8), ("drop", 16),
                       ("break", 8), ("build_up", 8), ("drop", 16), ("outro", 8)],
        "ambient": [("intro", 8), ("body", 16), ("climax", 8),
                    ("resolution", 8), ("outro", 8)],
        "lo-fi": [("intro", 4), ("verse", 8), ("chorus", 8),
                  ("verse", 8), ("outro", 4)],
        "hip-hop": [("intro", 4), ("verse", 16), ("hook", 8),
                    ("verse", 16), ("hook", 8), ("outro", 4)],
    }

    if template_name not in templates:
        raise ValueError(
            f"未知模板 '{template_name}'。可选: {list(templates.keys())}"
        )

    song = SongArrangement(name=f"{template_name}_song")
    for name, bars in templates[template_name]:
        song.add_section(name, bars)

    return song
