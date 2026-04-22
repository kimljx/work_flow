# 离线部署包说明

- Python 依赖：根据 `backend/requirements.txt` 预先构建 wheel 仓
- 前端依赖：根据 `frontend/package.json` 预先导出 npm 离线缓存或安装包
- 将依赖包与 `deploy/` 启动脚本一起分发到内网环境
