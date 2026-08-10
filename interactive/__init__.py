"""
互动/自适应音乐引擎 — 实时响应游戏状态
=======================================

本模块实现基于指导第 6 章的游戏互动音乐系统：

核心组件:
- MusicStateMachine: 探索→警戒→战斗→胜利 状态转换
- VerticalLayerMixer: 基于强度的多轨动态混音
- HorizontalSequencer: 按场景拼接音乐片段
- ParameterMapper: HP→调性 / 速度→BPM / 敌人数→密度
- RealtimeMusicEngine: 游戏循环集成接口

用法:
    from bloodmusic.interactive import RealtimeMusicEngine, MusicState
    
    engine = RealtimeMusicEngine()
    engine.setup_default_layers()
    engine.start(MusicState.EXPLORE)
    
    # 游戏循环
    while game_running:
        dt = clock.tick(60) / 1000.0
        game_state = {"hp_ratio": 0.8, "enemy_count": 2, ...}
        engine.update(game_state, dt)
        audio_output.write(engine.process_frame())
"""

from bloodmusic.interactive.state_machine import (
    MusicState,
    StateParams,
    TransitionParams,
    MusicStateMachine,
    DEFAULT_STATE_PARAMS,
)

from bloodmusic.interactive.layer_mixer import (
    LayerRole,
    MusicLayer,
    LayerMixerConfig,
    VerticalLayerMixer,
)

from bloodmusic.interactive.sequencer import (
    SegmentCategory,
    MusicSegment,
    BranchRule,
    HorizontalSequencer,
)

from bloodmusic.interactive.parameter_mapper import (
    ParameterMapping,
    MappingSet,
    ParameterMapper,
    COMBAT_MAPPINGS,
    EXPLORE_MAPPINGS,
    STEALTH_MAPPINGS,
)

from bloodmusic.interactive.engine import (
    EngineConfig,
    RealtimeMusicEngine,
    DEFAULT_LAYER_TEMPLATES,
)

__all__ = [
    # 状态机
    "MusicState",
    "StateParams",
    "TransitionParams",
    "MusicStateMachine",
    "DEFAULT_STATE_PARAMS",
    # 分层混音
    "LayerRole",
    "MusicLayer",
    "LayerMixerConfig",
    "VerticalLayerMixer",
    "DEFAULT_LAYER_TEMPLATES",
    # 横向排序
    "SegmentCategory",
    "MusicSegment",
    "BranchRule",
    "HorizontalSequencer",
    # 参数映射
    "ParameterMapping",
    "MappingSet",
    "ParameterMapper",
    "COMBAT_MAPPINGS",
    "EXPLORE_MAPPINGS",
    "STEALTH_MAPPINGS",
    # 引擎
    "EngineConfig",
    "RealtimeMusicEngine",
]
