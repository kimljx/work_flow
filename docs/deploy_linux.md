# Linux 部署说明

本仓库现在提供两种 Linux 部署方式：

1. 常规在线部署
2. Linux x86_64 内网离线部署

## 常规在线部署

1. 创建并激活虚拟环境
2. 安装后端依赖
3. 构建前端产物，并通过同域方式对外提供访问
4. 可使用 `deploy/linux/systemd.service` 作为 systemd 服务模板

## 离线部署

如果目标环境无法联网，或希望连 QAX 所需的 Playwright Chromium 浏览器也一并打进发布包，请使用：

```bash
./deploy/offline/build_linux_offline_package.sh
```

详细步骤请查看：

- `docs/deploy_linux_offline.md`
