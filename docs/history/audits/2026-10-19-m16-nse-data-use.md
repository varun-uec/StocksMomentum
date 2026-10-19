# M16 — NSE Data-Use Check (ADR-012 release check)

> **Date:** 2026-10-19 · **Read:** the NSE website Terms of Use at <https://www.nseindia.com/static/nse-terms-of-use>, fetched 2026-10-19 08:45 IST. This is not legal advice.

## What the app does
Each user's copy downloads NSE's daily bhavcopy files on a schedule. The daily job and the "Refresh" button do this through the `nsemine` library and the NSE archives. On first run it downloads about 340 daily files in one go. The app then screens, back-tests (walk-forward) and evaluates strategies (Strategy Studio) on that data, for its owner only. The project ships no data and runs no shared service.

## What the terms say (verbatim)

1. **Automated collection:** "User is prohibited to conduct any systematic or automated data collection activities (including scraping, data mining, data extraction and data harvesting) on or in relation to our Website / Mobile Application."
2. **Copying:** "Unless the information or Content is available for download, not to aggregate, copy or duplicate in any manner any of the content or information which is available on Website / Mobile Application."
3. **Redistribution:** content may not be "distributed, displayed, performed, broadcasted, published, hyperlinked, sold, marketed, licensed, rented, leased or distributed in any form, without prior written permission of NSE."
4. **Simulation:** "User acknowledges, agrees and undertakes that it shall not, in any form and manner, use or make the data or Content available on the Website / Mobile Application, for any gaming, virtual trading or simulation activities under any circumstances whatsoever."

Search results also point to NSE's [data policy](https://www.nseindia.com/market-data/nse-data-policy) and its [Data Sharing & Usage Policy](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Data_Sharing%26Usage_Policy.pdf). Under them, market data for other uses comes through NSE Data under an agreement. I did not read those documents in full.

## Assessment
- **Clause 1 likely covers the app's scheduled downloads.** The bhavcopy is offered for download, so clause 2 permits a copy. But a program that fetches it every day, and 340 files on first run, is "systematic or automated data collection" on a plain reading. The terms give no exception for personal use.
- **Clause 4 may cover the research features.** A walk-forward backtest and the Studio's evaluations replay past data to see how a strategy would have done. A reader could call that "simulation". The screener alone, which ranks today's stocks, is less exposed.
- **Clause 3 does not apply** as long as the project ships no data and runs no shared service (ADR-012).
- **Who is exposed.** Each user who runs the app, and arguably the project, which publishes a tool built to do clause 1.

## Recommendation
ADR-012 says: "If the terms forbid the app's retrieval method, the release waits until the provider strategy changes (ADR-003)." On this reading, **public release should wait.** The owner can:
1. ask NSE (or NSE Data) for written permission, or for a licensed feed, for personal self-hosted use;
2. get a legal opinion on clauses 1 and 4 for a self-hosted, single-user tool;
3. change the provider (ADR-003): a licensed vendor or a broker API the user already has access to. `kite.py` already exists as an adapter;
4. publish the code without any built-in NSE fetching, so each user supplies data they are entitled to. That changes the one-command fetch goal of M16.

The choice, and any legal advice, is the owner's.
