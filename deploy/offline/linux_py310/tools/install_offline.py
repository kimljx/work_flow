from __future__ import annotations

"""Installer checks for the Linux offline package."""

import os
import shutil
import sys
from pathlib import Path


def _print(message: str) -> None:
    print(message, flush=True)


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _certificate_files(config_root: Path) -> tuple[list[Path], list[Path]]:
    cert_suffixes = {".cer", ".crt", ".pem", ".p12", ".pfx"}
    certs = [path for path in config_root.iterdir() if path.is_file() and path.suffix.lower() in cert_suffixes]
    empty = [path for path in certs if path.stat().st_size == 0]
    return certs, empty


def _print_certificate_guidance(config_root: Path) -> None:
    certs, empty = _certificate_files(config_root)
    if certs:
        _print("[证书检查] 已发现以下证书文件：")
        for path in certs:
            _print(f"  - {path.name} ({path.stat().st_size} bytes)")
    else:
        _print("[证书检查] config/ 目录下未发现浏览器证书文件。")

    if empty:
        _print("[证书检查] 以下证书文件为空，不能用于真实登录：")
        for path in empty:
            _print(f"  - {path.name}")

    has_client_cert = any(path.suffix.lower() in {".p12", ".pfx"} and path.stat().st_size > 0 for path in certs)
    has_public_cert = any(path.suffix.lower() in {".cer", ".crt", ".pem"} and path.stat().st_size > 0 for path in certs)

    if has_public_cert and not has_client_cert:
        _print("[证书提示] 当前只有公钥/信任链证书，若目标系统要求客户端证书登录，通常还需要 .p12 或 .pfx。")
    if certs:
        _print("[证书提示] 如内网页面依赖自签发或内网 CA，仍可能需要在容器、宿主机或浏览器环境中导入信任链。")


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    app_root = root / "app"
    python_exe = root / "runtime" / "python" / "bin" / "python3.10"
    browser_root = root / "runtime" / "ms-playwright"
    config_root = root / "config"
    env_example = config_root / ".env.offline.example"
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
        _print("未找到离线包内置 Python 运行时，请确认当前目录是完整的 Linux 离线包。")
        return 1
    if not browser_root.exists():
        _print("未找到离线包内置 Playwright 浏览器，请确认当前目录是完整的 Linux 离线包。")
        return 1

    _print("")
    _print("[1/5] 初始化目录")
    _ensure_directory(backend_data_dir)
    for path in (local_root, local_home, local_temp, local_cache, local_pip_cache, local_pycache, local_logs, local_run):
        _ensure_directory(path)

    _print("[2/5] 初始化环境文件")
    if not env_file.exists():
        shutil.copy2(env_example, env_file)
        _print("已创建 app/.env，请按实际环境补充配置。")
    else:
        _print("检测到已有 app/.env，本次保留现有配置。")

    _print("[3/5] 检查证书与运行配置")
    _print(f"config 目录：{config_root}")
    _print_certificate_guidance(config_root)

    _print("[4/5] 设置本地运行环境变量")
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONPYCACHEPREFIX"] = str(local_pycache)
    os.environ["PYTHONUSERBASE"] = str(local_home)
    os.environ["PIP_CACHE_DIR"] = str(local_pip_cache)
    os.environ["TMPDIR"] = str(local_temp)
    os.environ["HOME"] = str(local_home)
    os.environ["XDG_CACHE_HOME"] = str(local_cache)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
    os.environ["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    _print("[5/5] 校验运行时依赖")
    try:
        __import__("fastapi")
        __import__("uvicorn")
        __import__("sqlalchemy")
        __import__("openpyxl")
        __import__("playwright")
    except Exception as exc:  # noqa: BLE001
        _print(f"运行时依赖校验失败：{exc}")
        return 1

    _print("")
    _print("离线包初始化完成。")
    _print(f"运行期目录：{local_root}")
    _print("若 Playwright 登录失败，请优先检查 config/ 中证书文件、信任链导入情况，以及 local/logs 下的日志。")
    _print("启动命令：./start_system.sh")

    if not silent:
        try:
            input("按回车键继续...")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
