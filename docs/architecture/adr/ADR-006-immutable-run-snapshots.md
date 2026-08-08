# ADR-006: Append-only Immutable Run Snapshots

**Status:** Accepted

## Context
The product must persist historical rankings/scores (FR-10), explain past results (FR-11), and support reproducibility/audit (NFR-2). Mutating "latest" state would destroy history and make audit impossible.

## Decision
Each screening run writes an **append-only snapshot**: `screening_runs` (one row) plus `screening_results` and `rule_results` keyed by `run_id`. A run is **immutable once `COMPLETED`**. Score/rank history is derived by querying snapshots across `run_date`.

## Consequences
- Free, accurate history + audit trail; trivial "score movement over time".
- Storage grows with runs × universe — acceptable (EOD cadence, ~2k symbols); prunable later by retention policy.
- No in-place updates → simpler concurrency and reproducibility.

## Alternatives considered
- **Mutable latest-only tables:** rejected — loses history and auditability.
- **Event-sourcing the whole domain:** rejected — overkill for an EOD batch system.
