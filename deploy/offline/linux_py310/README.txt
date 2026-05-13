Linux 离线绿色包说明

一、这是什么
1. 这是自带 Python 3.10 和 Playwright Chromium 的离线绿色包。
2. 程序不会部署进 Tomcat，而是单独启动一个 uvicorn 服务。
3. 默认监听 18849 端口，可以和现有 Tomcat 共存，只要 Tomcat 没占用 18849。

二、目录说明
1. app/
   业务代码与运行入口。
2. runtime/python/
   包内 Python 运行时。
3. runtime/ms-playwright/
   包内 Playwright 浏览器内核。
4. config/
   配置文件、模板文件、浏览器证书文件。
5. local/
   运行日志、缓存、PID、临时文件。
6. service/work_flow.service
   systemd 服务模板，需要按实际部署目录调整路径。

三、部署前检查清单
1. 服务器架构是 Linux x86_64。
2. 目标目录有读写权限，建议使用固定目录，例如 /opt/work_flow_release。
3. 18849 端口未被占用。
   可用命令：ss -ltnp | grep 18849
4. 服务器能启动 Chromium 所需的系统库。
   常见依赖包括 glibc、libstdc++、libnss3、libatk-1.0、libatk-bridge-2.0、libdrm、libgbm、libX11、libxcb、libxkbcommon、libasound、fontconfig。
5. 如服务器启用了 SELinux、最小化镜像或严格安全策略，需要提前确认浏览器子进程可启动。
6. 证书材料已准备好并放入 config/。
   支持 .cer、.crt、.pem、.p12、.pfx。
7. 如果目标站点要求客户端证书登录，优先准备 .p12 或 .pfx。
   只有 .cer/.crt/.pem 往往只代表公钥或信任链，通常不足以完成客户端证书登录。
8. 如目标站点要求导入 CA 或系统信任链，需要由运维提前完成系统级导入。
9. app/.env 中的关键配置已准备：
   QAX_BASE_URL
   QAX_USERNAME
   QAX_PASSWORD
   SMTP/IMAP/POP3 相关配置

四、首次部署
1. 解压到固定目录，例如 /opt/work_flow_release
2. 进入目录后执行：
   ./install_offline.sh
3. 检查并修改 app/.env
4. 启动服务：
   ./start_system.sh
5. 停止服务：
   ./stop_system.sh
6. 启动后默认访问：
   http://127.0.0.1:18849/

五、systemd 开机自启
1. 包内自带 service/work_flow.service 模板。
2. 如果实际部署目录不是 /opt/work_flow_release，请先修改下面 4 个路径：
   WorkingDirectory
   ExecStart
   ExecStop
   PIDFile
3. 示例安装步骤：
   cp service/work_flow.service /etc/systemd/system/work_flow.service
   systemctl daemon-reload
   systemctl enable work_flow
   systemctl start work_flow
4. 查看状态：
   systemctl status work_flow

六、与 Tomcat 共存建议
1. Tomcat 保持原有端口，不需要停掉。
2. 本系统继续跑在 18849。
3. 如果需要统一入口，建议在 Nginx 或现有反向代理上转发到 127.0.0.1:18849。
4. 不建议把这个 Python 服务硬塞进 Tomcat。

七、服务器现场执行命令清单
1. 创建部署目录
   mkdir -p /opt/work_flow_release
2. 上传并解压离线包
   tar -xzf work_flow_linux_offline_py310_xxx.tar.gz -C /opt
   mv /opt/work_flow_linux_offline_py310_xxx /opt/work_flow_release
3. 进入部署目录
   cd /opt/work_flow_release
4. 检查端口
   ss -ltnp | grep 18849
5. 执行离线安装检查
   ./install_offline.sh
6. 编辑配置
   vi app/.env
7. 启动服务
   ./start_system.sh
8. 查看启动日志
   tail -n 200 local/logs/server.log
9. 验证本机访问
   curl http://127.0.0.1:18849/
10. 安装 systemd 服务
   cp service/work_flow.service /etc/systemd/system/work_flow.service
   systemctl daemon-reload
   systemctl enable work_flow
   systemctl start work_flow
11. 查看服务状态
   systemctl status work_flow
12. 查看 service 日志
   journalctl -u work_flow -n 200 --no-pager

八、升级与数据保留
1. 升级前建议执行：
   ./backup_data.sh
2. 使用升级脚本：
   ./upgrade_from_release.sh <新版本目录>
3. local/ 与 app/backend/data/ 里的运行数据需要保留。
4. config/ 中的证书和本地配置也建议保留并复核。

九、排障
1. 安装检查失败时，先看终端输出。
2. 启动失败时，优先看：
   local/logs/server.log
3. 如果是 Playwright/QAX 登录失败，重点检查：
   config/ 下证书是否为空文件
   是否只有 .cer 而没有 .p12/.pfx
   服务器系统信任链是否已导入
   Linux 系统库是否齐全
4. 如果 service 启动失败，执行：
   systemctl status work_flow
   journalctl -u work_flow -n 200 --no-pager
