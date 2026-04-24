#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=.
exec /mnt/c/Users/Johna/lumen-ai/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
