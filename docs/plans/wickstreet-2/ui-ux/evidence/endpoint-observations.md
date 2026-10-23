# Local API smoke observations

28 representative calls returned 200. Single-call times under five concurrent readers are diagnostics, not performance benchmarks. No raw market history is stored here. See inspection.md for scope and limitations.

| Method | Path | Status | Time ms | Revision | List counts |
|---|---|---|---|---|---|
| GET | `/screener/fields` | 200 | 56 | 2801 | {"sources": 3, "fields": 160} |
| GET | `/screener/presets` | 200 | 15 | None | {"presets": 6} |
| GET | `/funds?q=Parag&limit=5` | 200 | 200 | 2801 | {"sources": 3, "funds": 5} |
| GET | `/funds/122639` | 200 | 64 | 2801 | {"sources": 3, "links": 0} |
| GET | `/funds/122639/metrics` | 200 | 54 | 2801 | {"sources": 3} |
| GET | `/funds/122639/navs` | 200 | 66 | 2801 | {"sources": 3, "navs": 2470} |
| GET | `/funds/122639/annual` | 200 | 27 | 2801 | {"sources": 3, "calendar": 11, "financial": 11, "monthly": 119} |
| GET | `/funds/122639/rolling?window=3y` | 200 | 26 | 2801 | {"sources": 3, "points": 1731} |
| GET | `/funds/122639/drawdowns?top=5` | 200 | 32 | 2801 | {"sources": 3, "drawdowns": 5} |
| GET | `/funds/122639/rank-history` | 200 | 14 | 2801 | {"sources": 3, "history": 108} |
| GET | `/funds/122639/direct-regular` | 200 | 15 | 2801 | {"sources": 3} |
| GET | `/funds/122639/underwater` | 200 | 25 | 2801 | {"sources": 3, "series": 2470, "recovery": 3} |
| GET | `/funds/122639/rolling-sip?tenor=3y` | 200 | 103 | 2801 | {"sources": 3, "starts": 84} |
| GET | `/funds/122639/near-duplicates` | 200 | 12 | 2801 | {"sources": 3, "listed": 0} |
| GET | `/funds/122639/score` | 200 | 13 | 2801 | {"sources": 3, "parts": 3, "penalties": 0, "data_quality": 0} |
| GET | `/funds/122639/confidence` | 200 | 112 | 2801 | {"sources": 2, "notes": 2} |
| GET | `/funds/122639/regimes` | 200 | 112 | 2801 | {"sources": 3, "windows": 12} |
| GET | `/regimes` | 200 | 95 | 2801 | {"sources": 3, "windows": 12} |
| GET | `/risk-free` | 200 | 17 | 2801 | {"sources": 3, "points": 529} |
| GET | `/compare?code=122639&code=118955` | 200 | 46 | 2801 | {"sources": 3, "funds": 2, "correlations": 1} |
| GET | `/peers/frontier?category=Equity%20Scheme%20-%20Flexi%20Cap%20Fund&plan=direct&option=growth` | 200 | 37 | 2801 | {"sources": 3, "points": 36} |
| GET | `/peers/transitions?category=Equity%20Scheme%20-%20Flexi%20Cap%20Fund&plan=direct&option=growth` | 200 | 38 | 2801 | {"sources": 3, "counts": 4, "shares": 4} |
| POST | `/screener/run` | 200 | 64 | 2801 | {"sources": 3, "excluded_missing": 3, "columns": 3, "rows": 5, "relaxations": 0} |
| POST | `/backtests` | 200 | 64 | 2801 | {"sources": 3, "regimes_spanned": 10, "limits": 4, "months": 107} |
| POST | `/calculators/sip` | 200 | 61 | 2801 | {"sources": 3, "codes": 1, "timeline": 61, "cautions": 2} |
| POST | `/calculators/lumpsum` | 200 | 57 | 2801 | {"sources": 3, "codes": 1, "timeline": 0, "cautions": 2} |
| POST | `/calculators/swp` | 200 | 49 | 2801 | {"sources": 3, "codes": 1, "timeline": 60, "cautions": 2} |
| POST | `/calculators/stp` | 200 | 30 | 2801 | {"sources": 3, "codes": 2, "timeline": 60, "cautions": 2} |
