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
import os
from pathlib import Path
import re
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, settings
from app.models import Notification, NotificationRecipient, Task, User
from app.services.runtime_settings import load_runtime_settings
from app.services.templates import strip_reply_guides


QAX_ROW_PENDING_STATUSES = ("准备中", "执行中")
QAX_ROW_DELIVERED_STATUSES = ("执行结束",)
QAX_ROW_FAILED_STATUSES = ("已取消",)
QAX_DETAIL_UNREAD_STATUSES = ("未接收", "正在执行")
QAX_DETAIL_READ_STATUSES = ("执行成功",)
QAX_DETAIL_FAILED_STATUSES = ("执行失败",)


QAX_CERTIFICATE_SUFFIXES = (".cer", ".crt", ".pem", ".p12", ".pfx")
QAX_CLIENT_CERTIFICATE_SUFFIXES = (".p12", ".pfx")
QAX_BROWSER_EXECUTABLE_GLOBS = (
    "chromium-*/chrome-win/chrome.exe",
    "chromium-*/chrome-linux/chrome",
    "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
)


@dataclass(frozen=True)
class QaxCertificateState:
    files: tuple[Path, ...]
    empty_files: tuple[Path, ...]
    public_files: tuple[Path, ...]
    client_files: tuple[Path, ...]


def _has_bundled_chromium(root: Path) -> bool:
    return any(root.glob(pattern) for pattern in QAX_BROWSER_EXECUTABLE_GLOBS)


def _relative_cert_paths(paths: tuple[Path, ...]) -> str:
    if not paths:
        return "无"
    values = []
    for path in paths:
        try:
            values.append(path.relative_to(PROJECT_ROOT).as_posix())
        except ValueError:
            values.append(path.as_posix())
    return ", ".join(values)


def _detect_qax_certificates() -> QaxCertificateState:
    config_root = PROJECT_ROOT / "config"
    if not config_root.exists():
        return QaxCertificateState(files=(), empty_files=(), public_files=(), client_files=())

    files = tuple(
        sorted(
            (
                path
                for path in config_root.iterdir()
                if path.is_file() and path.suffix.lower() in QAX_CERTIFICATE_SUFFIXES
            ),
            key=lambda item: item.name.lower(),
        )
    )
    empty_files = tuple(path for path in files if path.stat().st_size <= 0)
    client_files = tuple(path for path in files if path.suffix.lower() in QAX_CLIENT_CERTIFICATE_SUFFIXES)
    public_files = tuple(path for path in files if path.suffix.lower() not in QAX_CLIENT_CERTIFICATE_SUFFIXES)
    return QaxCertificateState(
        files=files,
        empty_files=empty_files,
        public_files=public_files,
        client_files=client_files,
    )


def _validate_qax_certificates() -> QaxCertificateState:
    state = _detect_qax_certificates()
    if state.empty_files:
        raise QaxAutomationError(
            "QAX 证书文件为空，无法用于浏览器登录，请替换为真实证书后重试："
            f"{_relative_cert_paths(state.empty_files)}"
        )
    return state


def _build_qax_certificate_hint(state: QaxCertificateState) -> str:
    if not state.files:
        return "当前 config/ 下未发现证书文件。"

    hints = [f"已发现证书文件：{_relative_cert_paths(state.files)}。"]
    if state.public_files and not state.client_files:
        hints.append("当前只有 .cer/.crt/.pem 公钥或信任链证书。若目标站点要求客户端证书登录，通常还需要带私钥的 .p12/.pfx。")
    elif state.client_files:
        hints.append("已发现 .p12/.pfx 客户端证书文件。")
    hints.append("当前内置 Playwright 不支持在代码里直接挂载客户端证书，请优先将证书导入系统、容器或浏览器运行环境的信任链或证书存储后再登录。")
    return "".join(hints)


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


@dataclass
class QaxTaskStatus:
    """描述单条 QAX 任务的查询结果。"""

    task_name: str
    found: bool
    row_text: str = ""
    delivery_status: str = "pending"
    read_status: str = "unread"
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
    """校验 QAX 必填配置。"""

    missing_items = []
    if not settings.qax_base_url:
        missing_items.append("QAX_BASE_URL")
    if not settings.qax_username:
        missing_items.append("QAX_USERNAME")
    if not settings.qax_password:
        missing_items.append("QAX_PASSWORD")
    if missing_items:
        raise QaxAutomationError(f"QAX 配置不完整，请补充：{', '.join(missing_items)}")


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
        self.page: Any | None = None
        self._timeout_error: Any | None = None

    async def __aenter__(self) -> "QaxAutomationClient":
        _ensure_local_playwright_browser_path()
        async_playwright, timeout_error = _load_playwright()
        self._timeout_error = timeout_error
        self._playwright_cm = async_playwright()
        playwright = await self._playwright_cm.start()
        certificate_state = _validate_qax_certificates()
        try:
            runtime = load_runtime_settings()
            launch_options = {"headless": not runtime.qax_browser_visible}
            executable_path = _local_chromium_executable()
            if executable_path:
                launch_options["executable_path"] = executable_path
            self._browser = await playwright.chromium.launch(**launch_options)
            self._context = await self._browser.new_context(ignore_https_errors=settings.qax_ignore_https_errors)
            self.page = await self._context.new_page()
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

    async def _login_and_open_task_page(self) -> None:
        """登录 QAX 并进入“资产管理 -> 终端任务”页面。"""

        assert self.page is not None
        await self.page.goto(settings.qax_base_url, wait_until="domcontentloaded")
        await self.page.get_by_placeholder("用户名/手机号/邮箱").fill(settings.qax_username)
        await self.page.get_by_role("button", name="下一步").click()
        await self.page.get_by_placeholder("请输入密码").fill(settings.qax_password)
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
        await page.get_by_role("button", name="新建").click()
        await page.get_by_placeholder("请输入").first.fill(task_name)
        await page.get_by_placeholder("请选择任务类型").click()
        await page.get_by_title("即时消息").click()
        await page.get_by_placeholder("请输入消息标题").fill(message_title)
        await page.locator(".ql-editor").fill(message_content)
        await page.get_by_placeholder("请输入发布人").fill(publisher_name)
        await page.get_by_role("button", name="下一步").click()
        await page.locator(".q-select.item-width.q-select--small input[placeholder='请选择']").click()
        await page.get_by_title(settings.qax_group_name).click()
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
        try:
            row = self.page.get_by_role("row",name=task_name)
            await row.wait_for(state="visible",timeout=2000)
            row_text = await row.get_by_role("cell").nth(4).inner_text()
            # print(f"row_text:{row_text}")
            # detail_text = row_text
        except Exception as e:
            # print(e)
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

                print(f"popup_text:{popup_text}")
                detail_text = f"{row_text}\n{(popup_text or '').strip()}"
                print(f"detail_text:{detail_text}")
            finally:
                await self.page.wait_for_timeout(2000)
                await popup.close()
        except Exception as e:
            # 查询详情只是增强判断，失败时回退到列表文本即可。
            pass

        return _map_qax_status(task_name, row_text=row_text, detail_text=detail_text)

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


def _map_qax_status(task_name: str, *, row_text: str, detail_text: str) -> QaxTaskStatus:
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


def collect_qax_status(db: Session, limit: int = 50) -> dict[str, object]:
    """批量采集 QAX 通知状态并回写通知接收人记录。"""

    qax_recipients = (
        db.query(NotificationRecipient, Notification, Task, User)
        .join(Notification, Notification.id == NotificationRecipient.notification_id)
        .outerjoin(Task, Task.id == Notification.task_id)
        .outerjoin(User, User.id == NotificationRecipient.user_id)
        .filter(Notification.channel == "qax")
        .order_by(NotificationRecipient.id.asc())
        .limit(max(limit, 1))
        .all()
    )
    if not qax_recipients:
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
                if recipient.read_status == "read":
                    await client.delete_task_if_exists(task_name)
                    continue
                try:
                    result = await client.query_task_status(task_name, ip_address)
                except TypeError:
                    result = await client.query_task_status(task_name)
                if not result.found:
                    continue

                recipient.last_error = result.detail[:1000] if result.delivery_status == "failed" else ""
                if recipient.delivery_status != result.delivery_status or recipient.read_status != result.read_status:
                    recipient.delivery_status = result.delivery_status
                    recipient.read_status = result.read_status
                    updated += 1
                if result.delivery_status == "failed":
                    failed += 1
                if result.read_status == "read":
                    await client.delete_task_if_exists(task_name)

    try:
        _run_async_blocking(_collect_async())
    except Exception as exc:
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
