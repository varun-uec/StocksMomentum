# ADR-016: Company Fundamentals, Stored by Publication Time

**Status:** Proposed (2026-10-22). Part of the [Wickstreet 2.0 blueprint](../../plans/wickstreet-2/README.md). Requires [ADD Amendment A2](../ADD-amendment-A2.md).

## Context
ADD §6 reserved a `FundamentalDataProvider` port and a disabled `FundamentalEngine`. Nothing else exists. Wickstreet 2.0 needs company financials for research pages, screens and scorecards, on today's date and on past dates. Companies restate results. A 2022 evaluation must never see a number first published in 2023. ADR-014 §7 already solves this for prices with history tables, a revision-based `data_version` and a point-in-time port.

## Decision
1. **Company is an entity.** A `companies` table holds the issuer; `securities.company_id` links listings to it. Names are effective-dated in `company_names`. Renames are never inferred (the R3-B-31 rule).
2. **A filing is the unit of knowledge.** `financial_filings` stores one row per published result set with `period_end`, `period_type`, `basis` (standalone or consolidated), `audit_status` and `published_at` (a timestamp). Facts sit in a narrow `financial_facts` table keyed by `(filing_id, line_item)` on a canonical taxonomy with `general`, `bank`, `nbfc` and `insurance` templates.
3. **Restatements append.** A revised result is a new filing with `supersedes_filing_id`. No source fact is updated in place. The `Versioned` history tables still record corrections to our own imports.
4. **Point-in-time rule.** At decision time *t*, the visible filing for `(company, period, basis)` is the one with the greatest `published_at ≤ t`. `PointInTimeFundamentals` serves only those and raises `LookAheadError` on any later read. A backfilled filing without a receipt time gets `published_at` = period end + 45 days (+ 60 days for Q4 and annual results, LODR Reg. 33) and provenance `reconstructed`.
5. **Metrics are pure domain functions** (`domain/fundamentals/`) returning a value, `NM` or `NA` with a reason. Formulas live in one dictionary (blueprint 03 §1.4) and are owner-approved methodology. `METRIC_VERSION` joins the engine identity (ADR-014 §11).
6. **Market cap uses traded close × shares outstanding** at the date, shares taken from the latest published observation and scaled by later splits and bonuses.
7. **Data enters only through the `financials-v1`, `shares-v1` and `classification-v1` import contracts** (ADR-021).
8. **Momentum25 is untouched.** The `FundamentalEngine` stays disabled in every production strategy. Fundamental rules may be offered to user strategies in Strategy Studio later; that changes the registry fingerprint by design.

## Consequences
- Historical screens and research can use fundamentals with the same guarantees as prices.
- Storage grows by about 2.4 M fact rows per year of history across 2,500 companies.
- Taxonomy mapping per supplier is the main ongoing cost.
- Bank and insurance companies show fewer metrics, with reasons.

## Alternatives considered
- **Wide table of pre-computed ratios from a vendor:** rejected. Not explainable, no restatement history, formulas not ours.
- **Overwrite on restatement:** rejected. Breaks point-in-time correctness.
- **Use `period_end` as the availability date:** rejected. It uses results up to 60 days before they were public.
