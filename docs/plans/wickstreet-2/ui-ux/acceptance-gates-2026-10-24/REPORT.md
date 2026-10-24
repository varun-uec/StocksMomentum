# Wickstreet 2.0 — acceptance gates R-01 and R-02

**24 October 2026 · IST · http://localhost:8000/mf · branch `wickstreet/m10-m11`**

This closes the two blockers in the [acceptance review](../acceptance-review-2026-10-24/REPORT.md). Nothing else was reopened. The review's 14 verified fixes keep passing: their browser tests are in the MF suite below.

| Gate | Review result | Now |
|---|---|---|
| R-01 overseas tax class | 119517 taxed as domestic equity, ₹0 | Class needed; ₹15,320.16 with class `other` |
| R-02 cold mobile LCP (median) | 7.10 / 8.26 / 7.07 s | **1.61 / 2.17 / 1.58 s** |

## R-01 — overseas funds no longer inherit equity tax

**Cause.** `tax_class_of` treated every Equity category as domestic equity. AMFI files international equity funds as "Sectoral/ Thematic", the same category as domestic sector funds. SEBI's 2026 labels "Sectoral Fund" and "Thematic Fund" map to that one category too. In the real data, fund names cannot separate the two: domestic "Innovation" funds sit beside "International" and "Global Agri" funds.

**Fix.** `tax_class_of` returns no class for "Equity Scheme - Sectoral/ Thematic". The service then returns `tax_class_needed`, and the Lab asks for a class. The review accepted this conservative fallback. Diversified equity categories, ELSS, the equity hybrids and debt keep their inferred class. The Lab's "Other" option now names overseas funds. Its hint says when the category does not settle the class.

**Why `other` is exact for overseas funds.** Section 50AA puts units bought from 1 Apr 2023 and sold before 1 Apr 2025 on the slab rate. No such unit can be held over 24 months, so the `other` 24-month rule gives slab too. From 1 Apr 2025 the amended section 50AA no longer covers overseas equity funds, and the 24-month rule applies. Units bought before April 2023 follow the 36-month indexed rule until 22 Jul 2024, then the 24-month rule. The `tax.py` docstring records this reasoning.

**Independent evidence.** [`scripts/tax-live.py`](scripts/tax-live.py) runs real funds through the served API. It derives each expected figure from the reported gain and the dated rules, not from the service's tax code. All 11 cases pass. [Results](evidence/tax-live.json).

| Fund | Sold | Class | Tax |
|---|---|---|---:|
| 119517 ABSL International Equity | 25 Jul 2024 | auto → needed | — |
| 119517, class chosen | 25 Jul 2024 | other | **₹15,320.16** = ₹49,103.07 × 30% × 1.04 |
| 120186 ICICI Pru US Bluechip (thematic, overseas) | 25 Jul 2024 | auto → needed | — |
| 145552 Motilal Oswal Nasdaq 100 FoF (filed "FoF Domestic") | 25 Jul 2024 | auto → needed | — |
| 120244 ICICI Pru Banking & Financial Services | 25 Jul 2024 | auto → needed | — |
| 120716 UTI Nifty 50 Index | 25 Jul 2024 | auto → needed | — |
| 122639 Parag Parikh Flexi Cap (A-03 anniversary) | 24 Jul 2024 | equity | ₹78,245.97 |
| 122639, a day later | 25 Jul 2024 | equity | ₹31,892.26 |
| 118632 Nippon India Large Cap | 25 Jul 2024 | equity | ₹33,372.09 |
| 120503 Axis ELSS Tax Saver | 25 Jul 2024 | equity | ₹23,322.57 |
| 118987 debt (A-04) | 25 Jul 2024 | debt | ₹24,639.57 |

Lump sum ₹10 lakh bought 24 Jul 2023, slab 30%. The equity figures are 12.5% on the gain above ₹1.25 lakh, plus cess.

**Regression tests** (`backend/tests/wickstreet/test_mf_slice3.py`):

- No thematic, FoF or dynamic-hybrid category gets the equity class. Diversified equity still does. The 119517 case gives ₹15,320.16.
- Overseas units across the rule changes: slab inside the section 50AA window; the 24-month boundary at 1–2 Apr 2025; the 22/23 Jul 2024 Finance Act boundary; the 20% indexed amount.

**Known limit.** A domestic sector fund, such as a banking fund, now needs the user to choose "Equity-oriented". That is the safe choice until a verified mandate field exists (the E1 fund-facts data). Then the category can settle domestic thematic funds again.

## R-02 — cold mobile LCP

**Profile.** This is the review's exact profile. Chromium at 390×844, mobile and touch, reduced motion, cache disabled, 4× CPU slowdown, 150 ms latency, 200,000 B/s down and 93,750 B/s up. Three cold runs per route against port 8000, with workspace records answered in memory. [`scripts/mobile-lcp.cjs`](scripts/mobile-lcp.cjs).

**Causes (measured waterfall, [before](evidence/lcp-before.json)):**

1. No compression. The 658 kB entry arrived uncompressed and took 3.8 s.
2. The `/mf` entry carried the stock app: `RootLayout`, lightweight-charts, stock components and indicators. The MF app uses none of them.
3. Every MF route imported Recharts (about 400 kB) statically. Even Discover's static heading waited for it. The API calls started only after it loaded, at about 7.1 s.

**Fixes:**

1. **Compression.** gzip on the static assets (`spa.py`) and on the MF API (`wickstreet/app.py`). The Momentum25 API responses are unchanged.
2. **A separate MF entry.** `/mf` routes are served `mf.html`, whose entry (`mf-main.tsx`) loads only the MF route tree. The stock entry (`main.tsx`) is unchanged in behaviour. It still loads its shell up front, and its chunks are all preloaded from `index.html`. The earlier attempt, which the remediation reverted, made the stock shell a late chunk; this avoids that. `index.html` still serves `/mf` in development and preview.
3. **Charts load after first render.** The Recharts drawing moved to `plots.tsx`, which loads lazily. Each chart in `charts.tsx` keeps its sized box, label and zoom control, so nothing shifts when the plot draws. Text, figures and API calls no longer wait for chart code.

**Results (medians of three cold runs; [after](evidence/lcp-after.json)):**

| Route | Before LCP | After LCP, three runs | After median | CLS before → after | JS encoded / decoded, after |
|---|---:|---|---:|---|---:|
| Discover `/mf` | 7.088 s | 1.592 / 1.608 / 1.612 s | **1.608 s** | 0.018 → 0.019 | 261 kB / 800 kB |
| Fund Overview `/mf/funds/122639` | 8.244 s | 2.152 / 2.168 / 2.176 s | **2.168 s** | 0.070 → 0.070 | 269 kB / 829 kB |
| Lab `/mf/simulate?code=118987` | 7.084 s | 1.580 / 1.580 / 1.580 s | **1.580 s** | 0.035 → 0.035 | 260 kB / 798 kB |

Before, encoded JS equalled decoded JS (about 1.18 MB): nothing was compressed. My before runs match the review's: 7.09 / 8.24 / 7.08 s against its 7.10 / 8.26 / 7.07 s. The after JS totals include the chart code, which still loads, but after first render. The intermediate step (compression and the separate entry only) measured 2.38 / 2.84 / 2.36 s ([evidence](evidence/lcp-intermediate-split-gzip.json)).

**Momentum25 under the same profile.** Same server, both runs gzipped ([before](evidence/lcp-stock-before.json), [after](evidence/lcp-stock-after.json)):

| Route | HEAD build | This build |
|---|---:|---:|
| `/` | 2.176 s | 2.220 s |
| `/chart/RELIANCE` | 2.156 s | 2.192 s |

The split costs the stock app about 40 ms under this throttled profile. The cause is extra chunk requests. Without the compression in this change, the stock app's entry alone took 3.8 s, so the stock app is still far faster than what was served before. CLS on `/` is 0.219 in both builds. It predates this change and is not part of these gates.

These are lab measurements on one machine, not field percentiles.

## Tests

| Suite | Result |
|---|---|
| Backend, dedicated `momentum25_test` | **1,420 passed, 13 skipped** (was 1,416; +2 tax, +2 SPA) |
| Web unit (Vitest) | **211 passed** |
| MF browser suite, served port 8000 | **56 passed** |
| Momentum25 browser suite, full, fresh `wickstreet_gates_full_e2e` | **236 passed, 8 skipped, 0 failed** |
| Momentum25 Ctrl+K and layout-switch specs (broke the earlier split) | **52 passed** |
| Live tax cases | **11/11** |

One MF test, F-02, read the scatter's axis labels as soon as the chart box was visible. The plot now draws a moment later, so the test waits for the first label before it reads them. Its assertion on round values is unchanged.

An earlier MF run lost one trace file because two Playwright suites ran at once and shared `test-results/`. That was a harness collision; the suites then ran one after the other.

No real workspace record was written. The browser tests used the in-memory mock, and the Momentum25 tests used new `_e2e` databases.

## Remaining limits

- Domestic sectoral and thematic funds need an explicit tax class until verified mandate data exists (see R-01).
- Stock `/` CLS of 0.219 is outside these gates.
- No physical-phone or field measurement was made.
