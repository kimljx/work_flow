from __future__ import annotations

import os
from pathlib import Path


def main() -> None:
    targets = [
        Path(os.getenv("TEST_DB_PATH", "backend/data/test.db")),
        Path("./test_users.db"),
        Path("./test_delay_decision.db"),
    ]
    for target in targets:
        if target.exists():
            target.unlink()
            print(f"Removed {target}")
        else:
            print(f"Skipped missing {target}")


if __name__ == "__main__":
    main()
