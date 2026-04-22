# 常见问题排查

- 登录失败：
  - 检查后端配置中的 `DEFAULT_PASSWORD`
  - 检查是否已生成默认管理员和成员账号
- SQLite 路径错误：
  - 检查 `DATABASE_URL`
  - 检查 `backend/data` 目录是否有写权限
- 前端刷新失败：
  - 检查刷新令牌流程
  - 检查 `/api/v1/auth/refresh` 是否可访问
- 测试数据库清理：
  - 运行 `py backend/scripts/cleanup_test_db.py`
