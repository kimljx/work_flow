from __future__ import annotations

import io
import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_task_import.db"

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Task, TaskImportHistory, User
from app.security import hash_password


class TaskImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            db.add_all(
                [
                    User(
                        username="admin",
                        password_hash=hash_password("ChangeMe123"),
                        role="admin",
                        name="系统管理员",
                        email="admin@example.com",
                        ip_address="10.0.0.1",
                        is_active=True,
                    ),
                    User(
                        username="member",
                        password_hash=hash_password("ChangeMe123"),
                        role="member",
                        name="默认成员",
                        email="member@example.com",
                        ip_address="10.0.0.2",
                        is_active=True,
                    ),
                ]
            )
            db.commit()

    def _build_workbook_bytes(self) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "任务导入模板"
        sheet.append(
            [
                "任务标题(title)",
                "任务内容(content)",
                "负责人姓名(owner_name)",
                "参与人员姓名(participant_names)",
                "开始时间(start_at)",
                "结束时间(end_at)",
                "优先级(priority)",
                "备注(remark)",
                "到期前提醒天数(due_remind_days)",
                "里程碑名称(milestone_names)",
                "里程碑时间(milestone_datetimes)",
                "里程碑提醒天数(remind_offsets)",
                "子任务标题(subtask_titles)",
                "子任务内容(subtask_contents)",
                "子任务执行人姓名(subtask_assignee_names)",
            ]
        )
        sheet.append(
            [
                "导入测试任务",
                "通过 Excel 模板导入任务。",
                "系统管理员",
                "默认成员",
                "2026-05-01T09:00:00",
                "2026-05-03T18:00:00",
                "high",
                "测试备注",
                1,
                "初稿|复核",
                "2026-05-01T18:00:00|2026-05-02T18:00:00",
                "1|1,2",
                "整理原始数据|提交汇总",
                "清洗并整理导入数据|输出最终汇总文档",
                "默认成员|系统管理员",
            ]
        )
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def _build_overlap_workbook_bytes(self) -> bytes:
        """构造用于重复导入检测的多行 Excel，确保能触发二次确认阈值。"""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "任务导入模板"
        sheet.append(
            [
                "任务标题(title)",
                "任务内容(content)",
                "负责人姓名(owner_name)",
                "参与人员姓名(participant_names)",
                "开始时间(start_at)",
                "结束时间(end_at)",
                "优先级(priority)",
                "备注(remark)",
                "到期前提醒天数(due_remind_days)",
                "里程碑名称(milestone_names)",
                "里程碑时间(milestone_datetimes)",
                "里程碑提醒天数(remind_offsets)",
                "子任务标题(subtask_titles)",
                "子任务内容(subtask_contents)",
                "子任务执行人姓名(subtask_assignee_names)",
            ]
        )
        for index in range(1, 4):
            sheet.append(
                [
                    f"重复导入测试任务{index}",
                    f"第 {index} 条重复检测样例",
                    "系统管理员",
                    "默认成员",
                    f"2026-05-0{index}T09:00:00",
                    f"2026-05-0{index + 1}T18:00:00",
                    "medium",
                    "重复检测",
                    1,
                    "",
                    "",
                    "",
                    f"子任务{index}",
                    f"处理第 {index} 条样例",
                    "默认成员",
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
                data={"confirm_duplicate": "false"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["success_count"], 1)
            self.assertEqual(payload["failure_count"], 0)

            list_response = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(list_response.status_code, 200)
            task_summary = list_response.json()[0]
            self.assertEqual(task_summary["subtask_count"], 2)
            self.assertEqual(task_summary["subtask_status_summary"][0]["status"], "pending")
            self.assertEqual(task_summary["subtask_status_summary"][0]["count"], 2)

        with SessionLocal() as db:
            task = db.query(Task).filter(Task.title == "导入测试任务").first()
            self.assertIsNotNone(task)
            self.assertEqual(len(task.subtasks), 2)
            self.assertEqual(db.query(TaskImportHistory).count(), 1)

    def test_import_overlap_preview_and_history_detail(self) -> None:
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123"})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]
            workbook_bytes = self._build_overlap_workbook_bytes()

            first_response = client.post(
                "/api/v1/tasks/import",
                files={
                    "file": (
                        "task-import-template.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={"confirm_duplicate": "false"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(first_response.json()["success_count"], 3)

            preview_response = client.post(
                "/api/v1/tasks/import",
                files={
                    "file": (
                        "task-import-template.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={"confirm_duplicate": "false"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(preview_response.status_code, 200)
            preview_payload = preview_response.json()
            self.assertTrue(preview_payload["needs_confirmation"])
            self.assertEqual(preview_payload["overlap_count"], 3)
            self.assertGreaterEqual(len(preview_payload["overlap_samples"]), 1)

            confirmed_response = client.post(
                "/api/v1/tasks/import",
                files={
                    "file": (
                        "task-import-template.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                data={"confirm_duplicate": "true"},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(confirmed_response.status_code, 200)
            self.assertEqual(confirmed_response.json()["success_count"], 3)

            histories_response = client.get("/api/v1/tasks/import-histories", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(histories_response.status_code, 200)
            histories = histories_response.json()
            self.assertEqual(len(histories), 2)
            self.assertTrue(histories[0]["confirmed_duplicate"])
            self.assertEqual(histories[0]["overlap_count"], 3)
            self.assertGreaterEqual(len(histories[0]["overlap_samples"]), 1)


if __name__ == "__main__":
    unittest.main()
