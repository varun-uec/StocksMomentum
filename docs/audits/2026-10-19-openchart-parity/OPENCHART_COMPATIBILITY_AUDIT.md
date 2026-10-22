# Wickstreet ↔ OpenChart Compatibility Audit

**Date:** 2026-10-19 · **Branch:** `wickstreet/m10-m11` (local) · **Reference:** OpenChart by Longsurf AI, public documentation only.

| Document | Content |
|---|---|
| This report | Executive assessment, scores, fixes, recommendations |
| [Parity matrix](OPENCHART_WICKSTREET_PARITY_MATRIX.md) | 78 capability rows in groups A–O, each with evidence, class, score and priority |
| [Interaction parity](OPENCHART_INTERACTION_PARITY.md) | Ten journeys measured in Wickstreet; eight documented interactions scored |
| [UX and visual audit](OPENCHART_UX_VISUAL_AUDIT.md) | Layout, feedback, keyboard, responsive and speed findings |
| [Gap backlog](OPENCHART_GAP_BACKLOG.md) | 23 ranked items, decisions needed, out-of-scope proposals |
| [Clean-room record](OPENCHART_CLEAN_ROOM_RECORD.md) | Sources, dates, exposure, origin of every fix |
| [`audit-evidence/openchart-parity/`](../../../audit-evidence/openchart-parity/) | Wickstreet screenshots and the evidence index |

## Executive assessment

Wickstreet matches OpenChart's documented **charting core**. It has candles with volume, several panes per chart, Stochastic, Keltner and Anchored VWAP, line, zone, channel and Fibonacci tools, a 4×4 grid, a watchlist panel, price and indicator alerts, and saved state. It falls short in three areas:

1. **Drawing breadth and drawing actions.** OpenChart documents wedges, polylines, curves and freehand paths, and a drawing menu with Lock, Hide and Create alert. Wickstreet has none of these. Seven of its eleven missing capabilities are here.
2. **Alert management.** OpenChart documents editing alerts, Once/Repeat, an Enabled toggle, a Feed and alerts on drawings. Wickstreet alerts can be created quickly from the chart, but cannot be edited, paused, or attached to a drawing, and keep no history.
3. **Volume Profile**, which OpenChart names in its README.

Wickstreet goes beyond the documented reference in saved state (conflict-protected server documents shared by every window), data provenance (a data version on every chart, adjusted prices with drawings that follow splits and bonuses), and everything Momentum25 adds: explained rankings, gates, Strategy Studio and point-in-time evaluations.

The audit found and fixed **ten Wickstreet defects**, each with a regression test. Two of them could mislead a user about the data. 1W and 1M showed an empty chart whenever stored data lagged today (D1). MA200 on a 1Y chart drew only its last 10 bars (D2). One lost user work: a drawing placed while the symbol's saved drawings were still loading disappeared and was never saved (D11). The full browser suite exposed D11; it was present before this audit.

**This audit cannot say how close the two products feel in use.** OpenChart is a desktop app and was not installed or run, so no OpenChart interaction, speed or visual-quality measurement exists here. To close that gap, the owner can run the free OpenChart desktop build and repeat the ten journeys in [interaction parity](OPENCHART_INTERACTION_PARITY.md) §1.

## Method

- **Reference:** the OpenChart README, five docs pages, the home page, the changelog, and chart.chat, which redirects to openchart.co (sources R1–R9). Clean-room rules held: no source code, no developer tools, no assets ([record](OPENCHART_CLEAN_ROOM_RECORD.md)).
- **Wickstreet:** the production build served by the real API on loopback, against a new PostgreSQL 16 container on tmpfs (`wickstreet_parity_e2e`). The E2E harness verified and marked the database, then seeded it with synthetic bars that end on 2026-08-07. The application database was not touched. Every workflow was exercised in Chromium by Playwright.
- **Classes:** *Full*: same functional result, comparable interaction. *Partial*: the core exists, but important behaviour differs. *Alternative*: Wickstreet meets the need another way, by design. *Missing*: no equivalent. *Out of scope*: excluded by ADD A1 §4. *Unverified*: not enough evidence to compare.

### Scoring rubric

0: missing or unusable. 1: major gap. 2: works with substantial friction. 3: comparable. 4: comparable or better. Out of scope, Alternative and Unverified rows are never scored and never count as parity.

## Assessment A: capability parity

39 scored rows (in scope, with documented or illustrated OpenChart evidence):

| Area | Rows | Mean | Missing |
|---|---|---|---|
| Charts | 3 | 2.7 | 0 |
| Indicators | 8 | 2.0 | 2 (Volume Profile, Squeeze Momentum) |
| Drawings | 13 | 1.3 | 7 (wedge, polyline, curve, freehand, lock, hide, drawing alert) |
| Layouts | 2 | 3.0 | 0 |
| Watchlist | 2 | 2.0 | 0 |
| Alerts | 10 | 1.5 | 2 (drawing, pattern) |
| Workspace | 1 | 4.0 | 0 |

17 of 39 rows (44%) are comparable or better (score 3–4). 11 (28%) are missing. The overall mean, 1.8, hides a split: the chart, layout and workspace core is comparable, while drawings and alerts are weak. Excluded from scoring: 12 out-of-scope, 4 alternative and 19 unverified rows.

## Assessment B: interaction parity

Eight interactions that OpenChart documents, scored against Wickstreet: one 0, one 1, four 2s, two 3s (mean 1.9). The low scores are drawing alerts (0) and alert editing (1). Before this audit's fixes, multi-pane use and the 4×4 workspace scored one point lower each.

The ten core journeys were measured in Wickstreet only. Search takes 3 actions, a study 3, a trendline 3, a compare 3, an alert from the chart 3, and save 0. Discoverability is good on a single chart. It is weaker in grids, which have no drawing rail, and for dialog studies, which have no on-chart legend.

## Assessment C: product-quality parity

**Not scored (n = 0).** Marketing images show structure, not quality. The measured Wickstreet findings are in the [UX audit](OPENCHART_UX_VISUAL_AUDIT.md). The main ones: two rows of always-on controls above the chart, phone controls that fill 41% of the screen, and heavy 4×4 cell headers.

## Where Wickstreet exceeds the reference

Exceeds the documented reference:

- **Saved state:** server documents with ETags, field-level merges and a conflict notice. Any browser restores the workspace (J-01, score 4).
- **Provenance:** every chart shows its data version. Prices are corporate-action adjusted, and drawings are stored at traded prices, so they stay on their bars after a split or bonus.
- **Momentum25:** the Details tab on the chart shows readiness, scores, gate failures and "Why it ranks". The screener explains every rank by rule. Strategy Studio labels results as Screening Result, Historical Research — In-Sample or Out-of-Sample Evaluation.
- **Deterministic alerts:** alerts are evaluated on complete stored bars, with the same series the chart draws. Price levels rescale with splits.

Wickstreet capabilities with no public OpenChart evidence (Unverified, not counted as exceeding): weekly and monthly bars, Heikin-Ashi, log and percent scales, 12 named drawing tools, undo and redo, 20 published shortcuts with a `?` sheet, and three sync modes.

## Fitting the differentiators into the chart-first workspace

The domain engine and the deterministic calculation contract are unchanged by this audit. The indicator dialog labels every study "browser" or "backend". Alerts read backend series only, so display studies never feed a score, gate, rank or alert (NFR-1a).

Recommendations, smallest first:

1. Keep the Details tab as the single entry from a chart to Momentum25. Add the stock's rank badge to the chart header when the symbol is in the latest Top-25, linked to Details. The Details tab already loads the data, so this is a small change.
2. In the watchlist panel, add the latest rank and gate status as a column (backlog BL-13 adds sorting). It answers "which of my names qualify today" without leaving the chart.
3. Leave Strategy Studio, research and validation under the Research menu. They are long-form tasks. A chart shortcut would crowd the workspace.
4. Do not mark Momentum25 signals on the price chart by default. The workspace chart should stay familiar; the analysis screen already shows signals.

## Confirmed defects and fixes

| ID | Defect | Severity | Fix | Test |
|---|---|---|---|---|
| D1 | 1W and 1M empty, 3M partial, whenever stored data lagged today | P1 | Ranges count back from the last stored bar; one full-history fetch per symbol and interval | unit + E2E |
| D2 | MAs started inside the range; MA200 on 1Y drew 10 bars, and on 1W showed "—" | P1 | Up to 199 earlier closes feed the MA; the duplicate `rollingMean` was replaced by the tested `sma` | E2E |
| D3 | RSI from the dialog read twice; its pane checkbox stuck on | P2 | One definition per pane id; the pane row removes the dialog study | E2E |
| D4 | Crosshair readout covered the price-axis labels | P2 | Readout at the top left | E2E |
| D5 | Workspace keys dead after a checkbox click | P1 | Only text-entry controls count as typing | E2E |
| D6 | Double-click saved a zero-length line | P2 | Ignore a click within the handle radius of the last anchor | E2E |
| D8 | Grid cells followed the active chart's symbol with sync off | P1 | A layout gives new cells the active chart's symbol (`withLayout`) | unit + E2E |
| D9 | Synced crosshair box stuck after a dialog | P3 | Follower clears its readout when it clears its crosshair | E2E |
| D10 | Enter in indicator search did nothing | P3 | Enter adds the first addable match | E2E |
| D11 | An edit made while a saved document loaded was dropped: a drawing placed just after a symbol change vanished unsaved | P1 | The store keeps edits made during the load and merges them onto the loaded version with the document's own three-way merge, so neither side is lost and a real clash still raises the conflict notice (ADR-013 §5) | unit (2) + the existing R2 endurance E2E |
| D7 | On the % scale each MA starts at 0% from its own first value | P2 | **Deferred** (backlog BL-12): needs a shared base; not low-risk | — |

The new spec `web/e2e/openchart-parity.spec.ts` has 7 tests. All 7 pass with the fixes, and all 7 fail on the unfixed code. D3, D4 and D9 use a new `crosshair-readout` test id, so their failures on old code prove less; those three were also reproduced by hand before the fix (screenshots).

Verification: see [Test results](#test-results).

## Remaining gaps (top of the backlog)

P1: scroll through all history (BL-01), drawing rail in grids (BL-02), on-chart legend for studies (BL-03), edit alerts (BL-07). P2: Volume Profile, lock/hide drawings, alert lines and history, per-study colour, editable RSI/MACD periods, percent-scale base, denser mobile and grid chrome. **Decision needed:** alerts attached to drawings (BL-15), which needs an ADR amendment.

## Intentional exclusions

AI agents and Select and Explain; Tea or Pine-style scripting; user-defined strategy code; intraday and real-time data; broker connections and orders; hosted multi-tenant service; OpenChart Cloud and other proprietary integrations. Each is recorded as Out of scope in the matrix. None is a defect.

## Recommendations ranked by impact and effort

| Rank | Item | Impact | Effort |
|---|---|---|---|
| 1 | BL-03 on-chart legend for studies | High | S |
| 2 | BL-02 drawing rail in grids | High | S |
| 3 | BL-07 edit armed alerts | High | S–M |
| 4 | BL-01 full-history scrolling | High | M |
| 5 | BL-06 alert lines on the chart; BL-05 inline text notes | Medium | S each |
| 6 | BL-08 lock, hide, dash style | Medium | S |
| 7 | BL-10 Volume Profile | Medium | M |
| 8 | BL-14 denser phone and grid chrome | Medium | M |
| 9 | BL-12 percent-scale base (D7) | Medium | M |
| 10 | BL-15 drawing alerts, after an ADR decision | Medium–High | M–L |

## Test results

All runs on 2026-10-19, against a disposable PostgreSQL 16 database on tmpfs (`wickstreet_parity_e2e`), recreated empty before each full run.

| Check | Result |
|---|---|
| Web unit tests (Vitest) | 107 passed, 13 files. New: `rangeStartIndex` (2), `withLayout` (2), `DocumentStore` edits during load (2) |
| Web lint (ESLint, zero warnings) and typecheck (`tsc`) | Pass |
| Backend unit tests | 620 passed. No backend code changed; integration tests not run. |
| New spec `openchart-parity.spec.ts` | 7 passed. On the unfixed code: 7 failed |
| Full Playwright suite, final run | 152 passed, 6 skipped (the opt-in M13 benchmark), 1 failed: the 200% reflow test, see below |
| Touched specs after the last fix, in suite order | 21 passed (parity, persistence-restart, r2-accessibility, r2-adversarial, r2-stress-bench) |
| Endurance test alone, repeated | 5 of 5 passed |

The full suite was not green at HEAD. Three browser tests failed before this audit, and each now passes:

| Test | Cause | Fix |
|---|---|---|
| R2 bounded endurance | Product defect D11, and a race in the test: its bar-count check could match the previous symbol's chart | D11 fixed in the store; the test waits for the new symbol's bars before it checks |
| R2 legacy strategy comparison | The E2E seed screened one strategy, so the comparison had no common run date | `seed-screening.py` also screens `benchmark_a_pure_momentum` |
| R2 200% reflow | It read the workspace that `persistence-restart` left on weekly bars | The test resets documents first |

Two failures in intermediate runs were caused by this audit and are fixed: the new spec left a 2×1 layout behind (it now resets after itself), and the audit's screenshot server held port 8766, which the NFR-11 cold-open test uses.

The full runs rewrite committed evidence under `audit-evidence/` (R2 screenshots, benchmark JSON). Those regenerated files were restored, not committed, so earlier audits' evidence is unchanged.
