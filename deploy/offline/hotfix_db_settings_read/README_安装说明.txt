Work Flow 数据库配置读取热修复包

适用问题：
1. 页面“系统设置”已经保存了 QAX、SMTP、IMAP、POP3 等配置到 PostgreSQL。
2. 发送或采集时仍提示 QAX_BASE_URL、QAX_USERNAME、QAX_PASSWORD 缺失。
3. 后台部分旧代码仍按 settings.xxx 读取旧 .env / 启动配置。

修复内容：
1. QAX 发送与采集链路改为读取数据库中的运行时配置。
2. settings.qax_*、settings.smtp_*、settings.imap_*、settings.pop3_* 等旧读取方式统一桥接到数据库配置。
3. 计划任务邮件轮询状态读取数据库中的收件协议配置。

安装方式：
1. 将本热修复包上传到内网服务器。
2. 解压：
   tar -xzf work_flow_db_settings_read_hotfix_20260521.tar.gz
3. 执行：
   cd work_flow_db_settings_read_hotfix_20260521
   bash install_db_settings_read_hotfix.sh /data/work_flow/current
4. 重启应用容器：
   podman restart work-flow
5. 查看日志：
   podman logs -f work-flow

注意事项：
1. 本补丁不会修改 PostgreSQL 数据目录 /data/sql/postgre。
2. 本补丁不会修改用户数据、任务数据、计划任务数据。
3. 安装脚本会自动备份被覆盖文件到 /data/work_flow/current/local/backup/。
