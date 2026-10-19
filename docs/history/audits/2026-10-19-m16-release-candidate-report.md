# M16 Report — Release Candidate

> **Date:** 2026-10-19 · **Branch:** `wickstreet/m10-m11` (local, never pushed) · **Candidate:** the commit that adds this report · **Plan:** [Wickstreet milestones](../plans/2026-10-18-wickstreet-milestones.md) § M16

## Verdict
The branch is a release candidate on the engineering side.
- Every check passes, on the dependency versions the production image already runs.
- A fresh clone starts with one command. It also fetches NSE data once the user follows the first-run step, which the README now states.

**Public release is blocked on data use.** NSE's website terms forbid "systematic or automated data collection", and also forbid using the data for "simulation activities". The app downloads bhavcopies on a schedule, and it back-tests and evaluates strategies. ADR-012 says the release waits in that case ([data-use check](2026-10-19-m16-nse-data-use.md)).

Publication also waits on other decisions only the owner can make (last section). Nothing has been pushed or published.

M16 found and fixed four defects that predate it:
- CI had never run a check.
- The Docker image ignored the lock.
- RS ratings read raw closes (found in M14.7).
- The first-run path was undocumented.

## Steps

| Step | Result | Record |
|---|---|---|
| 16.1 Licence | Every runtime dependency is permissive. ADR-015 (Proposed) recommends Apache-2.0, or AGPL-3.0 with a CLA if the owner wants to keep a hosted service. | [ADR-015](../../architecture/adr/ADR-015-licence.md) |
| 16.2 Name clearance | No product or mark named Wickstreet found. `wickstreet.com` is parked for sale; `.io` is free. A formal registry search remains. | [name clearance](2026-10-19-m16-name-clearance.md) |
| 16.3 Security review | History clean. Boundary documented. CI fixed. Two items for the owner. | below; [SECURITY.md](../../../SECURITY.md) |
| 16.4 Dependency audit | Python: no advisories outside the venv's own `pip`. npm: none at runtime; 11 dev-only. The image now builds from the lock. | below |
| 16.5 Usability | First-run guidance on the empty dashboard and in the README. Studio on a phone scrolls to the chosen family. The owner's M11 assessment is still open. | below |
| 16.6 Documentation | README, CONTRIBUTING, SECURITY, `docs/current/{state,capabilities,architecture}.md`, ADR-013 §4 and ADR-014 §8. | this branch |
| NSE data-use check (ADR-012) | **Blocking.** The terms forbid automated collection and "simulation activities". Four ways forward, for the owner. | [data-use check](2026-10-19-m16-nse-data-use.md) |
| 16.7 Fresh install | One command, healthy, migrations 0001 → 0019, 7 strategies, NSE fetch works. | below |

## 16.3 Security review

- **Git history** (all branches, 1,457 objects, 18 MB): no keys, tokens or private keys; no `.env`. The only data files are two 5-line BSE bhavcopy fixtures for tests.
- **Boundary** (ADR-012): every port on loopback; `Host` and `Origin` checks tested since M10. `SECURITY.md` states the boundary and its limits.
- **New surfaces (M14):**
  - Studio inputs pass Pydantic and the rule registry. All SQL is built with SQLAlchemy; the f-string SQL in the code names only module constants.
  - Families and finished evaluations are protected by database triggers.
- **Known limits, stated in `SECURITY.md`:**
  - no request-body size limit;
  - no limit on concurrent evaluations;
  - default database credentials, safe only on loopback.
- **CI never ran a check.** Every run on `main` since 2026-08-17 failed at the first step: `ruff: command not found` and `pytest: command not found`. The steps called the tools outside the uv environment. They now use `uv run`, install the frozen lock and run `lint-imports` too. This is confirmed from the run logs only. The fix will first run on the next push.
- **For the owner:**
  - 65 commits carry a personal Gmail address as author, and a public push would publish it. Rewriting authors (`.mailmap` for display, or a history rewrite before the first push) is the owner's call.
  - GitHub's private vulnerability reporting must be switched on for the address in `SECURITY.md` to work.

## 16.4 Dependency audit

- **Python (`pip-audit`).**
  - aiohttp, anyio, multidict and urllib3 had advisories with patch fixes. All are now at fixed versions.
  - Only the virtual environment's own `pip` 23.2.1 is still flagged. It is a tool, not an app dependency, and the image does not use it to install the app.
- **The image ignored the lock.**
  - The Dockerfile installed the newest versions that `pyproject.toml` allowed. So the production image (`cb0da94`) ran other versions than the tests: 44 of 67 runtime packages differed, among them SQLAlchemy 2.1.5 against the locked 2.0.51.
  - Built from the old lock, nsemine 1.5 crashed on import in the container: it writes a SQLite file into `site-packages`, and the app runs as a non-root user.
  - The lock now resolves with `--exclude-newer 2026-10-18`, the day the running image was built, and matches it package for package. The image installs the exported lock, and the `uv` tool image is pinned to 0.10.12.
  - SQLAlchemy 2.1 needed two typing fixes. Every check passes on the new set.
- **The image runs one process,** as `docker-compose.yml` already did. The scheduler (ADR-007) and Studio evaluations run inside it, and a second worker would run them twice.
- **npm:**
  - Runtime packages have no advisories.
  - 11 dev-only advisories (ReDoS and DoS in typescript-eslint 7 and the tailwindcss 3 tool chain) need major upgrades. They are open defect 10 in `state.md`.
- **Licences:** see ADR-015. No GPL or AGPL anywhere.

## 16.5 Usability

An independent pass on a fresh install and on the Studio with real data, at 1366 × 850 and 390 × 844:
- **Empty dashboard.** It said "Trigger a run from the API", which a new user cannot act on. It now says to choose Refresh, and that the first run downloads about 18 months of data. The refresh endpoint's warning now gives the same advice. The README has a "First run" line.
- **Studio on a phone.** Choosing a family left its view below the list and the new-family form. The page now scrolls to it.
- **No change needed:** the labels, the "no performance figure" line on a Screening Result, the hold-out prompt, and the bounds shown next to each parameter.
- **Still open:** the owner's own [M11 usability assessment](2026-10-18-m11-usability-assessment.md).

## 16.7 Fresh install

A clean clone of the branch, run with `cp .env.example .env` and `docker compose up --build`. It used a separate project name (`-p wsfresh`) and other ports, so the owner's running stack was never touched.
- The image builds from the lock. All three services become healthy. Alembic applies 0001 → 0019. Seven strategies sync. The SPA and `/studio` load through the `Host` check on a non-default port.
- `POST /market-data/refresh` fetched 2,691 NSE bars for 2026-10-16 from inside the container. It stored none, because a new database has no securities yet. **The first run is the bootstrap:** "Refresh" on the dashboard (`POST /runs/execute`) downloads about 500 calendar days of bhavcopies, registers the securities and screens. I did not run those ~340 downloads against NSE for this check; the README and the dashboard now state the step.
- **For anyone running two copies on one machine:** `docker-compose.yml` fixes the project name to `momentum25`. A second copy started from another folder would replace the first one's containers unless it passes `-p`. This does not affect a single install.

## Verification
Full run on the candidate (code as committed with this report):

| Suite | Result |
|---|---|
| Backend `pytest` | 811 passed; 3 more full runs also passed. One earlier run had 1 transient error that did not recur. |
| `ruff check`, `mypy --strict`, import contracts | clean |
| Generated API types | match the API |
| Web `tsc`, ESLint, build | clean |
| Web Vitest | 96 passed |
| Playwright | 66 passed |
| NFR-11 chart open (30 runs each) | Warm P95 181 ms (target ≤ 1 s); cold P95 219 ms (target ≤ 3 s) |
| `pip-audit` | no advisories outside the venv's own `pip` |
| `npm audit --omit=dev` | 0 |
| Fresh install (`-p wsfresh`) | healthy; migrations 0001 → 0019; NSE fetch reachable |

## Owner decisions before publication
1. **Licence.** Choose under [ADR-015](../../architecture/adr/ADR-015-licence.md): Apache-2.0 is recommended, or AGPL-3.0 with a CLA. Accept ADR-012 with it.
2. **Name.** Run a formal trademark search (IP India and USPTO, classes 9, 36 and 42) and choose a domain.
3. **Author emails.** Publish the history as it is, or rewrite the authors before the first push.
4. **Deploy the RS fix** (`18cab43`). It changes which names pass the RS gate on the live run: 28 more on the latest session.
5. **Re-route the older research tools** to the point-in-time path. Doing so changes numbers that earlier reports quote.
6. **Defaults taken in M14**, for review: the hold-out grid, the plausible effects, Bonferroni, and the Studio v1 scope (ADR-014 §8).
7. **NSE data use (blocking).** Choose a way forward ([data-use check](2026-10-19-m16-nse-data-use.md)): written permission or a licensed feed from NSE, a legal opinion, another provider, or a release without built-in NSE fetching.
8. **Push and publish.** Nothing has been pushed.
