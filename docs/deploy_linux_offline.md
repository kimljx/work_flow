# Linux x86_64 内网离线部署手册

## 1. 目标

将系统部署到内网 Linux x86_64 服务器或桌面环境中，部署后具备以下特征：

- 目标机器无需安装 Node.js
- 目标机器无需联网安装 Python 依赖
- 目标机器无需预装 Python 解释器
- 目标机器无需单独安装 Playwright Chromium 浏览器
- 浏览器访问 `http://部署主机IP:8000/` 即可打开系统

## 2. 目标机器要求

- Linux x86_64，建议 glibc 2.17 及以上
- 可执行 shell 脚本权限
- 建议至少 3GB 可用磁盘空间

## 3. 构建说明

Linux 离线包必须在 Linux x86_64 构建机上生成：

```bash
./deploy/offline/build_linux_offline_package.sh
```

构建脚本会自动完成：

1. 重新构建前端静态资源
2. 下载 Python 3.10 离线依赖包
3. 下载 Linux 便携 Python 3.10 运行时
4. 将后端依赖预装到内置运行时
5. 安装 QAX 所需的 Playwright Chromium 浏览器
6. 复制后端代码、前端静态资源、离线脚本与文档
7. 生成目录版发布包与 `.tar.gz` 压缩包

补充说明：

- 构建机不要求本机就是 Python 3.10。
- 只要具备可联网的 Python 3 与 Node.js 环境，脚本就会按目标 Linux `cp310` 依赖进行离线下载。

## 4. 发布包目录结构

```text
work_flow_linux_offline_py310_xxxxxxxx/
├─ app/
├─ backup/
├─ config/
├─ docs/
├─ packages/
├─ runtime/
│  ├─ python/
│  └─ ms-playwright/
├─ service/
│  └─ work_flow.service
├─ tools/
├─ install_offline.sh
├─ start_system.sh
├─ stop_system.sh
├─ backup_data.sh
├─ restore_data.sh
├─ upgrade_from_release.sh
└─ README.txt
```

## 5. 目标机器安装步骤

### 5.1 拷贝并解压发布包

示例：

```bash
mkdir -p /opt/work_flow_release
tar -xzf work_flow_linux_offline_py310_xxxxxxxx.tar.gz -C /opt/work_flow_release
cd /opt/work_flow_release/work_flow_linux_offline_py310_xxxxxxxx
```

### 5.2 首次初始化

```bash
./install_offline.sh
```

脚本会自动完成：

1. 创建 `local/` 运行目录、缓存目录和日志目录
2. 生成 `app/.env`
3. 校验内置 Python 运行时
4. 校验 Playwright 浏览器目录是否完整

### 5.3 修改配置

按需编辑：

```bash
vi app/.env
```

常见配置项：

- `APP_NAME`
- `DEFAULT_PASSWORD`
- `QAX_BASE_URL` / `QAX_USERNAME` / `QAX_PASSWORD`
- `QAX_BROWSER_HEADLESS`
- `QAX_COLLECT_CRON`
- `SYSTEM_LOG_RETENTION_DAYS`
- `MAIL_AUTO_POLL_ENABLED`
- `SMTP_*`、`IMAP_*`、`POP3_*`

### 5.4 启动系统

```bash
./start_system.sh
```

启动后：

- 服务监听 `0.0.0.0:8000`
- 日志写入 `local/logs/server.log`
- PID 写入 `local/run/uvicorn.pid`

### 5.5 停止系统

```bash
./stop_system.sh
```

## 6. 局域网访问方式

其他电脑浏览器访问：

```text
http://部署主机IP:8000/
```

如无法访问，请检查：

- 防火墙是否放行 `8000` 端口
- 服务是否已正常启动
- 部署主机与访问主机是否网络互通

## 7. 备份、恢复与升级

备份：

```bash
./backup_data.sh
```

恢复：

```bash
./restore_data.sh
./restore_data.sh 20260424_103000
```

升级旧版：

```bash
./upgrade_from_release.sh /旧版发布包目录
```

## 8. systemd 服务模板

发布包中已附带：

```text
service/work_flow.service
```

你可以按实际部署目录修改 `WorkingDirectory` 与 `ExecStart` 后再接入 systemd。

## 9. 常见问题

### 9.1 提示未找到内置 Python 运行时

说明 `runtime/python` 目录缺失或损坏，请重新复制完整发布包。

### 9.2 提示未找到内置 Playwright 浏览器目录

说明 `runtime/ms-playwright` 缺失，QAX 模块无法使用，请重新生成并复制完整发布包。

### 9.3 启动后访问不到页面

优先检查：

- `local/logs/server.log` 是否报错
- `app/frontend/dist` 是否存在
- 8000 端口是否被占用
