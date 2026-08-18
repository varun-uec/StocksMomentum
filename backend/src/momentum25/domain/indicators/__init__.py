"""Indicator pipeline port.

The domain layer defines only the ``IndicatorPipeline`` contract. The real
implementation lives in ``infrastructure/pipelines/indicator_pipeline.py``.
Exact formulas are specified in ``IMPLEMENTATION_SPEC.md`` §8.
"""

from momentum25.domain.indicators.pipeline import IndicatorPipeline

__all__ = ["IndicatorPipeline"]
