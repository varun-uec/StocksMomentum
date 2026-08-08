# ADR-009: Determinism Contract

**Status:** Accepted

## Context
The product's credibility rests on reproducible, explainable scores (NFR-1/2/3). Floating-point order sensitivity, RNG, wall-clock, and unordered iteration would make scores non-reproducible and undermine trust.

## Decision
Establish a binding determinism contract:
- All **persisted** numeric values are `decimal.Decimal`, quantized to fixed precision (prices 0.01, scores 0.0001, percentages 0.01).
- Indicator math may use numpy floats internally but is **quantized to Decimal before** reaching scoring/persistence.
- Scoring reduces rule contributions in **sorted `rule_id` order**; no reliance on dict/set ordering.
- No RNG or wall-clock inside the domain core; `run_date`/`Clock` are explicit inputs (Clock is a port).
- Run identity = `(strategy, data_version, config_hash)`; a recompute must byte-match the stored snapshot.

## Consequences
- Reproducibility verifiable via golden-master snapshot tests.
- Minor performance cost from Decimal at boundaries — negligible at MVP scale.

## Alternatives considered
- **Float throughout:** rejected — order/precision non-determinism.
- **Fixed-point integers only:** rejected — Decimal is clearer and sufficient.
