"""
参数映射器 — 游戏参数 → 音乐参数的实时映射
============================================

基于指导第 6.5.1 节：将游戏状态（HP、敌人数量、速度、紧张度等）
实时映射到音乐参数（BPM、调性、密度、效果等）。

核心映射关系:
- HP → 调性偏移、动态范围
- 敌人数量 → 密度、BPM、失真
- 速度 → BPM、节奏脉冲
- 环境紧张度 → 张力、调式、混响
- 时间 → 昼夜循环、场景变化
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import math


@dataclass
class ParameterMapping:
    """单个参数映射规则"""
    # 输入: 游戏参数名和范围
    game_param: str                   # 游戏参数名 (如 "hp_ratio")
    game_range: Tuple[float, float]   # 输入值的范围

    # 输出: 音乐参数名和范围
    music_param: str                  # 音乐参数名 (如 "bpm")
    music_range: Tuple[float, float]  # 输出值的范围

    # 映射曲线
    curve: str = "linear"             # linear / quadratic / sqrt / exp / inverse
    clamp: bool = True                # 是否夹到输出范围

    # 平滑
    smoothing: float = 0.1            # EMA 平滑因子 (0=无, 1=最大)

    # 可选: 仅当条件满足时生效
    condition: Optional[Callable[[Dict[str, float]], bool]] = None


@dataclass
class MappingSet:
    """预设映射集 — 一组映射规则的集合"""
    name: str
    description: str = ""
    mappings: List[ParameterMapping] = field(default_factory=list)


# ============================================================
# 预置映射集
# ============================================================

COMBAT_MAPPINGS = MappingSet(
    name="combat",
    description="战斗映射 — HP越低音乐越紧张",
    mappings=[
        ParameterMapping("hp_ratio", (0.0, 1.0), "bpm", (70, 160), curve="inverse"),
        ParameterMapping("hp_ratio", (0.0, 1.0), "tension", (0.9, 0.1), curve="inverse"),
        ParameterMapping("enemy_count", (0.0, 10.0), "density", (2, 6), curve="sqrt"),
        ParameterMapping("enemy_count", (0.0, 10.0), "distortion", (0.0, 0.4), curve="sqrt"),
        ParameterMapping("enemy_count", (0.0, 10.0), "pulse_weight", (0.4, 0.9), curve="sqrt"),
        ParameterMapping("intensity", (0.0, 1.0), "dynamic_range", (4.0, 10.0)),
        ParameterMapping("intensity", (0.0, 1.0), "reverb_mix", (0.5, 0.15), curve="inverse"),
        ParameterMapping("intensity", (0.0, 1.0), "filter_openness", (0.5, 1.0)),
        ParameterMapping("speed", (0.0, 10.0), "bpm", (100, 180), curve="sqrt"),
    ],
)

EXPLORE_MAPPINGS = MappingSet(
    name="explore",
    description="探索映射 — 环境感、区域变化",
    mappings=[
        ParameterMapping("depth", (0.0, 1.0), "reverb_mix", (0.2, 0.7)),
        ParameterMapping("depth", (0.0, 1.0), "filter_openness", (1.0, 0.4), curve="inverse"),
        ParameterMapping("danger_sense", (0.0, 1.0), "tension", (0.0, 0.5)),
        ParameterMapping("danger_sense", (0.0, 1.0), "bpm", (60, 100)),
        ParameterMapping("time_of_day", (0.0, 1.0), "low_freq_content", (0.2, 0.6)),
        ParameterMapping("time_of_day", (0.0, 1.0), "high_freq_content", (0.6, 0.2), curve="inverse"),
    ],
)

STEALTH_MAPPINGS = MappingSet(
    name="stealth",
    description="潜行映射 — 检测度越高越紧张",
    mappings=[
        ParameterMapping("detection", (0.0, 1.0), "tension", (0.0, 0.7)),
        ParameterMapping("detection", (0.0, 1.0), "bpm", (70, 110)),
        ParameterMapping("detection", (0.0, 1.0), "density", (1, 3)),
        ParameterMapping("detection", (0.0, 1.0), "pulse_weight", (0.1, 0.6)),
        ParameterMapping("detection", (0.0, 1.0), "reverb_mix", (0.6, 0.2), curve="inverse"),
        ParameterMapping("detection", (0.0, 1.0), "filter_openness", (0.3, 0.9)),
    ],
)


# ============================================================
# 映射器
# ============================================================

class ParameterMapper:
    """
    参数映射器

    用法:
        mapper = ParameterMapper()
        mapper.load_mapping_set(COMBAT_MAPPINGS)

        game_state = {"hp_ratio": 0.3, "enemy_count": 5, "speed": 7.0, "intensity": 0.8}
        music_params = mapper.map(game_state, dt=0.016)
        # music_params = {"bpm": 142, "tension": 0.72, "density": 4, ...}
    """

    def __init__(self):
        self._mappings: Dict[str, List[ParameterMapping]] = {}
        self._smoothed_values: Dict[str, float] = {}

    def add_mapping(self, mp: ParameterMapping):
        """添加单个映射规则"""
        self._mappings.setdefault(mp.game_param, []).append(mp)

    def load_mapping_set(self, ms: MappingSet):
        """加载映射集"""
        for mp in ms.mappings:
            self.add_mapping(mp)

    def clear(self):
        """清除所有映射规则"""
        self._mappings.clear()
        self._smoothed_values.clear()

    def map(self, game_state: Dict[str, float], dt: float = 0.016) -> Dict[str, float]:
        """
        映射游戏状态到音乐参数。
        dt: 帧间隔，用于平滑。
        返回 {music_param: value}
        """
        result: Dict[str, float] = {}

        for game_param, value in game_state.items():
            rules = self._mappings.get(game_param, [])
            for rule in rules:
                # 条件检查
                if rule.condition is not None:
                    try:
                        if not rule.condition(game_state):
                            continue
                    except Exception:
                        continue

                # 归一化输入
                g_min, g_max = rule.game_range
                normalized = (value - g_min) / (g_max - g_min) if g_max != g_min else 0.5
                normalized = max(0.0, min(1.0, normalized))

                # 应用映射曲线
                mapped = self._apply_curve(normalized, rule.curve)

                # 映射到输出范围
                m_min, m_max = rule.music_range
                raw_value = m_min + mapped * (m_max - m_min)

                # 平滑
                key = f"{game_param}__{rule.music_param}"
                if key in self._smoothed_values and rule.smoothing > 0:
                    alpha = min(dt / rule.smoothing, 1.0)
                    raw_value = self._smoothed_values[key] + (raw_value - self._smoothed_values[key]) * alpha
                self._smoothed_values[key] = raw_value

                # 合并 (如果多个规则映射到同一音乐参数，取最后一个)
                result[rule.music_param] = raw_value

                # 夹到范围
                if rule.clamp:
                    result[rule.music_param] = max(m_min, min(m_max, raw_value))

        return result

    def get_scale_type(self, hp_ratio: float, is_boss: bool = False) -> str:
        """
        根据 HP 比例推荐调式。
        hp > 0.7 → major/lydian (积极)
        hp 0.3-0.7 → dorian/mixolydian (中性)
        hp < 0.3 → minor/phrygian (紧张)
        is_boss → 强制 phrygian
        """
        if is_boss:
            return "phrygian"
        if hp_ratio > 0.7:
            return "major"
        elif hp_ratio > 0.3:
            return "dorian"
        else:
            return "minor"

    def get_root_note(self, tension: float, danger_zone: str = "neutral") -> str:
        """
        张力 → 根音偏移。
        低张力 → C (稳定)
        高张力 → 上行 (E/F/F# 紧张)
        danger_zone → 下行 (A/G 低沉)
        """
        if danger_zone == "low":
            return "A"
        if tension > 0.8:
            return "F#"
        elif tension > 0.5:
            return "E"
        elif tension > 0.2:
            return "D"
        return "C"

    # ── 内部 ──

    @staticmethod
    def _apply_curve(x: float, curve: str) -> float:
        """应用映射曲线到 [0,1]"""
        if curve == "linear":
            return x
        elif curve == "quadratic":
            return x * x
        elif curve == "sqrt":
            return math.sqrt(x)
        elif curve == "exp":
            return (math.exp(x) - 1) / (math.e - 1)
        elif curve == "inverse":
            return 1.0 - x
        elif curve == "cubic":
            return x * x * x
        elif curve == "s_curve":
            return 1.0 / (1.0 + math.exp(-10 * (x - 0.5)))
        return x
