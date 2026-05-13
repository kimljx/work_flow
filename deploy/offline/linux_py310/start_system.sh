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
APP_PORT="18849"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "未找到包内 Python 运行时，请确认这是完整的 Linux 离线绿色包。"
  exit 1
fi

if [[ ! -f "$INSTALL_SCRIPT" ]]; then
  echo "未找到离线安装检查脚本，请确认这是完整的 Linux 离线绿色包。"
  exit 1
fi

if [[ ! -d "$PLAYWRIGHT_BROWSER_ROOT" ]]; then
  echo "未找到 Playwright 浏览器目录，请确认这是完整的 Linux 离线绿色包。"
  exit 1
fi

echo "正在执行启动前检查..."
"$PYTHON_EXE" "$INSTALL_SCRIPT" --silent

mkdir -p "$LOCAL_LOGS" "$LOCAL_RUN"
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "服务已在运行，PID: $(cat "$PID_FILE")"
  exit 0
fi

echo "正在启动服务..."
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
  nohup "$PYTHON_EXE" -m uvicorn app.main:app --app-dir "$APP_ROOT/backend" --host 0.0.0.0 --port "$APP_PORT" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
)

sleep 2
echo "已启动，访问地址：http://127.0.0.1:$APP_PORT/"
echo "日志文件：$LOG_FILE"
