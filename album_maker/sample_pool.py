"""album_maker/sample_pool.py — 真实采样池自动构建（公共模块）
============================================================
从磁盘扫描真实采样（radio_music_stems / 特殊乐器 / 管弦库），
自动按角色归类生成 InstrumentPool raw dict。

quick / make / beat 制作共享此模块，确保采样选择逻辑一致。
"""

from __future__ import annotations

from pathlib import Path

# 真实采样扫描目录（优先级从上到下）
SAMPLE_SCAN_DIRS = [
    Path(r"G:/radio_music_stems"),                          # 真实歌拆解（优先）
    Path(r"G:/radio_special_instruments/world_percussion"),
    Path(r"G:/radio_special_instruments/VSCO-2-CE-master"),
]

# 合成器兜底乐器池
DEFAULT_SYNTH_POOL = {
    "name": "Quick Synth Pool",
    "bpm": 120, "key": "C", "scale": "major",
    "global_volume": 0.85,
    "generation": {"diversity": 0.5, "humanize": True, "seed": 42, "chord_progression": "dreamy"},
    "instruments": [
        {"name": "主旋律", "role": "melody", "engine": "wavetable", "preset": "synth_lead", "volume": 0.85, "pan": 0.1},
        {"name": "和弦铺底", "role": "chord", "engine": "fm_advanced", "preset": "warm_pad", "volume": 0.65, "pan": -0.2},
        {"name": "低音贝斯", "role": "bass", "engine": "subtractive", "preset": "deep_bass", "volume": 0.9, "pan": 0.0},
        {"name": "电子鼓", "role": "drum", "engine": "noise", "volume": 0.85, "pan": 0.0},
        {"name": "氛围铺底", "role": "pad", "engine": "granular", "preset": "bright_pad", "volume": 0.45, "pan": 0.3},
    ],
}

# 技法名 / 通用目录名黑名单（不当作乐器名）
_SKIP_WORDS = (
    "stac", "stacc", "pizz", "vib", "trem", "arco", "spic", "sus", "susvib",
    "susnv", "suslong", "short", "loud", "quiet", "rolls", "buzz", "fall",
    "sustain", "vibrato", "harmon", "expvib", "mute", "samples",
    "strings", "brass", "woodwinds", "percussion", "keys", "misc",
    "vsco-2-ce-master", "vsco", "varwood", "varmetal", "temp",
    "raw", "solo", "section",
)

# 乐器名 → 角色 映射规则
_ROLE_RULES = [
    (["drum", "bongo", "conga", "cajon", "darbuka", "shaker", "maraca",
      "castanet", "clap", "clave", "timpani", "snare", "cymb", "tambourine",
      "perc", "kick", "hihat"], "drum"),
    (["bass", "tuba", "trombone", "contrabass", "cello section"], "bass"),
    (["violin", "viola", "trumpet", "horn", "flute", "clarinet", "oboe",
      "harp", "cello", "solo"], "melody"),
    (["piano", "organ", "upright", "glock", "marimba", "xylo", "celesta",
      "bell", "gong", "vibra", "choir", "pad", "atmos"], "chord"),
    (["vocals", "voice", "vocal", "choir"], "melody"),
    (["other", "texture", "fx", "effect", "glitch", "noise"], "pad"),
]

ROLE_ORDER = ["melody", "chord", "bass", "drum", "pad", "fx"]


def wav_to_instrument_name(wav: Path, root: Path) -> str:
    """从 WAV 路径提取乐器名——跳过技法名，取真正的乐器目录名。

    特殊处理 radio_music_stems：用文件名 + 歌名前缀去重。
    """
    parts = list(wav.relative_to(root).parts)

    # radio_music_stems：文件名就是乐器名，加歌名前缀去重
    if "radio_music_stems" in root.as_posix():
        song = parts[0][:20] if parts else ""
        stem = wav.stem.replace("_", " ").strip()
        return f"{song}_{stem}" if song else stem

    # 从后往前找：第一个非技法名/非通用目录/非项目根的目录名
    for p in reversed(parts[:-1]):
        clean = p.replace("_", " ").strip()
        clean_lower = clean.lower()
        if len(clean) < 4 or clean[0].isdigit() or clean_lower in _SKIP_WORDS:
            continue
        if "world-percussion-main" in clean_lower or "salamand" in clean_lower:
            continue
        return clean[:35]

    return parts[-2].replace("_", " ").strip()[:35] if len(parts) >= 2 else wav.stem[:35]


def assign_sample_role(name: str) -> str:
    """根据乐器名推断角色。"""
    n = name.lower()
    for patterns, role in _ROLE_RULES:
        if any(p in n for p in patterns):
            return role
    return "chord"


def auto_build_pool(
    scan_dirs: list[Path] | None = None,
    max_per_role: int = 4,
    include_synth_fallback: bool = True,
) -> dict:
    """自动扫描真实采样池，优先用真实采样，不足时用合成器补位。

    Args:
        scan_dirs: 扫描目录列表，None=用默认 SAMPLE_SCAN_DIRS
        max_per_role: 每种角色最多取几件
        include_synth_fallback: 是否用合成器补位

    Returns:
        InstrumentPool raw dict（可直接传给 AlbumConfig(pool_raw=...)）
    """
    dirs = scan_dirs if scan_dirs is not None else SAMPLE_SCAN_DIRS
    by_role: dict[str, list[dict]] = {r: [] for r in ROLE_ORDER}

    for scan_dir in dirs:
        if not scan_dir.exists():
            continue
        for wav in scan_dir.rglob("*.wav"):
            inst_name = wav_to_instrument_name(wav, scan_dir)
            role = assign_sample_role(inst_name)

            existing_names = {i["name"] for i in by_role[role]}
            if len(by_role[role]) >= max_per_role or inst_name in existing_names:
                continue

            by_role[role].append({
                "name": inst_name,
                "role": role,
                "engine": "sampler",
                "sample_path": wav.as_posix(),
                "volume": 0.7,
                "pan": 0.0,
            })

    sampled_instruments = []
    for role in ROLE_ORDER:
        sampled_instruments.extend(by_role[role][:max_per_role])

    instruments = sampled_instruments
    synth_fallback = []
    if include_synth_fallback:
        seen_roles = {i["role"] for i in sampled_instruments}
        synth_fallback = [i for i in DEFAULT_SYNTH_POOL["instruments"]
                          if i["role"] not in seen_roles]
        instruments = sampled_instruments + synth_fallback

    pool_name = "Auto Pool"
    if sampled_instruments:
        pool_name = f"Auto Pool ({len(sampled_instruments)} sampled + {len(synth_fallback)} synth)"

    return {
        "name": pool_name,
        "bpm": 120, "key": "C", "scale": "major",
        "global_volume": 0.85,
        "generation": {"diversity": 0.5, "humanize": True, "seed": 42, "chord_progression": "dreamy"},
        "instruments": instruments,
    }
