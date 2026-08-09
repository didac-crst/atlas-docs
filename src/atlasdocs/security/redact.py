"""Redact secrets from strings before logging or raising errors."""

from __future__ import annotations

import re

_TOKEN_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)(token\s+)([A-Za-z0-9._\-]{8,})"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]{8,})"),
    re.compile(r"(?i)((?:paperless[_-]?token|api[_-]?token|access[_-]?token)\s*[:=]\s*)(\S+)"),
)


def redact_secrets(value: str | None) -> str:
    """Return a copy of ``value`` with token-like material replaced."""
    if not value:
        return ""
    text = value
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def safe_error_message(exc: BaseException, *, fallback: str, limit: int = 500) -> str:
    """Build a user/operator-safe short message from an exception."""
    raw = redact_secrets(str(exc) or fallback).strip() or fallback
    return raw[:limit]
