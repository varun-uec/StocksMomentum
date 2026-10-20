#!/usr/bin/env bash
# Disposable, labelled PostgreSQL for tests and audits, sized to share an 8 GB
# Docker VM with the development stack.
#
#   scripts/test-infra.sh up NAME PORT [MEMORY_MB] [DB_NAME]
#   scripts/test-infra.sh down NAME
#   scripts/test-infra.sh list
#   scripts/test-infra.sh free
#
# Rules it enforces:
# - data lives on a named volume (disk), never tmpfs: tmpfs is VM RAM;
# - the container has a hard memory cap, and shared_buffers is 1/4 of it;
# - it refuses to start when the VM's free memory is below the cap plus
#   MIN_FREE_MB (default 1024) of headroom for the running stack;
# - it binds 127.0.0.1 only and only touches containers it labelled.
set -euo pipefail

LABEL="wickstreet.test-infra=true"
MIN_FREE_MB="${MIN_FREE_MB:-1024}"
IMAGE="${IMAGE:-postgres:16-alpine}"

die() { echo "test-infra: $*" >&2; exit 1; }

to_mb() {  # "242.1MiB" / "1.5GiB" / "512kB" -> MB (integer)
  awk -v v="$1" 'BEGIN {
    n = v + 0; u = v; gsub(/[0-9.]/, "", u)
    if (u ~ /^G/) n *= 1024; else if (u ~ /^[kK]/) n /= 1024; else if (u ~ /^B$/) n /= 1048576
    printf "%d", n }'
}

free_mb() {
  local total used=0 m
  total=$(( $(docker info --format '{{.MemTotal}}') / 1048576 ))
  while read -r m; do
    [ -n "$m" ] && used=$(( used + $(to_mb "$m") ))
  done < <(docker stats --no-stream --format '{{.MemUsage}}' | awk -F' / ' '{print $1}')
  echo $(( total - used ))
}

cmd_up() {
  local name="${1:?NAME}" port="${2:?PORT}" mem="${3:-2048}" db="${4:-momentum25_test}"
  [[ "$port" =~ ^[0-9]+$ ]] || die "PORT must be a number"
  if docker container inspect "$name" >/dev/null 2>&1; then
    die "container $name already exists (scripts/test-infra.sh down $name first)"
  fi
  local free; free=$(free_mb)
  if (( free < mem + MIN_FREE_MB )); then
    die "Docker VM has ${free} MB free; need ${mem} MB plus ${MIN_FREE_MB} MB headroom. Stop something first."
  fi
  docker volume create --label "$LABEL" "${name}-data" >/dev/null
  docker run -d --name "$name" --label "$LABEL" \
    --memory "${mem}m" --memory-swap "${mem}m" --shm-size 256m \
    -p "127.0.0.1:${port}:5432" \
    -e POSTGRES_USER=momentum25 -e POSTGRES_PASSWORD=momentum25 -e POSTGRES_DB="$db" \
    -v "${name}-data:/var/lib/postgresql/data" \
    "$IMAGE" -c "shared_buffers=$(( mem / 4 ))MB" -c "effective_cache_size=$(( mem / 2 ))MB" >/dev/null
  for _ in $(seq 1 30); do
    docker exec "$name" pg_isready -U momentum25 -d "$db" >/dev/null 2>&1 && break
    sleep 1
  done
  docker exec "$name" pg_isready -U momentum25 -d "$db" >/dev/null || die "$name did not become ready"
  echo "postgresql+asyncpg://momentum25:momentum25@127.0.0.1:${port}/${db}"
}

cmd_down() {
  local name="${1:?NAME}"
  [ "$(docker container inspect -f '{{index .Config.Labels "wickstreet.test-infra"}}' "$name" 2>/dev/null)" = "true" ] \
    || die "$name is not a test-infra container; refusing to remove it"
  docker rm -f "$name" >/dev/null
  docker volume rm "${name}-data" >/dev/null 2>&1 || true
  echo "removed $name and ${name}-data"
}

case "${1:-}" in
  up) shift; cmd_up "$@" ;;
  down) shift; cmd_down "$@" ;;
  list) docker ps -a --filter "label=$LABEL" --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' ;;
  free) echo "$(free_mb) MB free in the Docker VM" ;;
  *) sed -n '2,17p' "$0"; exit 2 ;;
esac
