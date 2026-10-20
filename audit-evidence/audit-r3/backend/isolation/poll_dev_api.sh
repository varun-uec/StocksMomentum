#!/usr/bin/env bash
# Poll the owner's dev API and container state every 2 s until STOP file exists.
# Read-only: GET /health/ready and docker inspect.
out="$1"; stop="$2"
echo "utc_time http_status latency_s container_status oom_killed restart_count started_at" > "$out"
while [ ! -f "$stop" ]; do
  t=$(date -u +%H:%M:%S)
  r=$(curl -s -o /dev/null -m 5 -w "%{http_code} %{time_total}" http://localhost:8000/api/v1/health/ready || echo "000 5")
  s=$(docker inspect momentum25-api-1 --format '{{.State.Status}} {{.State.OOMKilled}} {{.RestartCount}} {{.State.StartedAt}}')
  echo "$t $r $s" >> "$out"
  sleep 2
done
