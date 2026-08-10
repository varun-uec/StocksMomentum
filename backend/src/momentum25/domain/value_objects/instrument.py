"""Instrument-type classification, read off the ISIN issuer code.

NSE prints one series code (``EQ``) for company shares and pooled-fund units
alike: ``GOLDBEES``, ``LIQUIDBEES`` and ``RELIANCE`` all arrive as
``SctySrs=EQ``, ``FinInstrmTp=STK``. The bhavcopy therefore carries no field
that separates them — verified against the live 2026-08-07 UDiFF file.

The ISIN does separate them. Its fourth character is the NSDL/SEBI issuer-type
code:

* ``INE`` — a company security (equity shares, including DVR variants).
* ``IN9`` — a company security under an older allocation block (``FELDVR``,
  ``JISLDVREQS``); still equity.
* ``INF`` — units of a mutual fund or ETF. Gold and silver ETFs, index ETFs
  and liquid funds all fall here.
* ``IN0`` — government paper (series ``GS``/``TB``, never ingested).

Only ``INF`` is excluded. Classifying by anything narrower would drop real
equities; classifying from the ticker text would be a guess.
"""

from __future__ import annotations

_FUND_UNIT_PREFIX = "INF"


def is_equity(isin: str | None) -> bool:
    """Return ``False`` only when the ISIN identifies a fund or ETF unit.

    An unknown ISIN (``None``) is treated as equity. The screening universe
    holds delisted and renamed rows whose ISIN was never captured, and a
    missing identity is not evidence of a fund.
    """
    if isin is None:
        return True
    return not isin.strip().upper().startswith(_FUND_UNIT_PREFIX)
