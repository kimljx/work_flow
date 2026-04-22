from __future__ import annotations

import pathlib
import unittest


class CleanupScriptContractTestCase(unittest.TestCase):
    def test_cleanup_script_exists(self) -> None:
        self.assertTrue(pathlib.Path("backend/scripts/cleanup_test_db.py").exists())


if __name__ == "__main__":
    unittest.main()
