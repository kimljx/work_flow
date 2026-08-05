Work Flow 数据持久化说明
========================

Podman 部署方案中，Work Flow 的所有业务数据都保存在 PostgreSQL 中。

默认 PostgreSQL 共享数据目录：

  /data/sql/postgre

默认项目目录：

  /data/work_flow/current

默认 Podman 离线脚本目录：

  /data/podman/podman_rhel7_offline

SQLite 文件只用于本地开发或自动化测试，不用于 Podman 生产部署。

以下数据都会保存在 PostgreSQL 中：

  - 用户数据
  - 任务数据
  - 计划任务设置
  - 邮件设置
  - QAX 设置
  - 域名 IP 映射

备份步骤：

  cd /data/podman/podman_rhel7_offline
  sudo STOP_DB=true bash stop_project.sh
  sudo tar -czf /data/sql/work_flow_postgre_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data/sql postgre

恢复步骤：

  1. 停止应用容器和 PostgreSQL 容器。
  2. 恢复 /data/sql/postgre 目录。
  3. 重新执行 /data/podman/podman_rhel7_offline/run_project.sh。
