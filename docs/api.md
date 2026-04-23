# 接口总览

基础前缀：`/api/v1`

认证接口：
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

管理员用户接口：
- `GET /admin/users`
- `POST /admin/users`
- `PUT /admin/users/{id}`
- `POST /admin/users/{id}/disable`
- `POST /admin/users/{id}/enable`
- `POST /admin/users/{id}/reset-password`

任务接口：
- `GET /tasks`
- `POST /tasks`
- `GET /tasks/{id}`
- `PUT /tasks/{id}`
- `DELETE /tasks/{id}`
- `POST /tasks/{id}/status`
- `POST /tasks/{id}/lock`
- `POST /tasks/{id}/unlock`

模板接口：
- `GET /templates`
- `POST /templates`
- `PUT /templates/{id}`
- `POST /templates/{id}/set-default`
- `POST /templates/preview-match`

通知接口：
- `GET /notifications`
- `GET /notifications/{notification_id}`

邮件接口：
- `GET /admin/mail/events`
- `GET /admin/mail/events/{event_id}`
- `GET /admin/mail/poll-state`
- `POST /admin/mail/test`
- `POST /admin/mail/inbox-test`
- `POST /admin/mail/poll`
- `POST /admin/mail/baseline`

延期审批接口：
- `POST /delay-requests`
- `GET /delay-requests/pending`
- `POST /delay-requests/{delay_id}/approve`

其他管理接口：
- `GET /dashboard/summary`
- `POST /tasks/{task_id}/remind`
- `POST /tasks/due-remind/run`
- `GET /tasks/import-template`
- `POST /tasks/import`
- `GET /reports/export`
- `GET /audit-logs`

补充说明：
- 通知详情接口会返回通知正文快照，以及按成员拆分的送达状态、已读状态、重试次数与错误信息
- 邮件列表接口只返回已匹配模板的邮件，详情接口会额外返回命中的模板编号、模板类型与模板正文
- 邮件轮询状态接口用于列表页展示自动收件倒计时
- 延期审批列表接口会返回任务优先级、开始时间、结束时间、申请人邮箱与创建时间，便于审批工作台直接展示
- 任务导入模板接口现在返回 `.xlsx` 文件，包含“任务导入模板”和“填写说明”两个工作表，覆盖任务创建所需字段、示例和填写规则
- 任务导入接口支持上传 `.xlsx` 模板文件，返回成功数量、失败数量、已创建任务编号以及失败行原因
- 任务详情接口中的延期记录会额外返回审批人、审批渠道和审批时间，供详情页直接展示审批结果
