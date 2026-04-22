# 后端说明

- 入口：`backend/app/main.py`
- 数据模型：`backend/app/models.py`
- 认证与令牌：`backend/app/security.py`
- 服务层职责：
  - 模板排序与匹配
  - 延期审批邮件解析
  - 延期审批原子生效
  - 通知收件人去重生成
  - 最后一个管理员保护

测试说明：
- 单元测试位于 `backend/tests`
- 测试库清理脚本位于 `backend/scripts/cleanup_test_db.py`
