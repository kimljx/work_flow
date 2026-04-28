# 接口说明

## 认证与用户

- `POST /login`
- `POST /refresh`
- `GET /users`
- `POST /users`
- `PUT /users/{user_id}`

## 任务

- `GET /tasks`
- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/notification-preview`
- `PUT /tasks/{task_id}`
- `DELETE /tasks/{task_id}`
- `POST /tasks/{task_id}/status`
- `POST /tasks/{task_id}/lock`
- `POST /tasks/{task_id}/unlock`
- `POST /tasks/{task_id}/remind`
- `POST /tasks/due-remind/run`

## 模板与通知

- `GET /templates`
- `POST /templates`
- `PUT /templates/{template_id}`
- `POST /templates/{template_id}/set-default`
- `POST /templates/preview-match`
- `GET /notifications`
- `GET /notifications/{notification_id}`

## 邮件与延期审批

- `GET /admin/mail/events`
- `GET /admin/mail/events/{event_id}`
- `GET /admin/mail/poll-state`
- `POST /admin/mail/test`
- `POST /admin/mail/inbox-test`
- `POST /admin/mail/poll`
- `POST /admin/mail/baseline`
- `POST /delay-requests`
- `GET /delay-requests/pending`
- `POST /delay-requests/{delay_id}/approve`

## 导入导出与审计

- `GET /tasks/import-template`
- `POST /tasks/import`
- `GET /tasks/import-histories`
- `GET /reports/export`
- `GET /audit-logs`

## 补充说明

- 系统管理员与管理员都可以调用管理接口；系统管理员在前端展示完整系统配置菜单，管理员隐藏模板、用户管理、邮件列表、审计日志入口。
- 任务创建与编辑接口现在按具体时间提交 `start_at`、`end_at`，前端默认会传入当天 `09:00` 到 `18:00`。
- 任务导入模板返回 `.xlsx` 文件，负责人、参与人员和子任务执行人统一使用系统姓名，不使用用户名。
- 任务导入接口支持高重叠检测；当历史重叠较高时，会先返回 `needs_confirmation=true`，前端确认后再继续导入。
- 任务导入接口与导入历史接口都会返回 `overlap_samples`；导入历史接口还会返回 `failure_samples` 便于回看失败摘要。
- 任务列表接口会返回 `subtask_status_summary`，按状态聚合子任务数量，供列表页直接展示进度汇总。
- 模板新增与编辑接口会校验正文中的占位符是否合法；发送类模板仅允许使用负责人、任务创建人、接收人、时间和子任务相关变量，非法占位符会直接返回 400。
- 默认发送模板上下文除 `task_title`、`owner_name`、`subtask_summary` 外，还会提供 `task_content`、`task_remark`、`remind_focus`，用于在正文中展示主任务详情、主任务备注和当前提醒重点。
- 通知详情接口会返回通知正文快照，以及按成员拆分的送达状态、回复状态、重试次数、错误信息和成员专属正文。
- 邮件回复被系统识别并成功落库后，会自动把对应邮件通知接收人标记为“已回复”；即时消息仍沿用“已读”口径，前端会按渠道动态展示“回复 / 已读”。
- 通知列表与通知详情接口会额外返回 `notify_scene_text`、`remind_focus`；系统会从已落库正文中自动提取提醒重点，并将 `manual_remind` 细分为任务提醒、子任务提醒、里程碑提醒。
- `GET /tasks/{task_id}/notification-preview` 支持按渠道、通知类型和接收人预览最终渲染结果，方便直接核对负责人、任务创建人和接收人子任务等占位符。
- 任务详情接口会返回子任务列表、子任务状态文案、通知记录、延期记录、状态时间线，以及任务创建人和创建时间等信息，供详情页直接展示。
- `DELETE /tasks/{task_id}` 会软删除任务，并同步清理该任务已生成的到期提醒通知和接收人明细。
- `POST /tasks/{task_id}/subtasks/{subtask_id}/remind` 会按子任务执行人定向发送提醒；`POST /tasks/{task_id}/milestones/{milestone_id}/remind` 会按里程碑节点向任务成员发送提醒。
- `GET /admin/mail/events/{event_id}` 会额外返回完整原始邮件正文，前端默认隐藏，仅在查看原始邮件时按弹窗展示。
- `POST /admin/mail/test` 在遇到 SMTP SSL/TLS 握手错误时，会返回中文排障提示，明确提示 `465 / 587 / 25` 端口与 `SMTP_USE_SSL`、`SMTP_USE_TLS` 的推荐组合。
- `POST /admin/mail/inbox-test` 与自动收件链路会读取 `IMAP_USE_SSL`、`IMAP_USE_TLS` 配置，支持明文、STARTTLS、SSL 三种收信连接方式。
- `POST /admin/mail/inbox-test` 与 `POST /admin/mail/poll` 还会读取 `MAIL_INBOX_PROTOCOL`；当配置为 `pop3` 时，接口会按 `POP3_HOST / POP3_PORT / POP3_USER / POP3_PASSWORD / POP3_USE_SSL / POP3_USE_TLS` 工作。
