# Work Flow Podman + PostgreSQL 离线部署说明

当前服务器默认目录如下：

- Podman 离线目录：`/data/podman/podman_rhel7_offline`
- 项目发布根目录：`/data/work_flow`
- 当前项目目录或软链接：`/data/work_flow/current`
- PostgreSQL 共享数据目录：`/data/sql/postgre`

本方案使用两个容器：

- 应用容器：`work-flow`
- PostgreSQL 容器：`work-flow-db`

说明：应用在容器内部仍挂载到 `/opt/work_flow`，这是容器内路径，不是宿主机项目目录。

## 1. 离线资源

把镜像包复制到：

```text
/data/podman/podman_rhel7_offline/images/
```

必须包含：

```text
playwright-python-v1.52.0-jammy.tar
postgres-16-alpine.tar
```

已知校验值：

```text
playwright-python-v1.52.0-jammy.tar
sha256: 54fb44169f0857e8e9edffb47bdb99cda1d804e63159d29d47bb2b784d770a5b

postgres-16-alpine.tar
sha256: af5a11d1030c3cdaa05a97cb7337240a8d62bdaaeb6aa7cea0c2819a6dad0bde
```

## 2. 安装 Podman

```bash
cd /data/podman/podman_rhel7_offline
sudo bash install_podman_offline.sh
podman --version
```

## 3. 导入镜像

```bash
cd /data/podman/podman_rhel7_offline
sudo bash load_and_build_image.sh
```

该步骤会导入并标记：

```text
localhost/work-flow-runtime:playwright-1.52
localhost/work-flow-postgres:16-alpine
```

## 4. 解压项目

```bash
mkdir -p /data/work_flow
cd /data/work_flow
tar -xzf /data/podman/work_flow_linux_offline_py310_*.tar.gz
ln -sfn "$(find /data/work_flow -maxdepth 1 -type d -name 'work_flow_linux_offline_py310_*' | sort | tail -n 1)" /data/work_flow/current
```

如果不使用软链接，启动时把真实发布目录传给 `run_project.sh` 即可。

## 5. 启动项目

```bash
cd /data/podman/podman_rhel7_offline
REAL_DIR=$(readlink -f /data/work_flow/current)
sudo APP_PORT=18849 \
  POSTGRES_PASSWORD='请替换为强密码' \
  bash run_project.sh "$REAL_DIR"
```

默认数据库参数：

```text
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432
POSTGRES_DB=work_flow
POSTGRES_USER=work_flow
POSTGRES_PASSWORD=work_flow_change_me
POSTGRES_DATA_DIR=/data/sql/postgre
```

如果多个项目共用同一个 PostgreSQL 集群，建议每个项目使用不同的 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`，但保持 `POSTGRES_DATA_DIR=/data/sql/postgre`。

## 6. 停止项目

只停止应用容器，保留 PostgreSQL 继续运行：

```bash
cd /data/podman/podman_rhel7_offline
sudo bash stop_project.sh
```

同时停止应用容器和 PostgreSQL 容器：

```bash
cd /data/podman/podman_rhel7_offline
sudo STOP_DB=true bash stop_project.sh
```

## 7. 数据备份

建议先停止 PostgreSQL，再备份共享数据目录：

```bash
cd /data/podman/podman_rhel7_offline
sudo STOP_DB=true bash stop_project.sh
sudo tar -czf /data/sql/work_flow_postgre_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data/sql postgre
```

## 8. 配置方式

`.env` 只保留启动必需配置，例如 `DATABASE_URL`、令牌配置等。

以下业务配置保存在 PostgreSQL 中：

- 计划任务设置
- SMTP/IMAP/POP3 邮件设置
- QAX 设置
- 域名 IP 映射

这些配置请在系统右上角“系统设置”弹窗中维护。

## 9. 常用排查命令

```bash
podman ps -a
podman logs -f work-flow
podman logs -f work-flow-db
podman exec work-flow-db pg_isready -h 127.0.0.1 -p 15432 -U work_flow -d work_flow
podman exec -it work-flow-db psql -h 127.0.0.1 -p 15432 -U work_flow -d work_flow
```
