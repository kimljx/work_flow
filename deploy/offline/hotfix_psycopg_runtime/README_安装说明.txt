Work Flow PostgreSQL 驱动热修复包
=================================

适用问题：

  应用容器日志出现：

    运行时依赖校验失败：No module named 'psycopg'

原因：

  项目已切换到 PostgreSQL，应用需要 Python PostgreSQL 驱动 psycopg。
  服务器当前项目内置 Python 运行时中缺少该模块。

安装步骤：

  1. 把本补丁包上传到服务器，例如：

       /data/podman/work_flow_psycopg_runtime_hotfix_20260521

  2. 执行安装：

       cd /data/podman/work_flow_psycopg_runtime_hotfix_20260521
       sudo bash install_psycopg_hotfix.sh /data/work_flow/current

  3. 重启应用容器：

       cd /data/podman/podman_rhel7_offline
       sudo bash stop_project.sh
       REAL_DIR=$(readlink -f /data/work_flow/current)
       sudo APP_PORT=18849 POSTGRES_PASSWORD='你的数据库密码' bash run_project.sh "$REAL_DIR"

说明：

  - 该补丁只安装 psycopg 和 psycopg-binary，不修改数据库数据。
  - PostgreSQL 容器可以保持运行。
  - 如果 /data/work_flow/current 不是实际项目目录，请把真实目录传给 install_psycopg_hotfix.sh。
