from __future__ import annotations

"""构建 Windows 内网离线发布包。

发布包目标：
1. 内网电脑只需具备 Python 3.10，无需 Node.js；
2. 所有后端依赖均提前下载为离线安装包；
3. 前端使用构建后的静态资源，由 FastAPI 统一托管；
4. 输出“目录版发布包 + zip 压缩包”，便于复制与归档。
"""

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFLINE_ROOT = PROJECT_ROOT / "deploy" / "offline"
WINDOWS_TEMPLATE_ROOT = OFFLINE_ROOT / "windows_py310"
DIST_ROOT = OFFLINE_ROOT / "dist"
PYTHON_EMBED_VERSION = "3.10.11"
PYTHON_EMBED_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_EMBED_VERSION}/"
    f"python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
)
RELEASE_NAME = f"work_flow_windows_offline_py310_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
RELEASE_ROOT = DIST_ROOT / RELEASE_NAME


def run_command(command: list[str], cwd: Path | None = None) -> None:
    """执行外部命令并在失败时直接中断。"""
    print(f"[执行] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def ensure_clean_directory(path: Path) -> None:
    """确保输出目录为空目录。"""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_windows_text_file(source: Path, destination: Path, encoding: str = "gbk") -> None:
    """按 Windows 文本习惯复制脚本与说明文件。

    这里统一转换为 CRLF 行尾，并默认使用 GBK 编码，确保在中文 Windows
    的 `cmd` 与记事本里直接打开时都能正常显示和执行。
    """
    content = source.read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding=encoding, newline="\r\n")


def build_frontend_dist() -> None:
    """重新构建前端静态资源，确保离线包中的页面与代码一致。"""
    npm_command = "npm.cmd" if sys.platform.startswith("win") else "npm"
    run_command([npm_command, "run", "build"], cwd=PROJECT_ROOT / "frontend")


def download_embedded_python(target_zip: Path) -> None:
    """下载官方 Windows 嵌入式 Python 运行时压缩包。"""
    print(f"[下载] {PYTHON_EMBED_URL}")
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(PYTHON_EMBED_URL, target_zip)


def download_python_packages(target_dir: Path) -> None:
    """下载 Python 3.10 对应的离线依赖包。"""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 使用本机 Python 3.10 环境下载与目标环境一致的依赖包，
    # 避免离线电脑安装时因为 Python 小版本或 ABI 不匹配而失败。
    run_command(
        [
            "py",
            "-3.10",
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )
    run_command(
        [
            "py",
            "-3.10",
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "pip",
            "setuptools",
            "wheel",
        ]
    )


def prepare_embedded_runtime(release_root: Path) -> None:
    """准备内置 Python 3.10 运行时并预装依赖。

    发布包内直接附带嵌入式 Python 解释器，目标机无需额外安装 Python，
    同时把后端依赖预装到运行时目录，确保开箱即可启动。
    """
    runtime_root = release_root / "runtime" / "python"
    embed_zip = release_root / "runtime" / f"python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
    site_packages_dir = runtime_root / "Lib" / "site-packages"

    download_embedded_python(embed_zip)

    with ZipFile(embed_zip) as zip_file:
        zip_file.extractall(runtime_root)

    (runtime_root / "Lib").mkdir(parents=True, exist_ok=True)
    site_packages_dir.mkdir(parents=True, exist_ok=True)

    # 嵌入式 Python 默认关闭 site 包加载，这里显式打开并补充 site-packages。
    (runtime_root / "python310._pth").write_text(
        "python310.zip\n.\nLib\nLib/site-packages\nimport site\n",
        encoding="utf-8",
        newline="\r\n",
    )

    run_command(
        [
            "py",
            "-3.10",
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(release_root / "packages"),
            "--target",
            str(site_packages_dir),
            "--upgrade",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )


def copy_release_files(release_root: Path) -> None:
    """复制发布包需要的应用、脚本与文档。"""
    app_root = release_root / "app"
    backend_root = app_root / "backend"
    frontend_root = app_root / "frontend"
    docs_root = release_root / "docs"
    config_root = release_root / "config"
    tools_root = release_root / "tools"

    shutil.copytree(PROJECT_ROOT / "backend" / "app", backend_root / "app")
    shutil.copy2(PROJECT_ROOT / "backend" / "requirements.txt", backend_root / "requirements.txt")
    shutil.copy2(PROJECT_ROOT / "backend" / "run.py", backend_root / "run.py")
    (backend_root / "data").mkdir(parents=True, exist_ok=True)

    shutil.copytree(PROJECT_ROOT / "frontend" / "dist", frontend_root / "dist")
    shutil.copytree(PROJECT_ROOT / "docs", docs_root)
    shutil.copytree(WINDOWS_TEMPLATE_ROOT / "tools", tools_root)

    config_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WINDOWS_TEMPLATE_ROOT / ".env.offline.example", config_root / ".env.offline.example")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "install_offline.bat", release_root / "install_offline.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "start_system.bat", release_root / "start_system.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "stop_system.bat", release_root / "stop_system.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "backup_data.bat", release_root / "backup_data.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "restore_data.bat", release_root / "restore_data.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "upgrade_from_release.bat", release_root / "upgrade_from_release.bat")
    copy_windows_text_file(WINDOWS_TEMPLATE_ROOT / "README.txt", release_root / "README.txt")


def zip_release_directory(release_root: Path) -> Path:
    """将目录版发布包压缩为 zip 文件。"""
    zip_path = release_root.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for file_path in release_root.rglob("*"):
            if file_path.is_file():
                zip_file.write(file_path, file_path.relative_to(release_root.parent))
    return zip_path


def main() -> int:
    """构建离线发布包主流程。"""
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_clean_directory(RELEASE_ROOT)
    ensure_clean_directory(RELEASE_ROOT / "packages")

    build_frontend_dist()
    download_python_packages(RELEASE_ROOT / "packages")
    prepare_embedded_runtime(RELEASE_ROOT)
    copy_release_files(RELEASE_ROOT)
    zip_path = zip_release_directory(RELEASE_ROOT)

    print()
    print("离线发布包已生成：")
    print(f"- 目录版：{RELEASE_ROOT}")
    print(f"- 压缩包：{zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
