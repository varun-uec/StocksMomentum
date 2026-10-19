# ADR-015: Licence

**Status:** Proposed (2026-10-19). The owner makes the final choice. Nothing is published until then.

## Context
ADR-012 publishes Wickstreet's source on GitHub and leaves the licence to this ADR. The licence must fit what the code already depends on, and what the owner may want later.

**Dependencies (checked 2026-10-19).**
- Python runtime: 86 packages. MIT, BSD-2/3-Clause, ISC, PSF and Apache-2.0, plus MPL-2.0 for `certifi` and `pathspec`. MPL-2.0 is file-level copyleft. It binds only changes to those files, and we ship them unmodified.
- Web runtime: 57 packages. MIT, ISC, BSD-3-Clause and Apache-2.0, plus OFL-1.1 for the Inter font. OFL allows bundling the font with any software.
- No dependency is GPL or AGPL. So any of the options below is compatible.

**Obligations that hold under every option.**
- `lightweight-charts` (Apache-2.0) needs its NOTICE text and a link to TradingView. The About page and the README already carry them (ADR-012).
- The Inter font needs its OFL licence text in the distribution.
- NSE data carries no grant from us (ADR-012). The licence covers code only.
- The clean-room rule stands. No TradingView or OpenChart source or assets are in the code, so their licences impose nothing on ours.

**What the owner has said or implied.**
- An open project, run privately by each user (ADR-012).
- A possible SaaS path later (ADR-010 keeps a `tenant_id` seam).
- OpenChart, the usability reference, uses Apache-2.0 plus a clause against multi-tenant hosting. That shows one way to keep a hosted service for the author. It also makes the licence no longer open source by the OSI definition.

## Options

| Option | Others may | Others must | Owner keeps a hosted service for themselves? | Contributions |
|---|---|---|---|---|
| **Apache-2.0** | Use, change, host, sell, close their fork | Keep notices; state changes | No | Inbound = outbound; no CLA needed |
| **MIT** | Same as Apache-2.0 | Keep the notice | No | Same; no patent grant |
| **AGPL-3.0** | Use, change, host | Publish the source of any changed version they run as a network service | Partly. Rivals can host, but only in the open. The owner can sell other licences only with a CLA from contributors. | A CLA if the owner wants to dual-license |
| **Apache-2.0 + no-hosting clause** (OpenChart style) | Self-host | Not run it as a service for others | Yes | A custom licence: not OSI open source, and it puts off contributors and packagers |

## Recommendation
**Apache-2.0**, unless the owner wants to keep a hosted service for themselves. In that case, AGPL-3.0 with a CLA.

- **Apache-2.0** is simple. It grants patent rights and fits every dependency. It matches the chart library's own licence and NOTICE handling. It needs no CLA. ADR-012 already rules out a shared service, so the main reason for copyleft is absent today.
- **AGPL-3.0** is the right choice only if a closed, hosted fork would harm the owner's plans. It does not stop anyone from hosting. It only makes them publish their changes.
- **Not recommended:** a custom no-hosting clause. It stops the project being open source, which is ADR-012's goal.

## To do once the owner chooses
- Add `LICENSE` at the root, and `NOTICE` (Apache-2.0) with the `lightweight-charts` notice and the Inter OFL text.
- Set `license` in `backend/pyproject.toml` and `web/package.json`.
- Add a licence line to the README. If AGPL-3.0, add a CLA note to CONTRIBUTING.
- Accept ADR-012 together with this ADR.
