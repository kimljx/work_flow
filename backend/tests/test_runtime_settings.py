from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config as app_config
from app.services import runtime_settings


class RuntimeSettingsTestCase(unittest.TestCase):
    def test_save_runtime_settings_overrides_mail_and_qax_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_path = Path(tmp_dir) / "runtime-settings.json"
            with patch.object(app_config, "RUNTIME_OVERRIDE_PATH", runtime_path), patch.object(runtime_settings, "RUNTIME_SETTINGS_PATH", runtime_path), patch.object(app_config.settings, "_session_overrides", {}):
                saved = runtime_settings.save_runtime_settings(
                    {
                        "smtp_host": "smtp.internal.example",
                        "smtp_port": 2525,
                        "smtp_use_ssl": True,
                        "mail_inbox_protocol": "pop3",
                        "pop3_host": "pop.internal.example",
                        "pop3_port": 995,
                        "qax_base_url": "https://qax.internal/login",
                        "qax_ignore_https_errors": False,
                        "qax_browser_visible": True,
                    }
                )

                self.assertEqual(saved.smtp_host, "smtp.internal.example")
                self.assertEqual(saved.smtp_port, 2525)
                self.assertEqual(saved.mail_inbox_protocol, "pop3")
                self.assertEqual(saved.pop3_host, "pop.internal.example")
                self.assertEqual(saved.qax_base_url, "https://qax.internal/login")

                self.assertEqual(app_config.settings.smtp_host, "smtp.internal.example")
                self.assertEqual(app_config.settings.smtp_port, 2525)
                self.assertEqual(app_config.settings.mail_inbox_protocol, "pop3")
                self.assertEqual(app_config.settings.pop3_host, "pop.internal.example")
                self.assertEqual(app_config.settings.qax_base_url, "https://qax.internal/login")
                self.assertFalse(app_config.settings.qax_ignore_https_errors)
                self.assertFalse(app_config.settings.qax_browser_headless)

    def test_load_runtime_settings_coerces_invalid_protocol_to_imap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            runtime_path = Path(tmp_dir) / "runtime-settings.json"
            runtime_path.write_text('{"mail_inbox_protocol":"invalid"}', encoding="utf-8")
            with patch.object(app_config, "RUNTIME_OVERRIDE_PATH", runtime_path), patch.object(runtime_settings, "RUNTIME_SETTINGS_PATH", runtime_path), patch.object(app_config.settings, "_session_overrides", {}):
                loaded = runtime_settings.load_runtime_settings()
                self.assertEqual(loaded.mail_inbox_protocol, app_config.base_settings.mail_inbox_protocol)
                self.assertEqual(app_config.settings.mail_inbox_protocol, app_config.base_settings.mail_inbox_protocol)


if __name__ == "__main__":
    unittest.main()
