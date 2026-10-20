"""The RS rating cache key names the computation, not the strategy (ADR-014 §11)."""

from __future__ import annotations

from momentum25.application.services import rs_ratings
from momentum25.application.services.rs_ratings import rs_cache_basis


def test_same_weights_share_a_basis_and_new_weights_do_not() -> None:
    weights = {"63": 0.4, "126": 0.2, "189": 0.2, "252": 0.2}
    assert rs_cache_basis(weights) == rs_cache_basis(dict(reversed(list(weights.items()))))
    assert rs_cache_basis(weights) != rs_cache_basis({**weights, "63": 0.5})
    assert rs_cache_basis(None) == rs_cache_basis({})


def test_a_new_engine_version_changes_the_basis(monkeypatch) -> None:
    before = rs_cache_basis(None)
    monkeypatch.setattr(rs_ratings, "ENGINE_VERSION", 99)
    assert rs_cache_basis(None) != before
