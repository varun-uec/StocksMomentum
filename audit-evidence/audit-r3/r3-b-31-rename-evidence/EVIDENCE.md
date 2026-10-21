# R3-B-31 rename evidence, 2026-10-21

Verdict: **no authoritative evidence found. Nothing is applied. `security_identity_links` stays empty (0 rows).**

## What was searched

- The repo and `audit-evidence/`: no exchange circular, no company announcement, no SHA-256-stamped document for any rename.
- The dev database (read-only): `corporate_actions` holds 26,562 rows (type `other` 25,624, `split` 490, `bonus` 448). Each row is `{symbol, subject}`. No row says "change of name" or "symbol change". A rename is not a corporate action in this feed.
- Web: not searched. This agent had no WebSearch or WebFetch tool, and scraping exchange pages would break the licence rule. Public regulator or company announcements are the right source and a person must read them (owner action).

## What the local data shows (observation, not evidence)

| Old symbol (id) | New symbol (id) | ISIN | Old: last bar | New: first bar | Gap | Reading |
|---|---|---|---|---|---|---|
| TWL (10179) | TITAGARH (2171) | old row has none; new INE615H01020 | 2023-06-16 | 2023-06-19 | next session | Matches the known "TWL to TITAGARH on 2023-06-19" in the register. |
| MAGMA (10076) | POONAWALLA (1635) | old row has none; new INE511C01022 | 2021-06-08 | 2021-09-13 | 3 months | The new row's bars start late. The gap is a data gap, not a trading gap. |
| MEGASOFT (10085) | SIGMAADV (1947) | both INE933B01012 | 2025-11-06 | 2026-02-09 | 3 months | Same ISIN on both rows. SIGMAADV has 66 bars to 2026-08-27, so it is a thin series. |

An equal ISIN or an adjacent last/first bar is a hint. It does not give the effective date, the ratio or a source. The importer requires all three, with a document SHA-256, and rejects a row without one.

## Proposed rows (NOT loadable, NOT applied)

`effective_date` is the first bar of the successor as seen in our data. An exchange or company document must confirm it. `evidence_reference` is deliberately `UNVERIFIED`, so `momentum25 import-identity-links` refuses the file until a person replaces it with the document name and its SHA-256.

```csv
predecessor_id,successor_id,effective_date,ratio,evidence_source,evidence_reference
10179,2171,2023-06-19,1,UNVERIFIED local bar spans,UNVERIFIED
10076,1635,2021-09-13,1,UNVERIFIED local bar spans,UNVERIFIED
10085,1947,2026-02-09,1,UNVERIFIED local bar spans,UNVERIFIED
```

The register also lists up to 334 heuristic candidate pairs (`audit-evidence/audit-r3/backend/decision-packet/stage-a/`). None has a source.

## Owner action

Read the company or regulator notice for each rename (name-change certificate from the registrar of companies, or the company's stock-exchange intimation). Record the effective date, old and new symbol, ISIN, and the document's SHA-256. Then build the file and load it with the CLI. Until then, treat every row above as unverified.
