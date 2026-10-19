#!/usr/bin/env bash
set -euo pipefail

# A self-contained restart test on a new, named volume. It refuses any resource
# with the names below before it creates anything, uses only a *_e2e database,
# binds Postgres to loopback, and removes only the resources it created.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
container_name="${WICKSTREET_RESTART_E2E_CONTAINER:-wickstreet_release_restart_e2e}"
volume_name="${WICKSTREET_RESTART_E2E_VOLUME:-wickstreet_release_restart_e2e_data}"
database_name="wickstreet_persistent_e2e"
database_user="wickstreet_e2e"
database_password="synthetic_e2e_only"
database_port="${WICKSTREET_RESTART_E2E_PORT:-55483}"
database_url="postgresql+asyncpg://${database_user}:${database_password}@127.0.0.1:${database_port}/${database_name}"
created_container=0
created_volume=0

cleanup() {
  if [[ "${created_container}" == "1" ]]; then
    docker rm -f "${container_name}" >/dev/null
  fi
  if [[ "${created_volume}" == "1" ]]; then
    docker volume rm "${volume_name}" >/dev/null
  fi
}
trap cleanup EXIT

for command in docker npm python3; do
  command -v "${command}" >/dev/null || { echo "required command missing: ${command}" >&2; exit 2; }
done
if docker inspect "${container_name}" >/dev/null 2>&1; then
  echo "refusing to reuse existing container: ${container_name}" >&2
  exit 2
fi
if docker volume inspect "${volume_name}" >/dev/null 2>&1; then
  echo "refusing to reuse existing volume: ${volume_name}" >&2
  exit 2
fi
if ! python3 -c 'import socket, sys; s=socket.socket(); s.bind(("127.0.0.1", int(sys.argv[1]))); s.close()' "${database_port}"; then
  echo "refusing to bind occupied E2E port ${database_port}" >&2
  exit 2
fi

mkdir -p "${repo_root}/audit-evidence/benchmarks"
result_file="${WICKSTREET_RESTART_E2E_LOG:-${repo_root}/audit-evidence/benchmarks/release-hardening-e2e-confirmed.log}"
if [[ -e "${result_file}" ]]; then
  echo "refusing to overwrite existing evidence: ${result_file}" >&2
  exit 2
fi
docker volume create "${volume_name}" >/dev/null
created_volume=1
docker run -d --name "${container_name}" \
  -e "POSTGRES_DB=${database_name}" \
  -e "POSTGRES_USER=${database_user}" \
  -e "POSTGRES_PASSWORD=${database_password}" \
  -p "127.0.0.1:${database_port}:5432" \
  -v "${volume_name}:/var/lib/postgresql/data" postgres:16-alpine >/dev/null
created_container=1

for attempt in $(seq 1 60); do
  if docker exec "${container_name}" pg_isready -U "${database_user}" -d "${database_name}" >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "60" ]]; then
    echo "isolated persistence E2E database did not become ready" >&2
    exit 1
  fi
  sleep 1
done

cd "${repo_root}/web"
E2E_DATABASE_URL="${database_url}" npm run e2e -- \
  e2e/m13-charting.spec.ts \
  e2e/m14-studio.spec.ts \
  e2e/m15-alerts.spec.ts \
  e2e/m16-release-hardening.spec.ts 2>&1 | tee -a "${result_file}"
E2E_DATABASE_URL="${database_url}" "${repo_root}/backend/.venv/bin/python" \
  "${repo_root}/web/e2e/db.py" reset
E2E_DATABASE_URL="${database_url}" npm run e2e -- --grep "phase 1 writes" 2>&1 | tee -a "${result_file}"
docker restart "${container_name}" >/dev/null
for attempt in $(seq 1 60); do
  if docker exec "${container_name}" pg_isready -U "${database_user}" -d "${database_name}" >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "60" ]]; then
    echo "isolated persistence E2E database did not recover after restart" >&2
    exit 1
  fi
  sleep 1
done
E2E_DATABASE_URL="${database_url}" npm run e2e -- --grep "phase 2 recovers" 2>&1 | tee -a "${result_file}"
echo "Evidence written to ${result_file#${repo_root}/}"
