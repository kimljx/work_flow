from __future__ import annotations

import os
import unittest
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_system_logs.db"

from app.db import Base, SessionLocal, engine
from app.models import AuditLog
from app.services.audit import cleanup_system_logs, write_audit
from app.timeutils import shanghai_now_naive


class SystemLogServiceTestCase(unittest.TestCase):
    """覆盖系统日志写入与过期清理的关键行为。"""

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_write_audit_records_detailed_system_log_fields(self) -> None:
        """兼容旧入口写入时，仍应补齐系统日志摘要、模块与详情信息。"""

        with SessionLocal() as db:
            write_audit(
                db=db,
                operator_id=7,
                action_type="UPDATE_TASK",
                target_type="Task",
                target_id=12,
                before={"main_status": "not_started"},
                after={"main_status": "in_progress"},
                source_ip="10.0.0.7",
                module_name="api.task",
                message="管理员更新了任务状态",
                detail={"remark": "成员已开始处理"},
            )
            db.commit()

            item = db.query(AuditLog).one()
            self.assertEqual(item.log_level, "INFO")
            self.assertEqual(item.module_name, "api.task")
            self.assertEqual(item.message, "管理员更新了任务状态")
            self.assertEqual(item.detail_json, '{"remark": "成员已开始处理"}')
            self.assertEqual(item.before_json, '{"main_status": "not_started"}')
            self.assertEqual(item.after_json, '{"main_status": "in_progress"}')
            self.assertEqual(item.source_ip, "10.0.0.7")

    def test_cleanup_system_logs_removes_only_expired_rows(self) -> None:
        """过期清理只删除保留期之外的日志，保留较新的记录供管理员追溯。"""

        with SessionLocal() as db:
            write_audit(
                db=db,
                operator_id=1,
                action_type="CREATE_TASK",
                target_type="Task",
                target_id=1,
                before={},
                after={"title": "近期任务"},
                module_name="api.task",
                message="保留期内日志",
            )
            db.flush()
            fresh_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
            fresh_log_id = fresh_log.id
            fresh_log.created_at = shanghai_now_naive() - timedelta(days=10)

            write_audit(
                db=db,
                operator_id=1,
                action_type="DELETE_TASK",
                target_type="Task",
                target_id=2,
                before={"title": "历史任务"},
                after={"deleted": True},
                module_name="api.task",
                message="过期日志",
            )
            db.flush()
            stale_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
            stale_log_id = stale_log.id
            stale_log.created_at = shanghai_now_naive() - timedelta(days=95)
            db.commit()

            deleted_count = cleanup_system_logs(db, retention_days=60)
            db.commit()

            remain_ids = {item.id for item in db.query(AuditLog).all()}
            self.assertEqual(deleted_count, 1)
            self.assertIn(fresh_log_id, remain_ids)
            self.assertNotIn(stale_log_id, remain_ids)


if __name__ == "__main__":
    unittest.main()
