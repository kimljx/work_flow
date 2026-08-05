# 常见问题排查

## 容器状态

```bash
podman ps -a
podman logs -f work-flow
podman logs -f work-flow-db
```

## PostgreSQL

```bash
podman exec work-flow-db pg_isready -h 127.0.0.1 -p 15432 -U work_flow -d work_flow
podman exec -it work-flow-db psql -h 127.0.0.1 -p 15432 -U work_flow -d work_flow
```

如果应用无法启动，优先检查：

- `run_project.sh` 中传入的 `POSTGRES_*` 参数是否一致。
- `/data/sql/postgre` 是否存在且可被 Podman 挂载。
- `DATABASE_URL` 是否由 `run_project.sh` 正确注入应用容器。
- 如果是本地测试且没有设置 `DATABASE_URL`，后端会使用 SQLite；这是开发测试能力，不是生产部署方式。

## 登录失败

- 检查启动时传入的 `DEFAULT_PASSWORD`。
- 检查 `work-flow` 容器日志中是否已完成默认用户初始化。
- 检查浏览器访问端口是否为启动时的 `APP_PORT`。

## QAX 证书与页面加载

证书采用系统级导入方式。若 QAX 页面打不开或一直加载：

```bash
podman exec -it work-flow bash
curl -vk https://QAX_HOST:PORT/login
openssl s_client -connect QAX_HOST:PORT -servername QAX_HOST -showcerts </dev/null
```

检查重点：

- 宿主机和容器内是否都能解析 QAX 域名或 IP。
- 系统信任链是否已导入 QAX 服务端证书链。
- `Verify return code: 0 (ok)` 是否成立。
- `local/logs/qax_debug/` 下的 `.png`、`.html`、`.log` 是否记录了页面错误、接口错误或网络错误。

## 邮件收发

- SMTP 报 SSL/TLS 握手错误时，核对 `25 / 465 / 587` 端口与 SSL/TLS 开关组合。
- IMAP/POP3 连接失败时，在系统设置中核对协议、端口、SSL/TLS 和账号密码。
- 邮件和 QAX 配置都保存在 PostgreSQL，不再通过 `.env` 文件修改。

## 停止与重启

只停止应用：

```bash
cd /data/podman/podman_rhel7_offline
sudo bash stop_project.sh
```

同时停止应用和 PostgreSQL：

```bash
cd /data/podman/podman_rhel7_offline
sudo STOP_DB=true bash stop_project.sh
```
