from __future__ import annotations

"""离线发布包数据恢复脚本。

恢复前会先把当前版本中的数据库与配置再做一份保护性备份，
避免误恢复后无法回退。
"""

from datetime import datetime
from pathlib import Path
import shutil
import sys


def _backup_current_files(root: Path, db_file: Path, env_file: Path) -> None:
    """在覆盖恢复前先备份当前数据。"""
    guard_dir = root / "backup" / f"_restore_guard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    guard_dir.mkdir(parents=True, exist_ok=True)

    if db_file.exists():
        shutil.copy2(db_file, guard_dir / "app.db")
    if env_file.exists():
        shutil.copy2(env_file, guard_dir / ".env")

    print(f"已先备份当前数据到：{guard_dir}")


def _choose_backup_dir(backup_root: Path, argv: list[str]) -> Path | None:
    """确定要恢复的备份目录。"""
    backups = sorted(
        [item for item in backup_root.iterdir() if item.is_dir() and not item.name.startswith("_restore_guard_")],
        key=lambda item: item.name,
        reverse=True,
    )
    if not backups:
        print("未找到可用备份目录，请先执行 backup_data.bat。")
        return None

    if len(argv) > 1:
        target = backup_root / argv[1]
        if target.exists() and target.is_dir():
            return target
        print(f"指定的备份目录不存在：{target}")
        return None

    print("可用备份列表：")
    for item in backups:
        print(f"- {item.name}")
    print()
    backup_name = input("请输入要恢复的备份目录名称：").strip()
    if not backup_name:
        print("未输入备份目录名称，已取消恢复。")
        return None

    target = backup_root / backup_name
    if not target.exists() or not target.is_dir():
        print(f"指定的备份目录不存在：{target}")
        return None
    return target


def main(argv: list[str]) -> int:
    """执行数据库与配置恢复。"""
    # 当前脚本位于“发布包根目录/tools”下，上一级就是发布包根目录。
    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    backup_root = root / "backup"
    db_file = app_root / "backend" / "data" / "app.db"
    env_file = app_root / ".env"

    backup_dir = _choose_backup_dir(backup_root, argv)
    if backup_dir is None:
        return 1

    print()
    print(f"即将从以下目录恢复：{backup_dir}")
    confirm = input("请输入 YES 确认恢复：").strip()
    if confirm.upper() != "YES":
        print("已取消恢复。")
        return 1

    db_file.parent.mkdir(parents=True, exist_ok=True)
    _backup_current_files(root, db_file, env_file)

    source_db = backup_dir / "app.db"
    source_env = backup_dir / ".env"

    if source_db.exists():
        shutil.copy2(source_db, db_file)
        print("已恢复数据库文件。")
    else:
        print("备份中未找到 app.db，数据库未恢复。")

    if source_env.exists():
        shutil.copy2(source_env, env_file)
        print("已恢复 .env 配置文件。")
    else:
        print("备份中未找到 .env，配置文件未恢复。")

    print()
    print("恢复完成。建议重新启动系统使配置与数据生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
