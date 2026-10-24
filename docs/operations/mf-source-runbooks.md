# Wickstreet MF source runbooks

**Checked against the adapters on 2026-10-24.** These commands run the local CLI in the API image, which has the configured runtime DB URL and the same mounted `WICKSTREET_RAW_DIR` as the app. Commands are resumable unless noted. They use the dates in this example as fixed examples; substitute the period needed.

For direct local execution, install the backend and set `WICKSTREET_DATABASE_URL`, `WICKSTREET_MIGRATION_DATABASE_URL`, and `WICKSTREET_RAW_DIR` from the local secret/config store. Do not put connection strings in the repository or command transcripts.

## Rights gate and shared request policy

The app denies a source/use without an active owner grant for the current mode. Grants are local database rows, not provider permission. Check the live register before work:

```bash
docker compose run --rm --entrypoint wickstreet wickstreet-migrate rights list
```

The owner records/revokes grant decisions with the migration login. Example form only; use the precise source-specific basis in ADR-023 U10/U11/U14 and identify the operator in `--by`:

```bash
docker compose run --rm --entrypoint wickstreet wickstreet-migrate rights grant amfi \
  --use automated_retrieval --use storage \
  --basis "Owner personal-mode decision per ADR-023 U10/U14; not AMFI permission" --by OPERATOR
```

Analytics also needs `derived_metrics` for each underlying source, and research API reads need `display`. Provider import grants are separate: each AMC uses its own source name (`ppfas`, `dsp`, `nippon`, `sbi`, `icici`, `tata`, `motilal`, `uti`, `barodabnp`, `groww`, `samco`, `pgim`, `whiteoak`, `trust`, `mirae`, `invesco`, `sundaram`, `lic`, `quant`, `quantum`); RBI imports require `rbi` storage; MFAPI checks require `mfapi` automated retrieval and storage. The CLI checks rights before network retrieval and before database publication. SaaS mode currently has no supported identity adapter and no commercial source permissions.

Shared HTTP policy from `WICKSTREET_*`: minimum interval 1 second per adapter, timeout 120 seconds (AMFI facts forces at least 180 seconds), maximum four attempts. Transport failures, 429 and 5xx retry with exponential backoff; other 4xx fail. No provider password or API token is configured. Each command prints outcomes and counts; a failed run is in `ingestion_run` and can be retried. Published/unchanged/unavailable periods skip unless a command has `--refetch`.

## AMFI NAV and scheme master

**URLs:** [daily NAV history](https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx) (`frmdt`/`todt`, one date per request), [scheme master](https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0). No authentication in the adapter.

1. Full default backfill (ten years plus seven calendar days through yesterday):

   ```bash
   docker compose run --rm api wickstreet mf backfill
   ```

   Explicit interval, inclusive:

   ```bash
   docker compose run --rm api wickstreet mf backfill --start 2016-10-17 --end 2026-10-23
   ```

   Backfill requests the scheme master first, then one date at a time. It binary-searches the first date AMFI serves (observed 2023-04-01), logs the older interval as unavailable, and resumes settled dates on rerun. After five consecutive failed dates it stops so a persistent layout/outage is not masked by continuing. There is no CLI `--refetch` for arbitrary historical AMFI dates.

2. Daily manual refresh (the app also runs this automatically at 11:30 IST when enabled):

   ```bash
   docker compose run --rm api wickstreet mf refresh
   ```

   It refreshes the master and latest seven calendar days up to yesterday; after longer downtime it resumes from the last stored NAV date. `--today YYYY-MM-DD` makes a fixed-date replay.

3. Parser correction from retained AMFI raw files:

   ```bash
   docker compose run --rm api wickstreet mf reparse --start 2026-09-01 --end 2026-09-30
   ```

   This makes no source requests. It checks each raw file against the revision SHA-256, writes a new revision only if parsed values differ, and preserves old rows as history. If a provider changes an old file but the retained payload is wanted, the current CLI has no arbitrary-date network refetch switch; the seven-day refresh is the source-correction path for recent data.

**Layout notes:** exact UTF-8 NAV header, section and AMC headings, eight semicolon fields per row; date names use English abbreviations independent of locale. `-`/blank plan, option, and ISIN values become null. A trailing decimal point like `222.` is accepted. The scheme master is exact-header CSV; its final field can contain two concatenated ISINs. Unknown headers or duplicate code/date conflicts block publication.

## TigZig archive and MFAPI check

**URLs:** TigZig full archive `https://api.tigzig.com/mf/v1/download/amfi_nav_master.csv.gz`; scheme snapshot `https://api.tigzig.com/mf/v1/download/amfi_nav_master_latest.csv.gz`. No auth in code. The code downloads the full gzip archive each run and filters it locally.

Run AMFI backfill first so the cutoff is the discovered first AMFI date, then:

```bash
docker compose run --rm api wickstreet mf archive
```

Default range matches the configured ten-year history window. For the wider publisher history use `--start 2006-04-01 --end YYYY-MM-DD`. `--refetch` rereads settled months. One monthly run is created per period/segment. Before AMFI's cutoff, the archive is authoritative; at/after cutoff it fills missing code/date rows only. Conflicts are counted; direct AMFI values win. Archive precision is four decimals, with `0.0001` comparison tolerance. The snapshot has no launch/closure/minimum fields and only fills scheme codes absent from the AMFI master.

Current CLI has no archive-only parser replay command. `--refetch` downloads the source again. The retained raw gzip contains the full archive and can be used by an adapter-level replay; the month staging CSVs under `<raw>/tigzig/work` are temporary and deleted after parsing.

MFAPI is only a comparison source. Public URL and docs: [homepage](https://www.mfapi.in/), [API docs](https://www.mfapi.in/docs/), request `GET https://api.mfapi.in/mf/{code}`. JSON date is `DD-MM-YYYY`; NAVs are strings; only `SUCCESS` is accepted. The provider page describes daily updates (homepage also describes six daily update times); adapter calls are still limited to one request per second. No numeric provider quota was found in its docs.

```bash
docker compose run --rm api wickstreet mf crosscheck --sample 50
docker compose run --rm api wickstreet mf crosscheck --code 10001 --code 10002 --start 2023-04-01 --end 2026-10-23
```

Without `--code`, the sample is deterministic by `md5(amfi_code)`. Checks report matched/differing/reference-only/stored-only counts and publish nothing. Comparison raw responses are retained under `mfapi/nav-v1` for audit; no command currently replays these saved comparisons offline.

## AMFI facts

The endpoints live in `backend/src/wickstreet/mf_data/infrastructure/amfi_facts.py`. The public HTTP client uses the same pacing/retry policy. Run NAV backfill and scheme master before these fact jobs.

| Dataset | Calls / format | Grain, dates and steps |
|---|---|---|
| `schemes` | `GET https://www.amfiindia.com/api/populate-scheme?MF_ID=N`, JSON; adapter queries IDs 1–120 and combines nonempty lists. | Current AMFI `sd_id`, fund-house ID and scheme name. Run before SSD/facts. |
| `ssd` | `GET https://portal.amfiindia.com/spages/SSD_{sd_id}.xml`, one XML per eligible scheme; combined raw JSON keyed by scheme ID. | Current scheme summary as-of run date. Uses only scheme names with a NAV in prior 30 days; `--missing` fetches only schemes with no stored SSD. |
| `ter` | `GET https://www.amfiindia.com/api/populate-te-rdata-revised` with `MF_ID=All`, `Month=MM-YYYY`, `strCat=-1`, `strType=-1`, `excel=true`; XLSX. | Daily TER within each requested month; stored as change points. Specify start/end spanning the inclusive months. |
| `performance` | POST filter/category/subcategory/report-date requests to `https://www.amfiindia.com/gateway/pollingsebi/api/amfi/`; combined JSON. | Reports at the latest stored NAV date in each requested month. Default open-ended only; `--closed-ended` adds closed-ended. Benchmark returns, AUM, riskometer, IR and filed returns are preserved as reported. |
| `tracking-error` | `GET https://www.amfiindia.com/api/tracking-error-data?MF_ID=all&strdt=...`; JSON. | Index fund/ETF tracking error and benchmark on the latest stored NAV date per requested month. |
| `idcw` | Per eligible `(MF_ID, strSDid)` request to `https://www.amfiindia.com/api/scheme-dividend?...&strYear=All`; combined JSON. | All listed distributions for schemes with a NAV in prior 30 days, as-of run date. |
| `market-caps` | Fetch categorisation page and its date-matched XLS/XLSX file. | AMFI average market cap and large/mid/small class for half-year ending June 30 or December 31. Requested months outside those two are ignored. |

Example historical load (availability is source-dependent):

```bash
docker compose run --rm api wickstreet mf facts schemes --end 2026-10-24
docker compose run --rm api wickstreet mf facts ssd --end 2026-10-24 --missing
docker compose run --rm api wickstreet mf facts ter --start 2019-01-01 --end 2026-09-30
docker compose run --rm api wickstreet mf facts performance --start 2019-01-01 --end 2026-09-30
docker compose run --rm api wickstreet mf facts tracking-error --start 2019-01-01 --end 2026-09-30
docker compose run --rm api wickstreet mf facts idcw --end 2026-10-24
docker compose run --rm api wickstreet mf facts market-caps --start 2024-06-01 --end 2026-06-30
```

For TER/performance/tracking-error, `--reparse` reads the retained payload instead of fetching. The current parser-only switch does not apply to scheme list, SSD, IDCW or caps; `--refetch` reacquires those but same-hash payload is a no-op. SSD has a manual `--stored GZIP_FILE` import route for a gzip-compressed combined JSON document. AMFI exposes SSD in both `<SchemeSummary>` element and label/value `<records>` XML layouts. TER requires expected header anchors (including “NSDL Scheme Code” and TER column), Excel serial date and direct/regular columns. Performance joins by compacted name, then by a unique regular/direct NAV pair; non-unique/missing joins count as unmatched.

## AMC monthly portfolios

Automated sources and listing URLs:

| `--amc` | Listing source / adapter behavior | Common file shape / quirk |
|---|---|---|
| `ppfas` | [PPFAS portfolio disclosure](https://amc.ppfas.com/downloads/portfolio-disclosure/) | One all-schemes workbook per month; older binary XLS before March 2026, later files may have XLSX bytes despite `.xls` suffix. |
| `dsp` | [DSP portfolio disclosures](https://www.dspim.com/mandatory-disclosures/portfolio-disclosures) | Monthly ZIP of scheme workbooks. |
| `nippon` | [Nippon downloads](https://mf.nipponindiaim.com/investor-service/downloads/factsheet-portfolio-and-other-disclosures) | One workbook with scheme sheets; many filenames use two-digit year; excludes fortnightly/half-yearly. |
| `sbi` | `POST https://www.sbimf.com/ajaxcall/CMS/GetSchemePortfolioSheets` | Browser-generated listing returned as HTML; one all-schemes workbook link. |
| `icici` | `POST https://apimf.icicipruamc.com/nms/v1/downloads/files` (`env: api`), download under `https://www.icicipruamc.com/blob` | Monthly ZIP of scheme workbooks; parser drops section-heading total rows only when their children reconcile. |
| `tata` | [Tata portfolio disclosures](https://www.tatamutualfund.com/schemes-related/portfolio); page script's `field_media_document` JSON links, which may redirect from `betacms.tatamutualfund.com` to `www.tatamutualfund.com` | One monthly workbook with one sheet per scheme. Filenames can contain the month or a numeric month-end date. Parser treats lettered rows such as `I) REPO` as sections, negative quantities as derivative positions, skips rows ending in `Total`, and stops at `Net Assets`. |
| `motilal` | `GET https://www.motilaloswalmf.com/content/aem-cloud-dept-backend-motilal-oswal/api/search-documents.json?year=&category=month%20end%20portfolio&month=&type=mf`; JSON listing `path` values are downloaded | One monthly workbook; filenames commonly say `Scheme Portfolio Details September 2026` or `Monthly Portfolio 31-07-2026-Final`. Adapter excludes fortnightly, half-yearly and performance files. |
| `uti` | `GET https://www.utimf.com/api/get-consolidate-portfolio-disclosure?year=YYYY&month=Month` | JSON listing and one ZIP; all schemes stacked in scheme-code blocks; block closes at scheme total. |
| `barodabnp` | [Baroda monthly portfolio page](https://www.barodabnpparibasmf.in/downloads/monthly-portfolio-scheme) and `POST https://www.barodabnpparibasmf.in/ajax-load-more-documents-new` | CSRF token/session and paginated HTML-in-JSON listing; finds all-funds workbook by title in the upload month and next month; up to 120 pages per month. |
| `groww` | [Groww portfolio page](https://www.growwmf.in/statutory-disclosure/portfolio); the page script's `publicUrl` values | One workbook a month (`Monthly Portfolio - September 30, 2026.xlsx`); names start with a sheet code (`IB43-Groww …`); futures are filed in percent beside fractional holdings. |
| `samco` | [Samco statutory disclosures](https://www.samcomf.com/StatutoryDisclosure) | One workbook per scheme a month (`IN_MF_MONTHLY_PORTFOLIO_September_2026_<scheme>_<stamp>.xlsx`), each on two hosts; the month is kept as one ZIP. Scheme named inside the title (`MONTHLY PORTFOLIO STATEMENT OF … AS ON …`). |
| `pgim` | `POST https://www.pgimindia.com/api/v1/brochure/published/disclosure` (section `SECTION_747960037`, "Monthly Portfolio") | One workbook per scheme a month (`PGIM INDIA SMALL CAP FUND Sep 2026.xlsx`), kept as one ZIP. Files before June 2025 are binary `.xlsb`, which the parser does not read; import them by hand after converting. |
| `whiteoak` | `GET https://cms.whiteoakamc.com/api/scheme-portfolios` (100 rows a page, `filters[period][$eq]=Monthly`) | One workbook per scheme a month; the month is read from `doc_name` ("… - 30th September2026"), not the file name. |
| `trust` | `POST https://www.trustmf.com/api/api/Trust/GetData` (`GetDisclosureByType`, `portfolio-monthly-disclosure`) | One workbook a month; the month is read from the title ("… as on 30.09.2026"); the file URL redirects to `www`. |
| `mirae` | `POST https://www.miraeassetmf.co.in/AjaxService/GetDownloadsData` (`portfolio_tab1`, 500 rows a page) | One workbook per scheme a month, titled "Portfolio Details as on 30th September 2026 for <scheme>"; target-maturity names carry other dates, so a title's first date decides. |
| `invesco` | `GET https://www.invescomutualfund.com/api/CompleteMonthlyHoldings?year=YYYY&classification=…` for `equity`, `hybrid`, `fixed-income`, `fund-of-funds`, `index-funds` | A row per scheme with `JanUrl` … `DecUrl`; the month comes from the key. Kept as one ZIP a month. |
| `sundaram` | Form `POST` `Catid=Monthly` to the portfolios page's `GetCategory` method (`/ajax/Modules_Disclosure_Monthly_Fortnightly_Adhoc_Portfolios,App_Web_0k2jxmrp.ashx`) | HTML links with titles; two workbooks a month (equity and FoF, fixed income), kept as one ZIP. |
| `lic` | Form `POST` `id=639&month=M&year=YYYY` to `https://www.licmf.com/downloads/consolidated-portfolio-files` | Two consolidated workbooks a month (equity, debt), kept as one ZIP. |
| `quant` | `POST https://quantmutual.com/statutorydisclosures.aspx/displaydisclouser` with `{"id": "YYYY", "cat": "MONTHLY PORTFOLIO"}` | One workbook a month under `/Admin/disclouser/`; names vary (`Monthly_Portfolio_July26`, `…_sept_30092026`). Seven months of 2024–2025 are not listed. |
| `quantum` | `GET https://www.quantumamc.com/portfolio/combined/-1/1/YYYY/0` | One all-funds workbook a month; the title ("September 2026 - All Funds") names the month, the file name is a GUID. |

Not fetched automatically (manual import only), with the reason found on 2026-10-24:

| AMC | Reason |
|---|---|
| Kotak | Radware bot check on the site. |
| HDFC, Edelweiss | HTTP 403 to clients other than a browser. |
| Axis | Listing API answers 403 without the page's session token; `robots.txt` disallows `/cms/`. |
| Bandhan, Mahindra Manulife, ITI, JM Financial | Listing APIs carry encrypted, signed payloads; Mahindra's `robots.txt` also disallows `/downloads`. |
| Wealth Company | TSPD bot challenge. |
| Canara Robeco | Files live under `/wp-content/uploads/`, which `robots.txt` disallows. |
| ABSL, HSBC, Franklin Templeton, Jio BlackRock | Their terms bar robots, scrapers or automated access; the owner kept these to manual import. |
| Union | The monthly list did not load (the site answered HTTP 500 and its list script failed) on 2026-10-24. |
| Navi, Zerodha, Bank of India, Bajaj, 360 ONE, Shriram | No machine-readable monthly listing found yet. |

A month that names its files only in titles, or that files one workbook per scheme, comes through `TitledPortfolioAdapter` or the `each` option: every matching file is fetched in turn and kept as one ZIP whose members are sorted and stamped 1980-01-01, so the same files give the same raw SHA-256.

A scheme renamed by its AMC joins its older months by sheet code: the codes in the AMC's newest kept file, where the names are AMFI's current ones, join sheets whose old names join nothing. Motilal reuses sheet codes across funds of funds, so none is learnt there.

Default command reads PPFAS and DSP for the last completed month. Choose an AMC explicitly and a month-end; `--start/--end` inclusive ranges are stepped monthly:

```bash
docker compose run --rm api wickstreet mf portfolios --amc ppfas --amc dsp --start 2026-01-31 --end 2026-09-30
docker compose run --rm api wickstreet mf portfolios --amc nippon --amc sbi --amc icici --amc tata --amc motilal --amc uti --amc barodabnp --start 2026-09-30 --end 2026-09-30
docker compose run --rm api wickstreet mf portfolios --amc groww --amc samco --amc pgim --amc whiteoak --amc trust --amc mirae --amc invesco --amc sundaram --amc lic --amc quant --amc quantum --start 2026-09-30 --end 2026-09-30
```

For parser-only replay, add `--reparse`; for provider refresh, use `--refetch`. `--refetch` with same file hash remains unchanged.

Manual fallback (one combined XLS/XLSX or ZIP for each AMC/month):

```bash
docker compose run --rm api wickstreet mf import-portfolios /path/monthly-portfolio.zip \
  --amc ppfas --month 2026-09-30 --url 'https://amc.example/path/to/file.zip'
```

If the AMC publishes one workbook per scheme, combine those workbooks into a single ZIP before import so one run contains the whole monthly disclosure. The command stores the supplied file in the raw store and records retrieval grant as absent (Wickstreet did not fetch it); storage still needs a source-specific grant. Do not import CAS statements here.

## RBI 91-day T-bill rates

There is intentionally no RBI HTTP adapter. Download from [DBIE](https://data.rbi.org.in/DBIE/) or an RBI release page in a browser, retain the source URL and import locally. Accepts either the annual Handbook XLSX (“Auctions of 91-Day Government of India Treasury Bills”) or the weekly HTML “Treasury Bills: Full Auction Result”. A release without accepted bids contributes no rate. Files are processed oldest first; repeated same-value dates are deduplicated, conflicting same-date values or no rates block the import.

```bash
docker compose run --rm api wickstreet mf import-rates \
  /path/handbook-2024-25.xlsx --url 'https://data.rbi.org.in/DBIE/'
docker compose run --rm api wickstreet mf import-rates \
  /path/auction-result.html --url 'https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=...'
```

Multiple paths can be passed with one `--url` per path, in the same order. Each file is a revision over its min/max auction dates. A same-hash file is unchanged; there is no RBI parser-only replay option. Import the corrected/manual file again after a parser or source correction. The metrics method treats a rate as stale after 35 days and the API response acknowledges RBI as source.

## Diagnostics and source changes

After any publish, CLI commands compute the snapshot for the new revision unless `--no-compute` is set. To rebuild the current snapshot by hand or report reconciliation:

```bash
docker compose run --rm api wickstreet mf metrics
docker compose run --rm api wickstreet mf report
```

`mf report` covers NAV completeness and all ingestion run statuses, not fact/holdings field completeness. For other datasets, group `wickstreet.ingestion_run` by source, dataset and status; compare requested date/month ranges with `published`, `unchanged`, `unavailable`, `failed`, and `denied` runs. Any parser header/layout failure is a source-change signal; keep the raw payload, update its runbook and fixture, bump the adapter version, then use that dataset's parser-only route when supported. Do not interpret owner grants as provider permission. See the full [as-built architecture](../current/mf-data-architecture.md).
