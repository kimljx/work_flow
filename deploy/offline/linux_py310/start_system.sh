#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$ROOT/app"
PYTHON_EXE="$ROOT/runtime/python/bin/python3.10"
INSTALL_SCRIPT="$ROOT/tools/install_offline.py"
PLAYWRIGHT_BROWSER_ROOT="$ROOT/runtime/ms-playwright"
LOCAL_ROOT="$ROOT/local"
LOCAL_HOME="$LOCAL_ROOT/home"
LOCAL_TMP="$LOCAL_ROOT/temp"
LOCAL_CACHE="$LOCAL_ROOT/cache"
LOCAL_PY_CACHE="$LOCAL_CACHE/pycache"
LOCAL_LOGS="$LOCAL_ROOT/logs"
LOCAL_RUN="$LOCAL_ROOT/run"
PID_FILE="$LOCAL_RUN/uvicorn.pid"
LOG_FILE="$LOCAL_LOGS/server.log"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "未找到内置 Python 运行时，请重新生成 Linux 离线发布包。"
  exit 1
fi

if [[ ! -f "$INSTALL_SCRIPT" ]]; then
  echo "未找到离线安装脚本，请重新生成 Linux 离线发布包。"
  exit 1
fi

if [[ ! -d "$PLAYWRIGHT_BROWSER_ROOT" ]]; then
  echo "未找到内置 Playwright 浏览器目录，请重新生成 Linux 离线发布包。"
  exit 1
fi

echo "正在检查本地运行环境..."
"$PYTHON_EXE" "$INSTALL_SCRIPT" --silent

mkdir -p "$LOCAL_LOGS" "$LOCAL_RUN"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "系统已在运行，PID: $(cat "$PID_FILE")"
  exit 0
fi

echo "正在启动工作流系统服务..."
(
  cd "$APP_ROOT"
  export PYTHONUTF8=1
  export PYTHONPYCACHEPREFIX="$LOCAL_PY_CACHE"
  export PYTHONUSERBASE="$LOCAL_HOME"
  export TMPDIR="$LOCAL_TMP"
  export HOME="$LOCAL_HOME"
  export XDG_CACHE_HOME="$LOCAL_CACHE"
  export PLAYWRIGHT_BROWSERS_PATH="$PLAYWRIGHT_BROWSER_ROOT"
  export PLAYWRIGHT_SKIP_BROWSER_GC=1
  nohup "$PYTHON_EXE" -m uvicorn app.main:app --app-dir "$APP_ROOT/backend" --host 0.0.0.0 --port 8000 >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
)

sleep 2
echo "已启动，访问地址：http://127.0.0.1:8000/"
echo "运行日志：$LOG_FILE"
