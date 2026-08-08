"""Durable PostgreSQL UI sessions (ADR 0002). Opaque cookie ID only in the browser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlasdocs.config import MAX_UI_SESSIONS, get_settings
from atlasdocs.db.models import UiSession as UiSessionRow
from atlasdocs.db.models import utcnow
from atlasdocs.security.tokens import (
    decrypt_token,
    encrypt_token,
    new_csrf_token,
    new_session_id,
    token_fingerprint,
)


@dataclass
class UiSession:
    """Request-facing session view (authorization decrypted in memory only)."""

    id: str
    csrf_token: str
    expires_at: datetime
    paperless_authorization: str | None = None
    token_fingerprint: str | None = None
    username_label: str | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.paperless_authorization)


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DbSessionStore:
    """PostgreSQL-backed session store."""

    def __init__(self, db: Session, *, max_sessions: int | None = None) -> None:
        self._db = db
        self._max_sessions = max_sessions

    def _settings_key(self) -> str:
        return get_settings().token_encryption_key

    def _purge_expired(self) -> None:
        now = utcnow()
        rows = list(self._db.scalars(select(UiSessionRow)).all())
        for row in rows:
            if _as_aware(row.expires_at) <= now:
                self._db.delete(row)
        self._db.flush()

    def _enforce_cap(self, *, max_sessions: int | None = None) -> None:
        cap = max_sessions if max_sessions is not None else (
            self._max_sessions if self._max_sessions is not None else MAX_UI_SESSIONS
        )
        if cap < 1:
            raise ValueError("max_sessions must be >= 1")
        rows = list(
            self._db.scalars(select(UiSessionRow).order_by(UiSessionRow.expires_at.asc())).all()
        )
        while len(rows) >= cap:
            oldest = rows.pop(0)
            self._db.delete(oldest)
        self._db.flush()

    def _to_view(self, row: UiSessionRow) -> UiSession:
        auth: str | None = None
        if row.paperless_authorization_ciphertext:
            auth = decrypt_token(
                row.paperless_authorization_ciphertext, key=self._settings_key()
            )
        return UiSession(
            id=row.id,
            csrf_token=row.csrf_token,
            expires_at=row.expires_at,
            paperless_authorization=auth,
            token_fingerprint=row.token_fingerprint,
            username_label=row.username_label,
        )

    def create(
        self,
        *,
        paperless_authorization: str | None = None,
        username_label: str | None = None,
    ) -> UiSession:
        settings = get_settings()
        self._purge_expired()
        self._enforce_cap()
        ciphertext = None
        fingerprint = None
        if paperless_authorization:
            ciphertext = encrypt_token(paperless_authorization, key=self._settings_key())
            fingerprint = token_fingerprint(paperless_authorization)
        row = UiSessionRow(
            id=new_session_id(),
            csrf_token=new_csrf_token(),
            expires_at=utcnow() + timedelta(seconds=settings.session_max_age_seconds),
            paperless_authorization_ciphertext=ciphertext,
            token_fingerprint=fingerprint,
            username_label=username_label,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self._db.add(row)
        self._db.flush()
        return self._to_view(row)

    def get(self, session_id: str | None) -> UiSession | None:
        if not session_id:
            return None
        self._purge_expired()
        row = self._db.get(UiSessionRow, session_id)
        if row is None:
            return None
        if _as_aware(row.expires_at) <= utcnow():
            self._db.delete(row)
            self._db.flush()
            return None
        return self._to_view(row)

    def save(self, session: UiSession) -> bool:
        row = self._db.get(UiSessionRow, session.id)
        if row is None:
            return False
        row.csrf_token = session.csrf_token
        row.expires_at = session.expires_at
        row.username_label = session.username_label
        row.updated_at = utcnow()
        if session.paperless_authorization:
            row.paperless_authorization_ciphertext = encrypt_token(
                session.paperless_authorization, key=self._settings_key()
            )
            row.token_fingerprint = token_fingerprint(session.paperless_authorization)
        else:
            row.paperless_authorization_ciphertext = None
            row.token_fingerprint = None
        self._db.flush()
        return True

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        row = self._db.get(UiSessionRow, session_id)
        if row is not None:
            self._db.delete(row)
            self._db.flush()

    def rotate_csrf(self, session: UiSession) -> bool:
        session.csrf_token = new_csrf_token()
        return self.save(session)

    def clear(self) -> None:
        self._db.execute(delete(UiSessionRow))
        self._db.flush()


class _NoopSessionStore:
    """Compat for tests that still call session_store.clear() before DB setup."""

    def clear(self) -> None:
        return None


session_store = _NoopSessionStore()


def read_session_id(request: Request) -> str | None:
    return request.cookies.get(get_settings().session_cookie_name)


def get_request_session(request: Request, db: Session) -> UiSession | None:
    return DbSessionStore(db).get(read_session_id(request))


def ensure_session(request: Request, db: Session) -> UiSession:
    store = DbSessionStore(db)
    existing = store.get(read_session_id(request))
    if existing is not None:
        return existing
    return store.create()


def set_session_cookie(response: Response, session: UiSession) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session.id,
        max_age=settings.session_max_age_seconds,
        expires=settings.session_max_age_seconds,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
