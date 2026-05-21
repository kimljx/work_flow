from __future__ import annotations

"""Back up mutable data from a Linux offline release."""

from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
import shutil
import sqlite3


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


def _database_candidates(root: Path) -> list[Path]:
    app_root = root / "app"
    env_file = app_root / ".env"
    candidates = [app_root / "backend" / "data" / "app.db"]
    db_from_env = _sqlite_path_from_url(_read_env(env_file).get("DATABASE_URL", ""), app_root)
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
    print(f"Backed up {label}: {destination}")
    return True


def _backup_sqlite_database(source: Path, destination: Path) -> bool:
    if not source.exists():
        print(f"Skip missing SQLite database: {source}")
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)

    source_uri = f"file:{source.as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source_conn:
        with sqlite3.connect(destination) as target_conn:
            source_conn.backup(target_conn)

    with sqlite3.connect(destination) as check_conn:
        result = check_conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError(f"SQLite backup integrity check failed for {destination}: {result}")

    print(f"Backed up SQLite database: {destination}")
    return True


def _copy_dir_if_exists(source: Path, destination: Path, label: str) -> bool:
    if not source.exists():
        print(f"Skip missing {label}: {source}")
        return False
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f"Backed up {label}: {destination}")
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    backup_root = root / "backup"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = backup_root / stamp
    target_dir.mkdir(parents=True, exist_ok=True)

    copied_any = False
    for index, db_path in enumerate(_database_candidates(root)):
        destination = target_dir / ("app.db" if index == 0 else f"app_extra_{index}.db")
        copied_any |= _backup_sqlite_database(db_path, destination)

    copied_any |= _copy_file_if_exists(app_root / ".env", target_dir / ".env", "app/.env")
    copied_any |= _copy_dir_if_exists(app_root / "config", target_dir / "app_config", "app/config")
    copied_any |= _copy_dir_if_exists(root / "config", target_dir / "config", "config")

    if not copied_any:
        print("No mutable data or config files were found to back up.")
        return 1

    print()
    print("Backup complete.")
    print(f"Backup directory: {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
