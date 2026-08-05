# 工作流管理系统

本项目是面向内网环境的任务协同与通知跟踪系统，包含任务管理、邮件回执、QAX 即时消息状态采集、延期审批、批量导入导出和系统日志等能力。

## 项目结构

- `frontend/`：Vue 3 + Vite 前端工程。
- `backend/`：FastAPI 后端服务，接口统一挂载在 `/api/v1`。
- `deploy/offline/podman_rhel7_offline/`：当前唯一保留的部署方案，适用于 RHEL 7 内网云主机的 Podman + 镜像部署。
- `docs/`：架构、接口、部署、使用和排障文档。
- `config/`：任务导入模板、邮件主机示例等运行辅助文件。

## 部署方式

当前部署方式已经固定为：

- 操作系统：RHEL 7.x 内网云主机。
- 容器运行时：Podman。
- 应用运行：Playwright Python 镜像容器。
- 数据库：生产使用 PostgreSQL 容器，数据目录默认 `/data/sql/postgre`；本地测试未注入 `DATABASE_URL` 时仍可使用 SQLite。
- 证书：在宿主机/系统信任链中做系统级导入，不再通过项目配置文件单独指定证书。
- 配置：不再使用 `.env` 文件；生产启动必需参数通过 `run_project.sh` 的环境变量注入，业务配置写入 PostgreSQL 并在系统设置中维护。

部署入口见 [docs/deploy_podman_rhel7.md](docs/deploy_podman_rhel7.md)；使用 PyCharm 打包和更新部署见 [docs/pycharm_packaging_podman.md](docs/pycharm_packaging_podman.md)。

## 本地测试

本地测试可以不配置 `DATABASE_URL`，后端会默认使用 `sqlite:///./backend/data/app.db`。需要连接 PostgreSQL 时，在当前终端临时设置 `DATABASE_URL` 即可。

## 默认账号

- 系统管理员：`admin`
- 成员：`member`
- 默认密码由启动环境变量 `DEFAULT_PASSWORD` 控制；未显式设置时使用后端默认值。

## 文档入口

- 部署说明：[docs/deploy_podman_rhel7.md](docs/deploy_podman_rhel7.md)
- PyCharm 打包与更新部署：[docs/pycharm_packaging_podman.md](docs/pycharm_packaging_podman.md)
- 架构说明：[docs/architecture.md](docs/architecture.md)
- 后端说明：[docs/backend.md](docs/backend.md)
- 前端说明：[docs/frontend.md](docs/frontend.md)
- 接口说明：[docs/api.md](docs/api.md)
- 用户手册：[docs/user_manual.md](docs/user_manual.md)
- QAX 集成：[docs/qax_integration.md](docs/qax_integration.md)
- 排障说明：[docs/troubleshooting.md](docs/troubleshooting.md)
