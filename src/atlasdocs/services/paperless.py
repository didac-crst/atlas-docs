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


@dataclass(frozen=True)
class PaperlessDocumentPage:
    count: int
    page: int
    page_size: int
    results: list[PaperlessDocument]
    has_next: bool
    has_previous: bool


class PaperlessClient:
    """Thin REST adapter. Never touches Paperless databases or filesystems."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def _headers(self, token: str) -> dict[str, str]:
        if token.lower().startswith("token ") or token.lower().startswith("bearer "):
            return {"Authorization": token}
        return {"Authorization": f"Token {token}"}

    def _request(self, method: str, url: str, token: str) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                return client.request(method, url, headers=self._headers(token))
        except httpx.TimeoutException as exc:
            raise PaperlessUnavailableError("Paperless request timed out") from exc
        except httpx.HTTPError as exc:
            raise PaperlessUnavailableError("Paperless request failed") from exc

    def _raise_for_status(self, response: httpx.Response, document_id: int | None = None) -> None:
        label = f"document {document_id}" if document_id is not None else "request"
        if response.status_code == 404:
            raise PaperlessNotFoundError(f"Paperless {label} not found")
        if response.status_code in {401, 403}:
            raise PaperlessAuthError(f"Access denied for Paperless {label}")
        if response.status_code >= 500:
            raise PaperlessUnavailableError(f"Paperless returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise PaperlessUnavailableError(f"Paperless returned HTTP {response.status_code}")

    def get_document(self, document_id: int, token: str) -> PaperlessDocument:
        url = f"{self._base_url}/api/documents/{document_id}/"
        response = self._request("GET", url, token)
        self._raise_for_status(response, document_id)
        payload = response.json()
        return PaperlessDocument(id=int(payload.get("id", document_id)), title=payload.get("title"))

    def list_documents(self, token: str, *, page: int = 1, page_size: int = 25) -> PaperlessDocumentPage:
        url = f"{self._base_url}/api/documents/?page={page}&page_size={page_size}"
        response = self._request("GET", url, token)
        self._raise_for_status(response)
        payload = response.json()
        results = [
            PaperlessDocument(id=int(item["id"]), title=item.get("title"))
            for item in payload.get("results", [])
        ]
        return PaperlessDocumentPage(
            count=int(payload.get("count", len(results))),
            page=page,
            page_size=page_size,
            results=results,
            has_next=bool(payload.get("next")),
            has_previous=bool(payload.get("previous")),
        )

    def document_exists(self, document_id: int, token: str) -> bool:
        self.get_document(document_id, token=token)
        return True

    def assert_accessible(self, document_id: int, token: str) -> PaperlessDocument:
        return self.get_document(document_id, token=token)
