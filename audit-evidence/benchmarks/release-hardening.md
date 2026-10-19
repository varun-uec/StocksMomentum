# Focused Release-Hardening Evidence

**Date:** 2026-10-19 · **Scope:** release hardening after the M16 audit; this does not repeat route discovery or the full product audit.

## Observed verification

- Playwright: **29 passed** across M13 charting, M14 Strategy Studio, M15 alerts and M16 data policy. Every one of the 12 drawing tools was drawn, selected, moved, recolored, undone/redone, deleted/restored and checked after reload.
- Strategy Studio: a synthetic 36-month hold-out with reconstructed inputs was rejected before an evaluation row was created or the family's hold-out was spent. A matured hold-out completed once per family, remained labeled “One evaluation is not validation,” and disabled a second attempt.
- Alerts: a synthetic GOLDIAM close alert armed before the 2026-07-10 bonus retained its threshold on the adjusted basis. The observed adjustment factor was `0.75`, the latest adjusted close was `75`, and a threshold of `90` stayed active without a false trigger.
- Restart recovery: two separate Playwright invocations passed. The first wrote TCS workspace state (`1W`, `3M`), one horizontal drawing and one active close alert. PostgreSQL 16 was restarted with the same newly created named volume. The second invocation started a fresh API process and recovered all three records.
- Data policy and imports: direct exchange refresh paths rejected while disabled; the Data page displayed the local authorized-import instructions; EOD/actions and benchmark import behavior was checked with synthetic CSV fixtures.
- The updated Data screen was rerun separately after adding `../.env` loading to its command block; that browser check passed and its rendered screenshot was visually inspected.
- Backend focused regressions: **9 unit tests** and **6 integration tests passed**. Ruff passed; strict mypy passed on 261 source files. Web ESLint passed, Vitest passed **101 tests**, and the production build passed.

The main browser log is [`release-hardening-e2e-confirmed.log`](release-hardening-e2e-confirmed.log); the Data-screen recapture log is [`release-hardening-ui-evidence.log`](release-hardening-ui-evidence.log); backend verification output is [`release-hardening-api-tests.log`](release-hardening-api-tests.log).

## Isolation and boundaries

The browser run used a newly created `wickstreet_persistent_e2e` database and named Docker volume, bound to a loopback port. The script refuses pre-existing container, volume, port and evidence-file names, verifies the exact E2E database marker before fixture writes, and removes only resources it created. The API integration run used a separate ephemeral PostgreSQL database named `wickstreet_release_hardening3_test`; its destructive test fixture rebuilt schema only there. No user database was reset, copied, seeded or modified. No NSE automated download or live-source file was used.

The tests validate application behavior against synthetic data. They do not validate vendor data correctness, legal permissions for a source, backup restoration, DB failure during a transaction, all schema migration histories, every Studio constraint, every corporate-action/alert combination, or a full accessibility/memory soak.

## Performance reference

NFR-11 was not re-benchmarked in this focused pass. The independent audit measured chart-open warm P95 **165 ms** and first open after a fresh API process **482 ms** against the agreed warm ≤1 s and cold ≤3 s targets. The 1/4/16 chart P95s from that audit are recorded in [`m13-bench.json`](m13-bench.json). This pass changes the data acquisition path and import UI, not the chart renderer.

## Release status

No P0/P1 defect was observed in the focused workflows. The source publication remains on hold while the project licence and Wickstreet name/trademark decisions are unresolved. Optional direct exchange adapters remain disabled by default and require operator authorization before enabling. Wickstreet has no login: keep it loopback-only, or place an authenticating proxy in front of any network-exposed instance; an unauthenticated network-exposed instance is not secure.
