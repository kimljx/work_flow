from __future__ import annotations

"""Build the Linux x86_64 offline release package."""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlretrieve
from zipfile import ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFLINE_ROOT = PROJECT_ROOT / "deploy" / "offline"
LINUX_TEMPLATE_ROOT = OFFLINE_ROOT / "linux_py310"
DIST_ROOT = OFFLINE_ROOT / "dist"
CACHE_ROOT = OFFLINE_ROOT / "env_cache" / "linux_py310"
CACHE_PACKAGES_ROOT = CACHE_ROOT / "packages"
CACHE_RUNTIME_ROOT = CACHE_ROOT / "runtime"
CACHE_BROWSER_ROOT = CACHE_ROOT / "ms-playwright"
COMPAT_BROWSER_REVISION = "1169"
COMPAT_BROWSER_VERSION = "136.0.7103.25"
COMPAT_BROWSER_CACHE_ROOT = OFFLINE_ROOT / "browser_cache" / f"chromium-{COMPAT_BROWSER_REVISION}"
COMPAT_BROWSER_LINUX_ROOT = COMPAT_BROWSER_CACHE_ROOT / "linux" / "chrome-linux"
COMPAT_BROWSER_ZIP = COMPAT_BROWSER_CACHE_ROOT / "chromium-linux.zip"
COMPAT_BROWSER_URLS = (
    f"https://playwright.azureedge.net/builds/chromium/{COMPAT_BROWSER_REVISION}/chromium-linux.zip",
    f"https://playwright-akamai.azureedge.net/builds/chromium/{COMPAT_BROWSER_REVISION}/chromium-linux.zip",
    f"https://playwright-verizon.azureedge.net/builds/chromium/{COMPAT_BROWSER_REVISION}/chromium-linux.zip",
)
REQUIREMENTS_PATH = PROJECT_ROOT / "backend" / "requirements.txt"
PYTHON_BUILD_HOST_CMD = [sys.executable]
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
PACKAGE_CACHE_META = CACHE_ROOT / "packages-meta.json"
RUNTIME_CACHE_META = CACHE_ROOT / "runtime-meta.json"
BROWSER_CACHE_META = CACHE_ROOT / "browser-meta.json"
RUNTIME_IMPORT_PROBE = "import fastapi, playwright, zmail, sqlalchemy, anyio, exceptiongroup"
PACKAGE_FILE_SUFFIXES = (".whl", ".gz", ".zip")
BROWSER_EXECUTABLE_GLOBS = ("chromium-*/chrome-linux/chrome",)


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print(f"[执行] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True, env=env)


def run_command_capture(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print(f"[检查] {' '.join(command)}")
    return subprocess.run(command, cwd=cwd, env=env, check=False, text=True, capture_output=True)


def ensure_clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def copy_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def copy_directory_contents(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def build_frontend_dist() -> None:
    run_command(["npm", "run", "build"], cwd=PROJECT_ROOT / "frontend")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def requirements_hash() -> str:
    return file_sha256(REQUIREMENTS_PATH)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def current_cache_meta() -> dict[str, str]:
    return {
        "requirements_sha256": requirements_hash(),
        "linux_runtime_version": LINUX_RUNTIME_VERSION,
        "linux_runtime_release": LINUX_RUNTIME_RELEASE,
        "browser_name": BROWSER_NAME,
        "browser_revision": COMPAT_BROWSER_REVISION,
        "browser_version": COMPAT_BROWSER_VERSION,
    }


def package_cache_meta() -> dict[str, str]:
    return {
        "requirements_sha256": requirements_hash(),
    }


def runtime_cache_meta() -> dict[str, str]:
    return {
        "requirements_sha256": requirements_hash(),
        "linux_runtime_version": LINUX_RUNTIME_VERSION,
        "linux_runtime_release": LINUX_RUNTIME_RELEASE,
    }


def browser_cache_meta() -> dict[str, str]:
    return {
        "browser_name": BROWSER_NAME,
        "browser_revision": COMPAT_BROWSER_REVISION,
        "browser_version": COMPAT_BROWSER_VERSION,
    }


def package_name_tokens() -> set[str]:
    names: set[str] = set()
    requirement_pattern = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
    for raw_line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = requirement_pattern.match(line)
        if not match:
            continue
        names.add(normalize_package_token(match.group(1)))
    names.update({"pip", "setuptools", "wheel", "exceptiongroup", "sniffio"})
    return names


def normalize_package_token(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


def package_dir_looks_usable(path: Path) -> bool:
    if not path.exists():
        return False
    files = [item for item in path.iterdir() if item.is_file() and item.suffix.lower() in PACKAGE_FILE_SUFFIXES]
    if not files:
        return False
    available = {normalize_package_token(item.name.split("-")[0]) for item in files}
    required = package_name_tokens()
    return required.issubset(available)


def meta_matches(path: Path, expected: dict[str, str]) -> bool:
    data = read_json(path)
    return all(data.get(key) == value for key, value in expected.items())


def discover_previous_linux_release_roots() -> list[Path]:
    roots: list[Path] = []
    if not DIST_ROOT.exists():
        return roots
    for item in sorted(DIST_ROOT.iterdir(), key=lambda candidate: candidate.name, reverse=True):
        if not item.is_dir():
            continue
        if item == RELEASE_ROOT:
            continue
        if item.name.startswith("work_flow_linux_offline_py310_"):
            roots.append(item)
    return roots


def restore_packages_from_cache_or_previous(target_dir: Path) -> bool:
    meta = package_cache_meta()
    if package_dir_looks_usable(CACHE_PACKAGES_ROOT) and meta_matches(PACKAGE_CACHE_META, meta):
        print(f"[复用] 使用项目缓存依赖包：{CACHE_PACKAGES_ROOT}")
        copy_directory_contents(CACHE_PACKAGES_ROOT, target_dir)
        return True

    return False

    for release_root in discover_previous_linux_release_roots():
        candidate = release_root / "packages"
        if package_dir_looks_usable(candidate):
            print(f"[复用] 使用旧离线包依赖包：{candidate}")
            copy_directory_contents(candidate, target_dir)
            ensure_clean_directory(CACHE_PACKAGES_ROOT)
            copy_directory_contents(candidate, CACHE_PACKAGES_ROOT)
            write_json(PACKAGE_CACHE_META, meta)
            return True
    return False


def download_python_packages(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    if restore_packages_from_cache_or_previous(target_dir):
        return

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
            str(REQUIREMENTS_PATH),
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

    ensure_clean_directory(CACHE_PACKAGES_ROOT)
    copy_directory_contents(target_dir, CACHE_PACKAGES_ROOT)
    write_json(PACKAGE_CACHE_META, package_cache_meta())


def download_linux_runtime(target_archive: Path) -> None:
    if target_archive.exists():
        print(f"[复用] 使用已缓存 Linux Python 运行时压缩包：{target_archive}")
        return
    print(f"[下载] {LINUX_RUNTIME_URL}")
    target_archive.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(LINUX_RUNTIME_URL, target_archive)


def resolve_linux_python(runtime_python_root: Path) -> Path:
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


def runtime_python_is_usable(runtime_python_root: Path) -> bool:
    try:
        runtime_python = resolve_linux_python(runtime_python_root)
    except FileNotFoundError:
        return False
    result = run_command_capture([str(runtime_python), "-c", RUNTIME_IMPORT_PROBE])
    if result.returncode == 0:
        return True
    if result.stderr:
        print(result.stderr.strip())
    return False


def restore_runtime_from_cache_or_previous(target_root: Path) -> bool:
    meta = runtime_cache_meta()
    if CACHE_RUNTIME_ROOT.exists() and meta_matches(RUNTIME_CACHE_META, meta) and runtime_python_is_usable(CACHE_RUNTIME_ROOT):
        print(f"[复用] 使用项目缓存 Python 运行时：{CACHE_RUNTIME_ROOT}")
        copy_directory(CACHE_RUNTIME_ROOT, target_root)
        return True

    for release_root in discover_previous_linux_release_roots():
        candidate = release_root / "runtime" / "python"
        if runtime_python_is_usable(candidate):
            print(f"[复用] 使用旧离线包 Python 运行时：{candidate}")
            copy_directory(candidate, target_root)
            ensure_clean_directory(CACHE_RUNTIME_ROOT)
            copy_directory_contents(candidate, CACHE_RUNTIME_ROOT)
            write_json(RUNTIME_CACHE_META, meta)
            return True
    return False


def prepare_linux_runtime(release_root: Path) -> Path:
    runtime_root = release_root / "runtime"
    runtime_python_root = runtime_root / "python"
    archive_path = CACHE_RUNTIME_ROOT / LINUX_RUNTIME_ASSET
    extract_root = runtime_root / "_extract"

    if restore_runtime_from_cache_or_previous(runtime_python_root):
        return resolve_linux_python(runtime_python_root)

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
            str(REQUIREMENTS_PATH),
        ]
    )

    ensure_clean_directory(CACHE_RUNTIME_ROOT)
    copy_directory_contents(runtime_python_root, CACHE_RUNTIME_ROOT)
    write_json(RUNTIME_CACHE_META, runtime_cache_meta())
    return runtime_python


def browser_dir_looks_usable(path: Path) -> bool:
    if not path.exists():
        return False
    return any(path.glob(pattern) for pattern in BROWSER_EXECUTABLE_GLOBS)


def compatible_browser_cache_looks_usable(path: Path) -> bool:
    return (path / f"chromium-{COMPAT_BROWSER_REVISION}" / "chrome-linux" / "chrome").exists()


def restore_browser_from_cache(target_root: Path) -> bool:
    # Do not fall back to previous release browsers here. Linux packages must
    # always use the Chromium revision paired with the pinned Playwright version.
    return False
    meta = browser_cache_meta()
    if browser_dir_looks_usable(CACHE_BROWSER_ROOT) and meta_matches(BROWSER_CACHE_META, meta):
        print(f"[复用] 使用项目缓存 Playwright 浏览器：{CACHE_BROWSER_ROOT}")
        copy_directory(CACHE_BROWSER_ROOT, target_root)
        return True

    for release_root in discover_previous_linux_release_roots():
        candidate = release_root / "runtime" / "ms-playwright"
        if browser_dir_looks_usable(candidate):
            print(f"[复用] 使用旧离线包 Playwright 浏览器：{candidate}")
            copy_directory(candidate, target_root)
            ensure_clean_directory(CACHE_BROWSER_ROOT)
            copy_directory_contents(candidate, CACHE_BROWSER_ROOT)
            write_json(BROWSER_CACHE_META, meta)
            return True
    return False


def download_compatible_browser_archive() -> None:
    if COMPAT_BROWSER_ZIP.exists():
        return
    COMPAT_BROWSER_ZIP.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in COMPAT_BROWSER_URLS:
        try:
            print(f"[browser] Download Chromium {COMPAT_BROWSER_VERSION}: {url}")
            urlretrieve(url, COMPAT_BROWSER_ZIP)
            return
        except Exception as exc:
            last_error = exc
            if COMPAT_BROWSER_ZIP.exists():
                COMPAT_BROWSER_ZIP.unlink()
            print(f"[browser] Download failed: {exc}")
    raise RuntimeError(f"Failed to download Chromium {COMPAT_BROWSER_VERSION}") from last_error


def ensure_compatible_browser_source() -> Path:
    executable = COMPAT_BROWSER_LINUX_ROOT / "chrome"
    if executable.exists():
        return COMPAT_BROWSER_LINUX_ROOT

    download_compatible_browser_archive()
    extract_root = COMPAT_BROWSER_CACHE_ROOT / "linux"
    ensure_clean_directory(extract_root)
    with ZipFile(COMPAT_BROWSER_ZIP) as zip_file:
        zip_file.extractall(extract_root)

    if executable.exists():
        return COMPAT_BROWSER_LINUX_ROOT
    raise RuntimeError(f"Chromium archive did not contain expected executable: {executable}")


def install_playwright_browser(runtime_python: Path, release_root: Path) -> None:
    browser_root = release_root / "runtime" / "ms-playwright"
    if compatible_browser_cache_looks_usable(CACHE_BROWSER_ROOT) and meta_matches(BROWSER_CACHE_META, browser_cache_meta()):
        print(f"[browser] Reuse Playwright-compatible Chromium cache: {CACHE_BROWSER_ROOT}")
        copy_directory(CACHE_BROWSER_ROOT, browser_root)
        return

    source_root = ensure_compatible_browser_source()
    target_root = browser_root / f"chromium-{COMPAT_BROWSER_REVISION}" / "chrome-linux"
    print(f"[browser] Package Playwright-compatible Chromium {COMPAT_BROWSER_VERSION}: {source_root}")
    copy_directory(source_root, target_root)
    for executable_name in ("chrome", "chrome_crashpad_handler", "chrome_sandbox"):
        executable = target_root / executable_name
        if executable.exists():
            ensure_executable(executable)
    ensure_clean_directory(CACHE_BROWSER_ROOT)
    copy_directory_contents(browser_root, CACHE_BROWSER_ROOT)
    write_json(BROWSER_CACHE_META, browser_cache_meta())


def copytree_filtered(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.log"),
    )


def copy_runtime_config_files(destination: Path) -> None:
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
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_runtime_executables(release_root: Path) -> None:
    executable_names = {
        "python",
        "python3",
        "python3.10",
        "pip",
        "pip3",
        "pip3.10",
        "uvicorn",
        "fastapi",
        "playwright",
        "dotenv",
        "2to3",
        "2to3-3.10",
        "idle3",
        "idle3.10",
        "pydoc3",
        "pydoc3.10",
        "python3-config",
        "python3.10-config",
    }
    python_bin = release_root / "runtime" / "python" / "bin"
    if python_bin.exists():
        for path in python_bin.iterdir():
            if path.is_file() and path.name in executable_names:
                ensure_executable(path)

    playwright_driver = (
        release_root
        / "runtime"
        / "python"
        / "lib"
        / "python3.10"
        / "site-packages"
        / "playwright"
        / "driver"
    )
    for path in (
        playwright_driver / "node",
        playwright_driver / "package" / "cli.js",
    ):
        if path.exists():
            ensure_executable(path)


def copy_release_files(release_root: Path) -> None:
    app_root = release_root / "app"
    backend_root = app_root / "backend"
    frontend_root = app_root / "frontend"
    app_config_root = app_root / "config"
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
    copy_runtime_config_files(app_config_root)
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
        if file_name.endswith(".sh"):
            ensure_executable(release_root / file_name)

    for script_path in tools_root.rglob("*.sh"):
        ensure_executable(script_path)
    ensure_runtime_executables(release_root)


def tar_release_directory(release_root: Path) -> Path:
    tar_path = release_root.with_suffix(".tar.gz")
    if tar_path.exists():
        tar_path.unlink()

    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(release_root, arcname=release_root.name)
    return tar_path


def main() -> int:
    if sys.platform != "linux":
        print("Linux 离线发布包请在 Linux x86_64 构建机上执行。")
        return 1

    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
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
    print(f"- 环境缓存：{CACHE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
