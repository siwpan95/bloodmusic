# -*- coding: utf-8 -*-
"""
taxonomy.py —— 机生成乐器分类体系（镜像 musickit instrument_taxonomy.json）

musickit 侧：242 乐器词 → 37 类目 → 13 采样池，每类带 mixer_role。
bloodmusic 侧：同一词表语义 → 同类目 → 同 13 池；差异在于
「素材落点」从采样文件子目录变为合成引擎 + 预设（见 pools.py）。

结构对齐：
    pools            13 个池名（顺序一致）
    canonical_class  {pool, subcategory, mixer_role, synth_engine, synth_preset, words}
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 13 池（与 musickit instrument_taxonomy.json 的 pools 完全同名同序）
POOLS = [
    "bass", "drum", "guita", "cowbell", "synth", "acapella", "animal",
    "sfx", "keys", "strings", "brass", "woodwind", "ethnic",
]

# 混音角色（镜像 musickit mixer_role 语义）
MIXER_ROLES = ("drum", "bass", "guita", "pad", "melody", "vocal", "fx")


@dataclass(frozen=True)
class CanonicalClass:
    """机生成乐器类目 —— 采样类目的镜像。"""

    key: str                 # 类目键（如 "808_bass"）
    pool: str                # 归属池（13 池之一）
    subcategory: str         # 子类（镜像采样目录子类）
    mixer_role: str          # 混音角色（drum/bass/guita/pad/melody/vocal/fx）
    synth_engine: str        # bloodmusic 侧：合成引擎
    synth_preset: str        # bloodmusic 侧：预设/音色
    note: str = ""           # 说明
    words: tuple = ()        # 乐器词（风格提示词 → 类目）

    def as_dict(self) -> dict:
        d = {
            "pool": self.pool,
            "subcategory": self.subcategory,
            "available": True,
            "mixer_role": self.mixer_role,
            "synth_engine": self.synth_engine,
            "synth_preset": self.synth_preset,
            "note": self.note,
            "words": list(self.words),
        }
        return d


# ═══════════════════════════════════════════════════════════════
# 类目表 —— 覆盖 13 池的代表性类目（词表可按需扩展至 242 词）
# ═══════════════════════════════════════════════════════════════

CANONICAL_CLASSES: dict[str, CanonicalClass] = {
    # bass
    "808_bass": CanonicalClass("808_bass", "bass", "808", "bass", "subtractive", "deep_bass",
        "808 贝斯", ("808", "808 bass", "808 贝斯", "808 滑音贝斯")),
    "sub_bass": CanonicalClass("sub_bass", "bass", "sub", "bass", "subtractive", "sub_bass",
        "重低音", ("bass drop", "wobble 贝斯", "重低音", "重低音贝斯")),
    "bass_guitar": CanonicalClass("bass_guitar", "bass", "guitar", "bass", "karplus_strong", "bass_pluck",
        "贝斯吉他", ("bass guitar", "贝斯", "贝斯吉他", "电贝斯")),
    "upright_bass": CanonicalClass("upright_bass", "bass", "upright", "bass", "karplus_strong", "upright",
        "低音提琴", ("低音提琴", "直立贝斯", "upright bass")),
    # drum
    "kick": CanonicalClass("kick", "drum", "kick", "drum", "drum_808", "kick",
        "底鼓", ("kick", "底鼓", "bass drum")),
    "snare": CanonicalClass("snare", "drum", "snare", "drum", "drum_808", "snare",
        "军鼓", ("snare", "军鼓", "小鼓")),
    "hihat": CanonicalClass("hihat", "drum", "hihat", "drum", "drum_808", "hihat",
        "踩镲", ("hihat", "hi-hat", "踩镲", "镲")),
    "toms": CanonicalClass("toms", "drum", "toms", "drum", "drum_acoustic", "toms",
        "通鼓", ("tom", "toms", "通鼓", "嗵鼓")),
    "crash": CanonicalClass("crash", "drum", "crash", "drum", "drum_acoustic", "crash",
        "吊镲", ("crash", "吊镲")),
    "percussion": CanonicalClass("percussion", "drum", "percussion", "drum", "drum_acoustic", "percussion",
        "打击乐", ("percussion", "打击乐", "congas", "bongos", "shaker", "沙锤")),
    # guita（musickit 约定：旋律轨 other 轨 → 机生成侧为拨弦/失真吉他类）
    "electric_guitar": CanonicalClass("electric_guitar", "guita", "electric", "guita", "karplus_strong", "guitar",
        "电吉他", ("guitar", "电吉他", "失真吉他", "吉他")),
    "acoustic_guitar": CanonicalClass("acoustic_guitar", "guita", "acoustic", "guita", "karplus_strong", "acoustic",
        "木吉他", ("acoustic guitar", "木吉他", "民谣吉他")),
    # cowbell
    "cowbell": CanonicalClass("cowbell", "cowbell", "cowbell", "fx", "noise_ring", "cowbell",
        "牛铃", ("cowbell", "牛铃")),
    # synth
    "synth_lead": CanonicalClass("synth_lead", "synth", "lead", "melody", "wavetable", "synth_lead",
        "合成主奏", ("synth lead", "lead", "合成主奏", "主奏")),
    "synth_pad": CanonicalClass("synth_pad", "synth", "pad", "pad", "fm_advanced", "warm_pad",
        "合成铺底", ("pad", "铺底", "氛围垫", "atmos")),
    "synth_pluck": CanonicalClass("synth_pluck", "synth", "pluck", "melody", "fm_advanced", "pluck",
        "合成拨弦", ("pluck", "拨弦", "arp")),
    # acapella（机生成：共振峰人声）
    "vocal_vowels": CanonicalClass("vocal_vowels", "acapella", "vowels", "vocal", "formant", "vowels",
        "元音吟唱", ("vocal", "vocals", "人声", "acapella", "吟唱", "哼鸣")),
    # animal（机生成：噪声拟声）
    "animal_calls": CanonicalClass("animal_calls", "animal", "calls", "fx", "noise_chirp", "animal",
        "动物叫声", ("animal", "动物", "鸟叫", "bird")),
    # sfx
    "riser": CanonicalClass("riser", "sfx", "riser", "fx", "riser", "edm_build",
        "上升音效", ("riser", "上升", "build up")),
    "impact": CanonicalClass("impact", "sfx", "impact", "fx", "impact", "impact_hit",
        "冲击音效", ("impact", "冲击", "hit")),
    # keys
    "piano": CanonicalClass("piano", "keys", "piano", "melody", "wavetable", "acoustic_grand_piano",
        "钢琴", ("piano", "钢琴", "grand piano")),
    "organ": CanonicalClass("organ", "keys", "organ", "pad", "organ", "organ",
        "管风琴", ("organ", "管风琴", "风琴")),
    "bells": CanonicalClass("bells", "keys", "bells", "melody", "fm_advanced", "bells",
        "钟琴", ("bell", "bells", "钟琴", "glockenspiel", "八音盒")),
    # strings
    "strings": CanonicalClass("strings", "strings", "bowed", "pad", "fm_advanced", "warm_strings",
        "弦乐", ("strings", "弦乐", "小提琴", "violin", "大提琴", "cello")),
    "harp": CanonicalClass("harp", "strings", "harp", "melody", "karplus_strong", "harp",
        "竖琴", ("harp", "竖琴")),
    # brass
    "brass": CanonicalClass("brass", "brass", "brass", "melody", "fm_advanced", "brass",
        "铜管", ("brass", "铜管", "trumpet", "小号", "trombone", "长号")),
    "saxophone": CanonicalClass("saxophone", "brass", "sax", "melody", "fm_advanced", "sax",
        "萨克斯", ("sax", "saxophone", "萨克斯")),
    # woodwind
    "flute": CanonicalClass("flute", "woodwind", "flute", "melody", "wavetable", "flute",
        "长笛", ("flute", "长笛", "笛", "木管")),
    "oboe": CanonicalClass("oboe", "woodwind", "oboe", "melody", "fm_advanced", "oboe",
        "双簧管", ("oboe", "双簧管")),
    # ethnic
    "ethnic_pluck": CanonicalClass("ethnic_pluck", "ethnic", "plucked", "melody", "karplus_strong", "ethnic",
        "民族拨弦", ("ethnic", "民族", "古筝", "琵琶", "sitar", "西塔")),
    "ethnic_pad": CanonicalClass("ethnic_pad", "ethnic", "pad", "pad", "fm_advanced", "ethnic_pad",
        "民族氛围", ("dizi", "笛子", "尺八", "shakuhachi")),
}


def classify_word(word: str) -> CanonicalClass | None:
    """风格乐器词 → 类目（大小写不敏感，最长词优先）。"""
    w = word.strip().lower()
    if not w:
        return None
    best: CanonicalClass | None = None
    best_len = 0
    for cls in CANONICAL_CLASSES.values():
        for cand in cls.words:
            cand_l = cand.lower()
            if cand_l in w and len(cand_l) > best_len:
                best = cls
                best_len = len(cand_l)
    return best


def resolve_pool(word: str) -> str | None:
    """风格乐器词 → 池名；未命中返回 None。"""
    cls = classify_word(word)
    return cls.pool if cls else None


def mixer_role_for(word: str) -> str | None:
    """风格乐器词 → 混音角色。"""
    cls = classify_word(word)
    return cls.mixer_role if cls else None


def as_dict() -> dict:
    """导出为与 musickit instrument_taxonomy.json 同构的字典。"""
    return {
        "version": 1,
        "description": "bloodmusic 机生成乐器分类体系（musickit instrument_taxonomy.json 的镜像）",
        "pools": list(POOLS),
        "canonical_classes": {
            key: cls.as_dict() for key, cls in sorted(CANONICAL_CLASSES.items())
        },
    }
