"""
Logging utilities: JSON structured logging with contextual fields.

- Configures a root logger emitting JSON using python-json-logger.
- Provides helpers to bind contextual fields for request_id, batch_id, record_key.
- Provides privacy-aware hashing for identifiers (e.g., patient id) with a salt.
"""
from __future__ import annotations

import hashlib
import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from pythonjsonlogger import jsonlogger


@dataclass
class LogContext:
    request_id: Optional[str] = None
    batch_id: Optional[str] = None
    record_key: Optional[str] = None


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


@contextmanager
def bind_context(logger: logging.Logger, **kwargs: Any) -> Iterator[None]:
    """Temporarily add contextual fields to a logger's extra dict.

    Usage:
        with bind_context(logger, request_id=..., batch_id=...):
            logger.info("message")
    """
    # Use LoggerAdapter to inject extra
    adapter = logging.LoggerAdapter(logger, extra=kwargs)
    try:
        yield adapter  # type: ignore[misc]
    finally:
        # Nothing to cleanup; context manager kept for symmetry if we add MDC later
        pass


def hash_identifier(value: str, salt: str) -> str:
    """Hash an identifier with a salt to avoid logging PII directly.

    Returns hex digest string.
    """
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(b"::")
    h.update(value.encode("utf-8"))
    return h.hexdigest()


def add_common_fields(record: logging.LogRecord) -> Dict[str, Any]:
    # Injects extra fields into the log output if present in the record
    extra: Dict[str, Any] = {}
    for key in ("request_id", "batch_id", "record_key"):
        if hasattr(record, key):
            extra[key] = getattr(record, key)
    return extra


class ContextJsonFormatter(jsonlogger.JsonFormatter):
    def process_log_record(self, log_record: Dict[str, Any]) -> Dict[str, Any]:
        # Nothing extra beyond defaults; hook present for future enrichment
        return super().process_log_record(log_record)
