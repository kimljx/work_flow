from __future__ import annotations

"""构建 Windows 内网离线发布包。

发布包目标：
1. 目标电脑无需预装 Python、Node.js 或 Playwright 浏览器。
2. 后端依赖、QAX 所需 Chromium 浏览器和前端静态资源全部提前打入包内。
3. 输出“目录版发布包 + zip 压缩包”，方便复制、归档和升级。
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
PYTHON_DOWNLOAD_CMD = ["py", "-3.10"]
BROWSER_NAME = "chromium"
RELEASE_NAME = f"work_flow_windows_offline_py310_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
RELEASE_ROOT = DIST_ROOT / RELEASE_NAME


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """执行外部命令，并在失败时直接中断构建。"""

    print(f"[执行] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True, env=env)


def ensure_clean_directory(path: Path) -> None:
    """确保输出目录为空目录。"""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_windows_text_file(source: Path, destination: Path, encoding: str = "gbk") -> None:
    """以 Windows 文本格式复制脚本和说明文件。"""

    content = source.read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding=encoding, newline="\r\n")


def build_frontend_dist() -> None:
    """重新构建前端静态资源，确保离线包内容与当前代码一致。"""

    run_command(["npm.cmd", "run", "build"], cwd=PROJECT_ROOT / "frontend")


def download_embedded_python(target_zip: Path) -> None:
    """下载官方 Windows 嵌入式 Python 运行时。"""

    print(f"[下载] {PYTHON_EMBED_URL}")
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(PYTHON_EMBED_URL, target_zip)


def download_python_packages(target_dir: Path) -> None:
    """下载 Python 3.10 对应的离线依赖包。"""

    target_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            *PYTHON_DOWNLOAD_CMD,
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
            *PYTHON_DOWNLOAD_CMD,
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


def prepare_embedded_runtime(release_root: Path) -> Path:
    """准备内置 Python 运行时并预装依赖，返回运行时 Python 路径。"""

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
            *PYTHON_DOWNLOAD_CMD,
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
    return runtime_root / "python.exe"


def install_playwright_browser(runtime_python: Path, release_root: Path) -> None:
    """把 QAX 依赖的 Chromium 浏览器直接安装到发布包内。"""

    browser_root = release_root / "runtime" / "ms-playwright"
    browser_root.mkdir(parents=True, exist_ok=True)

    env = dict(os_environ())
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
    env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    run_command([str(runtime_python), "-m", "playwright", "install", BROWSER_NAME], env=env)


def copytree_filtered(source: Path, destination: Path) -> None:
    """复制目录，同时排除缓存文件，避免把构建噪音带入发布包。"""

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.log"),
    )


def copy_release_files(release_root: Path) -> None:
    """复制发布包所需的应用、脚本与文档。"""

    app_root = release_root / "app"
    backend_root = app_root / "backend"
    frontend_root = app_root / "frontend"
    docs_root = release_root / "docs"
    config_root = release_root / "config"
    tools_root = release_root / "tools"
    backup_root = release_root / "backup"

    copytree_filtered(PROJECT_ROOT / "backend" / "app", backend_root / "app")
    shutil.copy2(PROJECT_ROOT / "backend" / "requirements.txt", backend_root / "requirements.txt")
    shutil.copy2(PROJECT_ROOT / "backend" / "run.py", backend_root / "run.py")
    (backend_root / "data").mkdir(parents=True, exist_ok=True)

    copytree_filtered(PROJECT_ROOT / "frontend" / "dist", frontend_root / "dist")
    copytree_filtered(PROJECT_ROOT / "docs", docs_root)
    copytree_filtered(WINDOWS_TEMPLATE_ROOT / "tools", tools_root)

    config_root.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
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


def os_environ() -> dict[str, str]:
    """返回当前环境变量副本，便于构建过程追加临时变量。"""

    return dict(__import__("os").environ)


def main() -> int:
    """执行 Windows 离线发布包构建主流程。"""

    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_clean_directory(RELEASE_ROOT)
    ensure_clean_directory(RELEASE_ROOT / "packages")

    build_frontend_dist()
    download_python_packages(RELEASE_ROOT / "packages")
    runtime_python = prepare_embedded_runtime(RELEASE_ROOT)
    install_playwright_browser(runtime_python, RELEASE_ROOT)
    copy_release_files(RELEASE_ROOT)
    zip_path = zip_release_directory(RELEASE_ROOT)

    print()
    print("Windows 离线发布包已生成：")
    print(f"- 目录版：{RELEASE_ROOT}")
    print(f"- 压缩包：{zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
