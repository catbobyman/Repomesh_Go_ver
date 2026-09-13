#!/usr/bin/env bash
# Per-boot reconciliation for RepoMesh. Starts the loopback PostgreSQL 17
# dev cluster and ensures the dev database exists. Tolerates restarts,
# avoids duplicate servers, checks readiness, then returns.
set -euo pipefail

PG_MAJOR=17
PG_BIN="/usr/lib/postgresql/${PG_MAJOR}/bin"
PG_ROOT="${HOME}/repomesh-pg"
PG_DATA="${PG_ROOT}/data"

if [ ! -s "${PG_DATA}/PG_VERSION" ]; then
  echo "PostgreSQL data directory missing; run install.sh first." >&2
  exit 1
fi

echo "==> Starting PostgreSQL ${PG_MAJOR}"
if "${PG_BIN}/pg_ctl" -D "${PG_DATA}" status >/dev/null 2>&1; then
  echo "    Already running"
else
  "${PG_BIN}/pg_ctl" -D "${PG_DATA}" -l "${PG_ROOT}/server.log" -w -t 30 start
fi

# Wait for readiness.
for _ in $(seq 1 30); do
  if "${PG_BIN}/pg_isready" -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
"${PG_BIN}/pg_isready" -h 127.0.0.1 -p 5432

echo "==> Ensuring dev database exists"
if ! "${PG_BIN}/psql" -h "${PG_ROOT}" -p 5432 -U ubuntu -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='repomesh_dev'" | grep -q 1; then
  "${PG_BIN}/psql" -h "${PG_ROOT}" -p 5432 -U ubuntu -d postgres \
    -c "CREATE DATABASE repomesh_dev OWNER ubuntu"
fi

echo "==> PostgreSQL ready on 127.0.0.1:5432 (database: repomesh_dev)."
echo "    The loopback dev connection string is stored at:"
echo "      ${PG_ROOT}/connection-url.txt"
echo "    Export it for integration tests / db commands, e.g.:"
echo "      export REPOMESH_TEST_DATABASE_URL=\"\$(cat ${PG_ROOT}/connection-url.txt)\""
echo "      export REPOMESH_DATABASE_URL=\"\$(cat ${PG_ROOT}/connection-url.txt)\""
echo "==> start.sh complete"
