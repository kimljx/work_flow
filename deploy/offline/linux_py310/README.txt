Linux 内网离线发布包说明

1. 首次使用请先执行：
   ./install_offline.sh

2. 启动系统：
   ./start_system.sh

3. 停止系统：
   ./stop_system.sh

4. 备份数据：
   ./backup_data.sh

5. 恢复数据：
   ./restore_data.sh

6. 升级旧版：
   ./upgrade_from_release.sh /旧版发布包目录

补充说明：
- QAX 所需 Chromium 浏览器已经内置在 runtime/ms-playwright 目录。
- 运行日志默认写入 local/logs/server.log。
- 配置文件路径为 app/.env。
