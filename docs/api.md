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
