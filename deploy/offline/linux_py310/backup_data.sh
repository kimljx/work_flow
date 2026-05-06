#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_EXE="$ROOT/runtime/python/bin/python3.10"

"$PYTHON_EXE" "$ROOT/tools/backup_data.py"
