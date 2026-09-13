#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for RepoMesh.
# Prepares durable, source-derived state after checkout: PostgreSQL 17,
# Go modules, and the built frontend. Safe to run repeatedly. Per-boot
# service startup lives in start.sh, not here.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PG_MAJOR=17
PG_BIN="/usr/lib/postgresql/${PG_MAJOR}/bin"
PG_ROOT="${HOME}/repomesh-pg"
PG_DATA="${PG_ROOT}/data"

echo "==> Installing PostgreSQL ${PG_MAJOR} (idempotent)"
if [ ! -x "${PG_BIN}/postgres" ]; then
  sudo install -d /usr/share/postgresql-common/pgdg
  sudo curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
  . /etc/os-release
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
    | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    "postgresql-${PG_MAJOR}" "postgresql-client-${PG_MAJOR}"
else
  echo "    PostgreSQL ${PG_MAJOR} already present"
fi
"${PG_BIN}/postgres" --version

echo "==> Initializing loopback dev cluster (idempotent)"
mkdir -p "${PG_ROOT}"
if [ ! -s "${PG_DATA}/PG_VERSION" ]; then
  if [ ! -s "${PG_ROOT}/password" ]; then
    openssl rand -hex 24 > "${PG_ROOT}/password"
    chmod 600 "${PG_ROOT}/password"
  fi
  PW_FILE="${PG_ROOT}/pw.txt"
  cp "${PG_ROOT}/password" "${PW_FILE}"
  # Loopback TCP requires a password (scram) so credential-enforcement tests
  # pass; the local unix socket stays trust for maintenance commands.
  "${PG_BIN}/initdb" -D "${PG_DATA}" -U ubuntu --pwfile="${PW_FILE}" \
    --auth-host=scram-sha-256 --auth-local=trust \
    --encoding=UTF8 --locale=C.UTF-8 >/dev/null
  rm -f "${PW_FILE}"
  {
    echo "listen_addresses = '127.0.0.1'"
    echo "port = 5432"
    echo "unix_socket_directories = '${PG_ROOT}'"
    echo "password_encryption = 'scram-sha-256'"
  } >> "${PG_DATA}/postgresql.conf"
  echo "    Cluster initialized at ${PG_DATA}"
else
  echo "    Cluster already initialized at ${PG_DATA}"
fi

# Record the loopback dev connection string for tests and db commands.
DEV_PW="$(cat "${PG_ROOT}/password")"
printf 'postgres://ubuntu:%s@127.0.0.1:5432/repomesh_dev?sslmode=disable\n' "${DEV_PW}" \
  > "${PG_ROOT}/connection-url.txt"
chmod 600 "${PG_ROOT}/connection-url.txt"

echo "==> Downloading Go modules"
go mod download

echo "==> Installing frontend dependencies and building assets"
npm --prefix web ci
npm --prefix web run build

echo "==> install.sh complete"
