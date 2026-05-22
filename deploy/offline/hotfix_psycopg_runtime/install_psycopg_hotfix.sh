#!/usr/bin/env bash
set -euo pipefail

HOTFIX_DIR="$(cd "$(dirname "$0")" && pwd)"
RELEASE_DIR="${1:-/data/work_flow/current}"
PYTHON_EXE="$RELEASE_DIR/runtime/python/bin/python3.10"
PACKAGES_DIR="$HOTFIX_DIR/packages"

if [[ "$(id -u)" != "0" ]]; then
  echo "请使用 root 执行：sudo bash install_psycopg_hotfix.sh $RELEASE_DIR" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_EXE" ]]; then
  echo "未找到项目内置 Python：$PYTHON_EXE" >&2
  echo "请把项目真实目录作为第一个参数传入，例如：sudo bash install_psycopg_hotfix.sh /data/work_flow/current" >&2
  exit 1
fi

if [[ ! -d "$PACKAGES_DIR" ]]; then
  echo "未找到补丁依赖目录：$PACKAGES_DIR" >&2
  exit 1
fi

echo "[1/3] 安装 PostgreSQL Python 驱动 psycopg"
"$PYTHON_EXE" -m pip install --no-index --find-links "$PACKAGES_DIR" "psycopg[binary]==3.2.3"

echo "[2/3] 校验运行时依赖"
"$PYTHON_EXE" - <<'PY'
import psycopg
print("psycopg import ok:", psycopg.__version__)
PY

echo "[3/3] 完成"
echo "现在可以重启应用容器："
echo "  cd /data/podman/podman_rhel7_offline"
echo "  sudo bash stop_project.sh"
echo "  REAL_DIR=\$(readlink -f /data/work_flow/current)"
echo "  sudo APP_PORT=18849 POSTGRES_PASSWORD='你的数据库密码' bash run_project.sh \"\$REAL_DIR\""
