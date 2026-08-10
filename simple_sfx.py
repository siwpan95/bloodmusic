"""
简单音效接口 —— 为游戏项目提供一键生成/播放常见音效的 API

无需理解合成器参数，直接按场景调用：
    from bloodmusic.simple_sfx import SimpleSFX
    sfx = SimpleSFX()
    sfx.play("attack")          # 播放攻击音效
    sfx.export("heal")          # 导出治疗音效为 WAV
    sfx.export_game_pack("./game_sfx")  # 导出全套游戏音效

同时支持 pygame.mixer 直接加载：
    sound = sfx.pygame_sound("gold")
    sound.play()
"""

import io
import os
from typing import Dict, Optional

import numpy as np

from .core.constants import SR
from .core.oscillator import OscType
from .core.envelope import EnvShape
from .core.voice import SynthVoice, synthesize_voice
from .sfx.presets import (
    UI_FX_PRESETS, CARD_FX_PRESETS, COMBAT_FX_PRESETS, SYSTEM_FX_PRESETS
)
from .effects.chain import EffectChain
from .export.batch import export_audio


# ═══════════════════════════════════════════════════════════
#  游戏音效映射表：简单名称 -> 现有预设或自定义合成参数
# ═══════════════════════════════════════════════════════════

GAME_SFX_MAP: Dict[str, SynthVoice] = {
    # ── UI ──
    "click":       UI_FX_PRESETS["button_click"],
    "hover":       UI_FX_PRESETS["button_hover"],
    "confirm":     UI_FX_PRESETS["confirm"],
    "cancel":      UI_FX_PRESETS["cancel"],
    "error":       UI_FX_PRESETS["error"],
    "notification": UI_FX_PRESETS["notification"],
    "scroll":      UI_FX_PRESETS["scroll"],

    # ── 卡牌 ──
    "card_play":   CARD_FX_PRESETS["card_play"],
    "card_draw":   CARD_FX_PRESETS["card_draw"],
    "card_hover":  CARD_FX_PRESETS["card_hover"],
    "shuffle":     CARD_FX_PRESETS["shuffle"],
    "card_upgrade": CARD_FX_PRESETS["card_upgrade"],

    # ── 战斗 ──
    "attack":      COMBAT_FX_PRESETS["attack_melee"],
    "magic":       COMBAT_FX_PRESETS["attack_magic"],
    "hit":         COMBAT_FX_PRESETS["block_hit"],
    "block":       COMBAT_FX_PRESETS["block_hit"],
    "damage":      COMBAT_FX_PRESETS["damage_taken"],
    "heal":        COMBAT_FX_PRESETS["heal"],
    "dodge":       COMBAT_FX_PRESETS["dodge"],
    "crit":        COMBAT_FX_PRESETS["critical_hit"],
    "death":       COMBAT_FX_PRESETS["enemy_death"],
    "player_hurt": COMBAT_FX_PRESETS["player_hurt"],
    "shield":      COMBAT_FX_PRESETS["shield_gain"],
    "poison":      COMBAT_FX_PRESETS["poison_tick"],
    "weak_hit":    COMBAT_FX_PRESETS["weak_hit"],

    # ── 系统 ──
    "level_up":    SYSTEM_FX_PRESETS["level_up"],
    "achievement": SYSTEM_FX_PRESETS["achievement"],
    "gold":        SYSTEM_FX_PRESETS["gold_pickup"],
    "item":        SYSTEM_FX_PRESETS["item_pickup"],
    "potion":      SYSTEM_FX_PRESETS["potion_use"],
    "transition":  SYSTEM_FX_PRESETS["transition"],
    "lose":        SYSTEM_FX_PRESETS["game_over"],
    "win":         SYSTEM_FX_PRESETS["victory_fanfare"],
    "elite":       SYSTEM_FX_PRESETS["elite_alert"],
    "boss":        SYSTEM_FX_PRESETS["boss_appear"],

    # ── 自定义 ──
    "summon": SynthVoice(
        freq=220.0, osc_type=OscType.SINE, duration=0.6,
        volume=0.55, env_shape=EnvShape.SWELL, pitch_mod=-12,
        harmonics=[(2.0, 0.25), (3.0, 0.1)],
        effect_chain=EffectChain(reverb_mix=0.3, reverb_decay=0.8, stereo_width=0.4),
    ),
    "buff": SynthVoice(
        freq=659.25, osc_type=OscType.TRIANGLE, duration=0.35,
        volume=0.5, env_shape=EnvShape.SWELL, pitch_mod=7,
        harmonics=[(1.5, 0.2), (2.0, 0.15)],
        effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.5),
    ),
    "debuff": SynthVoice(
        freq=220.0, osc_type=OscType.SAW, duration=0.3,
        volume=0.5, env_shape=EnvShape.REVERSE, pitch_mod=-8,
        effect_chain=EffectChain(lp_filter_hz=2500, reverb_mix=0.15),
    ),
}


class SimpleSFX:
    """简单音效生成器

    Args:
        output_dir: 默认导出目录
        format: 默认导出格式（wav / ogg / flac）
    """

    def __init__(self, output_dir: str = "./sfx_output", format: str = "wav"):
        self.output_dir = output_dir
        self.format = format.lower().strip(".")
        self._player = None

    @property
    def available_names(self):
        """返回所有可用的简单音效名称"""
        return sorted(GAME_SFX_MAP.keys())

    def generate(self, name: str) -> np.ndarray:
        """生成指定音效的音频数组（float32）"""
        if name not in GAME_SFX_MAP:
            raise ValueError(f"未知音效名称: {name}。可用: {self.available_names}")
        voice = GAME_SFX_MAP[name]
        return synthesize_voice(voice)

    def play(self, name: str) -> None:
        """立即播放指定音效（使用 sounddevice）"""
        audio = self.generate(name)
        if self._player is None:
            from .playback import PreviewPlayer
            self._player = PreviewPlayer()
        self._player.play(audio)

    def export(self, name: str, path: Optional[str] = None) -> str:
        """导出单个音效为音频文件

        Args:
            name: 音效名称
            path: 输出路径，默认保存到 output_dir/{name}.{format}

        Returns:
            输出文件路径
        """
        audio = self.generate(name)
        if path is None:
            os.makedirs(self.output_dir, exist_ok=True)
            path = os.path.join(self.output_dir, f"{name}.{self.format}")
        return export_audio(audio, path, format=self.format)

    def export_game_pack(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        """导出全套游戏音效，返回 {名称: 路径} 字典

        Args:
            output_dir: 输出目录，默认使用初始化时的 output_dir
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        exported: Dict[str, str] = {}
        for name in self.available_names:
            path = os.path.join(output_dir, f"{name}.{self.format}")
            exported[name] = self.export(name, path)
        return exported

    def pygame_sound(self, name: str):
        """生成 pygame.mixer.Sound 对象（如 pygame 可用）

        使用示例：
            sound = sfx.pygame_sound("attack")
            sound.play()
        """
        try:
            import pygame
        except ImportError as exc:
            raise ImportError("pygame 未安装，无法使用 pygame_sound") from exc

        audio = self.generate(name)
        # 转换为 16-bit PCM 字节流，供 pygame 直接加载
        audio_int16 = (audio * 32767).astype(np.int16)
        buffer = io.BytesIO()
        import wave
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(audio_int16.tobytes())
        buffer.seek(0)
        return pygame.mixer.Sound(buffer)


# ═══════════════════════════════════════════════════════════
#  模块级便捷函数
# ═══════════════════════════════════════════════════════════

_default_sfx: Optional[SimpleSFX] = None


def _get_default() -> SimpleSFX:
    global _default_sfx
    if _default_sfx is None:
        _default_sfx = SimpleSFX()
    return _default_sfx


def play(name: str) -> None:
    """播放指定音效（使用默认 SimpleSFX 实例）"""
    _get_default().play(name)


def export(name: str, path: Optional[str] = None) -> str:
    """导出指定音效（使用默认 SimpleSFX 实例）"""
    return _get_default().export(name, path)


def export_game_pack(output_dir: Optional[str] = None) -> Dict[str, str]:
    """导出全套游戏音效（使用默认 SimpleSFX 实例）"""
    return _get_default().export_game_pack(output_dir)


def pygame_sound(name: str):
    """获取 pygame.mixer.Sound 对象（使用默认 SimpleSFX 实例）"""
    return _get_default().pygame_sound(name)


def generate(name: str) -> np.ndarray:
    """生成指定音效的音频数组"""
    return _get_default().generate(name)
