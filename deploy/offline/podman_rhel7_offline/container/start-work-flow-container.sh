#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/work_flow"
APP_ROOT="$ROOT/app"
LOCAL_ROOT="$ROOT/local"
PYTHON_EXE="$ROOT/runtime/python/bin/python3.10"

export PYTHONUTF8=1
export PYTHONPYCACHEPREFIX="$LOCAL_ROOT/cache/pycache"
export PYTHONUSERBASE="$LOCAL_ROOT/home"
export PIP_CACHE_DIR="$LOCAL_ROOT/cache/pip"
export TMPDIR="$LOCAL_ROOT/temp"
export HOME="$LOCAL_ROOT/home"
export XDG_CACHE_HOME="$LOCAL_ROOT/cache"
export PLAYWRIGHT_BROWSERS_PATH="$ROOT/runtime/ms-playwright"
export PLAYWRIGHT_SKIP_BROWSER_GC=1

mkdir -p "$LOCAL_ROOT/home" "$LOCAL_ROOT/temp" "$LOCAL_ROOT/cache" "$LOCAL_ROOT/logs" "$LOCAL_ROOT/run"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "未找到离线包 Python：$PYTHON_EXE" >&2
  exit 1
fi

"$PYTHON_EXE" "$ROOT/tools/install_offline.py" --silent

exec "$PYTHON_EXE" -m uvicorn app.main:app \
  --app-dir "$APP_ROOT/backend" \
  --host 0.0.0.0 \
  --port "${APP_PORT:-18849}"
