# Security and Release-Gate Report — Round 3

Date: 2026-10-20. Code defects are separated from legal and contractual questions. Legal items are for the owner and counsel. This audit does not decide them.

## 1. Code-level security

**Model.** Single-user, loopback-only, no authentication (ADR-010, ADR-012). The product is not secure if exposed to a network. Add an authenticating proxy first.

| Check | Result | Evidence |
|---|---|---|
| Compose binds `127.0.0.1` for API, database and Redis | PASS | `docker-compose.yml`; `docker ps` ports all `127.0.0.1:` |
| Host header guard: `Host: evil.example` | 421 | worker `api-probe/probe-results.json` |
| Cross-origin write (PUT) | 403 | same; also `m10-stack.spec.ts` ADR-012 test |
| `Origin: null` with `text/plain` POST | 403 | same |
| No `Origin`, `text/plain` | 422 (JSON required) | same |
| CORS preflight from an evil origin | No `Access-Control-Allow-Origin` | same |
| Security headers | `nosniff`, `X-Frame-Options: DENY`, CSP, referrer-policy present | same |
| CSP in a real browser | `script-src 'self'`. My injection of an inline script (axe, `addScriptTag`) was **blocked** with a CSP error. Injection by init script worked only through the test harness. | Playwright MCP session |
| CSRF | A cross-site write is rejected; a JSON-only body type blocks form posts | `r2-adversarial.spec.ts`, probe |
| SQL injection in symbol and strategy-name parameters | JSON 404, no SQL error, no reflection | probe |
| XSS: `<script>` in symbol or strategy name | JSON 404, no HTML reflection | probe |
| Path traversal on the SPA handler | 10 variants on :8000 returned `index.html`, no file leaked. The handler uses `resolve()` and `is_relative_to`. `.env` is not served. | probe; `r2-adversarial.spec.ts` |
| SSRF | No user-supplied URL parameter exists. Refresh takes an exchange enum. | code review |
| File import and upload | No upload endpoint. Imports run through the local CLI on a file path the operator gives. | code review |
| Error messages | 500s are generic, with a correlation id, no stack trace | probe |
| Request body size | 15 MB body returned 422 in 0.15 s. **No explicit body-size cap** (R3-B-23, P3). | probe |
| Secrets | Only `.env.example` is tracked. No key patterns in git history. Only dev-default and synthetic E2E passwords appear. | `security/secrets-scan.txt` |
| Secrets in logs | **Defect R3-B-06 (P2): the settings log line printed the database and Redis URLs with passwords at every start.** Fixed in `e3b67dd` (masked, regression test). The running container is not rebuilt and still logs them. | worker; `git show e3b67dd` |
| Rate limit | 200 requests per minute per client. A page load costs 7 to 15 requests. About 13 fast page loads in a minute give HTTP 429. This is availability for the owner, not a security gap (R3-U-08, P3). | `settings.py:82`; real-app sweep |

**Result: no P0 or P1 security defect.** One P2 (password in logs) fixed in source, not deployed.

### Dependencies

| Check | Status |
|---|---|
| `pip-audit` | **NOT VERIFIED.** It sends the dependency list to an external service. Awaiting owner approval. |
| `npm audit` | **NOT VERIFIED** in this round for the same reason. The 2026-10-19 state record lists eleven development-only advisories (typescript-eslint 7, tailwind 3 tool chain); no runtime package affected. Not re-confirmed. |
| Lock files | The Docker image installs from `uv.lock` (fixed 2026-10-19). |
| `nsemine` | A scraping dependency still ships in the dependency set although downloads are off (see section 2). |

## 2. Licensing and market-data rights — owner and counsel

These are not code defects.

| Item | State | Needed |
|---|---|---|
| Project licence | ADR-015 is **Proposed**, not accepted. There is **no `LICENSE` or `NOTICE` file at the repository root**. | Owner accepts a licence; add the files before any publication. |
| Open-source attribution | The lightweight-charts notice and the TradingView link appear on every page footer and on `/about` (verified in all route screenshots). The Inter font licence text (OFL) was not found in the web source. | Add third-party notices for all bundled packages and fonts. |
| Name | Wickstreet name and trademark clearance is an open owner decision (`2026-10-19-m16-name-clearance.md`). | Owner |
| NSE data use | The M16 memo flags NSE terms clause 1 (automated collection) and clause 4 (simulation, which may cover backtests). No subscriber agreement is in the repository. | Counsel |
| BSE data use | BSE market data is offered through subscription products. No agreement is in the repository. | Counsel |
| 2026-10-20 refresh | One-time, authorised by the owner. It does not establish subscription rights. The data stays local and is not redistributed. | Owner to record the basis |
| Recurring downloads | **Off** by default and answered with 409. This audit did not enable them. | Do not enable until rights are verified |

## 3. Release-gate summary

Intended release: the owner's local, single-user, loopback workstation first; public distribution is a separate, blocked step.

| Gate | Status | Why |
|---|---|---|
| G1 Functional correctness | PASS with noted gaps | 232 browser tests and 947 backend tests pass on HEAD after fixes. See the Audit Report. |
| G2 Financial correctness of the live screener | PASS | Independently recomputed (Financial Correctness Report). |
| G3 Financial correctness of the walk-forward backtest | **FAIL — release blocker for any backtest claim** | R3-B-09 (27% of notional at stale fills). |
| G4 Spec conformance | **OPEN — owner decision** | R3-B-10 (four deviations). |
| G5 Operational reliability of the EOD job | **FAIL for unattended use** | No catch-up (R3-B-11), restart policy `no` (R3-O-02), scheduled run never observed, no automated authorised data source. |
| G6 Deployment currency | **FAIL** | The container runs the old image. The R3-B-02 import guard, run-id fix, 409 conflicts, SCHEDULED trigger, log masking, RS read-path fix and all web fixes are not deployed. |
| G7 Security (code) | PASS for the loopback model | One fixed P2, not deployed. |
| G8 Dependency audit | NOT VERIFIED | Owner approval needed. |
| G9 Licence and attribution | **BLOCKED** | ADR-015 unaccepted, no LICENSE/NOTICE. |
| G10 Data-use rights | **BLOCKED** | NSE and BSE terms need legal review. |
| G11 Name clearance | **BLOCKED** | Owner decision. |
| G12 Accessibility | PASS (automated); NOT VERIFIED (screen reader) | `r3-axe-routes.spec.ts` |
| G13 Performance | PASS | See the Audit Report. |

**P0 findings: 0. P1 findings: 3** (R3-B-02 fixed; R3-B-08 fixed, awaiting owner confirmation; R3-B-09 **open — release blocker for backtest results**).
