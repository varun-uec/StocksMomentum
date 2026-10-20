#!/bin/sh
# Screen the restored audit copy N times with the production CLI, hash every
# stored output, then delete that run so the next one recomputes from scratch.
# Runs only against the labelled round3 container (port 65450); never the dev DB.
set -eu
N=${1:-5}; STRAT=${2:-minervini_trend_template}; OUT=$(cd "$(dirname "$0")" && pwd)
DB=postgresql+asyncpg://momentum25:audit@127.0.0.1:65450/momentum25_audit
q() { docker exec r3-audit-pg psql -U momentum25 -d momentum25_audit -At -F '|' -c "$1"; }
export_run() {
  q "select s.symbol,r.rank,r.momentum_score,r.buy_setup_score,r.hard_filters_passed from screening_results r join securities s on s.id=r.security_id where run_id=$1 order by s.symbol" > "$OUT/$2.results"
  q "select s.symbol,engine_id,rule_id,passed,raw_value,threshold,operator,weight,contribution,explanation from rule_results r join securities s on s.id=r.security_id where run_id=$1 order by s.symbol,engine_id,rule_id" > "$OUT/$2.rules"
  q "select s.symbol,eligible,coalesce(reason,'') from universe_membership u join securities s on s.id=u.security_id where run_id=$1 order by s.symbol" > "$OUT/$2.universe"
  q "select run_date,data_version,config_hash,status from screening_runs where id=$1" > "$OUT/$2.identity"
}
export_run 149 baseline_run149
cd "$OUT/../../../../backend"
i=1
while [ "$i" -le "$N" ]; do
  t0=$(python3 -c 'import time;print(time.time())')
  M25_DATABASE_URL=$DB M25_REDIS_URL=redis://127.0.0.1:65451/0 M25_SCHEDULER_ENABLED=false \
    .venv/bin/momentum25 screen --strategy "$STRAT" > "$OUT/cli_$i.log" 2>&1
  t1=$(python3 -c 'import time;print(time.time())')
  id=$(grep -o 'run [0-9]*' "$OUT/cli_$i.log" | tail -1 | cut -d' ' -f2)
  dur=$(q "select stats->>'duration_seconds' from screening_runs where id=$id")
  echo "iter=$i run=$id wall_s=$(python3 -c "print(round($t1-$t0,2))") pipeline_s=$dur" | tee -a "$OUT/timings.txt"
  export_run "$id" "iter$i"
  q "delete from rule_results where run_id=$id; delete from screening_results where run_id=$id; delete from universe_membership where run_id=$id; delete from screening_runs where id=$id" >/dev/null
  i=$((i+1))
done
cd "$OUT" && shasum -a 256 *.results *.rules *.universe > hashes.txt
