#!/usr/bin/env bash
set -euo pipefail

STATE="${REPOMESH_VERIFY_STATE:?set REPOMESH_VERIFY_STATE}"

if [[ -f "$STATE/web.pid" ]]; then
  PID="$(cat "$STATE/web.pid")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    for _ in $(seq 1 30); do
      if ! kill -0 "$PID" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$PID" 2>/dev/null; then
      kill -9 "$PID" || true
    fi
  fi
fi

rm -rf "$STATE"
echo "cleaned state; evidence left in ${REPOMESH_VERIFY_EVIDENCE:-unset}"
