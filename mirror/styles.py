# -*- coding: utf-8 -*-
"""
styles.py —— 65 流派风格注册表 + 提示词生成
（镜像 musickit music/styles/ 的流派 JSON 文件；其中 63 个 slug 与其同名，
boom_bap / punk_rock 为 bloodmusic 机生成侧补充）

Phase 2（2026-08-21）全量精调：
  每个风格都给出独立的 bpm 区间 / 鼓组构成 / 贝斯与旋律轨乐器词 /
  点缀层乐器词 / 鼓密度 / 人声开关 / 调式偏好（scales），
  不再使用通用默认模板。乐器词经 taxonomy.classify_word 落到
  13 机生成声池（与采样侧同一词表语义）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .taxonomy import classify_word, mixer_role_for, resolve_pool


@dataclass(frozen=True)
class StyleDef:
    slug: str
    name: str
    mood: str
    bpm_range: tuple = (90, 150)
    drum_intensity: float = 0.6
    vocal: bool = False
    drum_words: tuple = ("kick", "snare", "hihat")
    bass_words: tuple = ("bass guitar",)
    guita_words: tuple = ("electric guitar",)
    accent_words: tuple = ()
    scales: tuple = ()      # 调式偏好（空 = 全局候选池）


def _s(slug: str, name: str, mood: str, bpm: tuple, drum: float = 0.6,
       vocal: bool = False, drum_w: tuple = ("kick", "snare", "hihat"),
       bass_w: tuple = ("bass guitar",), guita_w: tuple = ("electric guitar",),
       accents: tuple = (), scales: tuple = ()) -> StyleDef:
    return StyleDef(slug, name, mood, bpm, drum, vocal, drum_w, bass_w, guita_w,
                    accents, scales)


# ═══════════════════════════════════════════════════════════════
# 65 风格（slug 与 musickit music/styles/ 同名；Phase 2 全部精调）
# ═══════════════════════════════════════════════════════════════

STYLES: dict[str, StyleDef] = {
    # ── 嘻哈 / 陷阱系 ──
    "phonk": _s("phonk", "Phonk", "暗黑复古嘻哈/牛铃驱动", (130, 150), 0.9, True,
                ("kick", "snare", "hihat", "percussion"), ("808 bass",),
                ("electric guitar",), ("cowbell", "vocal", "synth lead"),
                ("自然小调", "弗里吉亚")),
    "trap": _s("trap", "Trap", "阴沉双倍踩镲/808 滑音", (130, 150), 0.85, True,
               ("kick", "snare", "hihat", "percussion"), ("808 bass",),
               ("electric guitar",), ("synth pad", "vocal", "cowbell"),
               ("自然小调", "和声小调")),
    "boom_bap": _s("boom_bap", "Boom Bap", "经典说唱采样感", (85, 95), 0.7, True,
                   ("kick", "snare", "hihat"), ("bass guitar",),
                   ("electric guitar",), ("piano", "vocal", "cowbell"),
                   ("自然小调", "多利安")),
    "trip_hop": _s("trip_hop", "Trip-Hop", "神游舞曲/慵懒氛围", (70, 95), 0.5, True,
                   ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                   ("electric guitar",), ("synth pad", "vocal", "piano"),
                   ("自然小调", "多利安")),
    # ── 电子舞曲系 ──
    "house": _s("house", "House", "四拍底鼓/律动", (118, 128), 0.7, True,
                ("kick", "hihat", "clap", "percussion"), ("sub bass",),
                ("electric guitar",), ("piano", "organ", "vocal", "cowbell"),
                ("自然小调", "多利安")),
    "deep_house": _s("deep_house", "Deep House", "深沉律动/爵士和声", (118, 124), 0.65, True,
                     ("kick", "hihat", "clap"), ("sub bass",),
                     ("electric guitar",), ("piano", "organ", "vocal"),
                     ("多利安", "自然小调")),
    "techno": _s("techno", "Techno", "机械重复/工业", (128, 140), 0.85, False,
                 ("kick", "hihat", "percussion"), ("sub bass",),
                 ("electric guitar",), ("synth lead", "riser", "impact"),
                 ("弗里吉亚", "自然小调")),
    "trance": _s("trance", "Trance", "迷幻渐升/琶音", (135, 142), 0.8, True,
                 ("kick", "hihat", "clap"), ("sub bass",),
                 ("electric guitar",), ("synth pad", "synth pluck", "riser", "vocal"),
                 ("自然小调", "大调")),
    "dubstep": _s("dubstep", "Dubstep", "半拍律动/重型 wobble", (138, 145), 0.9, False,
                  ("kick", "snare", "hihat"), ("wobble 贝斯",),
                  ("electric guitar",), ("riser", "impact", "synth lead"),
                  ("自然小调", "弗里吉亚")),
    "dnb": _s("dnb", "Drum & Bass", "高速碎拍", (165, 180), 0.9, False,
              ("kick", "snare", "hihat", "percussion"), ("sub bass",),
              ("electric guitar",), ("synth pad", "riser"),
              ("自然小调", "多利安")),
    "idm": _s("idm", "IDM", "智能舞曲/碎拍实验", (110, 150), 0.7, False,
              ("kick", "snare", "hihat", "percussion"), ("sub bass",),
              ("electric guitar",), ("synth pluck", "bells", "impact"),
              ("多利安", "全音阶")),
    "glitch": _s("glitch", "Glitch", "故障电子/切片感", (100, 140), 0.7, False,
                 ("kick", "snare", "hihat", "percussion"), ("808 bass",),
                 ("electric guitar",), ("synth lead", "impact"),
                 ("自然小调", "全音阶")),
    "futurebass": _s("futurebass", "Future Bass", "未来贝斯/华丽和弦", (140, 160), 0.75, True,
                     ("kick", "snare", "hihat", "clap"), ("sub bass",),
                     ("electric guitar",), ("synth pad", "synth pluck", "vocal"),
                     ("大调", "利底亚")),
    "future_garage": _s("future_garage", "Future Garage", "未来车库/UK 暗流", (125, 140), 0.65, True,
                        ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                        ("electric guitar",), ("synth pad", "vocal"),
                        ("自然小调", "多利安")),
    "garage": _s("garage", "Garage", "车库/UKG 摇摆律动", (128, 135), 0.7, True,
                 ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                 ("electric guitar",), ("organ", "vocal"),
                 ("多利安", "自然小调")),
    "hyperpop": _s("hyperpop", "Hyperpop", "超流行/高能拼贴", (140, 170), 0.85, True,
                   ("kick", "snare", "hihat", "clap"), ("808 bass",),
                   ("electric guitar",), ("synth lead", "vocal", "impact"),
                   ("大调", "自然小调")),
    "minimal": _s("minimal", "Minimal", "极简 techno/减法美学", (120, 130), 0.5, False,
                  ("kick", "hihat", "percussion"), ("sub bass",),
                  ("electric guitar",), ("synth pluck"),
                  ("弗里吉亚", "多利安")),
    "vinahouse": _s("vinahouse", "Vina House", "越南 house/弹跳 bass", (128, 140), 0.8, False,
                    ("kick", "hihat", "clap", "percussion"), ("sub bass",),
                    ("electric guitar",), ("synth lead", "riser"),
                    ("自然小调", "大调")),
    # ── 合成波 / 氛围系 ──
    "synthwave": _s("synthwave", "Synthwave", "复古未来/霓虹", (85, 110), 0.75, False,
                    ("kick", "snare", "hihat", "toms"), ("sub bass",),
                    ("electric guitar",), ("synth pad", "synth lead", "bells"),
                    ("自然小调", "多利安")),
    "darksynth": _s("darksynth", "Darksynth", "暗黑合成波/赛博惊悚", (90, 115), 0.8, False,
                    ("kick", "snare", "hihat"), ("808 bass",),
                    ("electric guitar",), ("synth lead", "riser", "impact"),
                    ("弗里吉亚", "和声小调")),
    "vaporwave": _s("vaporwave", "Vaporwave", "蒸汽波/慢速采样美学", (70, 90), 0.45, True,
                    ("kick", "snare", "hihat"), ("bass guitar",),
                    ("electric guitar",), ("synth pad", "vocal", "bells"),
                    ("大调", "利底亚")),
    "cyberpunk": _s("cyberpunk", "Cyberpunk", "赛博朋克/近未来", (120, 150), 0.8, False,
                    ("kick", "snare", "hihat", "percussion"), ("808 bass",),
                    ("electric guitar",), ("synth lead", "synth pad", "impact"),
                    ("弗里吉亚", "自然小调")),
    "ambient": _s("ambient", "Ambient", "空灵氛围/无节拍感", (60, 80), 0.15, True,
                  ("kick",), ("sub bass",), ("acoustic guitar",),
                  ("synth pad", "strings", "ethnic pad", "vocal"),
                  ("大调", "利底亚")),
    "drone": _s("drone", "Drone", "持续音/冥想", (50, 70), 0.1, False,
                ("kick",), ("sub bass",), ("acoustic guitar",),
                ("synth pad", "strings", "ethnic pad"),
                ("大调", "全音阶")),
    "new_age": _s("new_age", "New Age", "新世纪/治愈", (70, 90), 0.3, True,
                  ("kick", "hihat"), ("sub bass",), ("acoustic guitar",),
                  ("piano", "harp", "flute", "vocal"),
                  ("五声大调", "大调")),
    "chiptune": _s("chiptune", "Chiptune", "8-bit 游戏机", (120, 160), 0.7, False,
                   ("kick", "snare", "hihat"), ("808 bass",),
                   ("electric guitar",), ("synth lead", "synth pluck"),
                   ("大调", "自然小调")),
    # ── 影视 / 管弦系 ──
    "cinematic": _s("cinematic", "Cinematic", "影视史诗/张力", (80, 120), 0.6, True,
                    ("kick", "snare", "toms", "crash"), ("upright bass",),
                    ("electric guitar",), ("strings", "brass", "riser", "impact", "vocal"),
                    ("和声小调", "自然小调")),
    "orchestral": _s("orchestral", "Orchestral", "管弦乐队", (80, 120), 0.5, False,
                     ("kick", "toms", "crash"), ("upright bass",),
                     ("acoustic guitar",), ("strings", "brass", "flute", "harp"),
                     ("大调", "和声小调")),
    "neoclassical": _s("neoclassical", "Neoclassical", "新古典/钢琴弦乐", (70, 110), 0.35, False,
                       ("kick",), ("upright bass",), ("acoustic guitar",),
                       ("piano", "strings"),
                       ("大调", "旋律小调")),
    # ── 放克 / 灵魂系 ──
    "funk": _s("funk", "Funk", "放克切分/16 分律动", (95, 115), 0.7, True,
               ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
               ("electric guitar",), ("brass", "organ", "cowbell", "vocal"),
               ("多利安", "布鲁斯")),
    "disco": _s("disco", "Disco", "迪斯科四拍/弦乐扫弦", (115, 125), 0.75, True,
                ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                ("electric guitar",), ("brass", "strings", "vocal", "cowbell"),
                ("多利安", "大调")),
    "soul": _s("soul", "Soul", "灵魂乐/和声", (85, 110), 0.55, True,
               ("kick", "snare", "hihat"), ("bass guitar",),
               ("electric guitar",), ("piano", "organ", "brass", "vocal"),
               ("布鲁斯", "大调")),
    "rnb": _s("rnb", "R&B", "节奏布鲁斯", (70, 95), 0.55, True,
              ("kick", "snare", "hihat"), ("sub bass",),
              ("electric guitar",), ("piano", "bells", "vocal"),
              ("自然小调", "大调")),
    "jazz": _s("jazz", "Jazz", "摇摆即兴/ii-V-I", (90, 140), 0.5, False,
               ("kick", "snare", "hihat", "crash"), ("upright bass",),
               ("acoustic guitar",), ("piano", "saxophone", "organ"),
               ("多利安", "布鲁斯")),
    "jazzfusion": _s("jazzfusion", "Jazz Fusion", "爵士融合/电气化", (100, 140), 0.6, False,
                     ("kick", "snare", "hihat"), ("bass guitar",),
                     ("electric guitar",), ("piano", "saxophone", "synth lead"),
                     ("多利安", "利底亚")),
    "blues": _s("blues", "Blues", "布鲁斯 12 小节", (80, 120), 0.55, True,
                ("kick", "snare", "hihat"), ("upright bass",),
                ("electric guitar",), ("piano", "saxophone", "vocal"),
                ("布鲁斯", "五声小调")),
    # ── 摇滚 / 吉他系 ──
    "rock": _s("rock", "Rock", "摇滚", (120, 150), 0.8, True,
               ("kick", "snare", "hihat", "crash"), ("bass guitar",),
               ("electric guitar",), ("synth lead", "vocal", "impact"),
               ("自然小调", "混合利底亚")),
    "metal": _s("metal", "Metal", "金属/高速双踩", (150, 180), 0.95, False,
                ("kick", "snare", "hihat", "crash", "toms"), ("bass guitar",),
                ("electric guitar",), ("impact", "riser"),
                ("弗里吉亚", "和声小调")),
    "postrock": _s("postrock", "Post-Rock", "后摇/氛围堆叠", (90, 130), 0.5, False,
                   ("kick", "snare", "hihat", "crash"), ("bass guitar",),
                   ("electric guitar",), ("strings", "synth pad", "riser"),
                   ("大调", "利底亚")),
    "mathrock": _s("mathrock", "Math Rock", "数学摇滚奇数拍", (120, 160), 0.75, False,
                   ("kick", "snare", "hihat", "toms"), ("bass guitar",),
                   ("electric guitar",), ("piano", "impact"),
                   ("大调", "利底亚")),
    "shoegaze": _s("shoegaze", "Shoegaze", "自赏/音墙", (100, 130), 0.6, True,
                   ("kick", "snare", "hihat", "crash"), ("bass guitar",),
                   ("electric guitar",), ("synth pad", "strings", "vocal"),
                   ("大调", "混合利底亚")),
    "postpunk": _s("postpunk", "Post-Punk", "后朋克", (120, 150), 0.7, False,
                   ("kick", "snare", "hihat", "crash"), ("bass guitar",),
                   ("electric guitar",), ("synth lead", "impact"),
                   ("自然小调", "多利安")),
    "goth": _s("goth", "Goth", "哥特/暗潮", (110, 140), 0.65, True,
               ("kick", "snare", "hihat", "toms"), ("bass guitar",),
               ("electric guitar",), ("synth pad", "vocal", "riser"),
               ("自然小调", "弗里吉亚")),
    "punk_rock": _s("punk_rock", "Punk Rock", "朋克三和弦冲刺", (150, 190), 0.9, False,
                    ("kick", "snare", "hihat", "crash"), ("bass guitar",),
                    ("electric guitar",), ("impact",),
                    ("大调", "自然小调")),
    "folk": _s("folk", "Folk", "民谣", (90, 120), 0.45, True,
               ("kick", "snare", "hihat"), ("upright bass",),
               ("acoustic guitar",), ("flute", "harp", "vocal"),
               ("五声大调", "大调")),
    "country": _s("country", "Country", "乡村", (100, 130), 0.5, True,
                  ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                  ("acoustic guitar",), ("piano", "vocal"),
                  ("大调", "五声大调")),
    "bluegrass": _s("bluegrass", "Bluegrass", "蓝草", (120, 160), 0.65, False,
                    ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                    ("acoustic guitar",), ("harp", "flute"),
                    ("大调", "混合利底亚")),
    # ── 拉丁 / 世界系 ──
    "reggae": _s("reggae", "Reggae", "雷鬼反拍", (70, 85), 0.55, True,
                 ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                 ("electric guitar",), ("organ", "vocal"),
                 ("大调", "多利安")),
    "reggaeton": _s("reggaeton", "Reggaeton", "雷击顿 dembow", (88, 96), 0.8, True,
                    ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                    ("electric guitar",), ("synth lead", "vocal"),
                    ("自然小调", "弗里吉亚")),
    "salsa": _s("salsa", "Salsa", "萨尔萨拉丁", (160, 200), 0.8, True,
                ("kick", "snare", "hihat", "percussion", "cowbell"), ("upright bass",),
                ("acoustic guitar",), ("brass", "piano", "vocal"),
                ("大调", "多利安")),
    "samba": _s("samba", "Samba", "桑巴", (95, 110), 0.8, False,
                ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                ("acoustic guitar",), ("brass", "cowbell"),
                ("大调", "多利安")),
    "bossa_nova": _s("bossa_nova", "Bossa Nova", "波萨诺瓦", (110, 130), 0.5, True,
                     ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                     ("acoustic guitar",), ("piano", "vocal"),
                     ("大调", "多利安")),
    "latin": _s("latin", "Latin", "拉丁", (100, 140), 0.7, False,
                ("kick", "snare", "hihat", "percussion", "cowbell"), ("upright bass",),
                ("acoustic guitar",), ("brass", "piano"),
                ("多利安", "大调")),
    "merengue": _s("merengue", "Merengue", "梅伦格", (120, 160), 0.7, False,
                   ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                   ("acoustic guitar",), ("brass", "cowbell"),
                   ("大调", "多利安")),
    "cumbia": _s("cumbia", "Cumbia", "昆比亚", (85, 100), 0.65, False,
                 ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                 ("acoustic guitar",), ("brass", "cowbell"),
                 ("大调", "自然小调")),
    "afrobeat": _s("afrobeat", "Afrobeat", "非洲节拍/复合律动", (100, 120), 0.75, True,
                   ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
                   ("electric guitar",), ("brass", "vocal", "cowbell"),
                   ("多利安", "五声小调")),
    "indian": _s("indian", "Indian", "印度/西塔", (80, 120), 0.6, True,
                 ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                 ("acoustic guitar",), ("sitar", "ethnic", "vocal"),
                 ("大调", "多利安")),
    "arabic": _s("arabic", "Arabic", "阿拉伯", (90, 130), 0.65, False,
                 ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                 ("acoustic guitar",), ("ethnic", "brass"),
                 ("和声小调", "弗里吉亚")),
    "china_instr": _s("china_instr", "中国民乐", "中国风", (70, 110), 0.45, False,
                      ("kick", "toms", "percussion"), ("upright bass",),
                      ("acoustic guitar",), ("ethnic", "flute", "harp"),
                      ("五声大调", "五声小调")),
    "guofeng": _s("guofeng", "国风", "国风电子", (80, 110), 0.55, True,
                  ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                  ("acoustic guitar",), ("ethnic", "flute", "vocal", "bells"),
                  ("五声大调", "五声小调")),
    "wagakki": _s("wagakki", "和乐器", "和乐器摇滚", (100, 140), 0.75, True,
                  ("kick", "snare", "hihat", "toms"), ("bass guitar",),
                  ("electric guitar",), ("ethnic", "flute", "vocal"),
                  ("五声小调", "自然小调")),
    "korean": _s("korean", "K-Pop", "韩流", (95, 130), 0.7, True,
                 ("kick", "snare", "hihat", "percussion"), ("sub bass",),
                 ("electric guitar",), ("synth lead", "vocal", "bells"),
                 ("自然小调", "大调")),
    "pop": _s("pop", "Pop", "流行", (95, 125), 0.65, True,
              ("kick", "snare", "hihat", "percussion"), ("bass guitar",),
              ("electric guitar",), ("piano", "synth lead", "vocal"),
              ("大调", "自然小调")),
    "celtic": _s("celtic", "Celtic", "凯尔特", (90, 120), 0.5, False,
                 ("kick", "snare", "hihat", "percussion"), ("upright bass",),
                 ("acoustic guitar",), ("flute", "harp"),
                 ("大调", "混合利底亚")),
    "lofi": _s("lofi", "Lo-Fi", "慵懒低保真/怀旧", (70, 90), 0.5, False,
               ("kick", "snare", "hihat"), ("upright bass",),
               ("acoustic guitar",), ("piano", "bells", "strings"),
               ("大调", "多利安")),
}

STYLE_SLUGS: list[str] = sorted(STYLES.keys())


def get_style(slug: str) -> StyleDef:
    if slug not in STYLES:
        raise KeyError(f"未知风格 '{slug}'。可用: {STYLE_SLUGS}")
    return STYLES[slug]


def list_styles() -> list[str]:
    return list(STYLE_SLUGS)


# ═══════════════════════════════════════════════════════════════
# 提示词生成（镜像 musickit music_prompt_generator）
# ═══════════════════════════════════════════════════════════════

_MAJOR_KEYS = ["C", "D", "E", "F", "G", "A"]
_MINOR_KEYS = ["Am", "Bm", "C#m", "Dm", "Em", "F#m"]
_DEFAULT_SCALES = ["大调", "自然小调", "多利安", "五声大调", "五声小调", "布鲁斯"]
# 偏小调色彩的调式（配小调调号）
_MINOR_SCALES = {"自然小调", "和声小调", "旋律小调", "多利安", "弗里吉亚", "布鲁斯", "五声小调"}


@dataclass
class Prompt:
    """一条混音提示词（镜像 musickit 提示词 JSON 字段）。"""

    style: str
    mood: str
    bpm: int
    key: str
    scale: str
    drum_intensity: float
    vocal: bool
    instruments: list = field(default_factory=list)  # [{word, pool, role}]
    seed: int = 0

    def as_dict(self) -> dict:
        return {
            "style": self.style,
            "mood": self.mood,
            "bpm": self.bpm,
            "key": self.key,
            "scale": self.scale,
            "drum_intensity": self.drum_intensity,
            "vocal": self.vocal,
            "instruments": list(self.instruments),
            "seed": self.seed,
        }


def generate_prompt(slug: str | None = None, seed: int = 0) -> Prompt:
    """生成一条提示词：风格（可选随机）→ BPM/调性/乐器词 → 声池映射。

    调式按风格偏好（scales）优先，未声明偏好的风格用全局候选池。
    """
    rng = random.Random(seed)
    style = get_style(slug) if slug else STYLES[rng.choice(STYLE_SLUGS)]

    bpm = rng.randint(*style.bpm_range)
    scale_pool = list(style.scales) if style.scales else _DEFAULT_SCALES
    scale = rng.choice(scale_pool)
    key = rng.choice(_MINOR_KEYS if scale in _MINOR_SCALES else _MAJOR_KEYS)

    instruments: list[dict] = []
    words: list[str] = list(style.drum_words) + list(style.bass_words) + list(style.guita_words)
    if style.vocal:
        words.append("vocal")
    words += list(style.accent_words)

    seen_pools: set[str] = set()
    for w in words:
        pool = resolve_pool(w)
        role = mixer_role_for(w)
        if not pool or pool in seen_pools:
            continue
        seen_pools.add(pool)
        instruments.append({"word": w, "pool": pool, "role": role})

    return Prompt(
        style=style.slug,
        mood=style.mood,
        bpm=bpm,
        key=key,
        scale=scale,
        drum_intensity=style.drum_intensity,
        vocal=style.vocal,
        instruments=instruments,
        seed=seed,
    )
