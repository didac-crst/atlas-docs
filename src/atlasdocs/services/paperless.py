from __future__ import annotations

from dataclasses import dataclass

import httpx


class PaperlessError(Exception):
    """Base Paperless adapter error."""


class PaperlessNotFoundError(PaperlessError):
    """Document does not exist or must not be disclosed."""


class PaperlessAuthError(PaperlessError):
    """Caller is not allowed to access the document."""


class PaperlessUnavailableError(PaperlessError):
    """Paperless timed out or returned a server error."""


@dataclass(frozen=True)
class PaperlessDocument:
    id: int
    title: str | None = None


class PaperlessClient:
    """Thin REST adapter. Never touches Paperless databases or filesystems."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._token = token
        self._transport = transport

    def _headers(self, token: str | None) -> dict[str, str]:
        resolved = token or self._token
        if not resolved:
            return {}
        if resolved.lower().startswith("token ") or resolved.lower().startswith("bearer "):
            return {"Authorization": resolved}
        return {"Authorization": f"Token {resolved}"}

    def get_document(self, document_id: int, token: str | None = None) -> PaperlessDocument:
        url = f"{self._base_url}/api/documents/{document_id}/"
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.get(url, headers=self._headers(token))
        except httpx.TimeoutException as exc:
            raise PaperlessUnavailableError("Paperless request timed out") from exc
        except httpx.HTTPError as exc:
            raise PaperlessUnavailableError("Paperless request failed") from exc

        if response.status_code == 404:
            raise PaperlessNotFoundError(f"Paperless document {document_id} not found")
        if response.status_code in {401, 403}:
            raise PaperlessAuthError(f"Access denied for Paperless document {document_id}")
        if response.status_code >= 500:
            raise PaperlessUnavailableError(
                f"Paperless returned HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise PaperlessUnavailableError(
                f"Paperless returned HTTP {response.status_code}"
            )

        payload = response.json()
        return PaperlessDocument(id=int(payload.get("id", document_id)), title=payload.get("title"))

    def document_exists(self, document_id: int, token: str | None = None) -> bool:
        self.get_document(document_id, token=token)
        return True

    def assert_accessible(self, document_id: int, token: str | None = None) -> PaperlessDocument:
        return self.get_document(document_id, token=token)
