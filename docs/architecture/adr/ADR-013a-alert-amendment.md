# ADR-013 amendment — editable armed alerts and drawing snapshots

Status: Accepted · 2026-10-19 · Extends ADR-013 §§4–5 and M15; EOD only.

## Decision

Armed alerts can be edited with a revision precondition. Editing is a new arming
decision: the server sets `armed_after` to the latest stored session. Triggered
alerts cannot be edited. Evaluation conditionally fires the revision it read, so
a slow evaluation can never fire an older rule after an edit or re-arm.

A price alert may link to a saved horizontal ray (`horizontal`), horizontal line
(`hline`) or rectangle (`rectangle`). The server reads the symbol's persisted
drawing document and captures the drawing ID, kind, traded-price anchors and
document revision. Client-supplied prices cannot override this snapshot. Only
daily completed close prices are supported. No sloped, arbitrary-path,
intrabar, high/low-touch or browser-indicator evaluation is introduced.

## Trigger and adjustment semantics

- Horizontal levels support `crosses_above` and `crosses_below`, with the same
  equality convention as M15: previous ≤ level < current, or previous ≥ level >
  current. The anchor's traded price is multiplied by the current adjustment
  factor for its anchor date, exactly as drawing rendering specifies.
- Rectangles are **price zones**, irrespective of their drawn date extent.
  Each of the two traded anchors is adjusted using its own date; the resulting
  minimum and maximum define an inclusive zone. `enters_zone` means previous
  close outside and current close inside. `leaves_zone` means previous close
  inside and current close outside. A gap from below to above that never closes
  inside does not enter or leave. A degenerate adjusted zone never fires.
- Only the first qualifying complete bar strictly after `armed_after` fires.
  The preceding completed close can be the armed session. Missing values break
  a crossing; partial periods do not fire. No wall-clock or scheduling input
  affects the selected firing bar.
- The captured anchors retain their traded-price basis through later corporate
  actions. Scalar alerts retain M15's arming-date price basis. Sources used in
  screening or alerts remain backend authoritative.

## Drawing lifecycle and replay

Moving, hiding, locking or deleting a drawing does **not** rewrite an armed rule
or its history. The UI must explain that the alert uses a captured drawing.
Editing the alert explicitly refreshes its snapshot from the currently saved
drawing and starts a new observation window. Creating or refreshing from a
missing, unsupported or malformed drawing is rejected. Hidden and locked
drawings are valid sources: these are presentation/editing states, not monitoring
states. A deleted drawing's captured alert continues to evaluate.

The frozen snapshot, rule revision, arming session, first firing session/value
and market `data_version` identify the deterministic evaluation. Replaying the
same adjusted bars, schedule and snapshot produces the same first firing, even
if the scheduled job ran late or the live drawing was changed. As with M15,
the per-symbol content hash identifies inputs; it does not promise recovery of
an unavailable past adjustment schedule. Historical data replay remains subject
to the existing chart-input versioning limitations in ADR-013 §4.

## API and persistence

`POST /alerts` accepts optional `drawing_id`. For a linked rule the usual
`threshold` is ignored in favour of the saved anchors. `PATCH /alerts/{id}`
accepts the full creation rule plus required `expected_revision`; unknown IDs
return 404, stale revisions and triggered rules return 409. Returned alerts
include `revision` and nullable `drawing` (ID, kind, anchors, drawing revision).
Existing clients and scalar alert requests remain valid. A nullable JSONB
snapshot and integer revision extend the existing table; no market data changes.

Creation and editing also accept optional `expected_drawing_revision` and
`expected_data_version`. A changed saved drawing or market input hash returns
409 rather than capturing a rule in a basis the owner has not reviewed. A
drawing revision without a drawing ID is invalid. Existing clients may omit
these preconditions; the workstation supplies them when its inputs are loaded.

Re-arming a scalar price-scaled rule preserves its effective level: the stored
threshold is multiplied by `factor(old armed_after) / factor(new armed_after)`
before the new observation window is saved. RSI and ADX are unchanged; drawing
snapshots continue using each anchor date. The rule revision guards this write
against concurrent edits. Rectangle validity is checked after adjusting each
anchor, since equal traded prices at different dates can define a real zone.

## Validation

Golden tests cover direction, equality, zone entry/exit, gaps, partial bars,
late deterministic replay and corporate-action factors. API tests cover
snapshot capture, unsupported drawings, active editing, stale evaluation/edit
races and immutable triggered rules. Tests use isolated `*_test` databases.

Implementation verification (2026-10-19): full backend suite **874 passed** in
35.69 s against the disposable `wickstreet_alerts_test` database. The focused
alert/document suites contain 70 integration tests and 21 domain tests. Split
regressions cover re-arming, unchanged RSI/ADX thresholds, stale chart/drawing
preconditions and a refreshed drawing snapshot replayed after a second bonus.
Strict
mypy checked 263 source files; Ruff and both architecture import contracts
passed. Alembic reports one head, `0021_alert_drawing_snapshots`. Existing
Starlette/httpx and SQLAlchemy DISTINCT ON deprecation warnings remain.
