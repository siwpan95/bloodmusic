"""mirror —— 镜像层：musickit（纯采样混音）功能结构的机生成对应物
================================================================

bloodmusic 与 musickit 互为镜像、代码零共享：
  - musickit 的 13 采样池 → 本包 13 个机生成声池（同名）
  - instrument_taxonomy.json → taxonomy.py（同词表语义）
  - music/styles/ 65 流派 → styles.py
  - remix/templates/structures.json → structure.py
  - remix 选音规则 → selection.py
  - burbidge_album 24 混音师签名链 → mixer_styles.py
  - remix/main.py --remix → cli.py --remix（参数同名）

所有音频均由 bloodmusic 合成引擎 + autowav 作曲核心实时生成，
license_tier 恒为 selfgen（天然 release-safe）。

用法：
    python -m bloodmusic.mirror --remix --bars 16 --bpm 140 --seed 42
    详见 docs/PLAN_mirror_2026.md
"""

from .taxonomy import (
    POOLS,
    CANONICAL_CLASSES,
    classify_word,
    resolve_pool,
    mixer_role_for,
)
from .manifest import (
    SourceManifestEntry,
    PoolManifest,
    write_pool_manifest,
    read_pool_manifest,
)
from .styles import (
    STYLE_SLUGS,
    get_style,
    list_styles,
    generate_prompt,
)
from .structure import (
    STRUCTURES,
    resolve_structure,
    list_structures,
)
from .selection import SourceSpec, select_sources
from .mixer_styles import (
    MIXER_STYLES,
    resolve_style,
    list_mixers,
    apply_bus_chain,
    apply_master_chain,
)
from .report import RemixReport
from .renderer import run_remix, RemixResult

__version__ = "1.0.0"

__all__ = [
    "POOLS",
    "CANONICAL_CLASSES",
    "classify_word",
    "resolve_pool",
    "mixer_role_for",
    "SourceManifestEntry",
    "PoolManifest",
    "write_pool_manifest",
    "read_pool_manifest",
    "STYLE_SLUGS",
    "get_style",
    "list_styles",
    "generate_prompt",
    "STRUCTURES",
    "resolve_structure",
    "list_structures",
    "SourceSpec",
    "select_sources",
    "MIXER_STYLES",
    "resolve_style",
    "list_mixers",
    "apply_bus_chain",
    "apply_master_chain",
    "RemixReport",
    "run_remix",
    "RemixResult",
]
