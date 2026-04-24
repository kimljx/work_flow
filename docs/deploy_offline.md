# 离线部署说明

本项目支持打包为 Windows 内网离线发布包。

## 适用场景

- 目标电脑无法联网安装 Python 依赖。
- 目标电脑不具备 Node.js 或前端构建环境。
- 目标电脑需要通过浏览器直接访问系统页面。

## 发布包特点

- 后端使用 FastAPI 提供接口，并统一托管前端构建后的静态资源。
- 发布包内预置 Python 3.10 嵌入式运行时与后端依赖。
- 目标电脑无需额外安装 Python 或 Node.js。
- 提供 `install_offline.bat`、`start_system.bat`、`stop_system.bat`、`backup_data.bat`、`restore_data.bat`、`upgrade_from_release.bat` 常用脚本。
- 支持“旧版备份 -> 新版恢复”的升级方式，备份内容包含 SQLite 数据库和运行配置。

## 构建方式

在开发电脑执行：

```powershell
deploy\offline\build_windows_offline_package.bat
```

或：

```powershell
py -3.11 deploy\offline\build_windows_offline_package.py
```

构建完成后会在 `deploy/offline/dist/` 下生成：

- 目录版发布包
- zip 压缩包

详细部署步骤请查看：

- `docs/deploy_windows_offline.md`
