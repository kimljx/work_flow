#!/usr/bin/env bash
set -euo pipefail

RELEASE_DIR="${1:-/data/work_flow/current}"
APP_BACKEND="$RELEASE_DIR/app/backend/app"
HOTFIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$RELEASE_DIR/local/backup/hotfix_db_settings_read_$TS"

if [[ ! -d "$APP_BACKEND" ]]; then
  echo "未找到项目后端目录：$APP_BACKEND"
  echo "请确认参数是否为当前项目发布目录，例如：bash install_db_settings_read_hotfix.sh /data/work_flow/current"
  exit 1
fi

echo "[1/4] 备份当前后端文件到：$BACKUP_DIR"
mkdir -p "$BACKUP_DIR/services"
cp -a "$APP_BACKEND/config.py" "$BACKUP_DIR/config.py"
cp -a "$APP_BACKEND/api.py" "$BACKUP_DIR/api.py"
cp -a "$APP_BACKEND/services/qax.py" "$BACKUP_DIR/services/qax.py"

echo "[2/4] 覆盖数据库配置读取修复文件"
cp -a "$HOTFIX_DIR/backend/app/config.py" "$APP_BACKEND/config.py"
cp -a "$HOTFIX_DIR/backend/app/api.py" "$APP_BACKEND/api.py"
cp -a "$HOTFIX_DIR/backend/app/services/qax.py" "$APP_BACKEND/services/qax.py"

PYTHON_BIN="$RELEASE_DIR/runtime/python/bin/python3.10"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

echo "[3/4] 校验 Python 文件语法"
"$PYTHON_BIN" -m py_compile \
  "$APP_BACKEND/config.py" \
  "$APP_BACKEND/api.py" \
  "$APP_BACKEND/services/qax.py"

echo "[4/4] 修复完成"
echo "请重启应用容器让修复生效："
echo "  podman restart work-flow"
echo
echo "如果需要回滚，可执行："
echo "  cp -a \"$BACKUP_DIR/config.py\" \"$APP_BACKEND/config.py\""
echo "  cp -a \"$BACKUP_DIR/api.py\" \"$APP_BACKEND/api.py\""
echo "  cp -a \"$BACKUP_DIR/services/qax.py\" \"$APP_BACKEND/services/qax.py\""
echo "  podman restart work-flow"
