#!/usr/bin/env zsh
set -euo pipefail

ROOT_DIR="${0:A:h}"
cd "$ROOT_DIR"

if [[ ! -f "backend/database_seeder.py" || ! -f "backend/app.py" ]]; then
  echo "Run this script from the project root: $ROOT_DIR"
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Project environment not found. Create it with: python3 -m venv .venv"
  echo "Then install dependencies with: .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

"$ROOT_DIR/.venv/bin/python" backend/database_seeder.py
exec "$ROOT_DIR/.venv/bin/python" backend/app.py