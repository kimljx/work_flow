# 工作流管理系统

## 目录说明
- `frontend/`：Vue 3 前端工程
- `backend/`：FastAPI 后端服务
- `deploy/`：Windows、Win7、Linux、Docker 部署脚本与说明
- `docs/`：架构、接口与运维文档

## 环境准备
先复制 `.env` 文件，并按实际环境填写配置项。

```powershell
copy .env.example .env
```

Linux：

```bash
cp .env.example .env
```

## 安装依赖
```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
```

## 启动后端
```powershell
set PYTHONPATH=backend
py -m uvicorn app.main:app --app-dir backend --reload
```

## 运行测试
```powershell
set PYTHONPATH=backend
py -m unittest discover backend/tests
py backend/scripts/cleanup_test_db.py
```

## 启动前端
```powershell
cd frontend
npm install
npm run dev
```

## 默认账号
- 管理员：`admin`
- 成员：`member`
- 默认密码可通过 `.env` 中的 `DEFAULT_PASSWORD` 配置，默认值为 `ChangeMe123`

## 邮件配置
如需启用邮件通知，请在 `.env` 中配置 SMTP 参数：

```powershell
SMTP_HOST=smtp.example.com
SMTP_PORT=25
SMTP_USER=your_user
SMTP_PASSWORD=your_password
SMTP_FROM_ADDRESS=no-reply@example.com
SMTP_USE_TLS=false
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=20
```

端口建议：
- `25`：常见 SMTP 端口，通常配合 `STARTTLS`
- `587`：建议启用 `SMTP_USE_TLS=true`
- `465`：建议启用 `SMTP_USE_SSL=true`

## QQ 邮箱配置示例
SMTP 示例：

```powershell
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=你的QQ邮箱
SMTP_PASSWORD=邮箱授权码
SMTP_FROM_ADDRESS=你的QQ邮箱
SMTP_USE_SSL=true
SMTP_USE_TLS=false
SMTP_TIMEOUT_SECONDS=20
```

IMAP 示例：

```powershell
IMAP_HOST=imap.qq.com
IMAP_PORT=993
IMAP_USER=你的QQ邮箱
IMAP_PASSWORD=邮箱授权码
IMAP_MAX_UNSEEN_SCAN=20
```

说明：
- IMAP 用于自动扫描回复邮件
- 建议先在邮箱设置中开启 IMAP，并生成授权码用于登录
- `IMAP_MAX_UNSEEN_SCAN` 用于限制每轮扫描的未读邮件数量
- 首次接入建议先设置扫描基准时间，避免历史未读邮件被一次性批量处理

## 常见排查
- 域名解析失败：检查 SMTP/IMAP 主机名是否正确
- 连接超时：检查网络连通性与端口放通策略
- 认证失败：检查账号、密码或授权码是否正确
