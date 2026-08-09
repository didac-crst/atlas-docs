"""Unit tests for secret redaction helpers."""

from __future__ import annotations

from atlasdocs.security.redact import redact_secrets, safe_error_message


def test_redact_secrets_token_prefix() -> None:
    raw = "Authorization failed: Token secret-abc leaked in message"
    redacted = redact_secrets(raw)
    assert "secret-abc" not in redacted
    assert "Token [REDACTED]" in redacted


def test_redact_secrets_authorization_header_forms() -> None:
    cases = (
        "Authorization: Token secret-abc",
        "Authorization: Bearer secret-abc",
        "authorization=Token secret-abc",
        "Authorization=Bearer secret-abc",
    )
    for raw in cases:
        redacted = redact_secrets(raw)
        assert "secret-abc" not in redacted, raw
        assert "[REDACTED]" in redacted, raw


def test_redact_secrets_bearer_and_named_tokens() -> None:
    raw = "Bearer abcdefghij and paperless_token=super-secret-value"
    redacted = redact_secrets(raw)
    assert "abcdefghij" not in redacted
    assert "super-secret-value" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_empty_and_none() -> None:
    assert redact_secrets("") == ""
    assert redact_secrets(None) == ""


def test_safe_error_message_truncates_and_redacts() -> None:
    exc = RuntimeError("Token secret-abc in upstream body " + ("x" * 600))
    message = safe_error_message(exc, fallback="fallback")
    assert "secret-abc" not in message
    assert len(message) <= 500
