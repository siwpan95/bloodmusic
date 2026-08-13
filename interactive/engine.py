"""
实时音乐引擎 — 游戏循环集成接口
================================

基于指导第 6.7 节：将状态机、分层混音器、横排排序器、参数映射器
整合为统一引擎，提供游戏循环每帧调用的 update() → process_frame() 接口。

用法:
    engine = RealtimeMusicEngine()
    engine.setup_base_layers(["ambient", "harmony", "rhythm", "lead"])
    
    def game_loop():
        while running:
            dt = clock.tick(60) / 1000.0
            game_state = {"hp_ratio": player.hp / player.max_hp, "enemy_count": len(enemies), ...}
            engine.update(game_state, dt)
            audio_frame = engine.process_frame()
            audio_device.write(audio_frame)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import time

from bloodmusic.interactive.state_machine import (
    MusicState, MusicStateMachine, StateParams, TransitionParams,
)
from bloodmusic.interactive.layer_mixer import (
    LayerRole, MusicLayer, LayerMixerConfig, VerticalLayerMixer,
)
from bloodmusic.interactive.sequencer import (
    MusicSegment, SegmentCategory, BranchRule, HorizontalSequencer,
)
from bloodmusic.interactive.parameter_mapper import (
    ParameterMapper, ParameterMapping, MappingSet,
    COMBAT_MAPPINGS, EXPLORE_MAPPINGS, STEALTH_MAPPINGS,
)


@dataclass
class EngineConfig:
    """引擎配置"""
    sample_rate: int = 44100
    buffer_size: int = 512
    master_volume: float = 0.7

    # 音乐层模板
    layer_templates: Dict[str, MusicLayer] = field(default_factory=dict)

    # 默认使用战斗映射
    mapping_set: str = "combat"

    # 过渡参数
    transition_duration: float = 3.0

    # 状态→强度映射
    state_intensity_map: Dict[MusicState, float] = field(default_factory=lambda: {
        MusicState.EXPLORE: 0.15,
        MusicState.TENSION: 0.45,
        MusicState.COMBAT_LOW: 0.65,
        MusicState.COMBAT_HIGH: 0.9,
        MusicState.VICTORY: 0.05,
        MusicState.DEFEAT: 0.1,
        MusicState.TRANSITION: 0.3,
        MusicState.PAUSE: 0.05,
    })


# ============================================================
# 默认层模板
# ============================================================

DEFAULT_LAYER_TEMPLATES = {
    "ambient": MusicLayer(
        role=LayerRole.AMBIENT, name="ambient",
        intensity_range=(0.0, 1.0),
        volume_curve=[(0.0, 0.6), (0.3, 0.5), (0.7, 0.3), (1.0, 0.2)],
        osc_type="sine", base_octave=2,
        notes=["C", "G"],
        filter_open_curve=[(0.0, 0.3), (1.0, 0.8)],
        reverb_curve=[(0.0, 0.6), (1.0, 0.3)],
    ),
    "harmony": MusicLayer(
        role=LayerRole.HARMONY, name="harmony",
        intensity_range=(0.1, 1.0),
        volume_curve=[(0.0, 0.0), (0.3, 0.6), (0.7, 0.8), (1.0, 0.7)],
        osc_type="triangle", base_octave=3,
        notes=["C", "Eb", "G"],
        filter_open_curve=[(0.0, 0.5), (1.0, 1.0)],
        reverb_curve=[(0.0, 0.4), (1.0, 0.2)],
    ),
    "rhythm": MusicLayer(
        role=LayerRole.RHYTHM, name="rhythm",
        intensity_range=(0.3, 1.0),
        volume_curve=[(0.0, 0.0), (0.5, 0.4), (0.8, 0.7), (1.0, 0.9)],
        osc_type="noise_white", base_octave=2,
        notes=["C"],
        rhythm_pattern=[0.25],
        filter_open_curve=[(0.0, 0.1), (1.0, 1.0)],
        reverb_curve=[(0.0, 0.1), (1.0, 0.05)],
    ),
    "lead": MusicLayer(
        role=LayerRole.MELODY, name="lead",
        intensity_range=(0.4, 1.0),
        volume_curve=[(0.0, 0.0), (0.5, 0.3), (0.7, 0.6), (1.0, 0.8)],
        osc_type="saw", base_octave=4,
        notes=["Eb", "F", "G", "Bb"],
        filter_open_curve=[(0.0, 0.4), (1.0, 1.0)],
        reverb_curve=[(0.0, 0.3), (1.0, 0.15)],
    ),
    "accent": MusicLayer(
        role=LayerRole.ACCENT, name="accent",
        intensity_range=(0.6, 1.0),
        volume_curve=[(0.0, 0.0), (0.7, 0.2), (0.9, 0.6), (1.0, 0.9)],
        osc_type="square", base_octave=5,
        notes=["G", "Bb", "C"],
        filter_open_curve=[(0.0, 0.2), (1.0, 1.0)],
        reverb_curve=[(0.0, 0.1), (1.0, 0.0)],
    ),
}


# ============================================================
# 引擎核心
# ============================================================

class RealtimeMusicEngine:
    """
    实时音乐引擎 — 游戏循环集成的主接口

    三层架构:
        1. 状态机 (MusicStateMachine) — 决定"什么情绪"
        2. 参数映射器 (ParameterMapper) — 游戏参数→音乐参数
        3. 层混音器 (VerticalLayerMixer) — 多轨合成

    可选: 横向排序器 (HorizontalSequencer) — 预制片段拼接

    用法:
        engine = RealtimeMusicEngine()

        # 游戏初始化
        engine.setup_default_layers()

        # 游戏循环
        while game_running:
            dt = clock.tick(60) / 1000.0
            game_state = {
                "hp_ratio": player.hp / player.max_hp,
                "enemy_count": len(enemies),
                "speed": player.velocity,
                "intensity": combat_manager.intensity,
            }
            engine.update(game_state, dt)
            audio_frame = engine.process_frame()
            audio_output.write(audio_frame)
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()

        # 子引擎
        self.state_machine = MusicStateMachine()
        self.mapper = ParameterMapper()
        self.mixer = VerticalLayerMixer(LayerMixerConfig(
            sample_rate=self.config.sample_rate,
            buffer_size=self.config.buffer_size,
            master_volume=self.config.master_volume,
        ))
        self.sequencer: Optional[HorizontalSequencer] = None

        # 运行时状态
        self._initialized: bool = False
        self._active_mappings: Dict[str, float] = {}   # 当前音乐参数
        self._layer_audio_cache: Dict[str, np.ndarray] = {}
        self._t: float = 0.0                           # 引擎时间
        self._beat_count: int = 0

        # 回调
        self._on_state_change: List[Callable] = []
        self._on_beat: List[Callable] = []

    # ── 初始化 ──

    def setup_default_layers(self):
        """使用默认 5 层模板初始化"""
        for name, layer in DEFAULT_LAYER_TEMPLATES.items():
            self.mixer.add_layer(layer)

    def setup_layers_from_templates(self, templates: Dict[str, MusicLayer]):
        """从自定义模板初始化层"""
        for name, layer in templates.items():
            self.mixer.add_layer(layer)

    def setup_layer_generator(self, generator: Callable):
        """
        设置全局层音频生成器。
        (layer, intensity, n_samples, sr) -> np.ndarray
        """
        for layer in self.mixer._layers:
            self.mixer.set_layer_generator(layer.name, generator)

    def setup_sequencer(
        self,
        segments: List[MusicSegment],
        rules: Optional[List[BranchRule]] = None,
    ):
        """初始化横向排序器（预制片段模式）"""
        self.sequencer = HorizontalSequencer(
            sample_rate=self.config.sample_rate,
            buffer_size=self.config.buffer_size,
        )
        for seg in segments:
            self.sequencer.add_segment(seg)
        if rules:
            for rule in rules:
                self.sequencer.add_branch_rule(rule)

    def start(self, initial_state: MusicState = MusicState.EXPLORE):
        """启动引擎"""
        self.state_machine.start(initial_state)

        # 加载默认映射集
        self.mapper.load_mapping_set(COMBAT_MAPPINGS)
        self.mapper.load_mapping_set(EXPLORE_MAPPINGS)

        self._initialized = True

    # ── 钩子 ──

    def on_state_change(self, callback: Callable):
        """状态切换回调: (old_state, new_state) -> None"""
        self._on_state_change.append(callback)

    def on_beat(self, callback: Callable):
        """节拍回调: (beat_number) -> None"""
        self._on_beat.append(callback)

    # ── 游戏循环集成 ──

    def update(self, game_state: Dict[str, float], dt: float = 0.016):
        """
        每帧更新 — 从游戏状态推导音乐状态和参数。

        典型 game_state:
        {
            "hp_ratio": 0.75,        # HP 比例 (0=死亡, 1=满血)
            "enemy_count": 3,        # 敌人数量
            "speed": 4.0,            # 玩家速度
            "intensity": 0.5,        # 战斗强度
            "danger_sense": 0.1,     # 危险感知
            "depth": 0.3,            # 地牢深度
            "boss_active": False,    # BOSS 是否激活
        }
        """
        if not self._initialized:
            self.start()

        self._t += dt

        # 1. 确定目标音乐状态
        target_state = self._determine_state(game_state)

        # 2. 如果状态发生了变化，请求转换
        current_state = self.state_machine.current_state
        if target_state != current_state:
            self.state_machine.transition_to(
                target_state,
                TransitionParams(duration=self.config.transition_duration),
            )
            for cb in self._on_state_change:
                try:
                    cb(current_state, target_state)
                except Exception:
                    pass

        # 3. 更新状态机（平滑过渡参数）
        state_params = self.state_machine.tick(dt)

        # 4. 参数映射
        mapped = self.mapper.map(game_state, dt)
        self._active_mappings.update(mapped)

        # 5. 合并状态参数和映射参数
        intensity = self._compute_intensity(game_state, state_params)
        self.mixer.set_intensity(intensity)

        # 6. 更新混音器平滑值
        self.mixer.tick(dt)

        # 7. 节拍追踪
        bpm = mapped.get("bpm", state_params.bpm if state_params else 120)
        beats_per_sec = bpm / 60.0
        current_beat = int(self._t * beats_per_sec)
        if current_beat > self._beat_count:
            self._beat_count = current_beat
            for cb in self._on_beat:
                try:
                    cb(current_beat)
                except Exception:
                    pass

        # 8. 横向排序器更新
        if self.sequencer is not None:
            self.sequencer.update(game_state, dt)

    def process_frame(self) -> np.ndarray:
        """处理一帧音频输出 (n_samples,)"""
        if self.sequencer is not None:
            return self.sequencer.process_frame()

        # 生成层音频
        def _generate(layer: MusicLayer, intensity: float, n_samples: int, sr: int):
            return self._synthesize_layer(layer, intensity, n_samples, sr)

        return self.mixer.process_frame(generator_callback=_generate)

    # ── 查询 ──

    @property
    def current_state(self) -> Optional[MusicState]:
        return self.state_machine.current_state

    @property
    def active_params(self) -> Dict[str, float]:
        """当前活跃的音乐参数"""
        sp = self.state_machine.active_params
        result = dict(self._active_mappings)
        if sp:
            result.update({
                "bpm": sp.bpm,
                "tension": sp.tension,
                "density": sp.density,
                "dynamic_range": sp.dynamic_range,
                "reverb_mix": sp.reverb_mix,
                "filter_openness": sp.filter_openness,
                "distortion_amount": sp.distortion_amount,
                "pulse_weight": sp.pulse_weight,
            })
        return result

    @property
    def is_transitioning(self) -> bool:
        return self.state_machine.is_transitioning

    # ── 内部 ──

    def _determine_state(self, game_state: Dict[str, float]) -> MusicState:
        """从游戏状态推导音乐状态"""
        hp = game_state.get("hp_ratio", 1.0)
        enemy_count = game_state.get("enemy_count", 0)
        boss_active = game_state.get("boss_active", False)
        intensity = game_state.get("intensity", 0.0)
        game_over = game_state.get("game_over", False)
        victory = game_state.get("victory", False)

        if game_over:
            return MusicState.DEFEAT
        if victory:
            return MusicState.VICTORY
        if boss_active:
            return MusicState.COMBAT_HIGH
        if enemy_count >= 3:
            return MusicState.COMBAT_LOW
        if enemy_count > 0 or intensity > 0.3:
            return MusicState.TENSION
        return MusicState.EXPLORE

    def _compute_intensity(
        self,
        game_state: Dict[str, float],
        state_params: Optional[StateParams],
    ) -> float:
        """计算当前强度值 0-1"""
        # 优先使用映射参数
        mapped_intensity = self._active_mappings.get("intensity")
        if mapped_intensity is not None:
            return mapped_intensity

        # 从状态推导
        if state_params is not None:
            return state_params.tension

        # 从游戏状态直接推导
        enemy_count = game_state.get("enemy_count", 0)
        hp = game_state.get("hp_ratio", 1.0)
        raw = 0.1 + 0.2 * min(enemy_count / 5, 1.0) + 0.2 * (1.0 - hp)
        return min(raw, 1.0)

    def _synthesize_layer(
        self,
        layer: MusicLayer,
        intensity: float,
        n_samples: int,
        sr: int,
    ) -> np.ndarray:
        """合成单个层的音频"""
        from bloodmusic.core.note_utils import note_to_freq
        from bloodmusic.core.oscillator import oscillator, OscType

        t = np.linspace(
            self._t, self._t + n_samples / sr, n_samples, endpoint=False
        )

        osc_type_map = {
            "sine": OscType.SINE,
            "saw": OscType.SAW,
            "square": OscType.SQUARE,
            "triangle": OscType.TRIANGLE,
            "noise_white": OscType.NOISE_WHITE,
            "noise_pink": OscType.NOISE_PINK,
        }
        osc_type = osc_type_map.get(layer.osc_type, OscType.SINE)

        # 根据映射的 bpm 调整节奏
        bpm = self._active_mappings.get("bpm", 120)
        beat_dur = 60.0 / bpm

        result = np.zeros(n_samples, dtype=np.float32)
        for note_name in layer.notes:
            freq = note_to_freq(f"{note_name}{layer.base_octave}")
            wave = oscillator(t, freq, osc_type)

            # 节奏门控：根据 rhythm_pattern（每个元素为一个节拍相位段的
            # 占宽，取值 0~1）把每一拍切成若干段，逐样本在强拍(1.0)/弱拍
            # (0.5) 之间切换，从而让 layer 的节奏律动真正生效。
            if osc_type != OscType.NOISE_WHITE and layer.rhythm_pattern:
                pattern = np.asarray(layer.rhythm_pattern, dtype=np.float32)
                pattern = pattern[pattern > 0]
                if pattern.size:
                    # 归一化占宽，得到 [0,1) 的节拍相位边界
                    boundaries = np.cumsum(pattern / pattern.sum())
                    boundaries = np.clip(boundaries, 0.0, 1.0)
                    # 每样本在拍内的相位 [0,1)
                    phase = ((t % beat_dur) / beat_dur).astype(np.float64)
                    # 落入的段索引：第一个边界 > phase 的段
                    seg_idx = np.searchsorted(boundaries, phase, side="right")
                    seg_idx = np.clip(seg_idx, 0, len(boundaries) - 1)
                    # 偶数段=强拍(1.0)，奇数段=弱拍(0.5)
                    gate = np.where(seg_idx % 2 == 1, 0.5, 1.0)
                    wave = wave * gate.astype(np.float32)

            result += wave * 0.3 / len(layer.notes)

        # 应用滤波器
        filter_open = self._active_mappings.get("filter_openness", 0.7)
        result = VerticalLayerMixer._apply_simple_lowpass(result, filter_open, sr)

        return np.clip(result, -1.0, 1.0)
