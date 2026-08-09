from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Literal
from urllib.parse import unquote, urlencode

import httpx

from atlasdocs.security.redact import redact_secrets

_CONTENT_DISPOSITION_FILENAME = re.compile(
    r"""filename\*=UTF-8''([^;]+)|filename="([^"]+)"|filename=([^;\s]+)""",
    re.IGNORECASE,
)

_RESULT_DATA_KEYS = frozenset({"document_id", "duplicate_of"})
_TITLE_SEARCH_PAGE_SIZE = 25
_TITLE_SEARCH_MAX_PAGES = 50


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
    related_document_ids: tuple[int, ...] = ()
    result: str | None = None
    result_data: dict | None = None


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


def _coerce_document_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _safe_short_string(value: object, *, limit: int = 200) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = redact_secrets(value).strip()
    if not text:
        return None
    return text[:limit]


def _safe_result_data(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    safe: dict = {}
    for key in _RESULT_DATA_KEYS:
        if key in value:
            safe[key] = value[key]
    return safe or None


def _extract_document_ids_from_task_row(row: dict) -> list[int]:
    """Collect document ids from a Paperless task row in deterministic order."""
    ids: list[int] = []
    seen: set[int] = set()

    def add(value: object) -> None:
        doc_id = _coerce_document_id(value)
        if doc_id is not None and doc_id not in seen:
            seen.add(doc_id)
            ids.append(doc_id)

    # API v9 and earlier.
    add(row.get("related_document"))

    # API v10+ consume tasks expose related_document_ids (+ structured result_data).
    related_ids = row.get("related_document_ids")
    if isinstance(related_ids, list):
        for item in related_ids:
            add(item)

    result_data = row.get("result_data")
    if isinstance(result_data, dict):
        add(result_data.get("document_id"))
        add(result_data.get("duplicate_of"))

    # Legacy / mixed shapes: digit string or JSON blob in result.
    result = row.get("result")
    if isinstance(result, str):
        stripped = result.strip()
        if stripped.isdigit():
            add(stripped)
        else:
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                add(parsed.get("document_id"))
                add(parsed.get("duplicate_of"))

    return ids


def _filename_from_content_disposition(header: str | None) -> str | None:
    if not header:
        return None
    match = _CONTENT_DISPOSITION_FILENAME.search(header)
    if not match:
        return None
    star, quoted, plain = match.groups()
    if star:
        return unquote(star.strip())
    if quoted:
        return quoted.strip()
    if plain:
        return plain.strip()
    return None


class _StreamingBytes:
    """Iterator that always closes the upstream httpx response/client."""

    def __init__(self, response: httpx.Response, client: httpx.Client) -> None:
        self._response = response
        self._client = client
        self._closed = False

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self._response.iter_bytes()
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._response.close()
        self._client.close()


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

    @staticmethod
    def primary_document_id(status: PaperlessTaskStatus) -> int | None:
        """Return the first deterministic document id from a task status, if any."""
        if status.related_document_ids:
            return status.related_document_ids[0]
        return status.related_document_id

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
            body = redact_secrets((response.text or "")[:500]).lower()
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

    def find_document_id_by_correlation_title(self, token: str, title: str) -> int | None:
        """Resolve a document id via documented title_search + exact title match.

        Paperless-ngx documents searching (API docs):
        ``GET /api/documents/?title_search=...`` — title-only Tantivy search.

        AtlasDocs never uses undocumented Django filters such as
        ``title__iexact``. Correlation requires:

        - unique AtlasDocs title (``atlasdocs:{job_uuid}``)
        - exactly one result whose ``title`` equals the correlation value
          across **all** search pages
        - no filename / timing heuristics; ambiguous or mismatched hits → None
        """
        needle = (title or "").strip()
        if not needle:
            return None

        exact: list[int] = []
        page = 1
        while page <= _TITLE_SEARCH_MAX_PAGES:
            params = {
                "title_search": needle,
                "page_size": _TITLE_SEARCH_PAGE_SIZE,
                "page": page,
            }
            url = f"{self._base_url}/api/documents/?{urlencode(params)}"
            response = self._request("GET", url, token)
            self._raise_for_status(response)
            payload = self._parse_json(response)
            if not isinstance(payload, dict):
                raise PaperlessUnavailableError("Paperless returned malformed document list")
            raw_results = payload.get("results")
            if not isinstance(raw_results, list):
                raise PaperlessUnavailableError("Paperless document list has invalid results")

            for row in raw_results:
                if not isinstance(row, dict) or "id" not in row:
                    continue
                row_title = str(row.get("title") or "").strip()
                if row_title != needle:
                    continue
                try:
                    exact.append(int(row["id"]))
                except (TypeError, ValueError) as exc:
                    raise PaperlessUnavailableError(
                        "Paperless document list has invalid results"
                    ) from exc
                if len(exact) > 1:
                    return None

            if not payload.get("next"):
                break
            page += 1
        else:
            raise PaperlessUnavailableError("Paperless title search pagination exceeded limit")

        if len(exact) != 1:
            return None
        return exact[0]

    def find_document_id_by_title(self, token: str, title: str) -> int | None:
        """Backward-compatible alias for correlation title lookup."""
        return self.find_document_id_by_correlation_title(token, title)

    def post_document(
        self,
        token: str,
        *,
        filename: str,
        content: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        title: str | None = None,
    ) -> str:
        """Upload via POST /api/documents/post_document/; return Paperless task id."""
        url = f"{self._base_url}/api/documents/post_document/"
        files = {"document": (filename, content, content_type)}
        form: dict[str, str] = {}
        if title is not None:
            form["title"] = title
        response = self._request(
            "POST",
            url,
            token,
            files=files,
            data=form or None,
        )
        self._raise_for_status(response)
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
        document_ids = _extract_document_ids_from_task_row(row)
        related_id = document_ids[0] if document_ids else None
        result_data = _safe_result_data(row.get("result_data"))
        result_text = _safe_short_string(row.get("result"))
        return PaperlessTaskStatus(
            task_id=task_id,
            status=status,
            related_document_id=related_id,
            related_document_ids=tuple(document_ids),
            result=result_text,
            result_data=result_data,
        )

    def stream_document_file(
        self,
        token: str,
        document_id: int,
        *,
        kind: Literal["preview", "download"],
    ) -> tuple[Iterator[bytes], str, str | None]:
        """Stream preview or download bytes from Paperless without logging the body."""
        suffix = "preview" if kind == "preview" else "download"
        url = f"{self._base_url}/api/documents/{document_id}/{suffix}/"
        client = httpx.Client(timeout=self._timeout, transport=self._transport)
        try:
            response = client.send(
                client.build_request("GET", url, headers=self._headers(token)),
                stream=True,
            )
        except httpx.TimeoutException as exc:
            client.close()
            raise PaperlessUnavailableError("Paperless request timed out") from exc
        except httpx.HTTPError as exc:
            client.close()
            raise PaperlessUnavailableError("Paperless request failed") from exc

        if response.status_code in {401, 403}:
            response.close()
            client.close()
            raise PaperlessAuthError(f"Access denied for Paperless document {document_id}")
        if response.status_code == 404:
            response.close()
            client.close()
            raise PaperlessNotFoundError(f"Paperless document {document_id} not found")
        if response.status_code >= 500:
            response.close()
            client.close()
            raise PaperlessUnavailableError(f"Paperless returned HTTP {response.status_code}")
        if response.status_code >= 400:
            response.close()
            client.close()
            raise PaperlessUnavailableError(f"Paperless returned HTTP {response.status_code}")

        content_type = response.headers.get("content-type") or "application/octet-stream"
        filename = _filename_from_content_disposition(response.headers.get("content-disposition"))
        return _StreamingBytes(response, client), content_type, filename

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
