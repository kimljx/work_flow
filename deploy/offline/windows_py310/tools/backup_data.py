from __future__ import annotations

"""离线发布包数据备份脚本。

负责备份：
1. SQLite 数据库 `app.db`
2. 运行配置 `.env`

备份目录按时间戳生成，便于升级前快速留档。
"""

from datetime import datetime
from pathlib import Path
import shutil
import sys


def main() -> int:
    """执行数据库与配置备份。"""
    # 当前脚本位于“发布包根目录/tools”下，上一级就是发布包根目录。
    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    backup_root = root / "backup"
    db_file = app_root / "backend" / "data" / "app.db"
    env_file = app_root / ".env"

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = backup_root / stamp
    target_dir.mkdir(parents=True, exist_ok=True)

    copied_any = False

    if db_file.exists():
        shutil.copy2(db_file, target_dir / "app.db")
        print(f"已备份数据库：{target_dir / 'app.db'}")
        copied_any = True
    else:
        print("未找到数据库文件，已跳过数据库备份。")

    if env_file.exists():
        shutil.copy2(env_file, target_dir / ".env")
        print(f"已备份配置文件：{target_dir / '.env'}")
        copied_any = True
    else:
        print("未找到 .env 配置文件，已跳过配置备份。")

    if not copied_any:
        print("当前没有可备份的数据文件。")
        return 1

    print()
    print("备份完成。")
    print(f"备份目录：{target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
