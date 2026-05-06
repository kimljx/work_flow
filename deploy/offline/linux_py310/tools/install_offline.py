from __future__ import annotations

"""Linux 离线发布包本地化安装脚本。

职责：
1. 初始化发布包内的本地运行目录、缓存目录和日志目录。
2. 自动生成 `.env` 配置文件。
3. 校验内置 Python、后端依赖与 Playwright 浏览器是否齐全。
"""

from pathlib import Path
import os
import shutil
import sys


def _print(message: str) -> None:
    """统一输出安装日志。"""

    print(message, flush=True)


def _ensure_directory(path: Path) -> None:
    """确保目录存在。"""

    path.mkdir(parents=True, exist_ok=True)


def main(argv: list[str]) -> int:
    """执行 Linux 离线安装初始化流程。"""

    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    python_exe = root / "runtime" / "python" / "bin" / "python3.10"
    browser_root = root / "runtime" / "ms-playwright"
    env_example = root / "config" / ".env.offline.example"
    env_file = app_root / ".env"
    backend_data_dir = app_root / "backend" / "data"

    local_root = root / "local"
    local_home = local_root / "home"
    local_temp = local_root / "temp"
    local_cache = local_root / "cache"
    local_pip_cache = local_cache / "pip"
    local_pycache = local_cache / "pycache"
    local_logs = local_root / "logs"
    local_run = local_root / "run"

    silent = "--silent" in argv[1:]

    if not python_exe.exists():
        _print("未找到内置 Python 运行时，请重新生成 Linux 离线发布包。")
        return 1
    if not browser_root.exists():
        _print("未找到内置 Playwright 浏览器目录，请重新生成 Linux 离线发布包。")
        return 1

    _print("")
    _print("[1/4] 初始化本地目录")
    _ensure_directory(backend_data_dir)
    for path in (local_root, local_home, local_temp, local_cache, local_pip_cache, local_pycache, local_logs, local_run):
        _ensure_directory(path)

    _print("[2/4] 初始化环境配置")
    if not env_file.exists():
        shutil.copy2(env_example, env_file)
        _print("已自动生成 app/.env，请按实际情况补充邮件、QAX 等配置。")
    else:
        _print("检测到现有 app/.env，保留原配置不覆盖。")

    _print("[3/4] 锁定本地运行环境")
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONPYCACHEPREFIX"] = str(local_pycache)
    os.environ["PYTHONUSERBASE"] = str(local_home)
    os.environ["PIP_CACHE_DIR"] = str(local_pip_cache)
    os.environ["TMPDIR"] = str(local_temp)
    os.environ["HOME"] = str(local_home)
    os.environ["XDG_CACHE_HOME"] = str(local_cache)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
    os.environ["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    _print("[4/4] 验证内置运行时")
    try:
        __import__("fastapi")
        __import__("uvicorn")
        __import__("sqlalchemy")
        __import__("openpyxl")
        __import__("playwright")
    except Exception as exc:  # noqa: BLE001
        _print(f"内置运行时校验失败：{exc}")
        return 1

    _print("内置运行时检查通过。")
    _print(f"本地运行目录：{local_root}")
    _print("所有依赖、浏览器、缓存、临时文件和运行环境均保留在发布包目录内。")
    _print("")
    _print("Linux 离线安装完成。")
    _print("现在可执行 ./start_system.sh 启动系统。")

    if not silent:
        try:
            input("按回车键继续...")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
