"""Unit tests for ISIN-first security resolution (RP-012 Phase 2 fast-follow)."""

from __future__ import annotations

from momentum25.domain.research.symbol_resolution import (
    ResolutionPath,
    normalize_isin,
    resolve_security,
)

# A security whose ticker drifted: legacy row's period-correct symbol was
# "OLDTICK", but today's master lists it as "NEWTICK" under the same ISIN.
_SYMBOL_TO_ID = {"NEWTICK": 10, "STABLE": 20}
_ISIN_TO_ID = {"INE000A01011": 10, "INE000B01022": 20}


def test_resolves_by_isin_despite_ticker_drift() -> None:
    resolution = resolve_security("OLDTICK", "INE000A01011", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id == 10
    assert resolution.path is ResolutionPath.ISIN


def test_isin_takes_precedence_over_symbol() -> None:
    # Even when the symbol would resolve, a present, resolvable ISIN wins so the
    # identity is anchored to the stable key.
    resolution = resolve_security("STABLE", "INE000B01022", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id == 20
    assert resolution.path is ResolutionPath.ISIN


def test_falls_back_to_symbol_when_isin_absent() -> None:
    resolution = resolve_security("STABLE", None, _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id == 20
    assert resolution.path is ResolutionPath.SYMBOL_FALLBACK


def test_falls_back_to_symbol_when_isin_unknown() -> None:
    # ISIN present but not in the master (e.g. a data-quality issue in the
    # column) — must not fail hard; try the symbol next.
    resolution = resolve_security("STABLE", "INE999Z09099", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id == 20
    assert resolution.path is ResolutionPath.SYMBOL_FALLBACK


def test_unresolved_when_neither_matches() -> None:
    resolution = resolve_security("GHOST", "INE999Z09099", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id is None
    assert resolution.path is ResolutionPath.UNRESOLVED


def test_blank_isin_is_treated_as_absent() -> None:
    resolution = resolve_security("STABLE", "   ", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.path is ResolutionPath.SYMBOL_FALLBACK


def test_isin_lookup_is_case_and_whitespace_normalized() -> None:
    resolution = resolve_security("OLDTICK", "  ine000a01011 ", _SYMBOL_TO_ID, _ISIN_TO_ID)
    assert resolution.security_id == 10
    assert resolution.path is ResolutionPath.ISIN


def test_normalize_isin() -> None:
    assert normalize_isin(None) is None
    assert normalize_isin("") is None
    assert normalize_isin("  ") is None
    assert normalize_isin(" ine000a01011 ") == "INE000A01011"
