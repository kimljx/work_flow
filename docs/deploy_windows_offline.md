# Windows 内网离线部署手册

## 1. 目标

将系统部署到内网 Windows 电脑上，部署后具备以下特征：

- 目标电脑无需安装 Node.js
- 目标电脑无需联网安装 Python 依赖
- 目标电脑无需预装 Python 解释器
- 目标电脑无需单独安装 Playwright Chromium 浏览器
- 浏览器访问 `http://部署电脑IP:8000/` 即可打开系统
- 后续升级可通过“备份脚本 + 一键升级脚本”平滑迁移数据

## 2. 目标电脑要求

- Windows 10 / Windows 11 或同类 Windows Server
- 可用浏览器
- 建议至少 3GB 可用磁盘空间

## 3. 开发电脑打包步骤

### 3.1 前提

- 开发电脑可联网
- 开发电脑已安装 Node.js
- 开发电脑已安装 Python 3.10 与 Python 3.11

### 3.2 执行打包

在项目根目录执行：

```powershell
deploy\offline\build_windows_offline_package.bat
```

构建脚本会自动完成以下动作：

1. 重新执行前端构建，生成最新 `frontend/dist`
2. 下载 Python 3.10 对应的离线依赖包
3. 下载官方 Python 3.10 Windows 嵌入式运行时
4. 将后端依赖预装到发布包内置运行时
5. 安装 QAX 所需的 Playwright Chromium 浏览器到 `runtime/ms-playwright`
6. 复制后端代码、前端静态资源、部署脚本与文档
7. 生成目录版发布包与 zip 压缩包

构建产物目录：

```text
deploy/offline/dist/
```

## 4. 发布包目录结构

发布包解压后大致如下：

```text
work_flow_windows_offline_py310_xxxxxxxx/
├─ app/
│  ├─ backend/
│  └─ frontend/
├─ backup/
├─ config/
├─ docs/
├─ packages/
├─ runtime/
│  ├─ python/
│  └─ ms-playwright/
├─ tools/
├─ install_offline.bat
├─ start_system.bat
├─ stop_system.bat
├─ backup_data.bat
├─ restore_data.bat
├─ upgrade_from_release.bat
└─ README.txt
```

说明：

- `app/backend`：后端代码、数据库目录、运行入口
- `app/frontend/dist`：前端构建后的静态资源
- `runtime/python`：发布包自带的 Python 3.10 运行时
- `runtime/ms-playwright`：QAX 模块使用的 Playwright Chromium 浏览器
- `packages`：离线依赖包备份
- `config/.env.offline.example`：离线环境配置模板
- `backup/`：备份脚本生成的数据与配置备份目录

## 5. 目标电脑安装步骤

### 5.1 拷贝发布包

将 zip 包或目录版发布包复制到内网目标电脑，例如：

```text
D:\work_flow_release\
```

### 5.2 解压

如果复制的是 zip 包，先解压。

### 5.3 首次初始化

推荐先执行：

```text
install_offline.bat
```

脚本会自动完成：

1. 创建 `local/` 本地运行目录
2. 生成 `app\.env`
3. 校验内置 Python 运行时
4. 校验 Playwright 浏览器目录是否完整

### 5.4 修改配置

按需编辑：

```text
app\.env
```

常见配置项：

- `APP_NAME`：系统名称
- `DEFAULT_PASSWORD`：默认密码
- `QAX_BASE_URL` / `QAX_USERNAME` / `QAX_PASSWORD`：QAX 登录配置
- `QAX_BROWSER_HEADLESS`：QAX 自动化是否隐藏浏览器界面
- `QAX_COLLECT_CRON`：QAX 定时采集表达式
- `SYSTEM_LOG_RETENTION_DAYS`：系统日志保留天数
- `MAIL_AUTO_POLL_ENABLED`：是否自动收件
- `SMTP_*`、`IMAP_*`、`POP3_*`：邮件收发配置

### 5.5 启动系统

双击：

```text
start_system.bat
```

脚本会：

1. 自动检查并补齐本地初始化环境
2. 使用发布包内置 Python 启动 FastAPI 服务
3. 将 Playwright 浏览器路径固定到 `runtime\ms-playwright`
4. 自动打开浏览器首页 `http://127.0.0.1:8000/`

### 5.6 关闭系统

双击：

```text
stop_system.bat
```

## 6. 局域网访问方式

如需让局域网其他电脑访问：

1. 在部署电脑上执行 `ipconfig`
2. 记下内网 IP，例如 `192.168.1.20`
3. 其他电脑浏览器访问：

```text
http://192.168.1.20:8000/
```

如无法访问，请检查：

- Windows 防火墙是否放行 `8000` 端口
- 部署电脑与访问电脑是否处于同一网络
- 服务是否已正常启动

## 7. 数据备份与恢复

### 7.1 备份数据

执行：

```text
backup_data.bat
```

备份内容包括：

- `app\backend\data\app.db`
- `app\.env`

### 7.2 恢复数据

执行：

```text
restore_data.bat
```

也可指定备份目录：

```text
restore_data.bat 20260424_103000
```

## 8. 一键升级旧版

如果旧版系统已在其他目录正常运行，执行：

```text
upgrade_from_release.bat 旧版目录完整路径
```

脚本会自动完成：

1. 停止旧版服务
2. 备份旧版数据库与 `.env`
3. 初始化新版本环境
4. 复制旧版最新备份到新目录
5. 恢复数据到新版本
6. 启动新版本服务

## 9. 常见问题

### 9.1 提示未找到内置 Python 运行时

说明 `runtime/python` 目录缺失或损坏。请重新复制完整发布包。

### 9.2 提示未找到内置 Playwright 浏览器目录

说明 `runtime/ms-playwright` 缺失，QAX 模块无法使用。请重新生成并复制完整发布包。

### 9.3 启动成功但页面打不开

优先检查：

- 服务窗口是否报错
- `app/frontend/dist` 是否存在
- 8000 端口是否被占用

### 9.4 邮件功能暂时不用

可先保持：

```text
MAIL_AUTO_POLL_ENABLED=false
```

系统其他功能仍可正常使用。
