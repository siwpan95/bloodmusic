"""album_maker/style_db.py — 风格编配策略数据库（公共模块）
============================================================
每种风格 = BPM 范围 + 调性候选 + 调式候选 + 和弦进行候选 + 乐器 + 节奏模式。

- progression 值严格对齐 music/scale.py 的 CHORD_PROGRESSIONS（失配会 fallback）
- key/scale/progression 提供多个候选，调用方随机选取 → 保证随机性
- quick / make / beat 三处共享

来源：musichool.co / beatkey.app / violetrecording.com / sonygram.ai
"""

from __future__ import annotations

# 和弦进行候选（值必须存在于 music/scale.py CHORD_PROGRESSIONS）
STYLE_DB = {
    "classical": {
        "bpm_range": (60, 110),
        "keys": ["C", "G", "F", "D", "A"],
        "scales": ["major", "minor"],
        "progressions": ["I-IV-V-I", "I-V-vi-IV", "I-vi-IV-V", "I-V-vi-IV"],
        "mood": "优雅/古典",
        "instruments": ["strings", "woodwinds", "piano"],
        "drum_style": "timpani_rolls",
        "source": "musichool.co",
    },
    "jazz": {
        "bpm_range": (90, 160),
        "keys": ["F", "Bb", "C", "Eb", "D"],
        "scales": ["dorian", "mixolydian", "major"],
        "progressions": ["jazz_ii-V-I", "jazz_turnaround", "ii-V-I", "jazz_blues"],
        "mood": "swing/爵士",
        "instruments": ["piano", "bass", "drums", "sax"],
        "drum_style": "swing_ride",
        "source": "beatkey.app/jazz, violetrecording.com",
    },
    "electronic": {
        "bpm_range": (120, 150),
        "keys": ["Am", "Em", "Fm", "Gm", "Dm"],
        "scales": ["minor", "phrygian"],
        "progressions": ["edm_build", "edm_drop", "I-V-vi-IV", "vi-IV-I-V"],
        "mood": "高能/电子",
        "instruments": ["synth", "drums", "bass", "pad"],
        "drum_style": "four_on_floor",
        "source": "sonygram.ai/edm",
    },
    "cinematic": {
        "bpm_range": (70, 100),
        "keys": ["Dm", "Em", "Cm", "Gm", "Am"],
        "scales": ["minor", "harmonic_minor"],
        "progressions": ["epic", "heroic", "I-V-vi-IV", "vi-IV-I-V"],
        "mood": "宏大/史诗",
        "instruments": ["orchestra", "choir", "brass", "percussion"],
        "drum_style": "epic_taiko",
        "source": "musichool.co",
    },
    "ambient": {
        "bpm_range": (40, 70),
        "keys": ["C", "G", "D", "A", "E"],
        "scales": ["lydian", "major"],
        "progressions": ["ambient", "I-IV-V-I", "dreamy"],
        "mood": "空灵/氛围",
        "instruments": ["pad", "texture", "bell"],
        "drum_style": "none",
        "source": "beatkey.app/ambient",
    },
    "lofi": {
        "bpm_range": (70, 95),
        "keys": ["Am", "Dm", "Em", "Fm"],
        "scales": ["minor", "dorian"],
        "progressions": ["jazz_turnaround", "ii-V-I", "I-vi-IV-V", "vi-IV-I-V"],
        "mood": "温暖/低保真",
        "instruments": ["piano", "bass", "drums", "pad"],
        "drum_style": "dusty_boom_bap",
        "source": "sonygram.ai/lofi",
    },
    "battle": {
        "bpm_range": (130, 170),
        "keys": ["Em", "Dm", "Gm", "Bm"],
        "scales": ["phrygian", "minor"],
        "progressions": ["heroic", "epic", "I-V-vi-IV"],
        "mood": "激烈/战斗",
        "instruments": ["drums", "bass", "brass", "synth"],
        "drum_style": "double_kick",
        "source": "bloodmusic pool_styles",
    },
    "exploration": {
        "bpm_range": (80, 110),
        "keys": ["G", "C", "D", "A"],
        "scales": ["mixolydian", "major"],
        "progressions": ["I-IV-V-I", "I-V-vi-IV", "I-vi-IV-V"],
        "mood": "宽广/探索",
        "instruments": ["strings", "harp", "woodwinds", "pad"],
        "drum_style": "light_orchestral",
        "source": "bloodmusic pool_styles",
    },
    "dungeon": {
        "bpm_range": (70, 100),
        "keys": ["Dm", "Em", "Am", "Cm"],
        "scales": ["phrygian", "minor"],
        "progressions": ["minor_i-iv-v", "minor_i-VI-III-VII", "I-V-vi-IV"],
        "mood": "阴暗/地下城",
        "instruments": ["bass", "drums", "choir", "brass"],
        "drum_style": "heavy_tribal",
        "source": "bloodmusic pool_styles",
    },
    "town": {
        "bpm_range": (80, 110),
        "keys": ["C", "G", "F", "D"],
        "scales": ["major", "mixolydian"],
        "progressions": ["I-IV-V-I", "I-V-vi-IV", "pop_verse"],
        "mood": "温暖/城镇",
        "instruments": ["guitar", "flute", "piano", "percussion"],
        "drum_style": "light_brush",
        "source": "bloodmusic pool_styles",
    },
    "meditation": {
        "bpm_range": (40, 60),
        "keys": ["C", "D", "A", "E"],
        "scales": ["lydian", "major"],
        "progressions": ["ambient", "dreamy", "I-IV-V-I"],
        "mood": "冥想/舒缓",
        "instruments": ["pad", "bell", "harp", "texture"],
        "drum_style": "none",
        "source": "beatkey.app/ambient",
    },
    "folk": {
        "bpm_range": (80, 120),
        "keys": ["G", "C", "D", "A", "E"],
        "scales": ["major", "mixolydian"],
        "progressions": ["folk", "folk_minor", "I-IV-V-I", "I-V-vi-IV"],
        "mood": "自然/民谣",
        "instruments": ["guitar", "flute", "violin", "percussion"],
        "drum_style": "acoustic_brush",
        "source": "musichool.co/folk",
    },
}


def get_style(name: str) -> dict | None:
    """获取风格策略，未知风格返回 None。"""
    return STYLE_DB.get(name)
