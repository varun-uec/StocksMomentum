"""Backend EMA and MACD match the browser golden fixture (indicator v3).

The fixture comes from ``audit-evidence/audit-r3/ui/indicator_reference.py``,
which uses no app code. Warm-up gaps must match too, not only the numbers.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pytest

from momentum25.infrastructure.pipelines.indicator_pipeline import (
    IndicatorPipelineImpl,
    _ema,
    _macd_series,
)

FIXTURE = Path(__file__).parents[3] / "web/src/lib/indicators/golden-fixture.json"
DATA = json.loads(FIXTURE.read_text())
CLOSE = pd.Series([b["close"] for b in DATA["bars"]], dtype="float64")


def _same(got: pd.Series, key: str) -> None:
    want = DATA["expected"][key]
    assert len(got) == len(want)
    for i, (g, w) in enumerate(zip(got.tolist(), want, strict=True)):
        if w is None:
            assert math.isnan(g), f"{key}[{i}] should be warm-up, got {g}"
        else:
            assert abs(g - w) <= 1e-9 * max(1.0, abs(w)), f"{key}[{i}]: got {g}, want {w}"


def test_ema_matches_the_golden_fixture() -> None:
    _same(_ema(CLOSE, 20), "ema20")


def test_macd_matches_the_golden_fixture() -> None:
    line, signal, hist = _macd_series(CLOSE)
    _same(line, "macd")
    _same(signal, "macd_signal")
    _same(hist, "macd_hist")


@pytest.mark.parametrize(("bars", "expected"), [(49, None), (50, 2.0)])
def test_rel_volume_divides_by_the_same_fifty_bars_as_avg_volume(bars, expected) -> None:
    # 49 bars of 24 then today's 49: the 50-bar mean is 24.5, so 2.0. The old
    # rule (the 49 bars before today) read 49 / 24 = 2.04.
    volumes = [24.0] * (bars - 1) + [49.0]
    df = pd.DataFrame({"volume": volumes})
    assert IndicatorPipelineImpl._rel_volume(df, 50) == expected
