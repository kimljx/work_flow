#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RPM_DIR="$ROOT/rpms"
HOST_RPM_LIST="$ROOT/host-rpms.txt"

if [[ "$(id -u)" != "0" ]]; then
  echo "请使用 root 执行：sudo bash install_podman_offline.sh" >&2
  exit 1
fi

if [[ ! -d "$RPM_DIR" ]]; then
  echo "未找到 RPM 目录：$RPM_DIR" >&2
  exit 1
fi
if [[ ! -f "$HOST_RPM_LIST" ]]; then
  echo "未找到宿主机 RPM 清单：$HOST_RPM_LIST" >&2
  exit 1
fi

HOST_RPMS=()
while IFS= read -r rpm_name || [[ -n "$rpm_name" ]]; do
  rpm_name="${rpm_name%%#*}"
  rpm_name="$(echo "$rpm_name" | xargs)"
  [[ -z "$rpm_name" ]] && continue
  rpm_path="$RPM_DIR/$rpm_name"
  if [[ ! -f "$rpm_path" ]]; then
    echo "警告：宿主机 RPM 清单中的文件不存在，已跳过：$rpm_path" >&2
    continue
  fi
  HOST_RPMS+=("$rpm_path")
done < "$HOST_RPM_LIST"

if [[ "${#HOST_RPMS[@]}" -eq 0 ]]; then
  echo "host-rpms.txt 中没有找到任何可安装 RPM，已取消。" >&2
  exit 1
fi

echo "[1/2] 离线安装 Podman 与依赖 RPM"
echo "仅安装 host-rpms.txt 中的 Podman 宿主机依赖，浏览器/gtk/mesa/nss/CNI 依赖不会安装到宿主机。"
if ! yum install -y "${HOST_RPMS[@]}"; then
  echo
  echo "yum 依赖安装失败，尝试使用 rpm --nodeps 安装本地 Podman 栈。"
  echo "说明：本项目使用 --network host，不依赖 containernetworking-plugins/CNI bridge 插件。"
  rpm -Uvh --replacepkgs --nodeps "${HOST_RPMS[@]}"
fi

echo "[2/2] 检查 Podman"
podman --version

echo
echo "Podman 离线安装完成。下一步执行：bash load_and_build_image.sh"
