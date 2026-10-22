# ADR-021: Source-Neutral Data Supply

**Status:** Proposed (2026-10-22). Touches licensing; the owner decides each supplier. Part of the [Wickstreet 2.0 blueprint](../../plans/wickstreet-2/README.md). Extends ADR-003 and the ADR-012 data-use check.

## Context
The M16 check found that NSE's website terms forbid automated collection and simulation use. On 2026-10-22 the AMFI terms were read: use is "personal and non-commercial", "You shall not store electronically any significant portion of any part of the Site", derivative works are barred, and other uses need a written agreement. BSE and NSE Indices terms could not be read. Every 2.0 dataset (financials, NAV, holdings, classifications, TRI) has a licence question. The user's own portfolio does not.

## Decision
1. **Import contracts, not fetchers.** Each dataset enters through one documented, versioned file contract (`financials-v1`, `shares-v1`, `classification-v1`, `schemes-v1`, `nav-v1`, `costs-v1`, `holdings-v1`, `benchmark-v1`, `transactions-v1`). Code and tests depend on the contract, not on a supplier.
2. **No fetcher in the default build.** A fetcher may exist only for a source whose written terms permit automated personal use. It ships disabled and needs an explicit operator setting, as the NSE/BSE adapters do today.
3. **Bring your own licence.** A supplier adapter converts a licensed vendor's export into a contract. The project ships no data.
4. **Provenance on every import:** `source` label, `source_ref`, `file_sha256`, `published_at`, provenance class.
5. **No real data is imported on the owner's instance until the owner records a supplier decision per dataset** (blueprint 04 §5). Development uses synthetic fixtures.
6. **No unofficial aggregator** (an API that republishes another body's data without stated terms) is a default dependency.

## Consequences
- Implementation is not blocked by licensing; usefulness is.
- Users must obtain data they are entitled to use; the docs say so.
- Supplier changes cost one adapter, not a redesign.

## Alternatives considered
- **Ship scrapers like many open-source tools:** rejected. It breaches stated terms and exposes the project as distributor.
- **Depend on an unofficial free API:** rejected. Unknown upstream rights and a single operator.
- **Wait for a vendor before designing:** rejected. Contracts let design and code proceed.
