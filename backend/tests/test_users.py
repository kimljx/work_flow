from __future__ import annotations

import os
import unittest

os.environ["DATABASE_URL"] = "sqlite:///./test_users.db"

from fastapi import HTTPException

from app.db import Base, SessionLocal, engine
from app.models import User
from app.services.users import ensure_last_admin_not_removed


class UserProtectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            db.add(User(username="admin", password_hash="x", role="admin", name="Admin", email="admin@test.local", ip_address="1.1.1.1", is_active=True))
            db.commit()

    def test_last_admin_cannot_be_disabled(self) -> None:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "admin").first()
            self.assertIsNotNone(user)
            with self.assertRaises(HTTPException):
                ensure_last_admin_not_removed(db, user, new_role="member", new_active=False)


if __name__ == "__main__":
    unittest.main()
