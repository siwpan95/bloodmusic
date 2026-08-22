#!/usr/bin/env python3
"""
专辑乐池与 SKILL 集成测试（archive/album_generator.py 已移除后的收口版）。

覆盖:
  1. pool_presets/ 10 个专辑 YAML 结构完整性
  2. SKILL.md Workflow 10 与 frontmatter 校验
  3. InstrumentPool / PoolRenderer / pool_styles 导入回归
  4. 10 个专辑预设 YAML 与命名一致性
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
POOL_DIR = PROJECT_ROOT / "music" / "pool_presets"
SKILL_MD = PROJECT_ROOT / "skill" / "bloodmusic-beats" / "SKILL.md"

sys.path.insert(0, str(PROJECT_ROOT))


# ═════════════════════════════════════════════════════════════
# 1. YAML File Structural Integrity
# ═════════════════════════════════════════════════════════════

EXPECTED_ALBUM_FILES = [
    "album_dawn_overture.yaml",
    "album_lost_in_cosmos.yaml",
    "album_deep_sea.yaml",
    "album_midnight_jazz.yaml",
    "album_neon_pulse.yaml",
    "album_heros_journey.yaml",
    "album_nostalgia.yaml",
    "album_birds_mountains.yaml",
    "album_pastoral_tune.yaml",
    "album_finale_rebirth.yaml",
]

REQUIRED_TOP_KEYS = {"name", "version", "bpm", "key", "scale", "style"}
REQUIRED_INSTRUMENT_KEYS = {"name", "role", "engine"}
VALID_ROLES = {"melody", "chord", "bass", "drum", "pad", "fx"}
VALID_ENGINES = {
    "wavetable", "subtractive", "fm", "fm_advanced",
    "karplus_strong", "granular", "waveguide", "noise",
}
REQUIRED_GENERATION_KEYS = {"diversity", "humanize", "chord_progression"}


def test_all_10_album_yaml_files_exist():
    """Verify exactly 10 album YAML files exist in pool_presets/."""
    for fname in EXPECTED_ALBUM_FILES:
        path = POOL_DIR / fname
        assert path.exists(), f"Missing YAML: {fname}"
        assert path.stat().st_size > 0, f"Empty YAML: {fname}"


class TestYamlStructure:
    """Parameterized tests for each album YAML file."""

    @pytest.fixture(params=EXPECTED_ALBUM_FILES)
    def yaml_data(self, request):
        path = POOL_DIR / request.param
        with open(path, "r", encoding="utf-8") as f:
            return request.param, yaml.safe_load(f)

    def test_top_level_keys(self, yaml_data):
        """All YAML files have required top-level keys."""
        fname, data = yaml_data
        missing = REQUIRED_TOP_KEYS - set(data.keys())
        assert not missing, f"{fname}: missing top-level keys: {missing}"

    def test_bpm_is_positive_int(self, yaml_data):
        """bpm must be a positive integer."""
        fname, data = yaml_data
        bpm = data["bpm"]
        assert isinstance(bpm, int), f"{fname}: bpm should be int, got {type(bpm)}"
        assert bpm > 0, f"{fname}: bpm must be positive, got {bpm}"

    def test_style_is_valid(self, yaml_data):
        """style must match one of the known StylePreset names."""
        fname, data = yaml_data
        valid_styles = {"exploration", "battle", "town", "dungeon", "ambient"}
        assert data["style"] in valid_styles, (
            f"{fname}: unknown style '{data['style']}', expected one of {valid_styles}"
        )

    def test_instruments_array_not_empty(self, yaml_data):
        """Each YAML must have at least one instrument."""
        fname, data = yaml_data
        instruments = data.get("instruments", [])
        assert isinstance(instruments, list), f"{fname}: instruments must be a list"
        assert len(instruments) > 0, f"{fname}: instruments list is empty"

    def test_each_instrument_has_required_keys(self, yaml_data):
        """Every instrument entry must have name, role, and engine."""
        fname, data = yaml_data
        for i, inst in enumerate(data.get("instruments", [])):
            missing = REQUIRED_INSTRUMENT_KEYS - set(inst.keys())
            assert not missing, (
                f"{fname}: instrument[{i}] '{inst.get('name', '?')}' "
                f"missing keys: {missing}"
            )

    def test_each_instrument_role_valid(self, yaml_data):
        """Every instrument role must be a known role."""
        fname, data = yaml_data
        for i, inst in enumerate(data.get("instruments", [])):
            role = inst.get("role")
            assert role in VALID_ROLES, (
                f"{fname}: instrument[{i}] '{inst.get('name', '?')}' "
                f"invalid role: {role}"
            )

    def test_each_instrument_engine_valid(self, yaml_data):
        """Every instrument engine must be a known SynthEngine."""
        fname, data = yaml_data
        for i, inst in enumerate(data.get("instruments", [])):
            engine = inst.get("engine")
            assert engine in VALID_ENGINES, (
                f"{fname}: instrument[{i}] '{inst.get('name', '?')}' "
                f"invalid engine: {engine}"
            )

    def test_generation_section(self, yaml_data):
        """generation section must have diversity, humanize, chord_progression."""
        fname, data = yaml_data
        gen = data.get("generation", {})
        missing = REQUIRED_GENERATION_KEYS - set(gen.keys())
        assert not missing, f"{fname}: generation missing keys: {missing}"

        # diversity must be 0.0-1.0
        diversity = gen.get("diversity")
        assert isinstance(diversity, (int, float)), (
            f"{fname}: diversity must be numeric"
        )
        assert 0.0 <= diversity <= 1.0, (
            f"{fname}: diversity out of range: {diversity}"
        )

        # humanize must be bool
        assert isinstance(gen.get("humanize"), bool), (
            f"{fname}: humanize must be boolean"
        )


# ═════════════════════════════════════════════════════════════
# 2. SKILL.md Verification
# ═════════════════════════════════════════════════════════════

def test_skill_md_workflow_10_exists():
    """SKILL.md must contain Workflow 10 for InstrumentPool."""
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Workflow 10: InstrumentPool" in content, "Workflow 10 heading not found in SKILL.md"
    assert "InstrumentPool" in content, "InstrumentPool not mentioned in SKILL.md"


def test_skill_md_workflow_10_has_required_sections():
    """Workflow 10 must cover: core concepts, quick start, styles, templates, album gen."""
    content = SKILL_MD.read_text(encoding="utf-8")

    # Find Workflow 10 section
    wf_start = content.find("### Workflow 10: InstrumentPool")
    assert wf_start >= 0, "Workflow 10 heading not found"

    # Get the section content until next ### Workflow or ## heading
    rest = content[wf_start:]
    next_section = len(rest)
    for marker in ["\n### Workflow ", "\n## "]:
        idx = rest.find(marker, len("### Workflow 10: InstrumentPool"))
        if idx >= 0 and idx < next_section:
            next_section = idx
    wf_content = rest[:next_section]

    # Required sub-sections
    required = [
        ("核心概念", "InstrumentPool / StylePreset / PoolRenderer concept section"),
        ("快速开始", "Quick start code example"),
        ("StylePreset", "5 built-in styles table"),
        ("PoolTemplate", "5 built-in pool templates"),
        ("生成整张专辑", "Album generation command"),
        ("自定义乐池 YAML", "Custom YAML format documentation"),
    ]

    for keyword, desc in required:
        assert keyword in wf_content, (
            f"Workflow 10 missing required section: '{keyword}' ({desc})"
        )


def test_skill_md_frontmatter_has_pool_triggers():
    """Frontmatter description must include InstrumentPool trigger words."""
    content = SKILL_MD.read_text(encoding="utf-8")

    # Extract frontmatter (between first two --- markers)
    fm_start = content.find("---")
    fm_end = content.find("---", fm_start + 3)
    frontmatter = content[fm_start:fm_end + 3]

    pool_triggers = [
        "InstrumentPool",
        "instrument pool",
        "album with pool",
        "pool render",
        "使用乐器池",
        "乐池生成",
    ]

    for trigger in pool_triggers:
        assert trigger.lower() in frontmatter.lower(), (
            f"Frontmatter missing trigger word: '{trigger}'"
        )


# ═════════════════════════════════════════════════════════════
# 3. InstrumentPool Module Import Regression
# ═════════════════════════════════════════════════════════════

def test_instrument_pool_import():
    """Regression: InstrumentPool must be importable."""
    from bloodmusic.music.instrument_pool import InstrumentPool
    assert InstrumentPool is not None


def test_pool_renderer_import():
    """Regression: PoolRenderer must be importable."""
    from bloodmusic.music.pool_renderer import PoolRenderer
    assert PoolRenderer is not None


def test_pool_styles_import():
    """Regression: pool_styles must be importable with known styles."""
    from bloodmusic.music.pool_styles import get_style, list_styles
    styles = list_styles()
    assert "battle" in styles, "battle style missing"
    assert "ambient" in styles, "ambient style missing"


# ═════════════════════════════════════════════════════════════
# 4. 专辑预设命名一致性
# ═════════════════════════════════════════════════════════════

def test_album_style_pools_mapping_consistency():
    """10 个专辑预设 YAML 文件与预期清单一一对应（无缺漏、无多余）。"""
    album_yamls = sorted(p.name for p in POOL_DIR.glob("album_*.yaml"))
    assert album_yamls == sorted(EXPECTED_ALBUM_FILES), (
        f"pool_presets 专辑 YAML 与预期不一致:\n"
        f"  实际: {album_yamls}\n  预期: {sorted(EXPECTED_ALBUM_FILES)}"
    )
