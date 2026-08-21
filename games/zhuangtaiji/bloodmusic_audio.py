# -*- coding: utf-8 -*-
"""
bloodmusic_audio.py —— 真实状态源接入验证（zhuangtaiji FSM → bloodmusic 自适应音乐）

把 bloodmusic.interactive.RealtimeMusicEngine 接入 zhuangtaiji 的
GenericStateMachine（多范式决策引擎的状态机内核）：
    FSM 游戏状态（explore/combat/boss/victory）
      → 映射为 game_state（hp_ratio/enemy_count/intensity/boss_active…）
      → RealtimeMusicEngine.update(game_state, dt) → process_frame() 实时音频

这是评估报告 5.3「未接入任何真实游戏引擎」的收尾验证：
真实的外部状态机（zhuangtaiji 纯 stdlib 引擎）驱动自适应音乐，逐帧产出音频。
"""

from __future__ import annotations

import numpy as np

from bloodmusic.interactive.engine import RealtimeMusicEngine, EngineConfig

# ═══════════════════════════════════════════════════════════════
# 游戏场景 FSM（zhuangtaiji config 格式）
# ═══════════════════════════════════════════════════════════════

GAME_SCENARIO = {
    "state_machines": {
        "game": {
            "initial": "explore",
            "description": "自适应音乐验证场景：探索→遭遇战→BOSS→胜利",
            "states": {
                "explore": {
                    "content": "探索中：敌人未发现，气氛放松",
                    "transitions": {"enemy_spotted": "combat"},
                },
                "combat": {
                    "content": "遭遇战：多目标交火",
                    "transitions": {"boss_enters": "boss", "threat_cleared": "explore"},
                },
                "boss": {
                    "content": "BOSS 战：高压决战",
                    "transitions": {"boss_defeated": "victory"},
                },
                "victory": {
                    "content": "胜利：战斗结束",
                    "transitions": {},
                },
            },
        }
    }
}

# FSM 状态 → bloodmusic game_state（与 RealtimeMusicEngine.update 的文档一致）
STATE_TO_GAME: dict[str, dict] = {
    "explore": {
        "hp_ratio": 1.0, "enemy_count": 0, "intensity": 0.10,
        "boss_active": False, "victory": False, "speed": 3.0,
        "danger_sense": 0.0, "depth": 0.2,
    },
    "combat": {
        "hp_ratio": 0.70, "enemy_count": 4, "intensity": 0.60,
        "boss_active": False, "victory": False, "speed": 5.0,
        "danger_sense": 0.5, "depth": 0.4,
    },
    "boss": {
        "hp_ratio": 0.35, "enemy_count": 1, "intensity": 0.95,
        "boss_active": True, "victory": False, "speed": 6.0,
        "danger_sense": 0.9, "depth": 0.8,
    },
    "victory": {
        "hp_ratio": 0.90, "enemy_count": 0, "intensity": 0.15,
        "boss_active": False, "victory": True, "speed": 2.0,
        "danger_sense": 0.0, "depth": 0.3,
    },
}


class AdaptiveBGM:
    """zhuangtaiji FSM 状态 → bloodmusic 自适应音乐桥。

    Args:
        sr: 采样率（默认 44100）。
        buffer_size: 每帧样本数（默认 512，≈11.6ms/帧，满足 60fps 预算）。
        playback: True 时经 sounddevice 实时播放（默认 False，离线渲染）。
    """

    def __init__(self, sr: int = 44100, buffer_size: int = 512,
                 playback: bool = False) -> None:
        self.sr = sr
        self.buffer_size = buffer_size
        self.engine = RealtimeMusicEngine(
            EngineConfig(sample_rate=sr, buffer_size=buffer_size, master_volume=0.7)
        )
        self._transitions: list[tuple] = []
        self.engine.on_state_change(
            lambda old, new: self._transitions.append((str(old), str(new)))
        )
        self._device = None
        if playback:
            import sounddevice as sd  # noqa: E402
            self._device = sd.OutputStream(
                samplerate=sr, channels=1, blocksize=buffer_size, dtype="float32"
            )
            self._device.start()

    # ── 每帧驱动（游戏循环里调用）──

    def update(self, fsm_state: str, dt: float | None = None) -> np.ndarray:
        """FSM 当前状态 → game_state → 引擎 update + 一帧音频。

        Args:
            fsm_state: zhuangtaiji FSM 的当前状态 id（explore/combat/boss/victory）。
            dt: 本帧时长（秒）；None 时按 buffer_size/sr 计算。

        Returns:
            一帧音频 (buffer_size,) float64。
        """
        dt = dt if dt is not None else self.buffer_size / self.sr
        game_state = STATE_TO_GAME.get(fsm_state, STATE_TO_GAME["explore"])
        self.engine.update(game_state, dt)
        frame = self.engine.process_frame()
        if self._device is not None:
            self._device.write(frame.astype("float32"))
        return frame

    # ── 查询 / 收尾 ──

    @property
    def music_state(self) -> str:
        return str(self.engine.current_state)

    @property
    def transitions(self) -> list[tuple]:
        return list(self._transitions)

    def close(self) -> None:
        if self._device is not None:
            self._device.stop()
            self._device.close()
