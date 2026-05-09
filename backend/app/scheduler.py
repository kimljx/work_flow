from __future__ import annotations

from app.db import SessionLocal
from app.services.mail import poll_mailbox
from app.services.notifications import create_due_reminders, create_overdue_task_reminders
from app.services.qax import collect_qax_status


def run_scheduled_jobs() -> dict[str, dict[str, str]]:
    with SessionLocal() as db:
        due_count = create_due_reminders(db)
        overdue_count = create_overdue_task_reminders(db)
        mail_result = poll_mailbox(db)
        db.commit()
    return {
        "mail": {"status": str(mail_result.get("status", "")), "message": str(mail_result.get("message", ""))},
        "qax": collect_qax_status(),
        "due_remind": {"status": "success", "message": f"已创建 {due_count} 条到期提醒"},
        "overdue_remind": {"status": "success", "message": f"已创建 {overdue_count} 条延期未完成提醒"},
    }
