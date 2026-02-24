#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

python -c "from src.crew import run; result = run(); print(result)"
