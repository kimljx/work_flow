#!/usr/bin/env bash
set -euo pipefail

NEW_ROOT="$(cd "$(dirname "$0")" && pwd)"
OLD_ROOT="${1:-}"

if [[ -z "$OLD_ROOT" ]]; then
  read -r -p "请输入旧版发布包目录完整路径：" OLD_ROOT
fi

if [[ -z "$OLD_ROOT" ]]; then
  echo "未输入旧版发布包目录，已取消升级。"
  exit 1
fi

if [[ ! -f "$OLD_ROOT/backup_data.sh" ]]; then
  echo "旧版目录无效，未找到 backup_data.sh。"
  exit 1
fi

if [[ ! -f "$OLD_ROOT/stop_system.sh" ]]; then
  echo "旧版目录无效，未找到 stop_system.sh。"
  exit 1
fi

echo
echo "[1/6] 停止旧版服务"
bash "$OLD_ROOT/stop_system.sh" || true

echo "[2/6] 备份旧版数据"
bash "$OLD_ROOT/backup_data.sh"

LATEST_BACKUP="$(find "$OLD_ROOT/backup" -mindepth 1 -maxdepth 1 -type d ! -name '_restore_guard_*' -printf '%f\n' | sort -r | head -n 1)"
if [[ -z "$LATEST_BACKUP" ]]; then
  echo "未找到旧版备份目录，升级已中止。"
  exit 1
fi

echo "[3/6] 初始化新版环境"
bash "$NEW_ROOT/install_offline.sh" <<'EOF'

EOF

echo "[4/6] 复制备份数据到新版目录"
mkdir -p "$NEW_ROOT/backup"
cp -R "$OLD_ROOT/backup/$LATEST_BACKUP" "$NEW_ROOT/backup/$LATEST_BACKUP"

echo "[5/6] 恢复备份到新版"
printf 'YES\n' | bash "$NEW_ROOT/restore_data.sh" "$LATEST_BACKUP"

echo "[6/6] 启动新版服务"
bash "$NEW_ROOT/start_system.sh"

echo
echo "升级完成。"
echo "已从旧版目录导入备份批次：$LATEST_BACKUP"
