# 内网离线部署说明

1. 在外网环境为后端依赖构建 Python wheel 仓。
2. 为前端导出 npm 离线缓存或安装包。
3. 将 `backend/`、`frontend/`、`deploy/`、`docs/` 以及依赖缓存拷贝到内网机器。
4. 使用 `pip install --no-index --find-links <wheel目录> -r backend/requirements.txt` 安装后端依赖。
5. 使用离线缓存安装前端依赖。
