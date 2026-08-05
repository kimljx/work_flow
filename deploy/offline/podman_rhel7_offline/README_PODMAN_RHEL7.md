# RHEL 7.6 Podman 离线部署快速说明

默认服务器目录：

```text
/data/podman/podman_rhel7_offline
/data/work_flow/current
/data/sql/postgre
```

完整 PostgreSQL 部署说明见 `README_POSTGRES_PODMAN_OFFLINE.md`。

## 快速启动

安装 Podman：

```bash
cd /data/podman/podman_rhel7_offline
sudo bash install_podman_offline.sh
```

导入镜像：

```bash
sudo bash load_and_build_image.sh
```

解压项目：

```bash
mkdir -p /data/work_flow
cd /data/work_flow
tar -xzf /data/podman/work_flow_linux_offline_py310_*.tar.gz
ln -sfn "$(find /data/work_flow -maxdepth 1 -type d -name 'work_flow_linux_offline_py310_*' | sort | tail -n 1)" /data/work_flow/current
```

启动项目：

```bash
cd /data/podman/podman_rhel7_offline
REAL_DIR=$(readlink -f /data/work_flow/current)
sudo APP_PORT=18849 POSTGRES_PASSWORD='请替换为强密码' bash run_project.sh "$REAL_DIR"
```

生产配置不再使用 `.env` 文件。启动必需参数通过命令行环境变量传入，业务配置进入系统后在“系统设置”中维护并保存到 PostgreSQL。

QAX 等 HTTPS 证书按系统级导入处理，应用默认校验证书链。

停止项目：

```bash
sudo bash stop_project.sh
sudo STOP_DB=true bash stop_project.sh
```
