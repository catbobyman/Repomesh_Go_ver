#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

STATE="${REPOMESH_VERIFY_STATE:?set REPOMESH_VERIFY_STATE}"
EVIDENCE="${REPOMESH_VERIFY_EVIDENCE:?set REPOMESH_VERIFY_EVIDENCE}"
ADDR="${REPOMESH_VERIFY_ADDR:-127.0.0.1:18080}"
ASSETS="${REPOMESH_WEB_ASSETS:-$ROOT/web/dist}"

mkdir -p "$STATE" "$EVIDENCE"

if [[ -e "$STATE/web.pid" ]] && kill -0 "$(cat "$STATE/web.pid")" 2>/dev/null; then
  echo "already running pid=$(cat "$STATE/web.pid")" >&2
  exit 1
fi

if [[ ! -f "$ASSETS/index.html" ]]; then
  npm --prefix "$ROOT/web" ci
  npm --prefix "$ROOT/web" run build
fi

BIN="$STATE/repomesh-web"
go build -o "$BIN" ./cmd/repomesh-web

LOG="$STATE/web.stderr.log"
: >"$LOG"

"$BIN" --addr "$ADDR" --assets "$ASSETS" --auth-config= \
  >"$STATE/web.stdout.log" 2>"$LOG" &
echo $! >"$STATE/web.pid"

ORIGIN="http://$ADDR"
for _ in $(seq 1 150); do
  if curl -sf "$ORIGIN/healthz" >/dev/null; then
    printf '%s\n' "$ORIGIN" >"$STATE/origin"
    printf 'unconfigured\n' >"$STATE/mode"
    echo "ready origin=$ORIGIN"
    exit 0
  fi
  if ! kill -0 "$(cat "$STATE/web.pid")" 2>/dev/null; then
    echo "web exited before ready" >&2
    cat "$LOG" >&2 || true
    exit 1
  fi
  sleep 0.2
done

echo "web did not become ready" >&2
exit 1
