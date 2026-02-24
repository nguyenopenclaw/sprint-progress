#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE=".run_agent.pid"

cleanup() {
  if [ -f "$PID_FILE" ] && [ "$(cat "$PID_FILE")" = "$$" ]; then
    rm -f "$PID_FILE"
  fi
}

if [ -f "$PID_FILE" ]; then
  existing_pid="$(cat "$PID_FILE" || true)"
  if [ -n "${existing_pid:-}" ] && kill -0 "$existing_pid" 2>/dev/null; then
    echo "run_agent.sh is already running (PID: $existing_pid)."
    exit 1
  fi
  # Stale PID file from dead process.
  rm -f "$PID_FILE"
fi

echo "$$" > "$PID_FILE"
trap cleanup EXIT INT TERM

if [ -f ".venv/bin/activate" ]; then
  # Activate project virtualenv if present.
  source ".venv/bin/activate"
fi

if [ -f ".env" ]; then
  # Load environment variables from .env.
  set -a
  source ".env"
  set +a
fi

python -m src.crew
