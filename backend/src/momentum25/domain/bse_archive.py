"""Measured boundaries of the BSE bhavcopy archive (RP-014).

No public BSE bhavcopy exists before 2006-03-01. The legacy EQ_CSV format ends
2023-12-29. The UDiFF format begins 2024-01-02, the first trading day of 2024.
"""

from __future__ import annotations

from datetime import date

BSE_LEGACY_START: date = date(2006, 3, 1)
UDIFF_START: date = date(2024, 1, 2)
