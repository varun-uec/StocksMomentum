"""The RS rating cache key names the computation, not the strategy (ADR-014 §11)."""

from __future__ import annotations

from momentum25.application.services import rs_ratings
from momentum25.application.services.rs_ratings import rs_cache_basis


def test_same_weights_share_a_basis_and_new_weights_do_not() -> None:
    weights = {"63": 0.4, "126": 0.2, "189": 0.2, "252": 0.2}
    assert rs_cache_basis(weights, 1) == rs_cache_basis(dict(reversed(list(weights.items()))), 1)
    assert rs_cache_basis(weights, 1) != rs_cache_basis({**weights, "63": 0.5}, 1)
    assert rs_cache_basis(None, 1) == rs_cache_basis({}, 1)


def test_a_new_engine_version_changes_the_basis(monkeypatch) -> None:
    before = rs_cache_basis(None, 1)
    monkeypatch.setattr(rs_ratings, "ENGINE_VERSION", 99)
    assert rs_cache_basis(None, 1) != before


def test_a_same_day_correction_changes_the_basis() -> None:
    """R3-B-14: a committed correction moves the data revision and so the key."""
    assert rs_cache_basis(None, 41) != rs_cache_basis(None, 42)
