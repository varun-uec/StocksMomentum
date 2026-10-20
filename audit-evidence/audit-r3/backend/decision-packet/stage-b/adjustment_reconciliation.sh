#!/bin/sh
# Read-only: the session sets default_transaction_read_only=on, so no statement
# can write. Prints to stdout.
set -e
cd "$(dirname "$0")"
docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' momentum25-db-1 \
  psql -U momentum25 -d momentum25 -v ON_ERROR_STOP=1 < adjustment_reconciliation.sql
