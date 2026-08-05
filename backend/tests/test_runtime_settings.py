from __future__ import annotations

import unittest
from unittest.mock import patch

from app import config as app_config
from app.db import Base, SessionLocal, engine
from app.services import runtime_settings


class RuntimeSettingsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_save_runtime_settings_overrides_mail_and_qax_config(self) -> None:
        with patch.object(app_config.settings, "_session_overrides", {}):
            with SessionLocal() as db:
                saved = runtime_settings.save_runtime_settings(
                    {
                        "smtp_host": "smtp.internal.example",
                        "smtp_port": 2525,
                        "smtp_use_ssl": True,
                        "mail_inbox_protocol": "pop3",
                        "mail_inbox_folders": "Replies,Archive",
                        "pop3_host": "pop.internal.example",
                        "pop3_port": 995,
                        "qax_base_url": "https://qax.internal/login",
                        "qax_ignore_https_errors": False,
                        "qax_browser_visible": True,
                    },
                    db,
                )
                db.commit()

            self.assertEqual(saved.smtp_host, "smtp.internal.example")
            self.assertEqual(saved.smtp_port, 2525)
            self.assertEqual(saved.mail_inbox_protocol, "pop3")
            self.assertEqual(saved.mail_inbox_folders, "Replies,Archive")
            self.assertEqual(saved.pop3_host, "pop.internal.example")
            self.assertEqual(saved.qax_base_url, "https://qax.internal/login")

            self.assertEqual(app_config.settings.smtp_host, "smtp.internal.example")
            self.assertEqual(app_config.settings.smtp_port, 2525)
            self.assertEqual(app_config.settings.mail_inbox_protocol, "pop3")
            self.assertEqual(app_config.settings.mail_inbox_folders, "Replies,Archive")
            self.assertEqual(app_config.settings.pop3_host, "pop.internal.example")
            self.assertEqual(app_config.settings.qax_base_url, "https://qax.internal/login")
            self.assertFalse(app_config.settings.qax_ignore_https_errors)
            self.assertFalse(app_config.settings.qax_browser_headless)

    def test_load_runtime_settings_coerces_invalid_protocol_to_imap(self) -> None:
        from app.models import AppSetting
        from app.services.runtime_settings import APP_RUNTIME_SETTINGS_KEY

        with patch.object(app_config.settings, "_session_overrides", {}):
            with SessionLocal() as db:
                db.add(AppSetting(key=APP_RUNTIME_SETTINGS_KEY, value_json='{"mail_inbox_protocol":"invalid"}'))
                db.commit()
                loaded = runtime_settings.load_runtime_settings()
            self.assertEqual(loaded.mail_inbox_protocol, app_config.base_settings.mail_inbox_protocol)
            self.assertEqual(app_config.settings.mail_inbox_protocol, app_config.base_settings.mail_inbox_protocol)


if __name__ == "__main__":
    unittest.main()
