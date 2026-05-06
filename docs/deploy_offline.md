# 离线部署说明

本项目支持打包为 Windows 与 Linux x86_64 的内网离线发布包。

## 适用场景

- 目标电脑无法联网安装 Python 依赖
- 目标电脑不具备 Node.js 或前端构建环境
- 需要把 QAX 所需的 Playwright Chromium 浏览器一并打进发布包
- 希望通过浏览器直接访问系统，不再额外拆分前后端服务

## 发布包特点

- 后端使用 FastAPI 提供接口，并统一托管前端构建后的静态资源
- 发布包内预置 Python 3.10 运行时与后端依赖
- 发布包内预置 Playwright Chromium 浏览器，QAX 模块可直接使用
- 目标电脑无需额外安装 Python、Node.js 或浏览器驱动
- 提供安装、启动、停止、备份、恢复、升级等常用脚本
- 支持“旧版备份 -> 新版恢复”的平滑升级方式

## 构建方式

Windows 构建：

```powershell
deploy\offline\build_windows_offline_package.bat
```

Linux 构建：

```bash
./deploy/offline/build_linux_offline_package.sh
```

说明：

- Windows 离线包应在 Windows 构建机上生成。
- Linux 离线包应在 Linux x86_64 构建机上生成。
- 原因是内置 Python 运行时和 Playwright 浏览器都必须与目标平台一致。
- Linux 构建机不强制要求本机就是 Python 3.10，只要有可联网的 Python 3 环境即可，脚本会按目标 `cp310` 预下载依赖。

## 构建产物

构建完成后会在 `deploy/offline/dist/` 下生成：

- 目录版发布包
- Windows 的 `.zip` 压缩包
- Linux 的 `.tar.gz` 压缩包

## 详细文档

- Windows 离线部署：`docs/deploy_windows_offline.md`
- Linux 离线部署：`docs/deploy_linux_offline.md`
