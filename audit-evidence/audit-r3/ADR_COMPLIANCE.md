# ADR and Documentation Compliance — Round 3

Date: 2026-10-20. Reviewed: `docs/architecture/adr/` (18 files: ADR-001 to ADR-015, with three files numbered ADR-013), the ADD, ADD amendment A1, and `docs/current/*.md`.

**ADR-056 does not exist, and no other planning or governance document supplies it.** The audit brief names it. I searched the working tree (any case and spacing), all git history (`git log --all -S`), `docs/`, the plans in `docs/history/plans/`, the ADD and its amendment, the implementation spec, the design record (its numbered items are D-numbers up to D26, not ADRs), the README and contributing notes, the owner's saved memory notes and the sibling project folders. The only hits are in this audit's own reports. No ADR above 015 is mentioned anywhere. Nothing was invented and no record was renumbered. **Owner (Q5): name the document or project that holds it.** All 18 ADR files (001–015, with three ADR-013 files) were reviewed.

| ADR | Decision | Status | Deviations and gaps |
|---|---|---|---|
| 001 Hexagonal architecture | Dependencies point inward | **Implemented, with deviations** | 17 application → infrastructure imports in 11 files. The `lint-imports` contract keeps the domain pure but has no rule for the application layer (R3-B-16). `app/services` sits outside the layers (documented as D8). |
| 002 Python / FastAPI | | Implemented | — |
| 003 NSE bhavcopy provider | MVP data provider | **Implemented, superseded in practice** | The provider port exists. The default path is now authorised CSV import with downloads off. The ADR does not record this (R3-B-21). |
| 004 PostgreSQL | | Implemented | Schema drift between migrations, ORM and the development database (R3-B-15). |
| 005 Strategy as config | Versioned JSON plus rule registry | Implemented | Rank tie-break is `security_id`, not `symbol` (R3-B-10). |
| 006 Immutable run snapshots | Append-only | **Implemented at application level** | No database trigger guards `screening_runs` or result tables (SQL can still rewrite them). |
| 007 In-process scheduler | APScheduler, queue-ready | **Partly implemented** | Recovery after downtime is claimed but absent (R3-B-11). Redis is now required for the day lock. Restart policy `no` (R3-O-02). |
| 008 API-first, thin clients | | Implemented | — |
| 009 Determinism contract | Same inputs, same outputs | **Verified** | Six full-universe runs byte-identical. Text states 0.01 precision, code uses 0.0001. `date.today()` appears in `domain/research/validation_services.py:148`. Run identity also includes `run_date`. |
| 010 No auth in MVP | Seams prebuilt | Implemented | `get_current_user` exists but no router uses it. Loopback only. |
| 011 Chart engine | Keep lightweight-charts, build the workspace around it | **Implemented** | `lightweight-charts` ^5.2.0; attribution on every page. |
| 012 Open-source, self-hosted | Local by default | Implemented in code | ADR status **Proposed**. Request table covered by Host/Origin tests. No LICENSE/NOTICE file (owner). |
| 013 Web stack and chart data | S1–S7 spike criteria; weekly and monthly semantics; §5 document preconditions | **Verified; §5 amended 2026-10-20 (R3-U-06)** | S1 deep link, S3 same-origin, S4 query cache, S7 16-chart smoke: all pass in `m10-stack`. §4 weekly and monthly verified against independent aggregation. §5 verified: 10 parallel PUTs gave one 200 and nine 412; 428 without a precondition. §5 amendment: a never-saved document reads `200` with `ETag: "0"` and `{revision: 0, body: null}`; `PUT` with `If-Match: "0"` creates it (201); `If-None-Match: *` still works; malformed `If-Match` never creates. |
| 013 alert amendment | Editable armed alerts, drawing snapshots | Accepted; **verified by E2E** | `m15-alerts`, `b4-line-alerts` pass. |
| 013 line-alert amendment | Sloped drawing alerts, per-anchor factors | Accepted 2026-10-20; **verified by E2E** | `b4-line-alerts` passes (ray). Trendline and extended-line variants share the code path; only the ray case ran end to end. |
| 014 Strategy Studio | Three result classes, sealed hold-out | **Verified** | Hold-out grid and In-Sample gap equal an independent calculation. §9 hash-pinned runs: integration tests pass. The ADR lists `universe_membership` where history covers `securities`, and names `strategy_id=30` (the database id is 8). **§10 added 2026-10-20 (R3-U-09, R3-B-12):** `data_version` hashes market data and engine versions; the build id is stored, not hashed; stored manifests keep their keys. Decision pending (Q4): an `ENGINE_VERSION` constant. |
| 015 Licence | | **Proposed, not accepted** | Blocks publication. |
| README index | | **Stale** | Does not list all files (R3-B-21). |

## Documentation against implementation

| Document | Claim | Reality | Finding |
|---|---|---|---|
| `docs/current/state.md` | Backend 684 / 815 passed; web 101 | Backend **947** passed; Vitest **144**; Playwright 234 cases | R3-B-21 |
| `docs/current/architecture.md` | 19 migrations, 27 tables | 21 migrations, 28 tables | R3-B-21 |
| `docs/current/capabilities.md` | 12 drawing tools | 21 drawing kinds | R3-U-14 (P3) |
| `docs/current/capabilities.md` | Alerts on close, RSI, ADX, ATR, MACD | 7 supported sources | P3 |
| `docs/operations/production_readiness.md`, scheduler docstring | Missed jobs are recovered | Not recovered (`MemoryJobStore`) | R3-B-11 |
| `docs/current/capabilities.md` | Every endpoint documented | All 68 operations are listed | OK |
| `state.md` | "Not deployed: the owner's running image is unchanged until rebuilt" | Correct, and still true for every Round 3 fix | OK; see Release Gate G6 |

Outstanding obligations from the ADRs: accept ADR-012 and ADR-015; add LICENSE and NOTICE; resolve NSE and BSE data-use terms; clear the name; run the dependency audits; deploy the image.
