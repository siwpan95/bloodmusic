# -*- coding: utf-8 -*-
"""
demo_adaptive_music.py —— 端到端验证：zhuangtaiji 状态机驱动 bloodmusic 自适应音乐

场景（真实 FSM 事件触发，非硬编码混音）:
    explore 8s → enemy_spotted → combat 8s → boss_enters → boss 8s
    → boss_defeated → victory 8s（共 32s）

产物:
    demo_adaptive_music.wav —— 全程自适应音乐（44.1kHz 单声道）
    transitions.log        —— 音乐状态转移记录（旧态→新态）
    控制台                  —— 各音乐状态的时长占比与 RMS 能量（验证状态可区分）

用法:
    python games/zhuangtaiji/demo_adaptive_music.py            # 离线渲染
    python games/zhuangtaiji/demo_adaptive_music.py --play     # 实时播放
    python games/zhuangtaiji/demo_adaptive_music.py --out x.wav

这是 bloodmusic 评估报告 5.3「未接入任何真实游戏引擎」的收尾验证：
真实的外部状态机（zhuangtaiji 多范式决策引擎）逐帧驱动
RealtimeMusicEngine，产出随游戏状态变化的完整音频。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from core.state_machine import create_state_machine  # noqa: E402  (zhuangtaiji FSM)
from bloodmusic_audio import AdaptiveBGM, GAME_SCENARIO  # noqa: E402


# 时间线：(秒, 事件, 参数)；事件为 None 表示维持现状
TIMELINE = [
    (0.0, None),
    (8.0, "enemy_spotted"),
    (16.0, "boss_enters"),
    (24.0, "boss_defeated"),
    (32.0, None),  # 终点
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="zhuangtaiji FSM → bloodmusic 自适应音乐端到端验证")
    p.add_argument("--play", action="store_true", help="经 sounddevice 实时播放")
    p.add_argument("--out", default="demo_adaptive_music.wav", help="输出 WAV 路径")
    args = p.parse_args(argv)

    # 1) 构建真实 FSM（zhuangtaiji 引擎）
    fsm = create_state_machine("game", GAME_SCENARIO)

    # 2) 构建自适应音乐桥
    bgm = AdaptiveBGM(sr=44100, buffer_size=512, playback=args.play)
    sr, bs = bgm.sr, bgm.buffer_size
    dt = bs / sr

    # 3) 逐帧驱动
    total_sec = TIMELINE[-1][0]
    total_frames = int(total_sec / dt)
    audio = np.zeros(total_frames * bs, dtype=np.float64)
    state_log: list[tuple[float, str, str]] = []  # (t, fsm_state, music_state)
    tl_idx = 0

    print(f"=== zhuangtaiji FSM → bloodmusic 自适应音乐（{total_sec}s）===")
    print(f"初始 FSM 状态: {fsm.get_state_info()['id']}")
    for i in range(total_frames):
        t = i * dt
        # 时间线事件触发（真实 FSM 转移）
        while tl_idx + 1 < len(TIMELINE) and t >= TIMELINE[tl_idx + 1][0]:
            tl_idx += 1
            event = TIMELINE[tl_idx][1]
            if event is not None and event in fsm.available_events:
                fsm.trigger(event)
                print(f"  [t={t:5.1f}s] 事件 {event} → FSM 进入 {fsm.get_state_info()['id']}")

        fsm_state = fsm.get_state_info()["id"]
        frame = bgm.update(fsm_state, dt)
        audio[i * bs:(i + 1) * bs] = frame
        music_state = bgm.music_state
        if not state_log or state_log[-1][2] != music_state:
            state_log.append((round(t, 2), fsm_state, music_state))

    bgm.close()

    # 4) 落盘 WAV
    from bloodmusic.export.batch import export_audio
    out_path = Path(args.out)
    export_audio(audio, str(out_path), format="wav")
    print(f"\n已写出: {out_path}（{total_sec}s, {sr}Hz）")

    # 5) 状态转移记录
    trans_path = out_path.with_suffix(".log")
    with open(trans_path, "w", encoding="utf-8") as f:
        for old, new in bgm.transitions:
            f.write(f"{old} -> {new}\n")
        f.write("\n时间轴（音乐状态切换）:\n")
        for t, fs, ms in state_log:
            f.write(f"  t={t:5.2f}s  fsm={fs:8s}  music={ms}\n")
    print(f"音乐状态转移: {' → '.join(f'{a}->{b}' for a, b in bgm.transitions)}")
    print(f"转移记录: {trans_path}")

    # 6) 验证：按音乐状态统计时长与 RMS（状态间应显著可区分）
    print("\n=== 验证：各音乐状态 RMS 能量 ===")
    rms_by_state: dict[str, list[float]] = {}
    seg_rms = np.sqrt(np.mean(audio.reshape(-1, bs) ** 2, axis=1))
    for i in range(total_frames):
        t = i * dt
        ms = next((s[2] for s in reversed(state_log) if s[0] <= t), state_log[0][2])
        rms_by_state.setdefault(ms, []).append(seg_rms[i])
    states = sorted(rms_by_state)
    for ms in states:
        vals = np.array(rms_by_state[ms])
        print(f"  {ms:12s}  时长 {len(vals)*dt:5.1f}s  RMS {np.mean(vals):.4f}")
    if len(states) >= 2:
        means = [np.mean(rms_by_state[s]) for s in states]
        spread = max(means) / max(min(means), 1e-9)
        verdict = "状态能量可区分，自适应生效" if spread > 1.3 else "能量差异偏小，建议检查映射"
        print(f"  状态间 RMS 倍差: {spread:.2f} → {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
