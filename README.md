# 工作流管理系统

## 目录说明

- `frontend/`: Vue 3 前端工程
- `backend/`: FastAPI 后端服务
- `deploy/`: Windows、Linux、Docker 与离线发布相关脚本
- `docs/`: 架构、接口、部署与使用文档

## 开发环境准备

先复制 `.env` 文件，并按实际环境填写配置项：

```powershell
copy .env.example .env
```

## 本地开发

安装后端依赖：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
```

启动后端：

```powershell
set PYTHONPATH=backend
py -m uvicorn app.main:app --app-dir backend --reload
```

启动前端：

```powershell
cd frontend
npm install
npm run dev
```

## 默认账号

- 管理员：`admin`
- 成员：`member`
- 默认密码来自 `.env` 中的 `DEFAULT_PASSWORD`

## 文档入口

- 离线发布说明：`docs/deploy_offline.md`
- Windows 内网部署手册：`docs/deploy_windows_offline.md`
- 使用手册：`docs/user_manual.md`
- 接口说明：`docs/api.md`

## 离线升级建议

内网升级时建议按以下顺序执行：
1. 在旧版目录运行 `backup_data.bat`
2. 解压并安装新版离线发布包
3. 将旧版 `backup\时间戳目录` 复制到新版目录
4. 在新版目录运行 `restore_data.bat`

当前离线发布包还支持直接执行 `upgrade_from_release.bat 旧版目录完整路径`，
把停止旧版、备份、恢复和启动新版串成一次操作。
