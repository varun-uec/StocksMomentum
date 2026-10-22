# M15 Plan — Daily Alerts

> **Date:** 2026-10-18 · **Requirement:** FR-22 ([ADD A1](../../architecture/ADD-amendment-A1.md)) · **Authority:** NFR-1a · **Milestones:** [M15](2026-10-18-wickstreet-milestones.md)

## Goal

The owner sets a price or indicator condition on a symbol. After each daily sync, the app checks it and lists what fired. Delivery outside the app (email, Telegram, webhook) stays deferred (ADD A1 §4).

## Model

One table, `alerts`. An alert fires once; the owner re-arms it to watch again.

| Field | Meaning |
|---|---|
| `symbol` | The security. |
| `source` | `close`, `rsi14`, `adx14`, `atr14`, `macd_line`, `macd_signal` or `macd_histogram`. Each is a field of the chart's own series, so the chart and the alert read one value (NFR-1a). |
| `interval` | `1D`, `1W` or `1M`. |
| `condition` | `crosses_above`, `crosses_below`, `above` or `below`. |
| `threshold` | A decimal. |
| `armed_after` | The last stored session when the alert was created or re-armed. Only later bars count. |
| `status` | `active` or `triggered`. |
| `triggered_on`, `trigger_value`, `data_version` | The bar that fired, its value and the data it came from. Empty while active. |
| `seen` | False until the owner opens the alert list after it fired. |
| `tenant_id` | NULL; the SaaS seam (ADR-010). |

## Rules (deterministic)

- **Bars:** only complete bars dated after `armed_after`. A weekly or monthly bar counts once its period has closed (`partial` false).
- **Conditions:** `above`: value > threshold. `below`: value < threshold. `crosses_above`: previous bar ≤ threshold and this bar > threshold. `crosses_below`: previous bar ≥ threshold and this bar < threshold. The previous bar may be on or before `armed_after`. A bar with no value (warm-up) never fires and never serves as the previous bar.
- **Fires on the first bar that meets the condition.** The result depends only on the stored bars, never on when the check ran. A missed day therefore cannot hide a cross.
- **Values** are compared as the API reports them: the quantized decimals of the chart series.
- **Price basis.** A threshold on a price-scaled source (close, ATR, MACD) is in the price basis of `armed_after`, whose factor was 1 when it was set. A later split or bonus rescales every earlier bar, so the check rescales the threshold too: `threshold × factor(armed_after)` in the current schedule. RSI and ADX do not scale with price. Without this, a 1:1 bonus would fire every `below` alert set before it. (Found while building M15; the same reason drawings store traded prices.)

## Evaluation

- `EvaluateAlerts` reads each active alert's series through the same use cases the chart calls (`GetSecurityOHLCV`, `GetIndicatorSeries`). Parity is therefore structural, and a test proves it.
- The daily job calls it once after every strategy has run, so the day's bars are in. `POST /alerts/evaluate` runs it on demand. ADD A1 named the `RunCompleted` event as the hook. No publisher has subscribers yet, and one call site needs none. A subscriber can replace the call when a second consumer appears.
- The pure condition check lives in the domain (`domain/entities/alert.py`) and has golden tests.

## API

`GET /alerts`, `POST /alerts`, `DELETE /alerts/{id}`, `POST /alerts/{id}/rearm`, `POST /alerts/seen`, `POST /alerts/evaluate`. Pydantic DTOs with `extra=forbid`.

## UI

- The side panel gets an **Alerts** tab: the list, newest fired first, with the fired bar, value and data version. Unseen alerts show a count on the tab.
- **New alert:** a form in the Alerts tab for the open symbol: source, interval, condition, threshold. The chart's context menu offers "Alert at this price…", which fills a `close` alert at the price under the cursor.

## Tests

- **Golden:** fixed bars give fixed alerts, for each condition, warm-up gaps, weekly partial bars and re-arming.
- **Parity:** for every source, the value the evaluator used equals the chart API's value for the same bar and `data_version`.
- **API contract:** create, validation (unknown source, bad threshold), delete, re-arm, seen.
- **E2E:** create an alert from the panel, evaluate, see it fire and the count clear.

## Not in M15

Delivery outside the app, recurring alerts, alerts on browser-only indicators (NFR-1a forbids them), and alerts on drawings.
