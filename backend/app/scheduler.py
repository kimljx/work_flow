from __future__ import annotations

from app.db import SessionLocal
from app.services.mail import diagnose_imap_settings
from app.services.notifications import create_due_reminders
from app.services.qax import collect_qax_status


def run_scheduled_jobs() -> dict[str, dict[str, str]]:
    with SessionLocal() as db:
        due_count = create_due_reminders(db)
        db.commit()
    return {
        "mail": diagnose_imap_settings(),
        "qax": collect_qax_status(),
        "due_remind": {"status": "success", "message": f"已创建 {due_count} 条到期提醒"},
    }
