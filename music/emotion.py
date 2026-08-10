"""
情绪曲线映射系统 — 从叙事弧线到音乐参数
=========================================

基于指导第 5.4 节：将情绪张力曲线映射到和声密度、节奏密度、动态级别和调式选择。

核心映射:
    张力 0.0 → 放松: I-IV 和弦, 60 BPM, 1-2层, 大调/多利亚, 高混响
    张力 0.3 → 平静: I-V 行进, 80 BPM, 2层, 自然小调
    张力 0.5 → 中性: ii-V 行进, 100 BPM, 3层, 混合利底亚
    张力 0.8 → 紧张: vii-i 行进, 140 BPM, 5层, 弗里几亚
    张力 1.0 → 高潮: dim7 → I, 160 BPM, 6层+, 全音阶/半音阶

用法:
    from bloodmusic.music import EmotionCurve, EmotionMapper
    mapper = EmotionMapper()
    params = mapper.map(tension=0.7)
    # params = {"bpm": 128, "density": 4, "scale": "phrygian", ...}
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class EmotionCurve:
    """情绪曲线 — 描述一段音乐的情绪走向"""
    name: str = ""
    description: str = ""

    # 张力点: [(时间比例 0-1, 张力值 0-1), ...]
    points: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.0, 0.2),    # 开头 — 平静
        (0.3, 0.3),    # 发展
        (0.5, 0.5),    # 中部 — 中性
        (0.7, 0.7),    # 爬升
        (0.85, 0.9),   # 高潮
        (1.0, 0.2),    # 结尾 — 回归
    ])

    # 可选: 分段描述
    sections: List[str] = field(default_factory=list)


@dataclass
class MusicEmotionParams:
    """情绪到音乐参数的映射结果"""
    bpm: int = 100                      # 速度
    tension: float = 0.3                # 张力 (0-1)
    density: int = 2                    # 层密度
    scale_type: str = "minor"           # 调式
    root_note: str = "C"                # 根音
    dynamic_range: float = 6.0          # 动态范围 (dB)
    reverb_mix: float = 0.3             # 混响量
    filter_openness: float = 0.7        # 滤波器开放度
    pulse_weight: float = 0.4           # 脉冲感
    harmony_tension: float = 0.2        # 和声张力
    melodic_range_semitones: int = 7    # 旋律跨度 (半音)
    note_density: float = 2.0           # 音符密度 (每拍)
    key_brightness: float = 0.5         # 调性亮度 (0=暗, 1=亮)


class EmotionMapper:
    """
    情绪→音乐参数映射器

    用法:
        mapper = EmotionMapper()
        
        # 单点映射
        params = mapper.map_tension(0.7)
        
        # 整条曲线
        curve = EmotionCurve(points=[(0,0.2),(0.5,0.8),(1,0.3)])
        timeline = mapper.map_curve(curve, duration=60.0)
        # timeline = [(0.0, params), (1.0, params), ...]
        
        # 叙事模式
        hero_journey = mapper.preset_curve("hero_journey")
        params = mapper.map_tension(mapper.sample_curve(hero_journey, 0.5))
    """

    def __init__(self):
        self._curve_presets: Dict[str, EmotionCurve] = {}
        self._register_default_presets()

    # ── 映射 ──

    def map_tension(self, tension: float, extra: Optional[Dict] = None) -> MusicEmotionParams:
        """
        张力 → 音乐参数。
        tension: 0.0 (完全放松) → 1.0 (极度紧张)
        """
        t = max(0.0, min(1.0, tension))

        # BPM: 60 → 170
        bpm = int(60 + t * 110)

        # 层密度: 1 → 7
        density = max(1, int(1 + t * 6))

        # 调式选择
        if t < 0.2:
            scale_type = "lydian"       # 明亮放松
        elif t < 0.35:
            scale_type = "major"        # 积极
        elif t < 0.5:
            scale_type = "dorian"       # 中性
        elif t < 0.65:
            scale_type = "minor"        # 开始紧张
        elif t < 0.85:
            scale_type = "phrygian"     # 紧张
        else:
            scale_type = "whole_tone"   # 失稳/高潮

        # 根音偏移 (跟踪频率上移增加紧张感)
        root_notes = ["C", "C", "D", "Eb", "E", "F", "F#", "G"]
        idx = min(int(t * 7), 7)
        root_note = root_notes[idx]

        # 动态范围: 4→12 dB
        dynamic_range = 4.0 + t * 8.0

        # 混响: 0.6→0.1 (越紧张越干)
        reverb_mix = 0.6 - t * 0.5

        # 滤波器: 0.4→1.0 (越紧张越亮)
        filter_openness = 0.4 + t * 0.6

        # 脉冲感: 0.2→0.95
        pulse_weight = 0.2 + t * 0.75

        # 和声张力: 0→1
        harmony_tension = t

        # 旋律跨度: 5→12 半音
        melodic_range = int(5 + t * 7)

        # 音符密度: 1.0→4.0 每拍
        note_density = 1.0 + t * 3.0

        # 调性亮度: 1→0 (越暗)
        key_brightness = max(0.0, 1.0 - t * 1.2)

        return MusicEmotionParams(
            bpm=bpm, tension=t, density=density,
            scale_type=scale_type, root_note=root_note,
            dynamic_range=dynamic_range, reverb_mix=reverb_mix,
            filter_openness=filter_openness, pulse_weight=pulse_weight,
            harmony_tension=harmony_tension,
            melodic_range_semitones=melodic_range,
            note_density=note_density,
            key_brightness=key_brightness,
        )

    def map_curve(
        self,
        curve: EmotionCurve,
        duration: float,
        resolution: float = 0.25,
    ) -> List[Tuple[float, MusicEmotionParams]]:
        """
        将完整情绪曲线映射为时间轴上的音乐参数序列。
        resolution: 输出间隔 (秒)
        """
        if len(curve.points) < 2:
            return [(0.0, self.map_tension(0.3))]

        result = []
        t = 0.0
        while t <= duration + 1e-6:
            ratio = min(t / duration, 1.0) if duration > 0 else 0.0
            tension = EmotionMapper._interpolate_curve(curve.points, ratio)
            params = self.map_tension(tension)
            result.append((t, params))
            t += resolution

        return result

    # ── 曲线采样 ──

    @staticmethod
    def _interpolate_curve(points: List[Tuple[float, float]], x: float) -> float:
        """在曲线上线性插值求张力值"""
        if len(points) == 0:
            return 0.5
        if len(points) == 1:
            return points[0][1]
        sorted_pts = sorted(points, key=lambda p: p[0])
        for i in range(len(sorted_pts) - 1):
            x0, y0 = sorted_pts[i]
            x1, y1 = sorted_pts[i + 1]
            if x0 <= x <= x1:
                t = (x - x0) / (x1 - x0) if x1 != x0 else 0.0
                return y0 + (y1 - y0) * t
        if x < sorted_pts[0][0]:
            return sorted_pts[0][1]
        return sorted_pts[-1][1]

    @staticmethod
    def sample_curve(curve: EmotionCurve, progress: float) -> float:
        """在曲线的指定进度上采样张力值"""
        return EmotionMapper._interpolate_curve(curve.points, max(0.0, min(1.0, progress)))

    # ── 叙事弧线预置 ──

    def preset_curve(self, name: str) -> Optional[EmotionCurve]:
        """获取预置的情绪曲线"""
        return self._curve_presets.get(name)

    def register_curve(self, curve: EmotionCurve):
        """注册自定义情绪曲线"""
        self._curve_presets[curve.name] = curve

    def list_presets(self) -> List[str]:
        return list(self._curve_presets.keys())

    def _register_default_presets(self):
        """注册预置叙事弧线"""

        # 英雄之旅
        self._curve_presets["hero_journey"] = EmotionCurve(
            name="hero_journey",
            description="英雄之旅: 平凡世界→冒险召唤→考验→高潮→回归",
            points=[
                (0.0, 0.1),     # 平凡世界
                (0.15, 0.3),    # 冒险召唤
                (0.3, 0.2),     # 拒绝召唤（短暂回落）
                (0.45, 0.5),    # 跨越门槛
                (0.6, 0.7),     # 考验/敌人
                (0.75, 0.9),    # 最终对决
                (0.85, 0.95),   # 高潮
                (0.9, 0.4),     # 凯旋
                (1.0, 0.15),    # 回归平静
            ],
        )

        # 战斗曲线
        self._curve_presets["battle_arc"] = EmotionCurve(
            name="battle_arc",
            description="战斗弧线: 迎敌→激战→危急→逆转→胜利",
            points=[
                (0.0, 0.4),     # 迎敌
                (0.2, 0.65),    # 激战
                (0.45, 0.8),    # 危急
                (0.6, 0.55),    # 策略调整
                (0.7, 0.9),     # 逆转
                (0.85, 0.95),   # 最终一击
                (1.0, 0.1),     # 胜利
            ],
        )

        # 探索曲线
        self._curve_presets["explore_arc"] = EmotionCurve(
            name="explore_arc",
            description="探索弧线: 进入→发现→神秘→解密→豁然开朗",
            points=[
                (0.0, 0.05),
                (0.2, 0.15),
                (0.4, 0.35),
                (0.6, 0.5),
                (0.8, 0.2),
                (1.0, 0.1),
            ],
        )

        # 恐惧曲线 (恐怖/潜行)
        self._curve_presets["horror_arc"] = EmotionCurve(
            name="horror_arc",
            description="恐惧弧线: 平静→不安→恐惧→惊骇→释放",
            points=[
                (0.0, 0.1),
                (0.25, 0.3),
                (0.5, 0.6),
                (0.7, 0.4),     # 假安全
                (0.85, 0.95),   # jumpscare
                (1.0, 0.2),
            ],
        )

        # 煽情曲线
        self._curve_presets["emotional_arc"] = EmotionCurve(
            name="emotional_arc",
            description="煽情弧线: 悲伤→回忆→希望→涌动→释然",
            points=[
                (0.0, 0.1),
                (0.3, 0.2),
                (0.5, 0.4),
                (0.7, 0.7),
                (0.85, 0.85),
                (1.0, 0.1),
            ],
        )

        # 节拍驱动曲线
        self._curve_presets["beat_cycle"] = EmotionCurve(
            name="beat_cycle",
            description="四小节奏循环: 引→抬→落→收",
            points=[
                (0.0, 0.1),
                (0.25, 0.5),
                (0.5, 0.8),
                (0.75, 0.6),
                (1.0, 0.1),
            ],
        )

    # ── 和弦推荐 ──

    @staticmethod
    def tension_to_chords(tension: float, root: str = "C") -> List[str]:
        """
        张力→推荐和弦进行。
        """
        # 以 C 为基准的罗马数字和弦
        chord_map = {
            "I": f"{root}", "ii": f"{_transpose(root, 2)}m",
            "iii": f"{_transpose(root, 4)}m", "IV": f"{_transpose(root, 5)}",
            "V": f"{_transpose(root, 7)}", "vi": f"{_transpose(root, 9)}m",
            "vii°": f"{_transpose(root, 11)}dim",
            "bVII": f"{_transpose(root, 10)}",
        }

        if tension < 0.15:
            return ["I", "IV", "I", "V"]
        elif tension < 0.3:
            return ["I", "vi", "IV", "V"]
        elif tension < 0.5:
            return ["vi", "IV", "I", "V"]
        elif tension < 0.7:
            return ["i", "bVII", "bVI", "V"]
        elif tension < 0.85:
            return ["i", "V", "bVI", "bVII"]
        else:
            return ["i", "vii°", "i", "V7"]


def _transpose(root: str, semitones: int) -> str:
    """简单音名转调"""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    # 处理可能有的八度数字
    base = root.rstrip("0123456789")
    octave = root[len(base):] if root != base else ""
    idx = 0
    for i, n in enumerate(names):
        if n == base:
            idx = i
            break
    new_idx = (idx + semitones) % 12
    return names[new_idx] + octave


# ============================================================
# 和弦进行生成器 (补充情绪映射)
# ============================================================

class ChordProgressionGenerator:
    """
    根据情绪/场景生成和弦进行。
    """

    # 常用进行模式 (C 大调/小调)
    PATTERNS = {
        "peaceful":    ["I", "IV", "I", "V"],
        "mysterious":  ["i", "bVI", "bVII", "i"],
        "heroic":      ["I", "V", "vi", "IV"],
        "sad":         ["vi", "IV", "I", "V"],
        "tense":       ["i", "V", "bVI", "bVII"],
        "epic":        ["i", "bVI", "bIII", "bVII"],
        "jazz":        ["ii", "V", "I", "vi"],
        "dark":        ["i", "bV", "i", "V"],
        "uplifting":   ["I", "iii", "IV", "V"],
    }

    def generate(
        self,
        style: str = "peaceful",
        root: str = "C",
        length: int = 4,
    ) -> List[str]:
        """根据风格生成和弦进行"""
        pattern = self.PATTERNS.get(style, self.PATTERNS["peaceful"])
        # 转调到指定根音
        result = []
        for chord in pattern[:length]:
            # 简单的罗马数字→和弦名转换
            result.append(self._roman_to_chord(chord, root))
        return result

    @staticmethod
    def _roman_to_chord(roman: str, root: str) -> str:
        """罗马数字→和弦名（简单版）"""
        degrees = {
            "I": 0, "ii": 2, "iii": 4, "IV": 5, "V": 7,
            "vi": 9, "vii°": 11, "bII": 1, "bIII": 3,
            "bV": 6, "bVI": 8, "bVII": 10,
        }
        degree = degrees.get(roman, 0)
        chord_root = _transpose(root, degree)
        quality = ""
        if "°" in roman or "dim" in roman:
            quality = "dim"
        elif "m" in roman or roman.islower():
            quality = "m"
        # 默认大三和弦
        return f"{chord_root}{quality}"
