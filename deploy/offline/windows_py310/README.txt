工作流系统 Windows 内网离线发布包
一、首次部署
1. 直接双击 `install_offline.bat` 完成初始化。
2. 如需修改系统名称、默认密码、邮件配置，请编辑 `app\.env`。

二、启动系统
1. 双击 `start_system.bat`。
2. 浏览器会自动打开 `http://127.0.0.1:8000/`。
3. 其他电脑如需访问，请使用“部署电脑 IP:8000”打开。

三、停止系统
1. 双击 `stop_system.bat`。

四、备份与恢复
1. 双击 `backup_data.bat` 可备份数据库与 `.env` 配置。
2. 双击 `restore_data.bat` 可从备份目录恢复数据库与 `.env`。
3. 如需恢复指定批次，可在命令行执行 `restore_data.bat 备份目录名`。
4. 恢复完成后建议重新启动系统。

五、升级旧版
1. 将新版发布包解压到新目录。
2. 执行 `upgrade_from_release.bat 旧版目录完整路径`。
3. 脚本会自动停止旧版、备份数据、恢复到新版并启动新版。

六、说明文档
- 部署手册：`docs\deploy_windows_offline.md`
- 使用手册：`docs\user_manual.md`
- 接口说明：`docs\api.md`

七、默认账号
- 管理员：`admin`
- 成员：`member`
- 默认密码取决于 `app\.env` 中的 `DEFAULT_PASSWORD`
