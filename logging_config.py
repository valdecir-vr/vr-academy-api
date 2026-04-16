"""Structured logging + audit/error persistence — VR Academy."""

from typing import Optional
import logging
import sys
import traceback
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s — %(message)s"

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured logging for the entire app."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    logger = logging.getLogger("vr-academy")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


logger = setup_logging()


# ---------------------------------------------------------------------------
# DB-backed audit + error logging (async)
# ---------------------------------------------------------------------------

async def log_audit(
    action: str,
    user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: str = "{}",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Persist an audit event to the audit_log table."""
    try:
        from db.database import get_db
        db = await get_db()
        await db.execute(
            """INSERT INTO audit_log (user_id, action, target_type, target_id, details, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, action, target_type, target_id, details, ip_address, user_agent),
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to write audit_log: {e}")


async def log_error(
    source: str,
    message: str,
    level: str = "error",
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    user_id: Optional[int] = None,
    error_type: Optional[str] = None,
    stack_trace: Optional[str] = None,
    request_body: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Persist an error to the error_log table."""
    try:
        from db.database import get_db
        db = await get_db()
        await db.execute(
            """INSERT INTO error_log (source, level, endpoint, method, user_id, error_type,
                                      message, stack_trace, request_body, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, level, endpoint, method, user_id, error_type,
             message, stack_trace, request_body, ip_address, user_agent),
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to write error_log: {e}")


async def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """Persist a request to the request_log table."""
    try:
        from db.database import get_db
        db = await get_db()
        await db.execute(
            """INSERT INTO request_log (method, path, status_code, user_id, duration_ms, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (method, path, status_code, user_id, duration_ms, ip_address, user_agent),
        )
        await db.commit()
    except Exception:
        pass  # Never let logging break the app
