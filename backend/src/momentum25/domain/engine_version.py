"""Engine identity constants (ADR-014 §11, identity schema 3).

``ENGINE_VERSION`` names how scoring, ranking, RS ratings and other
computations outside the indicator pipeline and the rule registry turn data
into results. Bump it in the same commit as any change that alters a result
for unchanged data and is not already covered by ``INDICATOR_VERSION`` or the
rule-registry fingerprint.

``REFERENCE_UNIVERSE_VERSION`` names the definition of the reference equity
universe (IMPLEMENTATION_SPEC §8). Bump it when that definition changes.

History:
- ENGINE_VERSION 1, REFERENCE_UNIVERSE_VERSION 1: behaviour before engine v2
  (RS over every active equity with shortened windows; ``security_id``
  tie-break; the active list as the screening universe).
- ENGINE_VERSION 2, REFERENCE_UNIVERSE_VERSION 2: engine v2 (IMPLEMENTATION_SPEC
  §8, §10). RS is calendar-aligned on NSE sessions with a 5-session anchor
  tolerance, needs 253 bars and ranks the reference population; ties break by
  symbol, ISIN, security_id. The universe is NSE and dual-listed (``BOTH``)
  equities, listed and not delisted on the date; the active flag is not read.
  Runs stamped 1 are NOT comparable to runs stamped 2.
"""

from __future__ import annotations

ENGINE_VERSION = 2
REFERENCE_UNIVERSE_VERSION = 2
