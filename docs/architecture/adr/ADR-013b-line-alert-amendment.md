# ADR-013 amendment — sloped drawing alerts (trendline, ray, extended line)

Status: Accepted · 2026-10-20 · the owner approved per-anchor factors on 2026-10-20.
Extends `ADR-013a-alert-amendment.md` (drawing snapshots) and plan 2026-10-19 B4. EOD only.

## Decision

A close-price alert may link to a saved **trendline**, **ray** or **extended
line**. As with horizontal levels and price zones, the server reads the saved
drawing document and freezes the drawing ID, kind, both traded-price anchors
and the document revision. The rule never reads the live drawing again.
Conditions are `crosses_above` and `crosses_below` on the daily completed
close. Nothing intraday is claimed: no high or low touch, no path inside a bar.

## The line's value on a session

Sessions are the security's stored daily bars, numbered in date order. The
index of a date is the number of stored sessions before it, so a session's
index is its position.

Each anchor is first put in the chart's current price basis, exactly as the
chart draws it: traded price × the current adjustment factor **of that
anchor's own date**. This is the rule the accepted amendment already uses for
horizontal levels and rectangle zones.

With adjusted anchors (iA, pA) and (iB, pB) and iA ≠ iB, the line's value on
session i is

    L(i) = pA + (pB − pA) × (i − iA) / (iB − iA)

in exact decimal arithmetic. L is linear in the session index, which is how
the chart spaces bars, so the alert fires on the line the owner sees.

The line has a domain, and outside it there is no value:

| Kind | Sessions with a value |
|---|---|
| `trendline` | from the earlier anchor's index to the later one's, inclusive |
| `ray` | from the first anchor's index onward, in the direction of the second. A ray drawn backward in time can never fire after arming, so it is rejected |
| `extended` | every session |

**Plan wording.** Plan row B4 says "rescaled by factor(armed_after)". With
one factor for both anchors, the rule would disagree with the drawn line
whenever a split or bonus falls between the anchors. This amendment uses the
per-anchor factor instead, consistent with horizontal and zone rules and with
rendering. The owner approved it on 2026-10-20.

The governing invariant: the alert evaluates the same adjusted line the chart
draws. Closes and line levels are compared in one basis, the current one.

## Trigger

- `crosses_above`: previous close ≤ L(previous session) and current close >
  L(current session).
- `crosses_below`: previous close ≥ L(previous session) and current close <
  L(current session).
- Both sessions must have a line value. A session outside the domain breaks
  the crossing, just as a missing value does.
- Only the first qualifying session strictly after `armed_after` fires. The
  previous session can be on or before `armed_after`. No wall-clock input
  changes the result.

## Corporate actions

A later split or bonus rescales the closes before its ex-date. It also
rescales the anchors dated before that ex-date, because each anchor uses its
own date's factor. The line therefore stays on the same bars, as on the
chart. The frozen traded anchors never change.

## Snapshot freeze

Moving, restyling, hiding, locking or deleting the drawing does not change
an armed rule. Editing the alert refreshes the snapshot from the saved
drawing and starts a new observation window, as for horizontal rules. A
capture is rejected when:

- the anchors share a date;
- a price is not positive;
- the kind has no line semantics (only trendline, ray and extended qualify);
- the ray points backward in time.

## API and persistence

There is no API shape change and no migration. `drawing_id` may name a
trendline, ray or extended line, and the snapshot is stored in the existing
nullable JSONB column. A rule's `threshold` records the first anchor's traded
price, for display only. Evaluation always uses the line.

## Validation

Golden domain tests cover:

- line values inside and outside each kind's domain;
- both crossing directions and the equality convention;
- a domain edge breaking a crossing;
- deterministic replay.

A corporate-action case puts a split between the anchors. API tests cover
capture, rejection of a same-date line and of a backward ray, and the
snapshot freeze: a moved drawing does not change the armed rule or its
firing. An E2E creates the rule from the drawing menu ("Alert on this
line…") and fires it on stored bars.

Evaluator golden tests (`test_line_alert_evaluation.py`) run the real
`EvaluateAlerts` against fixed adjusted series. Each case re-expresses one
base chart, whose first cross is session 10:

- a 1:2 split and a 1:3 bonus between the anchors fire on the same session;
- the same actions after arming fire on the same session, at the scaled close;
- an ex-date on the crossing session is a cross above, never a false cross
  below from the raw price drop;
- each line kind watches only its own sessions;
- the first evaluation fires and a second fires nothing;
- a stale revision cannot fire;
- every stored prefix gives the same firing or none;
- a level never depends on later sessions.

Verification (2026-10-20): full backend suite **920 passed** on the
disposable `wickstreet_tv_test` database.
