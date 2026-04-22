from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_delay_decision.db"

from fastapi import HTTPException

from app.db import Base, SessionLocal, engine
from app.models import DelayRequest, Task, User
from app.services.delay import apply_delay_decision


class DelayDecisionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = User(username="admin", password_hash="x", role="admin", name="Admin", email="admin2@test.local", ip_address="2.2.2.2", is_active=True)
            member = User(username="member", password_hash="x", role="member", name="Member", email="member2@test.local", ip_address="2.2.2.3", is_active=True)
            db.add_all([admin, member])
            db.flush()
            task = Task(
                title="Task",
                content="Content",
                priority="medium",
                remark="",
                start_at=datetime(2026, 1, 1, 9, 0, 0),
                end_at=datetime(2026, 1, 10, 18, 0, 0),
                planned_minutes=100,
                created_by=admin.id,
            )
            db.add(task)
            db.flush()
            db.add(
                DelayRequest(
                    task_id=task.id,
                    applicant_id=member.id,
                    apply_reason="Need more time",
                    original_deadline=task.end_at,
                    proposed_deadline=datetime(2026, 1, 12, 18, 0, 0),
                )
            )
            db.commit()

    def test_first_decision_wins(self) -> None:
        with SessionLocal() as db:
            request_obj = db.query(DelayRequest).first()
            result, _ = apply_delay_decision(
                db=db,
                request_obj=request_obj,
                admin_id=1,
                request_id="req-1",
                action="APPROVE",
                channel="web",
                version=1,
                approved_deadline=datetime(2026, 1, 12, 18, 0, 0),
            )
            db.commit()
            self.assertEqual(result, "APPLIED")

        with SessionLocal() as db:
            request_obj = db.query(DelayRequest).first()
            with self.assertRaises(HTTPException):
                apply_delay_decision(
                    db=db,
                    request_obj=request_obj,
                    admin_id=1,
                    request_id="req-2",
                    action="REJECT",
                    channel="web",
                    version=1,
                )


if __name__ == "__main__":
    unittest.main()
