"""Server-side UI sessions: opaque cookie ID, secrets kept in process memory."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response

from atlasdocs.config import MAX_UI_SESSIONS, get_settings

COOKIE_NAME = "atlasdocs_sid"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class UiSession:
    id: str
    csrf_token: str
    expires_at: datetime
    paperless_authorization: str | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.paperless_authorization)


class InMemorySessionStore:
    """Process-local session store with explicit expiry, cap, and logout invalidation."""

    def __init__(self, max_sessions: int = MAX_UI_SESSIONS) -> None:
        if max_sessions < 1:
            raise ValueError("max_sessions must be >= 1")
        self._lock = threading.Lock()
        self._sessions: dict[str, UiSession] = {}
        self._max_sessions = max_sessions

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _purge_expired_locked(self) -> None:
        now = _utcnow()
        expired = [sid for sid, session in self._sessions.items() if session.expires_at <= now]
        for sid in expired:
            self._sessions.pop(sid, None)

    def _enforce_cap_locked(self) -> None:
        while len(self._sessions) >= self._max_sessions:
            oldest = min(self._sessions.values(), key=lambda item: item.expires_at)
            self._sessions.pop(oldest.id, None)

    def create(self, *, paperless_authorization: str | None = None) -> UiSession:
        settings = get_settings()
        session = UiSession(
            id=secrets.token_urlsafe(32),
            csrf_token=secrets.token_urlsafe(32),
            paperless_authorization=paperless_authorization,
            expires_at=_utcnow() + timedelta(seconds=settings.session_max_age_seconds),
        )
        with self._lock:
            self._purge_expired_locked()
            self._enforce_cap_locked()
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str | None) -> UiSession | None:
        if not session_id:
            return None
        with self._lock:
            self._purge_expired_locked()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expires_at <= _utcnow():
                self._sessions.pop(session_id, None)
                return None
            return session

    def save(self, session: UiSession) -> bool:
        """Update an existing session only. Returns False if the ID is unknown/deleted."""
        with self._lock:
            self._purge_expired_locked()
            if session.id not in self._sessions:
                return False
            self._sessions[session.id] = session
            return True

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def rotate_csrf(self, session: UiSession) -> bool:
        session.csrf_token = secrets.token_urlsafe(32)
        return self.save(session)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


session_store = InMemorySessionStore()


def read_session_id(request: Request) -> str | None:
    return request.cookies.get(get_settings().session_cookie_name)


def get_request_session(request: Request) -> UiSession | None:
    return session_store.get(read_session_id(request))


def ensure_session(request: Request) -> UiSession:
    existing = get_request_session(request)
    if existing is not None:
        return existing
    return session_store.create()


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
