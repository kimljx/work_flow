from __future__ import annotations

import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.bootstrap import bootstrap_database
from app.config import settings
from app.db import SessionLocal
from app.services.mail import poll_mailbox

logger = logging.getLogger(__name__)

_mail_poll_stop_event = threading.Event()
_mail_poll_thread: threading.Thread | None = None


def _mail_poll_loop() -> None:
    interval = max(settings.mail_auto_poll_interval_seconds, 30)
    while not _mail_poll_stop_event.wait(interval):
        try:
            with SessionLocal() as db:
                result = poll_mailbox(db)
                logger.info("Auto mail poll result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto mail poll failed: %s", exc)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    bootstrap_database()
    global _mail_poll_thread
    if settings.mail_auto_poll_enabled and _mail_poll_thread is None:
        _mail_poll_stop_event.clear()
        _mail_poll_thread = threading.Thread(target=_mail_poll_loop, name="mail-auto-poll", daemon=True)
        _mail_poll_thread.start()
        logger.info("Auto mail polling started, interval=%ss", max(settings.mail_auto_poll_interval_seconds, 30))


@app.on_event("shutdown")
def shutdown_event() -> None:
    global _mail_poll_thread
    _mail_poll_stop_event.set()
    if _mail_poll_thread and _mail_poll_thread.is_alive():
        _mail_poll_thread.join(timeout=2)
    _mail_poll_thread = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
