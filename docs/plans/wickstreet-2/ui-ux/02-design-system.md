# 02 · Design system specification

## Visual direction

**Paper, ink and a living margin.** Warm paper surfaces, crisp ink, a deep sea-green accent, editorial headings and disciplined numeric tables. Use whitespace and typography instead of a field of decorative dashboard boxes. Botanical linework may appear in empty discovery states; charts never carry decorative illustrations. The desktop hero is a compact invitation to research, not a marketing billboard. Original components are informed by consumer simplicity and analytical tools; no competitor assets or copied layouts.

## Tokens

| Token | Light | Dark | Role |
|---|---|---|---|
| `paper` | `#F6F5F0` | `#12221E` | Page |
| `surface` | `#FFFFFF` | `#192D27` | Cards, tables, dialogs |
| `ink` | `#172D27` | `#EEF4EF` | Primary text |
| `muted` | `#53675E` | `#B5C6BC` | Secondary text; never the only state indicator |
| `line` | `#D6DED5` | `#3A5045` | Dividers/grid; controls also have clear labels/outlines |
| `accent` | `#176B55` | `#83D1B3` | Primary action and evidence highlights |
| `accent-soft` | `#E3EFE7` | `#233F32` | Selected background |
| `warning` | `#84581E` | `#F0C47B` | Cautions and partial coverage |
| `loss` | `#A64340` | `#FFAAA3` | Negative returns with minus sign/text |
| `info` | `#3C6380` | `#A5CBE5` | Context or planned dependencies |
| `focus` | `#176B55` | `#A2E5CB` | 3 px focus ring, 3 px offset |

Do not override global `--ws-*` tokens until regression-tested. Scope these under an MF root and map reusable primitives deliberately. Target WCAG 2.2 AA: 4.5:1 body text, 3:1 large text and meaningful chart/control strokes. Muted text must pass against its actual surface; measure the delivered palette in both themes. Planned badges always say “Planned”; colour alone communicates nothing.

**Charts:** sea green `#176B55`, ochre `#976320`, violet `#655A9B`, blue `#356C8A`, rose `#A34B65`. Up to five distinguishable funds, with direct labels and solid/dashed/dotted patterns. Keep series identity stable when a fund is removed. Use a zero line on return plots and a visible benchmark label.

## Typography and geometry

Use the already bundled Inter Variable for interface and tabular numerals. Use a system editorial serif (`Iowan Old Style`, `Palatino Linotype`, Georgia) for large display headings only; no external font request. Hindi falls back to installed Noto Sans Devanagari or Mangal; implementation must bundle a licensed Devanagari font if target-device testing finds inadequate shaping. Hindi/English line heights are 1.55/1.45 minimum. Lakh/crore values carry explicit units.

| Style | Desktop / mobile | Weight / line-height |
|---|---|---|
| Display | 40 / 30 px | 500 serif / 1.14 |
| Page heading | 32 / 26 px | 600 / 1.2 |
| Section | 20 / 19 px | 600 / 1.3 |
| Body | 15 / 15 px | 400 / 1.5 |
| Label/table | 13 / 14 px | 500 / 1.4 |
| Metadata | 12 / 12 px | 450 / 1.5 |
| Key number | 28 / 26 px | 600 / 1.15, tabular |

Spacing scale 4, 8, 12, 16, 24, 32, 48, 64. Radii 6 for inputs/chips, 12 for cards, 16 for dialogs; pills only for categorical badges. Borders 1 px; shadow only on elevated panels. Desktop gutters 32, tablet 24, mobile 16. Content grid 12 columns with 24 px gaps, four columns on mobile. Readable prose max 68 characters per line. Default table rows 60 px; compact 44 px. Buttons 40 px desktop, 44 px touch. Do not shrink text to squeeze a table.

## Component contracts

| Component | Content and states | Interaction / accessibility |
|---|---|---|
| `ProductShell` | Product switch, primary nav, search/ask, snapshot status | Skip link, one `main`, landmark labels, current page, focus retained on close |
| `ResearchSearch` | Name/code/ISIN results with plan, option, status; recent public research | Debounce 250–300 ms, cancel stale requests; combobox arrows/Enter/Escape, live result count, no stock results mixed into MF |
| `EvidenceCard` | Observation, why it matters, caveat, open-evidence link | Whole card has one primary link, extra actions explicit; source drill-down is keyboard/tap accessible |
| `MetricCell` | Label, value/unit/window, missing reason, peer context | Help button opens a popover/dialog on click or Enter, Escape closes and returns focus |
| `FilterBuilder` | Registry groups, condition pills, AND/OR brackets, missing inclusion | Number/enum/date/boolean input by type; typed errors inline; never an unlabelled slider |
| `FormulaEditor` | Name, arithmetic, field autocomplete, description | Accept only backend language; expression errors at field; raw fraction units documented; no browser `eval` |
| `FundIdentity` | Scheme, AMC, code, direct/regular, growth/IDCW, status | Variant change resolves exact counterpart; missing pair cannot silently choose an unrelated fund |
| `FundRow/Card` | Fund link, 3–5 priority metrics, watch and compare actions | Link and buttons separate; row selection accessible; mobile cards retain the same sort/filter meaning |
| `CompareTray` | Selected plans, count, remove, compare action | 2–5 distinct codes, limit explained, no blocking overlay; screen-reader status on add/remove |
| `ChartFrame` | Question title, series/window/units, insight, chart, data/method | Keyboard date navigation, pinned tooltip, focusable data table, download; crosshair links only compatible date axes |
| `SnapshotBar` | Data as-of, per-fund last NAV, revision/method, new revision indicator | Refresh is explicit; stale fund not presented as live; source list has a detail drawer |
| `SaveState` | Loading/saved/unsaved/saving/error/conflict | No silent overwrite; retry, compare mine/theirs, preserve local draft; saved toast announced once |
| `DependencyPanel` | Capability, why unavailable, named dataset/service | No fabricated result or active execution control; optional “Read methodology” works |
| `DecisionBrief` | Goal, criteria, alternatives, evidence, doubts, scenario, review trigger | Editable sections, snapshot replay, export; output is research, not an order |
| `AgentResult` | Tool stages, citations, validated narrative, UI actions | Stream stages first; publish only validated figures; stop, retry and template fallback; language persists |
| `CASImportReview` | Local file, password, format, reconcile, duplicates, commit | Password once/in-memory; inline errors; commit disabled until blocking issues resolved; undo batch |

## Chart grammar

| Chart | Question and encoding | Controls, tooltip, limitations |
|---|---|---|
| Growth journey | How did equal starting money grow? Rebased NAV indexed to 100; optional rupee conversion | Common start displayed; 1Y/3Y/5Y/all/custom; linear default, log explicit; no synthetic interpolation across missing observations |
| Rolling return | How much did the entry date matter? Time series + p10–p90 band/quantile markers | 1Y/3Y/5Y; show start/end anchors, count, min/median/max/positive share; not independent samples |
| Annual/monthly | Which years/months drove the outcome? Diverging bars and heatmap | CY/FY explicit; partial periods hatched and labelled; keyboard grid announces date and signed return |
| Underwater | How far below the prior peak, and for how long? Negative area below 0% | Peak/trough/recovery, depth, fall and recovery duration; unrecovered line never implies recovery |
| Historical ranks | Did relative performance persist? Percentile ribbon 0–100 and quartile bands | Tooltip rank/count/date/peer key; higher better; current category labels applied historically disclosed |
| Transition matrix | Did leaders stay leaders? Row-normalised quartile transitions | Each cell includes numerator/denominator; 12-month transition, sample caveat; no prediction label |
| Frontier | Which peers offered more return for the observed risk? CAGR versus volatility scatter | Active category × plan × option; label non-dominated points; select dot opens fund; not an optimal personal allocation |
| Correlation | Do daily NAV returns move together? Symmetric heatmap | Pair sample, window, common-date rule, missing reason; does not measure security overlap |
| Regime timeline | How did it behave through proxy falls/recoveries? Shaded regime strips + return bars | Persistent “NAV-built proxy, not an official index”; no invented event names |
| Simulation | What happened under this schedule? Contributions and value paths | Event tooltip includes trade date/NAV/units/stamp duty; lumpsum may have no timeline, so show cash-flow table and summary instead |
| Holdings/exposure (future) | What do I actually own? Ranked bars, allocation stack, overlap matrix | Disclosure date, publication date, unresolved weight and unreported bucket; never smooth unknowns into 100% known |

Avoid decorative gauges, 3D, spider/radar comparisons and dual-axis charts. Use distribution strips when a mean would hide downside. A return caption distinguishes annualised and cumulative values. Schematic wireframe curves are labelled in the artboards; production charts only use service results.

## Motion, input and content

120 ms hover/focus; 180 ms disclosure; 220 ms drawer. No number-counting animation or re-sorting while the user is reading. Disable nonessential motion under `prefers-reduced-motion`. Skeletons match final geometry and announce loading once. After 10 seconds show a patient status and cancellation; never claim progress percentages without a job result.

Use “Maximum fall from a peak” beside “Drawdown”, “Yearly growth rate” beside “CAGR”, and “Typical daily loss in the worst 5% of days” for CVaR with its exact method in details. Avoid “safe”, “guaranteed”, “best for you” or “low risk” from a single metric. The riskometer is an AMC disclosure (E1), not the score or volatility. Use DD MMM YYYY in UI, ISO dates in API/exports, IST for operations and timestamps. Numeric fractions are multiplied by 100 for display only. Percentage-point changes and percent changes are named distinctly.

## Required state variants

Every data component has loading, populated, empty, partial, stale, unavailable (`NA`), not meaningful (`NM`), permission denied and recoverable error designs. Save operations add pending, saved, failed and conflict. Future dependency is not a network error. Empty screens offer explicit relaxations only when returned by the backend. No cached result may acquire the dates or freshness of a later failed request.
