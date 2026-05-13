#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_EXE="$ROOT/runtime/python/bin/python3.10"

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "未找到离线包内置 Python 运行时，请确认当前目录是完整的 Linux 离线包。"
  exit 1
fi

"$PYTHON_EXE" "$ROOT/tools/install_offline.py"
