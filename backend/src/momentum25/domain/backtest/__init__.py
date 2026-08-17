"""Multi-timeframe momentum backtest — signal, eligibility, ranking, and rebalance.

Pure domain logic implementing the strategy defined in
``handoff/brief.md`` ("Multi-Timeframe Momentum, 3/6/12M, Monthly Rebalance").
No I/O: callers supply price series and eligibility facts; nothing here reads
a database, a clock, or a file.
"""
