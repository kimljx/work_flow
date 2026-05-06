#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/local/run/uvicorn.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "未找到运行中的服务 PID 文件。"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi
  echo "已停止工作流系统服务，PID: $PID"
else
  echo "PID 文件存在，但服务已不在运行。"
fi

rm -f "$PID_FILE"
