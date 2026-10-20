#!/bin/sh
# Read-only export used by every script here. Every session sets
# default_transaction_read_only=on, so no statement can write.
# Writes CSVs to ./data/ (not committed: they are copies of development data).
set -e
mkdir -p data/runs
q(){ docker exec -e PGOPTIONS='-c default_transaction_read_only=on' momentum25-db-1 \
  psql -U momentum25 -d momentum25 -v ON_ERROR_STOP=1 -c "\copy ($1) to stdout with csv header" > "$2"; }
q "select id,symbol,isin,exchange,listing_date,delisting_date,last_trade_date,is_active,termination_reason from securities" data/securities.csv
q "select security_id,date,open,high,low,close,volume,adj_factor,adj_close,turnover_value from ohlcv_daily where date >= '2023-10-01' order by security_id,date" data/ohlcv.csv
q "select index_code,date,close from benchmark_index_daily where index_code='NIFTY500'" data/bench.csv
q "select run_id,security_id,eligible,reason from universe_membership where run_id=149" data/um149.csv
q "select id,strategy_id,run_date,data_version,config_hash,status,trigger from screening_runs where id=149" data/run149.csv
q "select run_id,security_id,rule_id,engine_id,passed,raw_value,threshold,weight,contribution from rule_results where run_id=149" data/rr149.csv
q "select * from screening_results where run_id=149" data/sr149.csv
q "select r.run_id, r.security_id, r.momentum_score, r.buy_setup_score, r.rank, s.symbol, (select raw_value from rule_results x where x.run_id=r.run_id and x.security_id=r.security_id and x.rule_id='tt_rs_rating_min') rs from screening_results r join securities s on s.id=r.security_id where r.hard_filters_passed" data/sr_all_passing.csv
q "select r.id,r.strategy_id,s.name,r.run_date,r.status,r.trigger,r.data_version from screening_runs r join strategies s on s.id=r.strategy_id order by r.id" data/runs.csv
q "select security_id,date,close,adj_close from (select security_id,date,close,adj_close,row_number() over (partition by security_id order by date desc) rn from ohlcv_daily where date <= '2026-10-19') t where rn <= 257 order by security_id,date" data/rs_bars.csv
for pair in 14:2020-11-27 88:2021-08-31 98:2022-06-30 43:2023-04-28 117:2024-01-31 62:2024-11-29 72:2025-09-30; do
  id=${pair%%:*}; d=${pair#*:}
  q "select run_id,security_id,rule_id,engine_id,passed,raw_value,threshold,weight,contribution from rule_results where run_id=$id" data/runs/rr$id.csv
  q "select run_id,security_id,eligible,reason from universe_membership where run_id=$id" data/runs/um$id.csv
  q "select * from screening_results where run_id=$id" data/runs/sr$id.csv
  q "select security_id,date,close,adj_close from (select security_id,date,close,adj_close,row_number() over (partition by security_id order by date desc) rn from ohlcv_daily where date <= '$d') t where rn <= 257 order by security_id,date" data/runs/bars$id.csv
done
# Run order (backend venv python, PYTHONPATH not needed: momentum25 is installed):
#   reproduce.py wf_repro.json   -> must print sha256 8da9853e...ef5 (= walkforward/wf_1.json)
#   compare.py NSE | compare.py NSE fresh | compare.py NSE,BOTH | compare.py NSE,BOTH fresh
#   headline.py, attrib.py, trace.py 3PLAND ABMINTLLTD LEXUS, stuck.py, liquidity.py
#   r3b10.py, r3b10_multi.py, r3b10_optc.py

# ---- Stage A additions ----
q "select security_id,date,open,high,low,close,volume,adj_factor,adj_close,turnover_value from ohlcv_daily order by security_id,date" data/ohlcv_full.csv
mkdir -p data/is
ids="79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,96,97,98"   # In-Sample runs, one per month-end, 2020-11-27..2022-06-30
q "select r.id, r.run_date from screening_runs r where id in ($ids)" data/is/runs.csv
q "select run_id,security_id,rule_id,engine_id,passed,raw_value,weight,contribution from rule_results where run_id in ($ids)" data/is/rr.csv
q "select run_id,security_id,eligible,reason from universe_membership where run_id in ($ids)" data/is/um.csv
q "select run_id,security_id,horizon_days,forward_return from forward_returns where run_id in ($ids)" data/is/fr.csv
# Stage A run order (from stage-a/, with ../data reachable as ./data): stageA.py, t1.py, stuckA.py, rs_ref.py, rs_align.py, gaps_top25.py
