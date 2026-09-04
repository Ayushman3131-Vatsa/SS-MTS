"""Central safeguards against writing credentials into application logs."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any


SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "temporary_password",
        "authorization",
        "cookie",
        "set-cookie",
        "session",
        "session_token",
        "csrf",
        "csrf_token",
        "token",
        "access_token",
    }
)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)([\"']?(?:password|current_password|new_password|temporary_password|authorization|"
    r"cookie|set-cookie|session(?:_token)?|csrf(?:_token)?|access_token|token)[\"']?"
    r"\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^,;\s]+)"
)
_REDACTED = "[REDACTED]"


def redact_sensitive_value(value: Any) -> Any:
    """Redact credential-shaped values without changing ordinary log context."""

    if isinstance(value, Mapping):
        return {
            key: _REDACTED if str(key).casefold() in SENSITIVE_FIELD_NAMES else redact_sensitive_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return tuple(redact_sensitive_value(item) for item in value)
    if isinstance(value, list):
        return [redact_sensitive_value(item) for item in value]
    if isinstance(value, str):
        return _ASSIGNMENT_PATTERN.sub(r"\1" + _REDACTED, value)
    return value


class SensitiveDataRedactionFilter(logging.Filter):
    """Redact message arguments before a handler serializes the log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive_value(record.msg)
        record.args = redact_sensitive_value(record.args)
        return True


def configure_sensitive_log_redaction() -> None:
    """Attach one redaction filter to application and server log handlers."""

    redaction_filter = SensitiveDataRedactionFilter()
    for logger_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "app"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(item, SensitiveDataRedactionFilter) for item in logger.filters):
            logger.addFilter(redaction_filter)
        for handler in logger.handlers:
            if not any(isinstance(item, SensitiveDataRedactionFilter) for item in handler.filters):
                handler.addFilter(redaction_filter)
