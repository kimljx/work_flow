#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/work_flow"
APP_ROOT="$ROOT/app"
LOCAL_ROOT="$ROOT/local"
PYTHON_EXE="${PYTHON_EXE:-python3}"

export PYTHONUTF8=1
export PYTHONPYCACHEPREFIX="$LOCAL_ROOT/cache/pycache"
export PYTHONUSERBASE="$LOCAL_ROOT/home"
export PIP_CACHE_DIR="$LOCAL_ROOT/cache/pip"
export TMPDIR="$LOCAL_ROOT/temp"
export HOME="$LOCAL_ROOT/home"
export XDG_CACHE_HOME="$LOCAL_ROOT/cache"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"
export PLAYWRIGHT_SKIP_BROWSER_GC=1

mkdir -p "$LOCAL_ROOT/home" "$LOCAL_ROOT/temp" "$LOCAL_ROOT/cache" "$LOCAL_ROOT/logs" "$LOCAL_ROOT/run"

if ! command -v "$PYTHON_EXE" >/dev/null 2>&1; then
  echo "Python runtime not found: $PYTHON_EXE" >&2
  exit 1
fi

exec "$PYTHON_EXE" -m uvicorn app.main:app   --app-dir "$APP_ROOT/backend"   --host 0.0.0.0   --port "${APP_PORT:-18849}"
