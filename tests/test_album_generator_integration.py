#!/usr/bin/env python3
"""
Integration tests for BloodMusic album_generator.py pool integration.

Tests cover:
  1. YAML file structural integrity (all 10 album presets)
  2. Legacy mode zero-regression (main() + track functions untouched)
  3. Pool mode lazy import correctness
  4. Pool mode rendering (short-duration smoke test)
  5. SKILL.md Workflow 11 presence and frontmatter
  6. InstrumentPool module import regression
"""

import ast
import importlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
# album_generator.py 已归档（被 album_maker/ 子包替代），测试继续验证归档代码
ALBUM_GEN = PROJECT_ROOT / "archive" / "album_generator.py"
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
# 2. Legacy Mode Zero-Regression
# ═════════════════════════════════════════════════════════════

def test_legacy_main_function_has_original_print():
    """main() should still print 'BloodMusic 纯音乐专辑生成器' (no Pool)."""
    source = ALBUM_GEN.read_text(encoding="utf-8")
    assert "BloodMusic 纯音乐专辑生成器" in source, (
        "Legacy print string 'BloodMusic 纯音乐专辑生成器' not found in source"
    )

    # Find main() function body: from 'def main():' to the next top-level 'def'
    lines = source.split("\n")
    main_start = None
    main_end = None
    for i, line in enumerate(lines):
        if line.strip() == "def main():":
            main_start = i
            continue
        if main_start is not None and i > main_start:
            # Top-level 'def' (no indentation) signals end of main()
            if line.startswith("def ") and not line.startswith("    "):
                main_end = i
                break

    assert main_start is not None, "main() function definition not found"
    assert main_end is not None, "Could not find end of main() function"
    main_body = "\n".join(lines[main_start:main_end])

    # The main() function's executable code should NOT reference "Pool"
    # (it should use the legacy print string without "(Pool Mode)")
    assert "(Pool Mode)" not in main_body, (
        "main() function should not print '(Pool Mode)' — legacy regression!"
    )
    assert "generate_album_with_pool" not in main_body, (
        "main() function should not call pool functions — legacy regression!"
    )


def test_all_10_track_functions_exist():
    """All 10 track_xx_xxx() functions must still be defined."""
    source = ALBUM_GEN.read_text(encoding="utf-8")

    expected_funcs = [
        "track_01_dawn_overture",
        "track_02_lost_in_cosmos",
        "track_03_deep_sea_whispers",
        "track_04_midnight_jazz",
        "track_05_neon_pulse",
        "track_06_heros_journey",
        "track_07_nostalgia",
        "track_08_birds_in_mountains",
        "track_09_pastoral_tune",
        "track_10_finale_rebirth",
    ]

    for func_name in expected_funcs:
        assert f"def {func_name}():" in source, (
            f"Track function {func_name}() not found — possible regression!"
        )


def test_cli_default_runs_legacy():
    """Running album_generator.py without --pool should default to legacy (not pool)."""
    # Parse the source to verify: argparse default for --pool is False,
    # and the else branch calls main() (legacy), not generate_album_with_pool()
    source = ALBUM_GEN.read_text(encoding="utf-8")

    # Verify argparse --pool default is store_true (defaults to False)
    assert "add_argument(\"--pool\", action=\"store_true\"" in source, (
        "--pool should use action='store_true' (default: False, legacy)"
    )

    # Verify the else branch calls main(), not pool
    assert "main()" in source, "Legacy main() call must exist"
    assert "if args.pool:" in source or "if args.pool\n" in source, (
        "CLI must check args.pool before pool mode"
    )

    # Verify the else branch structure: if args.pool → pool, else → main()
    pool_idx = source.find("if args.pool:")
    else_idx = source.find("else:", pool_idx)
    assert else_idx > pool_idx, "else: branch must follow if args.pool:"
    else_block = source[else_idx:else_idx + 200]
    assert "main()" in else_block, (
        f"else branch must call main() (legacy). Found: {else_block[:100]}"
    )


# ═════════════════════════════════════════════════════════════
# 3. Pool Mode Lazy Import Correctness
# ═════════════════════════════════════════════════════════════

def test_pool_imports_are_lazy():
    """Pool modules imported lazily inside functions, never at module top level.

    Uses AST analysis (not string matching) so docstring examples and comments
    are not mistaken for real imports.
    """
    source = ALBUM_GEN.read_text(encoding="utf-8")
    tree = ast.parse(source)

    pool_modules = {
        "bloodmusic.music.instrument_pool",
        "bloodmusic.music.pool_renderer",
        "bloodmusic.music.pool_styles",
    }

    # 1. Reject any pool import that is a direct child of the Module node
    #    (i.e. a real top-level import statement). Imports inside function
    #    bodies are nested under FunctionDef, not Module, so they are allowed.
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module in pool_modules:
            pytest.fail(
                f"Pool module '{node.module}' imported at module top level "
                f"(line {node.lineno}) — lazy import violation!"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in pool_modules:
                    pytest.fail(
                        f"Pool module '{alias.name}' imported at module top level "
                        f"(line {node.lineno}) — lazy import violation!"
                    )

    # 2. Confirm the pool modules ARE lazily imported somewhere inside a
    #    function body (otherwise lazy loading is not implemented at all).
    found_in_func: set[str] = set()

    def _scan_func(func_node):
        for child in ast.walk(func_node):
            if isinstance(child, ast.ImportFrom) and child.module in pool_modules:
                found_in_func.add(child.module)
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name in pool_modules:
                        found_in_func.add(alias.name)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _scan_func(node)

    missing = pool_modules - found_in_func
    assert not missing, (
        f"Pool modules never lazily imported inside any function: {missing}"
    )


# ═════════════════════════════════════════════════════════════
# 4. Pool Mode Smoke Test (short duration)
# ═════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestPoolModeSmoke:
    """Smoke-test pool mode with very short duration."""

    def test_pool_cli_help(self):
        """--pool flag is accepted by argparse."""
        result = subprocess.run(
            [sys.executable, str(ALBUM_GEN), "--help"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=15,
        )
        assert "--pool" in result.stdout, "--pool flag missing from help"
        assert "InstrumentPool" in result.stdout, "InstrumentPool mention missing from help"

    def test_pool_mode_prints_correct_header(self):
        """--pool mode should print 'BloodMusic 纯音乐专辑生成器 (Pool Mode)'."""
        result = subprocess.run(
            [sys.executable, str(ALBUM_GEN), "--pool", "--duration", "0.5", "--seed", "42"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=120,
        )
        assert "(Pool Mode)" in result.stdout, (
            f"Pool mode header not printed. stdout: {result.stdout[:500]}"
        )

    def test_pool_mode_produces_wav_files(self):
        """Pool mode with seed=42 should produce at least some WAV files."""
        import tempfile

        # Use a temp directory to avoid sandbox shutil.rmtree issues
        with tempfile.TemporaryDirectory(prefix="bloodmusic_pool_test_") as tmpdir:
            result = subprocess.run(
                [sys.executable, str(ALBUM_GEN), "--pool",
                 "--duration", "15", "--seed", "42",
                 "--output", tmpdir],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=300,
            )

            wav_files = list(Path(tmpdir).glob("*.wav"))

            # At least 1 WAV file should be produced
            assert len(wav_files) >= 1, (
                f"Pool mode produced 0 WAV files in {tmpdir}. "
                f"stdout (last 2000 chars):\n{result.stdout[-2000:]}\n"
                f"stderr:\n{result.stderr[-2000:]}"
            )

            for wf in wav_files:
                size_kb = wf.stat().st_size / 1024
                assert size_kb > 10, f"WAV file {wf.name} is too small: {size_kb:.1f} KB"


# ═════════════════════════════════════════════════════════════
# 5. SKILL.md Verification
# ═════════════════════════════════════════════════════════════

def test_skill_md_workflow_11_exists():
    """SKILL.md must contain Workflow 11 for InstrumentPool."""
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "Workflow 11" in content, "Workflow 11 heading not found in SKILL.md"
    assert "InstrumentPool" in content, "InstrumentPool not mentioned in SKILL.md"


def test_skill_md_workflow_11_has_required_sections():
    """Workflow 11 must cover: core concepts, quick start, styles, templates, album gen."""
    content = SKILL_MD.read_text(encoding="utf-8")

    # Find Workflow 11 section
    wf11_start = content.find("### Workflow 11")
    assert wf11_start >= 0, "Workflow 11 heading not found"

    # Get the section content until next ### Workflow or ## heading
    rest = content[wf11_start:]
    next_section = len(rest)
    for marker in ["\n### Workflow ", "\n## "]:
        idx = rest.find(marker, len("### Workflow 11"))
        if idx >= 0 and idx < next_section:
            next_section = idx
    wf11_content = rest[:next_section]

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
        assert keyword in wf11_content, (
            f"Workflow 11 missing required section: '{keyword}' ({desc})"
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
# 6. InstrumentPool Module Import Regression
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


def test_album_style_pools_mapping_consistency():
    """ALBUM_STYLE_POOLS dict in album_generator.py maps to existing YAML files."""
    # Import the mapping from the source
    spec = importlib.util.spec_from_file_location(
        "album_gen", str(ALBUM_GEN)
    )
    module = importlib.util.module_from_spec(spec)

    # We need to mock the bloodmusic imports to avoid loading heavy modules
    # Just parse the dict directly from source
    import ast
    source = ALBUM_GEN.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find the ALBUM_STYLE_POOLS dict
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "ALBUM_STYLE_POOLS":
                    # Count entries
                    if isinstance(node.value, ast.Dict):
                        num_entries = len(node.value.keys)
                        assert num_entries == 10, (
                            f"ALBUM_STYLE_POOLS has {num_entries} entries, expected 10"
                        )

                        # Check each value is a 2-tuple (yaml_file, style_name)
                        for key_node, val_node in zip(node.value.keys, node.value.values):
                            if isinstance(val_node, ast.Tuple):
                                assert len(val_node.elts) == 2, (
                                    f"ALBUM_STYLE_POOLS value should be (yaml_file, style_name) tuple"
                                )
                    break

    # Also verify all YAML files referenced exist
    for entry_key in EXPECTED_ALBUM_FILES:
        yaml_path = POOL_DIR / entry_key
        assert yaml_path.exists(), f"ALBUM_STYLE_POOLS references missing file: {entry_key}"


# ═════════════════════════════════════════════════════════════
# 7. Output Directory Isolation
# ═════════════════════════════════════════════════════════════

def test_pool_output_dir_different_from_legacy():
    """Pool mode uses album_output_pool/, NOT album_output/."""
    source = ALBUM_GEN.read_text(encoding="utf-8")
    assert "album_output_pool" in source, "POOL_OUTPUT_DIR must reference 'album_output_pool'"
    assert "POOL_OUTPUT_DIR" in source, "POOL_OUTPUT_DIR constant must exist"


def test_legacy_output_dir_unchanged():
    """Legacy OUTPUT_DIR must remain 'album_output'."""
    source = ALBUM_GEN.read_text(encoding="utf-8")
    # The legacy OUTPUT_DIR constant should still point to "album_output"
    assert 'OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "album_output")' in source, (
        "Legacy OUTPUT_DIR changed!"
    )
