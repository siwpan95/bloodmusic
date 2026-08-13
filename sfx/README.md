# SFX 音效合成模块

程序化音效合成：预设库 + 分层音效 + 模拟鼓合成 + 参数序列化 + 变异引擎。

## 模块

| 文件 | 说明 |
|------|------|
| `presets.py` | 40+ 预设（UI/卡牌/战斗/系统）+ 游戏通用 8 类（pickup_coin/laser_shoot/explosion/power_up/hit_hurt/jump/blip_select/random_pick） |
| `layered.py` | 分层音效（冲击层/主体层/尾音层）+ `mix_voices` N 路加权叠加 |
| `drum_synth.py` | 808 鼓合成 + 原声鼓（Tom/Crash/Shaker/Snare/Kick） |
| `riser.py` | Riser / Impact / Braam 过渡音效 |
| `serialize.py` | SynthVoice ↔ JSON / 紧凑短串（仿 jsfxr base58 短 URL） |
| `mutate.py` | 变异引擎（mutate/randomize/锁定字段，仿 bfxr） |

## 用法

```python
from bloodmusic.sfx import (
    UI_FX_PRESETS, GAME_FX_PRESETS,
    synthesize_layered_sfx, mix_voices,
    voice_to_compact, voice_from_compact,
    mutate_voice, mutate_preset,
)

# 游戏通用音效
from bloodmusic.core import synthesize_voice
audio = synthesize_voice(GAME_FX_PRESETS["pickup_coin"])

# 参数序列化（短串分享）
compact = voice_to_compact(GAME_FX_PRESETS["laser_shoot"])
voice = voice_from_compact(compact)

# 变异生成 5 个变体
variants = mutate_preset("explosion", n=5, amount=0.2)

# 多声部叠加
mixed = mix_voices([UI_FX_PRESETS["confirm"], UI_FX_PRESETS["error"]])
```

## 许可

MIT License · Copyright (c) 2026 siwpan
