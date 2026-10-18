# M15 Report — Daily Alerts

> **Date:** 2026-10-18 · **Branch:** `wickstreet/m10-m11` · **Plan:** [M15 plan](../plans/2026-10-18-m15-alerts-plan.md) · **Requirement:** FR-22, NFR-1a ([ADD A1](../../architecture/ADD-amendment-A1.md))

## What changed

| Part | Result | Commit |
|---|---|---|
| Plan | One-shot alerts on the chart's own series; rules, API and UI. | `1de89f6` |
| Backend | `alerts` table (migration `0015_alerts`). Sources: close, RSI 14, ADX 14, ATR 14, MACD line, signal and histogram. Intervals 1D, 1W, 1M. Conditions: crosses above or below, is above or below. API: list, create, delete, re-arm, mark seen, check now. The daily job checks alerts once every strategy has synced. | `42cecfe` |
| Price basis | A threshold on close, ATR or MACD follows later splits and bonuses. | `6fe4d6b` |
| UI | An Alerts tab in the side panel, with a count of new firings. "Alert at this price…" in the chart menu. | `6c8bdde` |

## Exit criteria

| Criterion | Result |
|---|---|
| Golden alert tests: fixed bars give fixed alerts | 11 tests: each condition, equality, a cross that starts on the armed bar, warm-up gaps, running weeks and months, re-arming, and a late check that fires on the same bar as a check on the day. |
| Parity: chart series and alert input match for one `data_version` | For all 7 sources at 1D, 1W and 1M, the evaluator's values equal the chart API's, value for value, with the same `data_version`. The evaluator calls the chart's own use cases, so parity holds by construction; the test proves it. |

## Decisions taken

- **An alert fires once.** The owner re-arms it to watch again. A recurring alert would need a rule for repeats, which no one asked for.
- **It fires on the first complete bar after it was armed that meets the condition,** so the result never depends on when the check ran. A missed daily job cannot hide a cross.
- **Weekly and monthly alerts wait for the period to close.** A running week can still change.
- **A direct call, not an event subscriber.** ADD A1 named the `RunCompleted` event as the hook. The publisher has no subscribers, and one call site needs none. A subscriber can replace the call when a second consumer appears.
- **Delivery stays in the app**, as ADD A1 §4 says. Email, Telegram and webhooks would need third-party accounts.

## Defect found and fixed in the design

**Price thresholds did not follow corporate actions.** A threshold is set in the price basis of its day. A later split or bonus rescales every earlier bar, so a `below 90` alert on a ₹100 stock would have fired on the ₹50 post-bonus bars, though nothing fell. The check now compares at `threshold × factor(armed day)`, from the current adjustment schedule; RSI and ADX do not scale. It is the same reason drawings store traded prices (ADR-013 §5). A regression test applies a 1:1 bonus after arming: without the fix the wrong alert fires; with it, only the rescaled one does.

Two test errors were mine, not the code's. A parity sanity check expected indicator values on 14 monthly bars, which are too few to warm up. A test created an alert after the bonus, so it had no later bars to watch. Both tests were corrected; no assertion was weakened.

## Verification

| Suite | Result |
|---|---|
| Backend `pytest` | 743 passed (24 new) |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Web Vitest | 91 passed |
| Web ESLint, build | clean |
| Playwright | 65 passed (2 new: set from the chart, check, fire, see, re-arm, delete; a count for firings while the list was closed) |
| NFR-11 chart open (30 runs each) | Warm P95 168 ms (target ≤ 1 s); cold P95 207 ms (target ≤ 3 s) |

The E2E database gets no new bars, so the E2E script can move an alert's armed date 30 days back (`db.py age-alerts`, guarded to `*_e2e` databases like `reset`).

## Not in M15

Delivery outside the app, recurring alerts, alerts on browser-only indicators (NFR-1a forbids them), and alerts on drawings.
