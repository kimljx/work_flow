from __future__ import annotations

"""QAX 即时消息自动化服务。

本模块把 Playwright codegen 录制脚本收敛为可复用的发送与状态采集能力，
供通知模块在创建即时消息通知时直接调用。由于 QAX 登录态有效期较短，
发送与采集都会在各自会话内重新登录，避免依赖不稳定的浏览器缓存状态。

注意：
- 对外仍保留同步函数签名，便于现有通知服务直接复用。
- 内部统一改为 Playwright async API，避免在 FastAPI 的 asyncio 事件循环中误用 sync API。
"""

import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, settings
from app.models import Notification, NotificationRecipient, Task, TaskStatusEvent, User
from app.services.runtime_settings import load_runtime_settings
from app.services.templates import strip_reply_guides
from app.timeutils import shanghai_now_naive


QAX_ROW_PENDING_STATUSES = ("准备中", "执行中")
QAX_ROW_DELIVERED_STATUSES = ("执行结束",)
QAX_ROW_FAILED_STATUSES = ("已取消",)
QAX_DETAIL_UNREAD_STATUSES = ("未接收", "正在执行")
QAX_DETAIL_READ_STATUSES = ("执行成功",)
QAX_DETAIL_FAILED_STATUSES = ("执行失败",)


QAX_BROWSER_EXECUTABLE_GLOBS = (
    "chromium-*/chrome-win/chrome.exe",
    "chromium-*/chrome-linux/chrome",
    "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
)
QAX_DEBUG_DIR = PROJECT_ROOT / "local" / "logs" / "qax_debug"
QAX_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
_qax_collect_lock = Lock()


@dataclass(frozen=True)
class QaxCertificateState:
    system_trust_required: bool = True


def _has_bundled_chromium(root: Path) -> bool:
    return any(root.glob(pattern) for pattern in QAX_BROWSER_EXECUTABLE_GLOBS)


def _detect_qax_certificates() -> QaxCertificateState:
    return QaxCertificateState()


def _validate_qax_certificates() -> QaxCertificateState:
    return _detect_qax_certificates()


def _build_qax_certificate_hint(state: QaxCertificateState) -> str:
    return (
        "QAX 证书采用系统级信任链导入方式，项目不会读取 config/ 下的证书文件。"
        "请确认宿主机和应用容器运行环境都已信任目标站点证书链；"
        "如目标站点要求客户端证书，也应导入系统或浏览器运行环境的证书存储。"
    )


def _is_qax_certificate_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    keywords = (
        "err_cert",
        "ssl",
        "tls",
        "certificate",
        "client auth cert",
        "https",
        "net::err",
    )
    return any(keyword in message for keyword in keywords)


def _wrap_qax_startup_error(exc: BaseException, state: QaxCertificateState) -> QaxAutomationError:
    message = str(exc).strip() or exc.__class__.__name__
    if "glibc_2.18" in message.lower() or "libc.so.6" in message.lower():
        return QaxAutomationError(
            "QAX 浏览器启动失败，当前 Linux 系统的 glibc 版本过低，内置 Chromium 无法运行。"
            "请重新打包适配当前 Linux 服务器的离线版本，或更换到 glibc 版本兼容的服务器。"
            f"原始错误：{message}"
        )
    if _is_qax_certificate_error(exc):
        return QaxAutomationError(f"QAX 浏览器登录出现证书/TLS 错误：{message}。{_build_qax_certificate_hint(state)}")
    return QaxAutomationError(message)


def _ensure_local_playwright_browser_path() -> None:
    """Prefer the browser bundled inside the offline package."""
    configured = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if configured and _has_bundled_chromium(Path(configured)):
        return
    current = Path(__file__).resolve()
    candidates = [
        current.parents[4] / "runtime" / "ms-playwright",
        current.parents[3] / "runtime" / "ms-playwright",
        Path.cwd() / "runtime" / "ms-playwright",
    ]
    for candidate in candidates:
        if candidate.exists():
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(candidate)
            os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_GC", "1")
            return


def _qax_debug_dir() -> Path:
    return PROJECT_ROOT / "local" / "logs" / "qax_debug"


def _ensure_qax_runtime_directories() -> None:
    """Create writable local runtime directories before launching Playwright."""
    local_root = PROJECT_ROOT / "local"
    targets = {
        "HOME": local_root / "home",
        "TMPDIR": local_root / "temp",
        "XDG_CACHE_HOME": local_root / "cache",
        "PYTHONPYCACHEPREFIX": local_root / "cache" / "pycache",
        "PIP_CACHE_DIR": local_root / "cache" / "pip",
    }
    for path in (
        local_root / "logs",
        local_root / "run",
        _qax_debug_dir(),
        *targets.values(),
    ):
        path.mkdir(parents=True, exist_ok=True)
    for key, path in targets.items():
        os.environ[key] = str(path)


def _local_chromium_executable() -> str | None:
    browser_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if not browser_root:
        return None
    root = Path(browser_root)
    for pattern in QAX_BROWSER_EXECUTABLE_GLOBS:
        candidates = sorted(root.glob(pattern), reverse=True)
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    return None


def _check_chromium_runtime_dependencies(executable_path: str | None) -> None:
    if not executable_path or sys.platform.startswith("win"):
        return
    executable = Path(executable_path)
    if not executable.exists():
        return
    try:
        result = subprocess.run(
            ["ldd", str(executable)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return
    output = "\n".join(item for item in (result.stdout, result.stderr) if item)
    missing_lines = [line.strip() for line in output.splitlines() if "not found" in line]
    if missing_lines:
        missing = "; ".join(missing_lines)
        raise QaxAutomationError(f"QAX 浏览器缺少 Linux 系统依赖库，请先在服务器补齐后再采集：{missing}")


def _format_request_failure(request: Any) -> str:
    failure = getattr(request, "failure", None)
    if callable(failure):
        try:
            failure = failure()
        except Exception as exc:  # noqa: BLE001
            failure = str(exc)
    return f"{getattr(request, 'method', '')} {getattr(request, 'url', '')} -> {failure or 'failed'}"


@dataclass
class QaxTaskStatus:
    """描述单条 QAX 任务的查询结果。"""

    task_name: str
    found: bool
    row_text: str = ""
    delivery_status: str = "pending"
    read_status: str = "unread"
    read_at: str = ""
    detail: str = ""


class QaxAutomationError(RuntimeError):
    """QAX 自动化执行失败时抛出的统一异常。"""


def _load_playwright() -> Any:
    """按需加载 Playwright async API。"""

    _ensure_local_playwright_browser_path()
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover
        raise QaxAutomationError("未安装 Playwright，请先执行 pip install playwright 并安装浏览器内核") from exc
    return async_playwright, PlaywrightTimeoutError


def sanitize_qax_content(content: str) -> str:
    """清洗 QAX 正文，移除邮件专属回复指引并压缩空行。"""

    normalized = strip_reply_guides(content or "")
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    return "\n".join(lines).strip()


def build_qax_task_name(notification: Notification, recipient: NotificationRecipient, task: Task | None) -> str:
    """为单个接收人生成稳定且不重复的 QAX 任务名称。"""

    title = re.sub(r"\s+", "", task.title if task else "system")
    title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_-]", "", title)[:18] or "task"
    return f"WF-{notification.id}-{recipient.user_id}-{notification.notify_type}-{title}"


def _ensure_qax_settings() -> None:
    """校验数据库中的 QAX 必填配置，避免缺少运行时业务配置时继续发送或采集。"""

    runtime = load_runtime_settings()
    missing_items = []
    if not runtime.qax_base_url:
        missing_items.append("QAX 登录地址")
    if not runtime.qax_username:
        missing_items.append("QAX 用户名")
    if not runtime.qax_password:
        missing_items.append("QAX 密码")
    if missing_items:
        raise QaxAutomationError(f"QAX 配置不完整，请在系统设置中补充：{', '.join(missing_items)}")


async def _click_if_visible(locator: Any, timeout_ms: int = 1200) -> bool:
    """在元素可见时执行点击。"""

    try:
        if await locator.count() > 0 and await locator.first.is_visible(timeout=timeout_ms):
            await locator.first.click(timeout=timeout_ms)
            return True
    except Exception:
        return False
    return False


class QaxAutomationClient:
    """QAX Playwright 自动化客户端。"""

    def __init__(self) -> None:
        self._playwright_cm: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._runtime = load_runtime_settings()
        self.page: Any | None = None
        self._timeout_error: Any | None = None
        self._console_messages: list[str] = []
        self._page_errors: list[str] = []
        self._request_failures: list[str] = []
        self._bad_responses: list[str] = []

    async def __aenter__(self) -> "QaxAutomationClient":
        _ensure_qax_runtime_directories()
        _ensure_local_playwright_browser_path()
        async_playwright, timeout_error = _load_playwright()
        self._timeout_error = timeout_error
        self._playwright_cm = async_playwright()
        playwright = await self._playwright_cm.start()
        certificate_state = _validate_qax_certificates()
        try:
            runtime = load_runtime_settings()
            self._runtime = runtime
            launch_options = {
                "headless": not runtime.qax_browser_visible,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            }
            executable_path = _local_chromium_executable()
            if executable_path:
                _check_chromium_runtime_dependencies(executable_path)
                launch_options["executable_path"] = executable_path
            self._browser = await playwright.chromium.launch(**launch_options)
            self._context = await self._browser.new_context(
                ignore_https_errors=runtime.qax_ignore_https_errors,
                locale="zh-CN",
                user_agent=QAX_BROWSER_USER_AGENT,
                viewport={"width": 1366, "height": 768},
            )
            self.page = await self._context.new_page()
            self._attach_page_diagnostics()
            await self._login_and_open_task_page()
            return self
        except Exception as exc:
            await self.__aexit__(type(exc), exc, exc.__traceback__)
            raise _wrap_qax_startup_error(exc, certificate_state) from exc

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright_cm is not None:
            await self._playwright_cm.__aexit__(exc_type, exc, tb)

    def _attach_page_diagnostics(self) -> None:
        assert self.page is not None

        def on_console(message: Any) -> None:
            self._console_messages.append(f"{message.type}: {message.text}")

        def on_page_error(error: Any) -> None:
            self._page_errors.append(str(error))

        def on_request_failed(request: Any) -> None:
            self._request_failures.append(_format_request_failure(request))

        def on_response(response: Any) -> None:
            status = getattr(response, "status", 0)
            if status >= 400:
                self._bad_responses.append(f"{status} {getattr(response, 'url', '')}")

        self.page.on("console", on_console)
        self.page.on("pageerror", on_page_error)
        self.page.on("requestfailed", on_request_failed)
        self.page.on("response", on_response)

    async def _dump_qax_debug_artifacts(self, label: str) -> Path:
        assert self.page is not None
        debug_dir = _qax_debug_dir()
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = debug_dir / f"{timestamp}_{label}"

        try:
            await self.page.screenshot(path=str(prefix.with_suffix(".png")), full_page=True, timeout=10000)
        except Exception as exc:  # noqa: BLE001
            prefix.with_suffix(".screenshot_error.txt").write_text(str(exc), encoding="utf-8")

        try:
            prefix.with_suffix(".html").write_text(await self.page.content(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            prefix.with_suffix(".html_error.txt").write_text(str(exc), encoding="utf-8")

        diagnostics = [
            f"url: {self.page.url}",
            "",
            "[console]",
            *self._console_messages[-200:],
            "",
            "[pageerror]",
            *self._page_errors[-100:],
            "",
            "[requestfailed]",
            *self._request_failures[-100:],
            "",
            "[bad_responses]",
            *self._bad_responses[-100:],
        ]
        prefix.with_suffix(".log").write_text("\n".join(diagnostics), encoding="utf-8")
        return prefix

    async def _login_and_open_task_page(self) -> None:
        """登录 QAX 并进入“资产管理 -> 终端任务”页面。"""

        assert self.page is not None
        runtime = load_runtime_settings()
        self._runtime = runtime
        await self.page.goto(runtime.qax_base_url, wait_until="domcontentloaded", timeout=60000)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        username_input = self.page.get_by_placeholder("用户名/手机号/邮箱")
        try:
            await username_input.wait_for(state="visible", timeout=30000)
            await username_input.fill(runtime.qax_username)
        except Exception as exc:
            debug_prefix = await self._dump_qax_debug_artifacts("login_username_missing")
            raise QaxAutomationError(
                "QAX 登录页未出现“用户名/手机号/邮箱”输入框，页面可能停留在加载状态。"
                f"已保存诊断文件：{debug_prefix}.png / {debug_prefix}.html / {debug_prefix}.log"
            ) from exc
        await self.page.get_by_role("button", name="下一步").click()
        await self.page.get_by_placeholder("请输入密码").fill(runtime.qax_password)
        await self.page.get_by_role("button", name="立即登录").click()
        await self.page.wait_for_timeout(500)

        # 登录后可能会有确认弹窗，但不是每次都有，这里只做兼容点击。
        await self.page.get_by_role("button", name="确 认").click()
        await self.page.get_by_role("button", name="我知道了").click()

        await self.page.get_by_text("资产管理", exact=True).click()
        await self.page.get_by_role("link", name="终端任务").click()

    async def create_instant_message_task(
        self,
        *,
        task_name: str,
        message_title: str,
        message_content: str,
        publisher_name: str,
        recipient_ip: str,
    ) -> None:
        """按录制脚本创建一条即时消息任务。"""

        assert self.page is not None
        page = self.page
        runtime = load_runtime_settings()
        self._runtime = runtime
        await page.get_by_role("button", name="新建").click()
        await page.get_by_placeholder("请输入").first.fill(task_name)
        await page.get_by_placeholder("请选择任务类型").click()
        await page.get_by_title("即时消息").click()
        await page.get_by_placeholder("请输入消息标题").fill(message_title)
        await page.locator(".ql-editor").fill(message_content)
        await page.get_by_placeholder("请输入发布人").fill(publisher_name)
        await page.get_by_role("button", name="下一步").click()
        await page.locator(".q-select.item-width.q-select--small input[placeholder='请选择']").click()
        await page.get_by_title(runtime.qax_group_name).click()
        await page.locator(".client-group-select").click()
        await page.locator(".checkbox-btn").first.click()
        await page.get_by_role("button", name="确 认").click()
        await page.get_by_role("radio", name="所选分组的部分终端").click()
        await page.get_by_role("radio", name="终端列表").click()
        await page.get_by_role("button", name="添 加").click()

        terminal_input = page.get_by_role("textbox", name="终端名称/IP地址/使用人")
        await terminal_input.fill(recipient_ip)
        await page.locator("img:nth-child(3)").click()
        await page.get_by_role("row").locator("span").nth(1).click()
        await page.get_by_role("button", name="确 定").click()
        await page.get_by_role("button", name="下一步").click()
        await page.get_by_role("button", name="下一步").click()
        await page.get_by_role("button", name="确 认").click()
        await self.page.wait_for_timeout(5000)

    async def query_task_status(self, task_name: str, ip_address:str) -> QaxTaskStatus:
        """按任务名查询 QAX 任务状态。"""

        assert self.page is not None
        popup_text_time = ""
        try:
            row = self.page.get_by_role("row",name=task_name)
            await row.wait_for(state="visible",timeout=2000)
            row_text = await row.get_by_role("cell").nth(4).inner_text()
            detail_text = row_text
        except Exception as e:
            return QaxTaskStatus(task_name=task_name, found=False, detail="QAX 中未找到对应任务")
        try:
            detail_button = row.get_by_role("button").nth(1)
            async with self.page.expect_popup() as popup_info:
                await detail_button.click()
            popup = await popup_info.value
            try:
                await self.page.wait_for_timeout(1000)
                await popup.get_by_role("button", name="确 认").click()
                popup_text = await popup.locator(".q-table__body-wrapper tbody tr").filter(
                    has_text=ip_address).first.locator(".q-table_3_column_18.q-table__cell").inner_text()
                popup_text_time = await popup.locator(".q-table__body-wrapper tbody tr").filter(
                    has_text=ip_address).first.locator(".q-table_3_column_19.q-table__cell").inner_text()

                print(f"popup_text:{popup_text}")
                detail_text = f"{row_text}\n{(popup_text or '').strip()}"
                print(f"detail_text:{detail_text}")
            finally:
                await self.page.wait_for_timeout(2000)
                await popup.close()
        except Exception:
            # 查询详情只是增强判断，失败时回退到列表文本即可。
            pass

        return _map_qax_status(
            task_name,
            row_text=row_text,
            detail_text=detail_text,
            read_at=popup_text_time,
        )

    async def delete_task_if_exists(self, task_name: str) -> bool:
        """在 QAX 中尽力删除已不再需要的即时消息任务。"""
        assert self.page is not None
        try:
            row = self.page.get_by_role("row", name=task_name)
            await row.wait_for(state="visible", timeout=2000)
        except Exception as e:
            return False
        try:
            trigger = row.get_by_role("button").nth(2)
            await trigger.scroll_into_view_if_needed()
            await trigger.hover()
            await self.page.wait_for_timeout(500)
            delbtn = self.page.locator('ul:visible li:has-text("删除")').last
            await delbtn.click()
            await self.page.get_by_role("button", name="确 认").click()
            await self.page.wait_for_timeout(1000)
            return True
        except Exception as e:
            return False


def _run_async_blocking(coro: Any) -> Any:
    """在同步服务层安全执行异步协程。

    如果当前线程已经位于运行中的 asyncio 事件循环内，则切到独立线程执行，
    避免再触发 “using Playwright sync API inside asyncio loop” 这类冲突。
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: dict[str, Any] = {}
    error_holder: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result_holder["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            error_holder["error"] = exc

    thread = threading.Thread(target=_runner, name="qax-async-runner", daemon=True)
    thread.start()
    thread.join()
    if "error" in error_holder:
        raise error_holder["error"]
    return result_holder.get("value")


def _map_qax_status(task_name: str, *, row_text: str, detail_text: str, read_at: str = "") -> QaxTaskStatus:
    """将 QAX 页面文本映射为通知系统内部状态。"""

    combined_text = f"{row_text}\n{detail_text}".strip()
    delivery_status = "pending"
    read_status = "unread"

    if any(keyword in row_text for keyword in QAX_ROW_FAILED_STATUSES):
        delivery_status = "failed"
    elif any(keyword in row_text for keyword in QAX_ROW_DELIVERED_STATUSES):
        delivery_status = "delivered"
    elif any(keyword in row_text for keyword in QAX_ROW_PENDING_STATUSES):
        delivery_status = "pending"

    if any(keyword in detail_text for keyword in QAX_DETAIL_FAILED_STATUSES):
        read_status = "unread"
        delivery_status = "failed"
    elif any(keyword in detail_text for keyword in QAX_DETAIL_READ_STATUSES):
        read_status = "read"
        delivery_status = "delivered"
    elif any(keyword in detail_text for keyword in QAX_DETAIL_UNREAD_STATUSES):
        read_status = "unread"

    return QaxTaskStatus(
        task_name=task_name,
        found=True,
        row_text=row_text,
        delivery_status=delivery_status,
        read_status=read_status,
        read_at=read_at.strip() if read_status == "read" else "",
        detail=combined_text,
    )


def _build_send_payload(
    *,
    notification: Notification,
    recipient: NotificationRecipient,
    task: Task | None,
    user: User | None,
    subject: str,
    content: str,
    publisher_name: str,
) -> dict[str, str]:
    """整理 QAX 发送所需的标准化字段。"""

    if user is None:
        raise QaxAutomationError("QAX 接收人不存在")
    if not user.ip_address:
        raise QaxAutomationError(f"用户 {user.name or user.username} 未配置 IP 地址")

    task_name = build_qax_task_name(notification, recipient, task)
    message_title = (subject or (task.title if task else "系统通知")).strip()[:120]
    if not message_title:
        message_title = "系统通知"

    sanitized_content = sanitize_qax_content(content)
    if not sanitized_content:
        raise QaxAutomationError("QAX 正文为空，无法创建即时消息任务")

    return {
        "task_name": task_name,
        "message_title": message_title,
        "message_content": sanitized_content,
        "publisher_name": (publisher_name or "系统通知").strip()[:64],
        "recipient_ip": user.ip_address.strip(),
    }


def send_qax_notification(
    *,
    notification: Notification,
    recipient: NotificationRecipient,
    task: Task | None,
    user: User | None,
    subject: str,
    content: str,
    publisher_name: str,
) -> dict[str, str]:
    """创建单个接收人的 QAX 即时消息任务。"""

    async def _send_async() -> dict[str, str]:
        _ensure_qax_settings()
        payload = _build_send_payload(
            notification=notification,
            recipient=recipient,
            task=task,
            user=user,
            subject=subject,
            content=content,
            publisher_name=publisher_name,
        )
        async with QaxAutomationClient() as client:
            await client.create_instant_message_task(**payload)
        return {"status": "queued", "message": "QAX 即时消息任务已创建", "task_name": payload["task_name"]}

    try:
        return _run_async_blocking(_send_async())
    except Exception as exc:
        task_name = build_qax_task_name(notification, recipient, task)
        return {"status": "failed", "message": str(exc), "task_name": task_name}


def _refresh_notification_status(db: Session, notification_id: int) -> None:
    """根据接收人结果回刷通知主状态。"""

    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification is None:
        return

    recipients = db.query(NotificationRecipient).filter(NotificationRecipient.notification_id == notification_id).all()
    if not recipients:
        notification.status = "pending"
        return
    if any(item.read_status == "read" for item in recipients) or any(item.delivery_status == "delivered" for item in recipients):
        notification.status = "delivered"
        return
    if all(item.delivery_status == "failed" for item in recipients):
        notification.status = "failed"
        return
    notification.status = "pending"


def _promote_task_started_by_qax_read(db: Session, notification: Notification) -> None:
    """任一任务 QAX 通知被成员已读后，将未开始主任务推进为进行中。"""

    if not notification.task_id:
        return
    task = db.query(Task).filter(Task.id == notification.task_id, Task.deleted_at.is_(None)).first()
    if not task or task.main_status != "not_started":
        return
    task.main_status = "in_progress"
    task.completed_at = None
    db.add(
        TaskStatusEvent(
            task_id=task.id,
            from_status="not_started",
            to_status="in_progress",
            source="qax_read",
            remark="任务即时消息已读，自动更新为进行中",
            operator_id=None,
        )
    )


def collect_qax_status(
    db: Session,
    limit: int = 50,
    *,
    task_id: int | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, object]:
    """批量采集 QAX 通知状态并回写通知接收人记录。"""

    if not _qax_collect_lock.acquire(blocking=False):
        return {
            "status": "busy",
            "message": "另一项 QAX 状态采集正在执行，请稍后重试。",
            "processed": 0,
            "processed_count": 0,
            "updated": 0,
            "updated_count": 0,
            "failed": 0,
            "failed_count": 0,
        }

    query = (
        db.query(NotificationRecipient, Notification, Task, User)
        .join(Notification, Notification.id == NotificationRecipient.notification_id)
        .outerjoin(Task, Task.id == Notification.task_id)
        .outerjoin(User, User.id == NotificationRecipient.user_id)
        .filter(Notification.channel == "qax")
    )
    if task_id is not None:
        query = query.filter(Notification.task_id == task_id)
    qax_recipients = query.order_by(NotificationRecipient.id.asc()).limit(max(limit, 1)).all()
    if not qax_recipients:
        _qax_collect_lock.release()
        return {
            "status": "success",
            "message": "没有可采集的 QAX 通知",
            "processed": 0,
            "processed_count": 0,
            "updated": 0,
            "updated_count": 0,
            "failed": 0,
            "failed_count": 0,
        }

    try:
        _ensure_qax_settings()
    except Exception as exc:
        _qax_collect_lock.release()
        return {
            "status": "failed",
            "message": str(exc),
            "processed": 0,
            "processed_count": 0,
            "updated": 0,
            "updated_count": 0,
            "failed": len(qax_recipients),
            "failed_count": len(qax_recipients),
        }

    updated = 0
    failed = 0
    touched_notifications: set[int] = set()

    async def _collect_async() -> None:
        nonlocal updated, failed
        async with QaxAutomationClient() as client:
            for recipient, notification, task, user in qax_recipients:
                task_name = build_qax_task_name(notification, recipient, task)
                ip_address = user.ip_address
                touched_notifications.add(notification.id)
                if progress_callback:
                    progress_callback(recipient.user_id, "正在查询 QAX 状态")
                if recipient.read_status == "read":
                    if not recipient.read_at:
                        recipient.read_at = shanghai_now_naive().isoformat(sep=" ", timespec="seconds")
                        updated += 1
                    await client.delete_task_if_exists(task_name)
                    _promote_task_started_by_qax_read(db, notification)
                    if progress_callback:
                        progress_callback(recipient.user_id, "QAX 已读")
                    continue
                try:
                    result = await client.query_task_status(task_name, ip_address)
                except TypeError:
                    result = await client.query_task_status(task_name)
                if not result.found:
                    continue

                recipient.last_error = result.detail[:1000] if result.delivery_status == "failed" else ""
                read_at = result.read_at.strip()
                if result.read_status == "read" and not read_at:
                    read_at = shanghai_now_naive().isoformat(sep=" ", timespec="seconds")
                status_changed = recipient.delivery_status != result.delivery_status or recipient.read_status != result.read_status
                read_time_changed = result.read_status == "read" and recipient.read_at != read_at
                if status_changed or read_time_changed:
                    recipient.delivery_status = result.delivery_status
                    recipient.read_status = result.read_status
                    if read_time_changed:
                        recipient.read_at = read_at
                    updated += 1
                if result.delivery_status == "failed":
                    failed += 1
                if result.read_status == "read":
                    await client.delete_task_if_exists(task_name)
                    _promote_task_started_by_qax_read(db, notification)
                if progress_callback:
                    progress_callback(recipient.user_id, "已读" if result.read_status == "read" else "未读")

    try:
        _run_async_blocking(_collect_async())
    except Exception as exc:
        _qax_collect_lock.release()
        return {
            "status": "failed",
            "message": f"QAX 状态采集失败：{exc}",
            "processed": len(qax_recipients),
            "processed_count": len(qax_recipients),
            "updated": updated,
            "updated_count": updated,
            "failed": max(failed, 1),
            "failed_count": max(failed, 1),
        }

    for notification_id in touched_notifications:
        _refresh_notification_status(db, notification_id)

    try:
        return {
            "status": "success",
            "message": f"已采集 {len(qax_recipients)} 条 QAX 通知状态",
            "processed": len(qax_recipients),
            "processed_count": len(qax_recipients),
            "updated": updated,
            "updated_count": updated,
            "failed": failed,
            "failed_count": failed,
        }
    finally:
        _qax_collect_lock.release()


def delete_qax_task_notifications(db: Session, task: Task) -> dict[str, object]:
    """删除任务在 QAX 中尚存的全部即时消息通知。"""
    rows = (
        db.query(NotificationRecipient, Notification)
        .join(Notification, Notification.id == NotificationRecipient.notification_id)
        .filter(Notification.task_id == task.id, Notification.channel == "qax")
        .order_by(NotificationRecipient.id.asc())
        .all()
    )
    if not rows:
        return {"status": "success", "attempted": 0, "deleted": 0, "failed": 0, "failures": []}

    try:
        _ensure_qax_settings()
    except Exception as exc:
        return {
            "status": "failed",
            "attempted": len(rows),
            "deleted": 0,
            "failed": len(rows),
            "failures": [{"reason": str(exc)}],
        }

    deleted = 0
    failures: list[dict[str, str]] = []

    async def _delete_async() -> None:
        nonlocal deleted
        async with QaxAutomationClient() as client:
            for recipient, notification in rows:
                task_name = build_qax_task_name(notification, recipient, task)
                try:
                    if await client.delete_task_if_exists(task_name):
                        deleted += 1
                    else:
                        failures.append({"task_name": task_name, "reason": "QAX 中未找到任务或删除失败"})
                except Exception as exc:  # pragma: no cover - depends on QAX runtime
                    failures.append({"task_name": task_name, "reason": str(exc)})

    try:
        _run_async_blocking(_delete_async())
    except Exception as exc:
        failures.append({"reason": str(exc)})

    return {
        "status": "success" if not failures else "partial_failed",
        "attempted": len(rows),
        "deleted": deleted,
        "failed": len(failures),
        "failures": failures,
    }
