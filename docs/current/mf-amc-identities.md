# Canonical AMC identity (method v9)

Identity registry version 1 is `mf_data/domain/amc_identity.py`. Its 55 stable
IDs join the exact NAV and scheme-master labels below. Case and whitespace are
insignificant. Punctuation and corporate history are not guessed. IDs are fixed
constants; a future rename adds evidence and aliases without regenerating IDs.
Unknown labels retain their source text and have no asserted canonical ID.

## Authoritative retained evidence

Both files were already retained. This change fetches nothing.

| Source | Raw path beneath `WICKSTREET_RAW_DIR` | SHA-256 of uncompressed bytes |
|---|---|---|
| AMFI master (16,472 rows) | `amfi/schemes-v1/2026/2026-10-24-d9be116b194d4030.gz` | `d9be116b194d403070bf0900f66bdb4b1ec4c83500e04ac345d01e7281d6f6fc` |
| AMFI NAV (8,684 rows) | `amfi/nav-v1/2026/2026-10-23-3617afb7a2ef0ed8.gz` | `3617afb7a2ef0ed8113ab0fec1463bf4b285a221ec30594113106f4897f9fedf` |

An independent reviewer parsed each file, indexed master rows by AMFI code, and
joined every NAV row to that code. All 8,684 codes match. Each NAV AMC has exactly
one master AMC, and each matched master AMC has exactly one NAV AMC. The table
records pair counts and a representative code. This proves the listed current
aliases; it does not establish historical mergers or AMC permission.

IIFCL, IL&FS Infra and Sahara occur only in the master and remain separate,
unmapped labels. Historical Reliance, IIFL and IDFC names are not inferred aliases.

## Semantics and provenance

- Snapshot `amc` is the canonical NAV label for evidenced identities. Fund-house
  filtering, sorting, grouping, peer selection and direct/regular identity keys
  use that identity. Scheme-to-plan and ISIN joins retain their existing rules.
- Snapshot row `anchors.source_amc` retains the chosen source label;
  `anchors.amc_id` holds its known stable ID. `tables.amc_identity_version` is 1.
  The source DB, raw bytes, source IDs, effective dates and revisions are unchanged.
- Fund search and detail responses include canonical `amc`, `source_amc` and,
  when known, `amc_id`. Exact full-label or stable-ID searches query both source
  aliases before pagination and use the same ranking.
- `amc in` and `amc not_in` accept either source alias or stable ID. Unknown labels
  keep exact comparison semantics. Membership never expands by substring.
- `/screener/fields` advertises one canonical value per known AMC plus an alias
  map. Saved/URL conditions normalize before controls render, including nested
  groups and exclusion filters. Opening a saved record does not rewrite it.
- Method v9 preserves the positional field registry and v8 snapshot decoder.
  Rebuilds read source rows at the requested revision. Rebuilding historical
  snapshots uses the repository's current scheme identity links; this is corrected
  v9 evidence, not a claim that all old v8 facts were valid.

## Rebuild and recovery

1. Restore the DB and raw tree using [the recovery runbook](../operations/mf-data-recovery.md).
2. Verify both raw hashes above after gzip decompression. Parse with
   `parse_scheme_master` and `parse_nav_file`; join by `amfi_code`, then confirm
   all registry aliases and evidence codes against these retained records.
3. Run `wickstreet mf metrics` for the live revision. For every serving v8
   revision retained for saved research, run `wickstreet mf metrics --revision R`.
   Each operation is idempotent and leaves source records/publication untouched.
4. Independently verify alias result sets, saved controls, representative financial
   facts and reproducible encoded hashes before retiring superseded snapshots.
5. Use `wickstreet mf retire-snapshot ID --by OWNER --reason "Superseded by v9
   canonical AMC identity; replacement snapshot ID ..."`. Retire only after a
   replacement is stored and checked. Old payloads and audit rows remain intact.

## Registry evidence

| Stable ID | Canonical NAV label | Master label (as filed) | Shared codes | Example code |
|---|---|---|---|---|
| `in-amc-360-one` | 360 ONE Mutual Fund | 360 ONE Asset Management Limited | 45 | 153703 |
| `in-amc-ask` | ASK MUTUAL FUND | ASK ASSET MANAGEMENT PRIVATE LIMITED | 8 | 154591 |
| `in-amc-abakkus` | Abakkus Mutual Fund | Abakkus Investment Managers Private Limited | 19 | 154477 |
| `in-amc-aditya-birla-sun-life` | Aditya Birla Sun Life Mutual Fund | Aditya Birla Sun Life AMC Limited | 390 | 148921 |
| `in-amc-alphagrep` | AlphaGrep Mutual Fund | AlphaGrep Investment Management Private Limited | 12 | 154518 |
| `in-amc-angel-one` | Angel One Mutual Fund | Angel One Asset Management Company Limited | 15 | 153529 |
| `in-amc-axis` | Axis Mutual Fund | Axis Asset Management Co. Ltd. | 381 | 120505 |
| `in-amc-bajaj-finserv` | Bajaj Finserv Mutual Fund | Bajaj Finserv Asset Management Limited | 108 | 153309 |
| `in-amc-bandhan` | Bandhan Mutual Fund | Bandhan AMC Limited | 406 | 149303 |
| `in-amc-bank-of-india` | Bank of India Mutual Fund | Bank of India Investment Managers Private Limited | 138 | 151443 |
| `in-amc-baroda-bnp-paribas` | Baroda BNP Paribas Mutual Fund | Baroda BNP Paribas Asset Management India Private Limited | 239 | 119354 |
| `in-amc-canara-robeco` | Canara Robeco Mutual Fund | Canara Robeco Asset Management Company Limited | 130 | 147532 |
| `in-amc-capitalmind` | Capitalmind Mutual Fund | Capitalmind Asset Management Private Limited | 8 | 154011 |
| `in-amc-carnelian` | Carnelian Mutual Fund | Carnelian Investment Managers Private Limited | 5 | 154784 |
| `in-amc-choice` | Choice Mutual Fund | Choice AMC Private Limited | 10 | 154416 |
| `in-amc-dsp` | DSP Mutual Fund | DSP Asset Managers Private Limited | 343 | 119250 |
| `in-amc-edelweiss` | Edelweiss Mutual Fund | Edelweiss Asset Management Limited | 298 | 152094 |
| `in-amc-franklin-templeton` | Franklin Templeton Mutual Fund | Franklin Templeton Asset Management (India) Private Limited | 204 | 152739 |
| `in-amc-groww` | Groww Mutual Fund | Groww Asset Management Limited | 216 | 147458 |
| `in-amc-hdfc` | HDFC Mutual Fund | HDFC Asset Management Company Limited | 348 | 149366 |
| `in-amc-hsbc` | HSBC Mutual Fund | HSBC Asset Management (India) Private Ltd. | 232 | 154294 |
| `in-amc-helios` | Helios Mutual Fund | Helios Capital Asset Management (India) Pvt. Ltd. | 34 | 152151 |
| `in-amc-icici-prudential` | ICICI Prudential Mutual Fund | ICICI Prudential Asset Management Company Limited | 523 | 120585 |
| `in-amc-iti` | ITI Mutual Fund | ITI Asset Management Limited | 108 | 147183 |
| `in-amc-invesco` | Invesco Mutual Fund | Invesco Asset Management (India) Private Limited | 247 | 147884 |
| `in-amc-jm-financial` | JM Financial Mutual Fund | JM Financial Asset Management Limited | 123 | 147838 |
| `in-amc-jio-blackrock` | Jio BlackRock Mutual Fund | Jio BlackRock Asset Management Private Limited | 33 | 153650 |
| `in-amc-kotak-mahindra` | Kotak Mahindra Mutual Fund | Kotak Mahindra Asset Management Company Limited. | 384 | 120152 |
| `in-amc-lic` | LIC Mutual Fund | LIC Mutual Fund Asset Management Limited | 220 | 150659 |
| `in-amc-lakshya` | Lakshya Mutual Fund | Lakshya Asset Management Private Limited | 2 | 154736 |
| `in-amc-mahindra-manulife` | Mahindra Manulife Mutual Fund | Mahindra Manulife Investment Management Pvt Ltd | 120 | 147563 |
| `in-amc-mirae-asset` | Mirae Asset Mutual Fund | Mirae Asset Investment Managers (India) Pvt. Ltd | 280 | 147737 |
| `in-amc-monarch` | Monarch Mutual Fund | Monarch Networth Asset Management Private Limited | 4 | 154705 |
| `in-amc-motilal-oswal` | Motilal Oswal Mutual Fund | Motilal Oswal Asset Management Company Limited | 220 | 152650 |
| `in-amc-nj` | NJ Mutual Fund | NJ Asset Management Private Limited | 25 | 150369 |
| `in-amc-navi` | Navi Mutual Fund | Navi AMC Limited | 72 | 141414 |
| `in-amc-nippon-india` | Nippon India Mutual Fund | Nippon Life India Asset Management Limited | 542 | 106235 |
| `in-amc-old-bridge` | Old Bridge Mutual Fund | Old Bridge Asset Management Private Limited | 12 | 152358 |
| `in-amc-pgim-india` | PGIM India Mutual Fund | PGIM India Asset Management Private Limite | 126 | 152815 |
| `in-amc-ppfas` | PPFAS Mutual Fund | PPFAS Asset Management Pvt. Ltd. | 28 | 154155 |
| `in-amc-quantum` | Quantum Mutual Fund | Quantum Asset Management Company Private Limited | 36 | 152107 |
| `in-amc-sbi` | SBI Mutual Fund | SBI Funds Management Limited | 461 | 149887 |
| `in-amc-samco` | Samco Mutual Fund | Samco Asset Management Private Limited | 29 | 150631 |
| `in-amc-shriram` | Shriram Mutual Fund | Shriram Asset Management Co. Ltd. | 39 | 153076 |
| `in-amc-sundaram` | Sundaram Mutual Fund | Sundaram Asset Management Company Ltd | 172 | 149668 |
| `in-amc-tata` | Tata Mutual Fund | Tata Asset Management Private Limited | 363 | 151232 |
| `in-amc-taurus` | Taurus Mutual Fund | Taurus Asset Management Company Limited | 34 | 118870 |
| `in-amc-the-wealth-company` | The Wealth Company Mutual Fund | Wealth Company Asset Management Holdings Private Limited | 49 | 154381 |
| `in-amc-trust` | Trust Mutual Fund | Trust Asset Management Private Limited | 45 | 153644 |
| `in-amc-uti` | UTI Mutual Fund | UTI Asset Mgmt. Co. Ltd. | 419 | 120656 |
| `in-amc-unifi` | Unifi Mutual Fund | Unifi Asset Management Private Limited | 6 | 153570 |
| `in-amc-union` | Union Mutual Fund | Union Asset Management Company Private Limited | 140 | 150858 |
| `in-amc-whiteoak-capital` | WhiteOak Capital Mutual Fund | WhiteOak Capital Asset Management Limited | 80 | 145969 |
| `in-amc-zerodha` | Zerodha Mutual Fund | Zerodha Asset Management Private Limited | 24 | 153436 |
| `in-amc-quant` | quant Mutual Fund | quant Money Managers Limited | 129 | 100631 |
