"""Technical indicator functions and the indicator pipeline contract.

Pure functions only (no I/O). Exact formulas are specified in
``IMPLEMENTATION_SPEC.md`` §8 and implemented in milestone M2. This phase defines
the pipeline interface and function signatures, plus a placeholder pipeline that
returns empty indicator sets.
"""

from momentum25.domain.indicators.pipeline import IndicatorPipeline
from momentum25.domain.indicators.pipeline_impl import IndicatorPipelinePlaceholder

__all__ = ["IndicatorPipeline", "IndicatorPipelinePlaceholder"]