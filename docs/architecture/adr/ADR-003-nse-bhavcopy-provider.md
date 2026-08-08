# ADR-003: NSE Bhavcopy as MVP Data Provider

**Status:** Accepted

## Context
A daily momentum screener needs reliable EOD OHLCV for the **entire** NSE equity universe. Options range from official free EOD files to paid broker/vendor APIs with auth, rate limits, and licensing.

## Decision
Use the official **NSE EOD Bhavcopy** as the MVP primary data source, accessed through a `MarketDataProvider` port so additional adapters (broker/vendor) can be added without core changes.

## Consequences
- Zero data cost; official, full-universe coverage; ideal for daily EOD methodology.
- Must handle archive format/URL drift and corporate-action adjustment ourselves (mitigated by parser versioning + contract tests + explicit `corporate_actions`).
- Intraday and fundamentals are not available from this source → deferred behind their own ports/adapters.

## Alternatives considered
- **Broker API (Kite/Upstox/Angel/Dhan):** richer (intraday, some fundamentals) but adds auth/token complexity, rate limits, per-user/paid licensing. Deferred to a future adapter.
- **Paid vendor (EOD + fundamentals):** cleanest data but recurring cost; revisit for SaaS scale.
