from __future__ import annotations

"""Build a Windows offline release package from the current workspace."""

import os
import shutil
import subprocess
import sys
from hashlib import sha256
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
HOST_PYTHON_CMD = ["py", "-3.11"]
BROWSER_NAME = "chromium"
RELEASE_NAME = f"work_flow_windows_offline_py310_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
RELEASE_ROOT = DIST_ROOT / RELEASE_NAME
STAGING_ROOT = DIST_ROOT / f"{RELEASE_NAME}__incomplete"


def run_command(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run an external command and fail fast on error."""

    print(f"[run] {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True, env=env)


def ensure_clean_directory(path: Path) -> None:
    """Ensure an empty output directory exists."""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_windows_text_file(source: Path, destination: Path, encoding: str = "gbk") -> None:
    """Copy a text file with CRLF line endings for Windows deployment scripts."""

    content = source.read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding=encoding, newline="\r\n")


def build_frontend_dist() -> None:
    """Rebuild frontend assets so the package matches the latest code."""

    run_command(["npm.cmd", "run", "build"], cwd=PROJECT_ROOT / "frontend")


def download_embedded_python(target_zip: Path) -> None:
    """Download the official Windows embeddable Python runtime."""

    print(f"[download] {PYTHON_EMBED_URL}")
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(PYTHON_EMBED_URL, target_zip)


def download_bootstrap_packages(target_dir: Path) -> None:
    """Download pip bootstrap wheels using the host Python."""

    target_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            *HOST_PYTHON_CMD,
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


def install_wheels_from_directory(packages_dir: Path, site_packages_dir: Path, pattern: str = "*.whl") -> None:
    """Install downloaded wheels by unpacking them into site-packages."""

    wheel_paths = sorted(packages_dir.glob(pattern))
    if not wheel_paths:
        raise RuntimeError(f"No wheel files matching {pattern!r} found in {packages_dir}")

    for wheel_path in wheel_paths:
        with ZipFile(wheel_path) as wheel_file:
            for member in wheel_file.namelist():
                normalized = Path(member)
                parts = normalized.parts
                target_path = None

                if len(parts) >= 3 and parts[0].endswith(".data") and parts[1] in {"purelib", "platlib"}:
                    target_path = site_packages_dir.joinpath(*parts[2:])
                elif len(parts) >= 2 and parts[0].endswith(".data"):
                    continue
                else:
                    target_path = site_packages_dir.joinpath(*parts)

                if member.endswith("/"):
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with wheel_file.open(member) as source, target_path.open("wb") as destination:
                    shutil.copyfileobj(source, destination)


def prepare_embedded_runtime(release_root: Path) -> Path:
    """Prepare embedded Python and preinstall packages into it."""

    runtime_root = release_root / "runtime" / "python"
    embed_zip = release_root / "runtime" / f"python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
    site_packages_dir = runtime_root / "Lib" / "site-packages"

    download_embedded_python(embed_zip)

    with ZipFile(embed_zip) as zip_file:
        zip_file.extractall(runtime_root)

    (runtime_root / "Lib").mkdir(parents=True, exist_ok=True)
    site_packages_dir.mkdir(parents=True, exist_ok=True)

    (runtime_root / "python310._pth").write_text(
        "python310.zip\n.\nLib\nLib/site-packages\nimport site\n",
        encoding="utf-8",
        newline="\r\n",
    )

    install_wheels_from_directory(release_root / "packages", site_packages_dir, "pip-*.whl")
    install_wheels_from_directory(release_root / "packages", site_packages_dir, "setuptools-*.whl")
    install_wheels_from_directory(release_root / "packages", site_packages_dir, "wheel-*.whl")
    install_wheels_from_directory(release_root / "packages", site_packages_dir, "packaging-*.whl")
    return runtime_root / "python.exe"


def download_python_packages(runtime_python: Path, target_dir: Path) -> None:
    """Download backend dependencies with the embedded Python 3.10 resolver."""

    target_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            str(runtime_python),
            "-m",
            "pip",
            "download",
            "--dest",
            str(target_dir),
            "--only-binary=:all:",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )


def install_python_packages(runtime_python: Path, release_root: Path) -> None:
    """Install backend dependencies into the embedded runtime from local wheels only."""

    run_command(
        [
            str(runtime_python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(release_root / "packages"),
            "--target",
            str(release_root / "runtime" / "python" / "Lib" / "site-packages"),
            "--upgrade",
            "-r",
            str(PROJECT_ROOT / "backend" / "requirements.txt"),
        ]
    )


def install_playwright_browser(runtime_python: Path, release_root: Path) -> None:
    """Install Chromium needed by Playwright directly into the release."""

    browser_root = release_root / "runtime" / "ms-playwright"
    browser_root.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
    env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    run_command([str(runtime_python), "-m", "playwright", "install", BROWSER_NAME], env=env)


def copytree_filtered(source: Path, destination: Path) -> None:
    """Copy a directory while skipping cache and transient files."""

    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.log"),
    )


def file_sha256(path: Path) -> str:
    """Return the SHA256 checksum of a file."""

    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_build_info(release_root: Path) -> None:
    """Write a build manifest for offline verification."""

    tracked_files = [
        PROJECT_ROOT / "frontend" / "dist" / "index.html",
        PROJECT_ROOT / "backend" / "app" / "services" / "mail.py",
        PROJECT_ROOT / "backend" / "requirements.txt",
        PROJECT_ROOT / "deploy" / "offline" / "build_windows_offline_package.py",
    ]
    lines = [
        f"release_name={RELEASE_NAME}",
        f"built_at={datetime.now().isoformat(timespec='seconds')}",
        "",
        "[sha256]",
    ]
    for path in tracked_files:
        lines.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}={file_sha256(path)}")
    lines.append("")
    (release_root / "BUILD_INFO.txt").write_text("\n".join(lines), encoding="utf-8", newline="\r\n")


def copy_release_files(release_root: Path) -> None:
    """Copy application code, scripts, and docs into the release package."""

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
    """Zip the directory release for easy transfer."""

    zip_path = release_root.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for file_path in release_root.rglob("*"):
            if file_path.is_file():
                zip_file.write(file_path, file_path.relative_to(release_root.parent))
    return zip_path


def main() -> int:
    """Build the Windows offline release package."""

    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_clean_directory(STAGING_ROOT)
    ensure_clean_directory(STAGING_ROOT / "packages")

    build_frontend_dist()
    download_bootstrap_packages(STAGING_ROOT / "packages")
    runtime_python = prepare_embedded_runtime(STAGING_ROOT)
    download_python_packages(runtime_python, STAGING_ROOT / "packages")
    install_python_packages(runtime_python, STAGING_ROOT)
    install_playwright_browser(runtime_python, STAGING_ROOT)
    copy_release_files(STAGING_ROOT)
    write_build_info(STAGING_ROOT)

    if RELEASE_ROOT.exists():
        shutil.rmtree(RELEASE_ROOT)
    STAGING_ROOT.rename(RELEASE_ROOT)

    zip_path = zip_release_directory(RELEASE_ROOT)

    print()
    print("Windows offline package generated:")
    print(f"- directory: {RELEASE_ROOT}")
    print(f"- zip: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
