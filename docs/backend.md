# 后端说明

- 后端使用 FastAPI + SQLAlchemy，接口统一挂在 `/api/v1`。
- 生产环境固定运行在 RHEL 7 + Podman 应用容器中，数据库使用 PostgreSQL 容器。
- 本地测试保留 SQLite 支持；未设置 `DATABASE_URL` 时默认使用 `sqlite:///./backend/data/app.db`。
- 后端不再读取项目根目录 `.env`；启动必需配置由容器环境变量注入，业务配置从 PostgreSQL 读取。
- QAX/HTTPS 证书采用系统级导入方式，默认不忽略证书校验。
- 角色分为系统管理员、管理员和成员；系统管理员与管理员都属于管理角色并拥有管理接口权限，前端通过菜单可见性区分系统级配置入口。
- 任务创建、编辑、导入和邮件回执共用同一套任务、成员、子任务和通知规则，避免不同入口出现行为漂移。
- 通知服务按接收人过滤子任务，确保不同成员收到的正文只包含分配给自己的子任务内容。
- 默认发送模板上下文统一补充 `task_content`、`task_remark`、`remind_focus`，默认邮件 / 即时消息正文都会带出主任务详情、主任务备注和当前提醒重点。
- QAX 通知链路使用 Playwright 自动化：创建通知时登录 QAX、进入“资产管理 -> 终端任务”、按成员 IP 创建即时消息任务；后续通过状态采集接口按任务名回查执行状态并回写通知接收人。
- 任务提醒支持整任务提醒、参与人提醒、子任务定向提醒和里程碑节点提醒。
- 通知接收人的 `read_status` 字段按渠道解释：邮件渠道表示“是否已回复”，即时消息渠道表示“是否已读”。
- 模板新增与编辑接口会在入库前校验占位符，非法变量会直接拦截。
- 任务导入使用 Excel 模板，负责人、参与人员和子任务执行人统一按姓名匹配系统用户；高重叠导入需要二次确认。
- 邮件收件支持 IMAP 与 POP3，并支持明文、STARTTLS、SSL 三种连接方式。
- 手动邮件、手动 QAX 和任务同步采集统一由后台采集协调模块调度；同一时间只允许一个采集任务运行。
- 系统日志记录关键管理动作、后台自动收件、QAX 采集、定时清理结果和异常告警。

## 运行配置

生产启动时由 `deploy/offline/podman_rhel7_offline/run_project.sh` 注入：

- `DATABASE_URL`
- `APP_PORT`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DEFAULT_PASSWORD`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_MINUTES`

SMTP/IMAP/POP3、QAX、计划任务和域名 IP 映射等业务配置在系统设置中维护，落库到 PostgreSQL。

本地测试可不设置 `DATABASE_URL`，此时使用 SQLite；如需本地连接 PostgreSQL，可在终端临时设置 `DATABASE_URL`，不需要恢复 `.env` 文件。
