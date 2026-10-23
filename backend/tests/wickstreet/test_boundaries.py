"""Static boundary checks: OM-1 (no mode in the core), OM-11 (layering), OM-12 (routes, tables).

import-linter enforces the import rules (``lint-imports``, CI). These tests catch
what it cannot see: mode checks written without an import, a new context left out
of the layering contract, and MF tables or routes leaking into Momentum25.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

import wickstreet
from momentum25.infrastructure.persistence.history import ALL_VERSIONED
from momentum25.infrastructure.persistence.models import Base
from momentum25.main import create_app as create_momentum25_app
from wickstreet.app import create_app as create_wickstreet_app
from wickstreet.config import WickstreetSettings
from wickstreet.persistence.database import SCHEMA, metadata

_BACKEND = Path(__file__).resolve().parents[2]
_PACKAGE = Path(wickstreet.__file__).parent
_CONTRACTS = tomllib.loads((_BACKEND / "pyproject.toml").read_text())["tool"]["importlinter"]


def _contexts() -> list[Path]:
    return sorted(p for p in _PACKAGE.iterdir() if (p / "domain").is_dir())


def _core_modules() -> list[Path]:
    return [
        module
        for context in _contexts()
        for layer in ("domain", "application")
        for module in sorted((context / layer).rglob("*.py"))
    ]


def test_there_is_core_code_to_check() -> None:
    assert _core_modules()


@pytest.mark.parametrize("module", _core_modules(), ids=lambda p: str(p.relative_to(_PACKAGE)))
def test_core_code_never_mentions_the_mode(module: Path) -> None:
    """OM-1: no mode name, mode value or settings object in domain or application code."""
    tree = ast.parse(module.read_text())
    words: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            words.add(node.attr.lower())
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            words.update(node.value.lower().split())
        elif isinstance(node, ast.ImportFrom) and node.module:
            words.add(node.module)
    found = words & {"mode", "personal", "saas", "settings", "wickstreet.config"}
    assert not found, f"{module.name} mentions {sorted(found)}"


def test_every_context_is_in_the_layering_contract() -> None:
    """OM-11: a new context must join the layers contract before it can pass."""
    layers = next(c for c in _CONTRACTS["contracts"] if c["type"] == "layers" and "containers" in c)
    expected = {f"wickstreet.{context.name}" for context in _contexts()}
    assert set(layers["containers"]) == expected
    assert layers["layers"] == ["(interface)", "application", "domain"]


def test_the_two_applications_stay_independent() -> None:
    """OM-11: import-linter forbids imports in both directions."""
    independence = next(c for c in _CONTRACTS["contracts"] if c["type"] == "independence")
    assert set(independence["modules"]) == {"momentum25", "wickstreet"}


def test_momentum25_registers_no_mf_route() -> None:
    """OM-12: only the wickstreet composition root registers MF routes."""
    paths = list(create_momentum25_app().openapi()["paths"])
    assert paths
    assert not [path for path in paths if path.startswith("/api/v1/mf")]


def test_wickstreet_registers_its_own_routes() -> None:
    assert "/me" in create_wickstreet_app(WickstreetSettings()).openapi()["paths"]


def test_mf_tables_live_in_their_own_schema_only() -> None:
    """OM-12: MF tables never join Momentum25's metadata or its data_version."""
    mf_names = {table.name for table in metadata.tables.values()}
    assert mf_names
    assert all(table.schema == SCHEMA for table in metadata.tables.values())
    assert not mf_names & {table.name for table in Base.metadata.tables.values()}
    assert not mf_names & set(ALL_VERSIONED)


def test_momentum25_migrations_never_touch_the_mf_schema() -> None:
    versions = _BACKEND / "src" / "momentum25" / "infrastructure" / "persistence" / "migrations"
    assert not [p.name for p in versions.rglob("*.py") if SCHEMA in p.read_text()]
