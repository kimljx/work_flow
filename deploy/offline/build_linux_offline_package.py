from __future__ import annotations

"""构建 Linux x86_64 内网离线发布包。

说明：
1. 该脚本需要在 Linux x86_64 构建机上执行，才能打入匹配平台的 Python 运行时与 Playwright 浏览器。
2. 目标机无需预装 Python、Node.js 或 Playwright 浏览器。
3. 输出“目录版发布包 + tar.gz 压缩包”，便于复制、归档和升级。
"""

import os
import shutil
import stat
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlretrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFLINE_ROOT = PROJECT_ROOT / "deploy" / "offline"
LINUX_TEMPLATE_ROOT = OFFLINE_ROOT / "linux_py310"
DIST_ROOT = OFFLINE_ROOT / "dist"
PYTHON_BUILD_HOST_CMD = ["python3"]
LINUX_RUNTIME_RELEASE = "20260414"
LINUX_RUNTIME_VERSION = "3.10.20"
LINUX_RUNTIME_ASSET = (
    f"cpython-{LINUX_RUNTIME_VERSION}+{LINUX_RUNTIME_RELEASE}"
    "-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
)
LINUX_RUNTIME_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    f"{LINUX_RUNTIME_RELEASE}/{quote(LINUX_RUNTIME_ASSET)}"
)
BROWSER_NAME = "chromium"
RELEASE_NAME = f"work_flow_linux_offline_py310_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
RELEASE_ROOT = DIST_ROOT / RELEASE_NAME


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """执行外部命令，并在失败时立即终止构建。"""

    print(f"[执行] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True, env=env)


def ensure_clean_directory(path: Path) -> None:
    """确保输出目录为空目录。"""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_frontend_dist() -> None:
    """重新构建前端静态资源。"""

    run_command(["npm", "run", "build"], cwd=PROJECT_ROOT / "frontend")


def download_python_packages(target_dir: Path) -> None:
    """跨版本下载 Linux Python 3.10 对应的离线依赖包。

    这里显式指定目标平台、实现、ABI 与 Python 版本，避免构建机必须本地安装 Python 3.10。
    只要构建机有可联网的 Python 3 环境，就能提前把目标 Linux x86_64 所需 wheel 拉齐。
    """

    target_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            *PYTHON_BUILD_HOST_CMD,
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "--only-binary=:all:",
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            "310",
            "--abi",
            "cp310",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )
    # pip download may miss marker-gated runtime deps when cross-resolving for cp310.
    # Pull them explicitly so the embedded Python 3.10 runtime can install offline.
    run_command(
        [
            *PYTHON_BUILD_HOST_CMD,
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "--only-binary=:all:",
            "--platform",
            "manylinux2014_x86_64",
            "--implementation",
            "cp",
            "--python-version",
            "310",
            "--abi",
            "cp310",
            "exceptiongroup",
            "sniffio",
        ]
    )
    run_command(
        [
            *PYTHON_BUILD_HOST_CMD,
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "--only-binary=:all:",
            "pip",
            "setuptools",
            "wheel",
        ]
    )


def download_linux_runtime(target_archive: Path) -> None:
    """下载 Linux 便携 Python 运行时压缩包。"""

    print(f"[下载] {LINUX_RUNTIME_URL}")
    target_archive.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(LINUX_RUNTIME_URL, target_archive)


def resolve_linux_python(runtime_python_root: Path) -> Path:
    """定位解压后的 Python 可执行文件。"""

    candidates = [
        runtime_python_root / "bin" / "python3.10",
        runtime_python_root / "install" / "bin" / "python3.10",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    for candidate in runtime_python_root.rglob("python3.10"):
        if candidate.is_file() and candidate.parent.name == "bin":
            return candidate
    raise FileNotFoundError("未找到 Linux 离线运行时中的 python3.10")


def prepare_linux_runtime(release_root: Path) -> Path:
    """准备 Linux 内置 Python 运行时并预装依赖。"""

    runtime_root = release_root / "runtime"
    runtime_python_root = runtime_root / "python"
    archive_path = runtime_root / LINUX_RUNTIME_ASSET
    extract_root = runtime_root / "_extract"

    download_linux_runtime(archive_path)
    ensure_clean_directory(extract_root)

    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(extract_root)

    python_binary = resolve_linux_python(extract_root)
    extracted_install_root = python_binary.parent.parent

    if runtime_python_root.exists():
        shutil.rmtree(runtime_python_root)
    shutil.move(str(extracted_install_root), str(runtime_python_root))
    shutil.rmtree(extract_root)

    runtime_python = resolve_linux_python(runtime_python_root)
    run_command([str(runtime_python), "-m", "ensurepip", "--upgrade"])
    run_command(
        [
            str(runtime_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(release_root / "packages"),
            "--upgrade",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )
    return runtime_python


def install_playwright_browser(runtime_python: Path, release_root: Path) -> None:
    """将 QAX 依赖的 Chromium 浏览器安装到发布包内。"""

    browser_root = release_root / "runtime" / "ms-playwright"
    browser_root.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
    env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    run_command([str(runtime_python), "-m", "playwright", "install", BROWSER_NAME], env=env)


def copytree_filtered(source: Path, destination: Path) -> None:
    """复制目录，同时排除缓存文件。"""

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.log"),
    )


def copy_runtime_config_files(destination: Path) -> None:
    """复制运行期配置文件，并将浏览器证书一并打入离线包。"""

    source_root = PROJECT_ROOT / "config"
    destination.mkdir(parents=True, exist_ok=True)
    if not source_root.exists():
        return

    allowed_suffixes = {".json", ".md", ".txt", ".xlsx", ".cer", ".crt", ".pem", ".p12", ".pfx"}
    for source_path in source_root.iterdir():
        if not source_path.is_file():
            continue
        if source_path.suffix.lower() not in allowed_suffixes:
            continue
        shutil.copy2(source_path, destination / source_path.name)


def ensure_executable(path: Path) -> None:
    """为 shell 脚本补充可执行权限。"""

    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_release_files(release_root: Path) -> None:
    """复制 Linux 离线发布包所需文件。"""

    app_root = release_root / "app"
    backend_root = app_root / "backend"
    frontend_root = app_root / "frontend"
    docs_root = release_root / "docs"
    config_root = release_root / "config"
    tools_root = release_root / "tools"
    backup_root = release_root / "backup"
    service_root = release_root / "service"

    copytree_filtered(PROJECT_ROOT / "backend" / "app", backend_root / "app")
    shutil.copy2(PROJECT_ROOT / "backend" / "requirements.txt", backend_root / "requirements.txt")
    shutil.copy2(PROJECT_ROOT / "backend" / "run.py", backend_root / "run.py")
    (backend_root / "data").mkdir(parents=True, exist_ok=True)

    copytree_filtered(PROJECT_ROOT / "frontend" / "dist", frontend_root / "dist")
    copytree_filtered(PROJECT_ROOT / "docs", docs_root)
    copytree_filtered(LINUX_TEMPLATE_ROOT / "tools", tools_root)

    copy_runtime_config_files(config_root)
    backup_root.mkdir(parents=True, exist_ok=True)
    service_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LINUX_TEMPLATE_ROOT / ".env.offline.example", config_root / ".env.offline.example")
    shutil.copy2(PROJECT_ROOT / "deploy" / "linux" / "systemd.service", service_root / "work_flow.service")

    for file_name in (
        "install_offline.sh",
        "start_system.sh",
        "stop_system.sh",
        "backup_data.sh",
        "restore_data.sh",
        "upgrade_from_release.sh",
        "README.txt",
        "DEPLOY_ON_LINUX_SERVER.txt",
    ):
        shutil.copy2(LINUX_TEMPLATE_ROOT / file_name, release_root / file_name)
        ensure_executable(release_root / file_name)

    for script_path in tools_root.rglob("*.sh"):
        ensure_executable(script_path)


def tar_release_directory(release_root: Path) -> Path:
    """将目录版发布包压缩为 tar.gz 文件。"""

    tar_path = release_root.with_suffix(".tar.gz")
    if tar_path.exists():
        tar_path.unlink()

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(release_root, arcname=release_root.name)
    return tar_path


def main() -> int:
    """执行 Linux 离线发布包构建主流程。"""

    if sys.platform != "linux":
        print("Linux 离线发布包请在 Linux x86_64 构建机上执行。")
        return 1

    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_clean_directory(RELEASE_ROOT)
    ensure_clean_directory(RELEASE_ROOT / "packages")

    build_frontend_dist()
    download_python_packages(RELEASE_ROOT / "packages")
    runtime_python = prepare_linux_runtime(RELEASE_ROOT)
    install_playwright_browser(runtime_python, RELEASE_ROOT)
    copy_release_files(RELEASE_ROOT)
    tar_path = tar_release_directory(RELEASE_ROOT)

    print()
    print("Linux 离线发布包已生成：")
    print(f"- 目录版：{RELEASE_ROOT}")
    print(f"- 压缩包：{tar_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
