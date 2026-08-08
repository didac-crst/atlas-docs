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
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None


@dataclass(frozen=True)
class PaperlessDocumentPage:
    count: int
    page: int
    page_size: int
    results: list[PaperlessDocument]
    has_next: bool
    has_previous: bool


def _label_from_field(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("name", "slug", "title"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
    if isinstance(value, int):
        return None
    return None


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

    def _parse_json(self, response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise PaperlessUnavailableError("Paperless returned non-JSON response") from exc

    def _document_from_payload(self, payload: object) -> PaperlessDocument:
        if not isinstance(payload, dict):
            raise PaperlessUnavailableError("Paperless returned malformed document payload")
        if "id" not in payload:
            raise PaperlessUnavailableError("Paperless document payload missing id")
        title = payload.get("title")
        if title is not None and not isinstance(title, str):
            raise PaperlessUnavailableError("Paperless document payload has invalid title")
        created = payload.get("created_date")
        if created is None:
            created = payload.get("created")
        if created is not None and not isinstance(created, str):
            created = str(created)
        try:
            return PaperlessDocument(
                id=int(payload["id"]),
                title=title,
                created_date=created,
                correspondent=_label_from_field(payload.get("correspondent")),
                document_type=_label_from_field(payload.get("document_type")),
            )
        except (TypeError, ValueError) as exc:
            raise PaperlessUnavailableError("Paperless returned malformed document payload") from exc

    def get_document(self, document_id: int, token: str) -> PaperlessDocument:
        url = f"{self._base_url}/api/documents/{document_id}/"
        response = self._request("GET", url, token)
        self._raise_for_status(response, document_id)
        return self._document_from_payload(self._parse_json(response))

    def list_documents(self, token: str, *, page: int = 1, page_size: int = 25) -> PaperlessDocumentPage:
        url = f"{self._base_url}/api/documents/?page={page}&page_size={page_size}"
        response = self._request("GET", url, token)
        self._raise_for_status(response)
        payload = self._parse_json(response)
        if not isinstance(payload, dict):
            raise PaperlessUnavailableError("Paperless returned malformed document list")
        if "results" not in payload:
            raise PaperlessUnavailableError("Paperless document list missing results")
        raw_results = payload["results"]
        if not isinstance(raw_results, list):
            raise PaperlessUnavailableError("Paperless document list has invalid results")
        try:
            results = [self._document_from_payload(item) for item in raw_results]
            count_raw = payload.get("count", len(results))
            return PaperlessDocumentPage(
                count=int(count_raw),
                page=page,
                page_size=page_size,
                results=results,
                has_next=bool(payload.get("next")),
                has_previous=bool(payload.get("previous")),
            )
        except (TypeError, ValueError) as exc:
            raise PaperlessUnavailableError("Paperless returned malformed document list") from exc
        except PaperlessUnavailableError:
            raise

    def document_exists(self, document_id: int, token: str) -> bool:
        self.get_document(document_id, token=token)
        return True

    def assert_accessible(self, document_id: int, token: str) -> PaperlessDocument:
        return self.get_document(document_id, token=token)

    def validate_token(self, token: str) -> None:
        """Verify the token is accepted by Paperless (does not authorize a document)."""
        self.list_documents(token, page=1, page_size=1)

    def iter_all_documents(self, token: str, *, page_size: int = 100, limit: int | None = None):
        """Yield Paperless documents across pages until exhausted or ``limit`` reached."""
        page = 1
        yielded = 0
        while True:
            batch = self.list_documents(token, page=page, page_size=page_size)
            if not batch.results:
                break
            for doc in batch.results:
                yield doc
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if not batch.has_next:
                break
            page += 1
