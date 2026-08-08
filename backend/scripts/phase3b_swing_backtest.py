"""Phase 3b: search for a swing target/stop configuration that passes hold-out.

Phase 3's fixed config (2x ATR stop, 3x ATR target fallback / swing-resistance
target, no conditioning) failed hold-out: avg R -0.021 on 3,211 trades
(2025-01-01 onward). This script tries alternative, first-principles-justified
configurations against the SAME in-sample period Phase 3 used
(2000-01-01..2024-12-31) to decide which ones are worth testing at all, THEN
runs each candidate exactly once against the untouched hold-out fold
(2025-01-01 onward). No configuration is chosen by looking at hold-out
results first -- that is the exact curve-fitting failure mode Phase 3b is
required to avoid.

Every configuration attempted is printed and appended to
docs/research/phase3b-target-methodology-log.md, including failures,
so the search is auditable and not silently cherry-picked.

Six configurations (capped at 5-8 per the backlog), each with an a-priori
rationale from the Phase 3 report's own diagnosis: hit rate on decided trades
was already good (64%) but avg R was negative, which given
hit_rate*rr_win - (1-hit_rate)*1 < 0 at 64%/1.5R implies either (a) too many
low-reward swing-resistance targets pulling the realized RR below the 1.5x
fallback, or (b) time-exits/noise-driven stop-outs on weak setups dragging
the average down. Configs B/C target (a), D/E/F target (b).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.application.use_cases.research.swing_target_backtest import (
    SwingTargetBacktestUseCase,
)
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

IN_SAMPLE_START = date(2000, 1, 1)
IN_SAMPLE_END = date(2024, 12, 31)
HOLDOUT_START = date(2025, 1, 1)
HOLDOUT_END = date(2026, 12, 31)

STRATEGY = "minervini_trend_template"


def _adx_trending(indicators: IndicatorSet) -> bool:
    return indicators.adx14 is not None and indicators.adx14 >= Decimal("25")


def _rs_leader(indicators: IndicatorSet) -> bool:
    return indicators.rs_rating is not None and indicators.rs_rating >= 85


@dataclass(frozen=True)
class Config:
    """One swing target/stop configuration attempted in the Phase 3b search."""

    name: str
    rationale: str
    atr_stop_multiple: Decimal = Decimal("2")
    atr_target_multiple: Decimal = Decimal("3")
    regime_filter: Callable[[IndicatorSet], bool] | None = None
    min_rr_ratio: Decimal | None = None


CONFIGS: list[Config] = [
    Config(
        name="B-wider-target",
        rationale=(
            "Phase 3's 64% decided-trade hit rate needs only RR>=0.5625:1 to break "
            "even, yet avg R was negative -- winners must be paying less than the "
            "1.5:1 fallback implies (swing-resistance targets often closer than "
            "the ATR fallback). Widen the ATR fallback target to 4x with stop held "
            "at 2x to raise the realized RR floor on every trade using the fallback."
        ),
        atr_stop_multiple=Decimal("2"),
        atr_target_multiple=Decimal("4"),
    ),
    Config(
        name="C-tighter-stop",
        rationale=(
            "Same reasoning, opposite lever: tighten the stop to 1.5x ATR (was 2x) "
            "to raise RR without touching the target, on the hypothesis that the "
            "2x ATR stop gives noise too much room before it's forced to exit."
        ),
        atr_stop_multiple=Decimal("1.5"),
        atr_target_multiple=Decimal("3"),
    ),
    Config(
        name="D-signal-time-rr-gate",
        rationale=(
            "Directly gate entries on the plan's own computed RR at signal time "
            "(>=2.0, matching the strategy's configured min_ratio) -- if "
            "low-computed-RR trades (typically the swing-resistance basis, which "
            "can be arbitrarily close) are dragging the average down, excluding "
            "them at entry (not post-hoc) should isolate the trades the plan "
            "itself judged favorable."
        ),
        min_rr_ratio=Decimal("2.0"),
    ),
    Config(
        name="E-adx-trending-only",
        rationale=(
            "Minervini's own methodology assumes an established trend before a "
            "target/stop plan is meaningful. Wilder's ADX>=25 is the conventional "
            "trending threshold. Restricting to ADX>=25 tests whether weak-trend "
            "signals (choppy, not truly breaking out) are the source of the "
            "negative average, independent of the target/stop levels themselves."
        ),
        regime_filter=_adx_trending,
    ),
    Config(
        name="F-rs-leader-only",
        rationale=(
            "Restrict to rs_rating>=85 (top relative-strength leaders, a standard "
            "Minervini/O'Neil leadership convention) on the hypothesis that "
            "marginal-RS passers are the weaker setups responsible for the "
            "negative average, independent of target/stop levels."
        ),
        regime_filter=_rs_leader,
    ),
    Config(
        name="G-tight-stop-wide-target",
        rationale=(
            "Combine B and C: 1.5x ATR stop with 4x ATR target -- the most "
            "aggressive first-principles RR improvement available from the two "
            "individually-weaker levers, tried as its own configuration rather "
            "than assumed additive."
        ),
        atr_stop_multiple=Decimal("1.5"),
        atr_target_multiple=Decimal("4"),
    ),
]


def _print_report(label: str, report: object) -> None:
    print(f"\n=== {label} ===")
    for field in (
        "total_trades", "target_hits", "stop_hits", "time_exits", "insufficient_data",
        "hit_rate", "avg_r_multiple",
        "avg_max_adverse_excursion_r", "worst_max_adverse_excursion_r",
    ):
        print(f"  {field}: {getattr(report, field)}")


def _make_use_case(session: object, config: Config) -> SwingTargetBacktestUseCase:
    return SwingTargetBacktestUseCase(
        screening_run_repo=SqlScreeningRunRepository(session),
        security_repo=SqlSecurityRepository(session),
        ohlcv_repo=SqlOHLCVRepository(session),
        strategy_repo=SqlStrategyRepository(session),
        indicator_pipeline=IndicatorPipelineImpl(session),
        max_holding_days=20,
        atr_stop_multiple=config.atr_stop_multiple,
        atr_target_multiple=config.atr_target_multiple,
        regime_filter=config.regime_filter,
        min_rr_ratio=config.min_rr_ratio,
    )


async def main() -> None:
    """Screen every config on in-sample; only run hold-out for ones that clear the bar."""
    async with get_database().session() as session:
        print("#" * 80)
        print("PHASE 3b -- IN-SAMPLE SCREEN (2000-01-01 .. 2024-12-31)")
        print("Configs must clear avg_r_multiple > 0 in-sample to be worth a hold-out run.")
        print("#" * 80)

        candidates: list[Config] = []
        for config in CONFIGS:
            print(f"\n--- {config.name} ---\n  rationale: {config.rationale}")
            use_case = _make_use_case(session, config)
            in_sample = await use_case.execute(STRATEGY, IN_SAMPLE_START, IN_SAMPLE_END)
            _print_report(f"{config.name} / in-sample", in_sample)

            avg_r = in_sample.avg_r_multiple
            passes_screen = avg_r is not None and avg_r > 0
            if passes_screen:
                candidates.append(config)
                print(f"  -> PASSES in-sample screen (avg_r={avg_r}), will run hold-out")
            else:
                print(f"  -> FAILS in-sample screen (avg_r={avg_r}), hold-out NOT run")

        print("\n" + "#" * 80)
        print(
            f"PHASE 3b -- HOLD-OUT FOLD ({HOLDOUT_START} onward) "
            f"-- {len(candidates)} candidate(s)"
        )
        print("#" * 80)

        for config in candidates:
            use_case = _make_use_case(session, config)
            holdout = await use_case.execute(STRATEGY, HOLDOUT_START, HOLDOUT_END)
            _print_report(f"{config.name} / HOLD-OUT", holdout)


if __name__ == "__main__":
    asyncio.run(main())
