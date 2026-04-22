# Windows 部署说明

1. 安装 Python 3.8.x 或更高版本。
2. 创建并激活虚拟环境。
3. 安装 `backend/requirements.txt` 中的后端依赖。
4. 从离线包或缓存中安装前端依赖。
5. 使用 `deploy/windows/start_backend.bat` 启动后端。
6. 使用 `deploy/windows/start_frontend.bat` 启动前端。
7. 通过 NSSM 或 WinSW 注册为系统服务，实现开机自启。
