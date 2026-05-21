from __future__ import annotations

"""Restore mutable data into a Linux offline release."""

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
import shutil
import sys


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _sqlite_path_from_url(database_url: str, app_root: Path) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        return None
    raw_path = unquote(parsed.path or "")
    if database_url.startswith("sqlite:///./"):
        return app_root / database_url.removeprefix("sqlite:///./")
    if database_url.startswith("sqlite:///"):
        return Path(raw_path)
    if database_url.startswith("sqlite://"):
        return app_root / raw_path.lstrip("/")
    return None


def _database_candidates(root: Path, env_file: Path | None = None) -> list[Path]:
    app_root = root / "app"
    env_path = env_file or app_root / ".env"
    candidates = [app_root / "backend" / "data" / "app.db"]
    db_from_env = _sqlite_path_from_url(_read_env(env_path).get("DATABASE_URL", ""), app_root)
    if db_from_env is not None:
        candidates.insert(0, db_from_env)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _copy_file_if_exists(source: Path, destination: Path, label: str) -> bool:
    if not source.exists():
        print(f"Skip missing {label}: {source}")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    print(f"Restored {label}: {destination}")
    return True


def _copy_dir_if_exists(source: Path, destination: Path, label: str) -> bool:
    if not source.exists():
        print(f"Skip missing {label}: {source}")
        return False
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f"Restored {label}: {destination}")
    return True


def _backup_current_files(root: Path) -> None:
    app_root = root / "app"
    guard_dir = root / "backup" / f"_restore_guard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    guard_dir.mkdir(parents=True, exist_ok=True)

    for index, db_path in enumerate(_database_candidates(root)):
        destination = guard_dir / ("app.db" if index == 0 else f"app_extra_{index}.db")
        _copy_file_if_exists(db_path, destination, "current SQLite database guard copy")
    _copy_file_if_exists(app_root / ".env", guard_dir / ".env", "current app/.env guard copy")
    _copy_dir_if_exists(app_root / "config", guard_dir / "app_config", "current app/config guard copy")
    _copy_dir_if_exists(root / "config", guard_dir / "config", "current config guard copy")

    print(f"Created pre-restore guard backup: {guard_dir}")


def _choose_backup_dir(backup_root: Path, argv: list[str]) -> Path | None:
    if not backup_root.exists():
        print("Missing backup directory. Run ./backup_data.sh first.")
        return None

    if len(argv) > 1:
        target = backup_root / argv[1]
        if target.exists() and target.is_dir():
            return target
        print(f"Requested backup directory does not exist: {target}")
        return None

    backups = sorted(
        [item for item in backup_root.iterdir() if item.is_dir() and not item.name.startswith("_restore_guard_")],
        key=lambda item: item.name,
        reverse=True,
    )
    if not backups:
        print("No usable backup directories found. Run ./backup_data.sh first.")
        return None

    print("Available backup directories:")
    for item in backups:
        print(f"- {item.name}")
    print()
    backup_name = input("Backup directory to restore: ").strip()
    if not backup_name:
        print("No backup directory provided; restore canceled.")
        return None

    target = backup_root / backup_name
    if not target.exists() or not target.is_dir():
        print(f"Requested backup directory does not exist: {target}")
        return None
    return target


def _restore_database(backup_dir: Path, root: Path) -> bool:
    source_db = backup_dir / "app.db"
    if not source_db.exists():
        print(f"Skip missing SQLite database: {source_db}")
        return False

    env_source = backup_dir / ".env"
    destinations = _database_candidates(root, env_source if env_source.exists() else None)
    restored = False
    for destination in destinations:
        restored |= _copy_file_if_exists(source_db, destination, "SQLite database")
    return restored


def _restore_legacy_runtime_settings(backup_dir: Path, root: Path) -> bool:
    legacy = backup_dir / "config" / "runtime-settings.json"
    if not legacy.exists():
        return False
    restored = False
    for destination in (
        root / "app" / "config" / "runtime-settings.json",
        root / "config" / "runtime-settings.json",
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, destination)
        print(f"Restored legacy runtime settings: {destination}")
        restored = True
    return restored


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    backup_root = root / "backup"

    backup_dir = _choose_backup_dir(backup_root, argv)
    if backup_dir is None:
        return 1

    print()
    print(f"Restore from: {backup_dir}")
    confirm = input("Type YES to restore: ").strip()
    if confirm.upper() != "YES":
        print("Restore canceled.")
        return 1

    _backup_current_files(root)

    restored_any = False
    restored_any |= _copy_file_if_exists(backup_dir / ".env", app_root / ".env", "app/.env")
    restored_any |= _restore_database(backup_dir, root)
    restored_any |= _copy_dir_if_exists(backup_dir / "app_config", app_root / "config", "app/config")
    restored_any |= _copy_dir_if_exists(backup_dir / "config", root / "config", "config")
    restored_any |= _restore_legacy_runtime_settings(backup_dir, root)

    if not restored_any:
        print("No restorable data or config was found in the backup directory.")
        return 1

    print()
    print("Restore complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
