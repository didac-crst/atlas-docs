from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import urlencode

import httpx


class PaperlessError(Exception):
    """Base Paperless adapter error."""


class PaperlessNotFoundError(PaperlessError):
    """Document does not exist or must not be disclosed."""


class PaperlessAuthError(PaperlessError):
    """Caller is not allowed to access the document."""


class PaperlessUnavailableError(PaperlessError):
    """Paperless timed out or returned a server error."""


class PaperlessDuplicateError(PaperlessError):
    """Paperless rejected the upload as a duplicate document."""


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


@dataclass(frozen=True)
class PaperlessTaskStatus:
    task_id: str
    status: str  # PENDING | STARTED | SUCCESS | FAILURE | ...
    related_document_id: int | None = None
    result: str | None = None


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
        self._correspondent_names: dict[int, str | None] = {}
        self._document_type_names: dict[int, str | None] = {}

    def _headers(self, token: str | None = None) -> dict[str, str]:
        if not token:
            return {}
        if token.lower().startswith("token ") or token.lower().startswith("bearer "):
            return {"Authorization": token}
        return {"Authorization": f"Token {token}"}

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)

    def _request(
        self,
        method: str,
        url: str,
        token: str | None = None,
        *,
        json: object | None = None,
        files: object | None = None,
        data: object | None = None,
    ) -> httpx.Response:
        try:
            with self._client() as client:
                return client.request(
                    method,
                    url,
                    headers=self._headers(token),
                    json=json,
                    files=files,
                    data=data,
                )
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
            body = (response.text or "").lower()
            if "duplicate" in body:
                raise PaperlessDuplicateError("Paperless rejected duplicate document")
            raise PaperlessUnavailableError(f"Paperless returned HTTP {response.status_code}")

    def _parse_json(self, response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise PaperlessUnavailableError("Paperless returned non-JSON response") from exc

    def _lookup_named_resource(
        self, resource: str, resource_id: int, token: str, cache: dict[int, str | None]
    ) -> str | None:
        if resource_id in cache:
            return cache[resource_id]
        url = f"{self._base_url}/api/{resource}/{resource_id}/"
        response = self._request("GET", url, token)
        if response.status_code in {401, 403, 404} or response.status_code >= 500:
            cache[resource_id] = None
            return None
        if response.status_code >= 400:
            cache[resource_id] = None
            return None
        label = _label_from_field(self._parse_json(response))
        cache[resource_id] = label
        return label

    def _resolve_label(
        self, value: object, token: str, *, resource: str, cache: dict[int, str | None]
    ) -> str | None:
        direct = _label_from_field(value)
        if direct is not None:
            return direct
        if isinstance(value, int):
            return self._lookup_named_resource(resource, value, token, cache)
        return None

    def _document_from_payload(self, payload: object, token: str) -> PaperlessDocument:
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
                correspondent=self._resolve_label(
                    payload.get("correspondent"),
                    token,
                    resource="correspondents",
                    cache=self._correspondent_names,
                ),
                document_type=self._resolve_label(
                    payload.get("document_type"),
                    token,
                    resource="document_types",
                    cache=self._document_type_names,
                ),
            )
        except (TypeError, ValueError) as exc:
            raise PaperlessUnavailableError("Paperless returned malformed document payload") from exc

    def exchange_password(self, username: str, password: str) -> str:
        """POST /api/token/ — returns raw token string (without Token prefix)."""
        url = f"{self._base_url}/api/token/"
        response = self._request(
            "POST",
            url,
            json={"username": username, "password": password},
        )
        if response.status_code in {400, 401, 403}:
            raise PaperlessAuthError("Invalid Paperless credentials")
        self._raise_for_status(response)
        payload = self._parse_json(response)
        if not isinstance(payload, dict) or not isinstance(payload.get("token"), str):
            raise PaperlessUnavailableError("Paperless token response malformed")
        token = payload["token"].strip()
        if not token:
            raise PaperlessUnavailableError("Paperless token response empty")
        return token

    def get_document(self, document_id: int, token: str) -> PaperlessDocument:
        url = f"{self._base_url}/api/documents/{document_id}/"
        response = self._request("GET", url, token)
        self._raise_for_status(response, document_id)
        return self._document_from_payload(self._parse_json(response), token)

    def list_documents(
        self,
        token: str,
        *,
        page: int = 1,
        page_size: int = 25,
        query: str | None = None,
        ordering: str | None = None,
        created_gte: str | None = None,
        created_lte: str | None = None,
        correspondent: str | None = None,
        document_type: str | None = None,
        tag: str | None = None,
    ) -> PaperlessDocumentPage:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if query:
            params["query"] = query
        if ordering:
            params["ordering"] = ordering
        if created_gte:
            params["created__date__gte"] = created_gte
        if created_lte:
            params["created__date__lte"] = created_lte
        if correspondent:
            params["correspondent__name__icontains"] = correspondent
        if document_type:
            params["document_type__name__icontains"] = document_type
        if tag:
            params["tags__name__icontains"] = tag
        url = f"{self._base_url}/api/documents/?{urlencode(params)}"
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
            results = [self._document_from_payload(item, token) for item in raw_results]
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

    def post_document(
        self,
        token: str,
        *,
        filename: str,
        content: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload via POST /api/documents/post_document/; return Paperless task id."""
        url = f"{self._base_url}/api/documents/post_document/"
        files = {"document": (filename, content, content_type)}
        response = self._request("POST", url, token, files=files)
        self._raise_for_status(response)
        # Paperless may return a bare UUID string or JSON.
        text = (response.text or "").strip().strip('"')
        if text and "\n" not in text and len(text) < 80 and "{" not in text:
            return text
        payload = self._parse_json(response)
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if isinstance(payload, dict):
            for key in ("task_id", "id", "task"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        raise PaperlessUnavailableError("Paperless post_document response missing task id")

    def get_task(self, task_id: str, token: str) -> PaperlessTaskStatus:
        url = f"{self._base_url}/api/tasks/?{urlencode({'task_id': task_id})}"
        response = self._request("GET", url, token)
        self._raise_for_status(response)
        payload = self._parse_json(response)
        rows: list[object]
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
            rows = payload["results"]
        else:
            raise PaperlessUnavailableError("Paperless tasks response malformed")
        if not rows:
            return PaperlessTaskStatus(task_id=task_id, status="PENDING")
        row = rows[0]
        if not isinstance(row, dict):
            raise PaperlessUnavailableError("Paperless task row malformed")
        status = str(row.get("status") or row.get("state") or "PENDING").upper()
        related = row.get("related_document")
        related_id: int | None = None
        if isinstance(related, int):
            related_id = related
        elif isinstance(related, str) and related.isdigit():
            related_id = int(related)
        result = row.get("result")
        result_text = result if isinstance(result, str) else None
        if related_id is None and result_text and result_text.isdigit():
            related_id = int(result_text)
        return PaperlessTaskStatus(
            task_id=task_id,
            status=status,
            related_document_id=related_id,
            result=result_text,
        )

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
