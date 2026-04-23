from __future__ import annotations

import io
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_task_import.db"

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Task


class TaskImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def _build_workbook_bytes(self) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "任务导入模板"
        sheet.append(
            [
                "任务标题(title)",
                "任务内容(content)",
                "负责人账号(owner_username)",
                "参与者账号(participant_usernames)",
                "开始时间(start_at)",
                "结束时间(end_at)",
                "优先级(priority)",
                "备注(remark)",
                "到期前提醒天数(due_remind_days)",
                "里程碑名称(milestone_names)",
                "里程碑时间(milestone_datetimes)",
                "里程碑提醒天数(remind_offsets)",
            ]
        )
        sheet.append(
            [
                "导入测试任务",
                "通过 Excel 模板导入任务。",
                "admin",
                "member",
                "2026-05-01T09:00:00",
                "2026-05-03T18:00:00",
                "high",
                "测试备注",
                1,
                "初稿|复核",
                "2026-05-01T18:00:00|2026-05-02T18:00:00",
                "1|1,2",
            ]
        )
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def test_import_tasks_from_excel(self) -> None:
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123"})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            response = client.post(
                "/api/v1/tasks/import",
                files={
                    "file": (
                        "task-import-template.xlsx",
                        self._build_workbook_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["success_count"], 1)
            self.assertEqual(payload["failure_count"], 0)

        with SessionLocal() as db:
            task = db.query(Task).filter(Task.title == "导入测试任务").first()
            self.assertIsNotNone(task)


if __name__ == "__main__":
    unittest.main()
