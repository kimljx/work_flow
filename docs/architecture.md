# 系统架构说明

本项目采用单仓前后端分离结构，生产部署时由 Podman 容器运行后端并统一托管前端静态资源。

- `frontend/`：Vue 3 + Vite，包含管理员端和成员端页面。
- `backend/`：FastAPI 接口、任务通知、邮件收件、延期审批、导入导出、QAX 采集和系统日志逻辑。
- `deploy/offline/podman_rhel7_offline/`：RHEL 7 内网云部署脚本、离线 Podman RPM、应用运行镜像和 PostgreSQL 镜像。
- `docs/`：接口、架构、部署与维护文档。

## 生产部署架构

- 宿主机：RHEL 7.x 内网云主机。
- 容器运行时：Podman。
- 应用容器：`work-flow`，使用本地镜像 `localhost/work-flow-runtime:playwright-1.52`。
- 数据库容器：`work-flow-db`，使用本地镜像 `localhost/work-flow-postgres:16-alpine`。
- 网络：默认使用 host 网络，应用监听 `APP_PORT`，PostgreSQL 默认监听 `127.0.0.1:15432`。
- 数据持久化：PostgreSQL 数据目录默认挂载到宿主机 `/data/sql/postgre`。
- 证书信任：QAX 等 HTTPS 目标证书通过宿主机/系统信任链统一导入，应用默认不忽略 HTTPS 证书错误。

## 配置模型

- 项目不再使用 `.env` 文件。
- 生产启动必需配置由 `run_project.sh` 接收环境变量并注入容器，例如 `APP_PORT`、`DATABASE_URL`、`POSTGRES_*`、`DEFAULT_PASSWORD`、令牌配置等。
- 本地测试未注入 `DATABASE_URL` 时，后端默认使用 SQLite，便于快速运行自动化测试和开发调试。
- 业务运行配置保存在 PostgreSQL 中，包括计划任务、SMTP/IMAP/POP3、QAX 设置和域名 IP 映射。
- 前端系统设置页面写入数据库，后端通过运行时配置服务读取。

## 核心业务域

- 任务域：维护任务基础信息、成员、子任务、状态流转与起止时间。
- 通知域：按邮件和即时消息两个渠道发送通知，并按成员维度记录送达、反馈、重试和成员专属正文。
- 邮件域：负责邮箱拉取、模板匹配、回复动作解析、处理结果回写与手动收件。
- QAX 域：负责即时消息发送、状态采集、已读回写和诊断日志。
- 延期审批域：负责成员发起延期、管理员审批、幂等校验与版本控制。
- 导入导出域：负责 Excel 模板、任务批量导入、导入历史和重复导入预警。
- 系统日志域：记录关键管理动作、后台采集、定时清理和异常排障信息。
