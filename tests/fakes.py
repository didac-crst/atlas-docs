"""Deterministic Paperless REST stand-in for API and browser smoke tests."""

from __future__ import annotations

import json
import uuid
from urllib.parse import parse_qs, urlparse

import httpx

from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE


class FakePaperlessTransport(httpx.BaseTransport):
    """Deterministic Paperless REST stand-in. No real HTTP or Paperless DB."""

    def __init__(self) -> None:
        self.correspondents: dict[int, dict] = {
            1: {"id": 1, "name": "Acme Payroll"},
            2: {"id": 2, "name": "Contoso"},
        }
        self.document_types: dict[int, dict] = {
            10: {"id": 10, "name": "Payslip"},
            11: {"id": 11, "name": "Invoice"},
        }
        self.documents: dict[int, dict] = {
            184: {
                "id": 184,
                "title": "Payslip Germany",
                "created_date": "2024-01-15",
                "correspondent": 1,
                "document_type": 10,
            },
            185: {
                "id": 185,
                "title": "Invoice Spain",
                "created_date": "2024-02-01",
                "correspondent": 2,
                "document_type": 11,
            },
            186: {"id": 186, "title": "Already classified"},
        }
        self.denied: set[int] = set()
        self.unauthorized: set[int] = set()
        self.server_error: set[int] = set()
        self.timeout: set[int] = set()
        self.list_denied = False
        self.list_server_error = False
        self.calls: list[str] = []
        self.document_calls: list[int] = []

        # Auth / token exchange
        self.valid_credentials: dict[str, str] = {"ada": "correct-horse"}
        self.valid_tokens: set[str] | None = None  # None = accept any Authorization
        self.token_exchange_status: int | None = None
        self.next_token: str = "fake-exchanged-token"

        # Upload / tasks
        self.next_document_id = 500
        self.post_document_status: int | None = None
        self.post_document_duplicate = False
        self.post_document_server_error = False
        self.uploaded_files: list[dict] = []
        self.tasks: dict[str, dict] = {}
        self.task_auto_succeed = True
        # When True, SUCCESS tasks omit related_document/result (resolution path).
        self.omit_related_document_on_success = False
        # When True, SUCCESS tasks expose document_id only via result_data.
        self.success_document_id_in_result_data = False
        # When True, SUCCESS tasks use related_document_ids only.
        self.success_via_related_document_ids = False
        # When True, SUCCESS tasks use a JSON string in result.
        self.success_via_json_result = False
        # Override Content-Type for preview/download responses (415 tests).
        self.preview_content_type: str | None = None
        self.content_hashes: dict[str, int] = {}  # sha256 hex -> paperless id
        self.deleted_document_ids: list[int] = []
        self.delete_denied: set[int] = set()
        self.delete_unauthorized: set[int] = set()
        self.delete_server_error: set[int] = set()

    def _authorized(self, request: httpx.Request) -> bool:
        auth = request.headers.get("Authorization", "")
        if self.valid_tokens is None:
            return bool(auth)
        if auth.lower().startswith("token "):
            raw = auth[6:].strip()
        elif auth.lower().startswith("bearer "):
            raw = auth[7:].strip()
        else:
            raw = auth.strip()
        return raw in self.valid_tokens or auth in self.valid_tokens

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        query = request.url.query
        if isinstance(query, (bytes, bytearray)):
            query = query.decode("ascii")
        self.calls.append(f"{request.method} {request.url.path}?{query}")

        if path.endswith("/api/token") and request.method == "POST":
            if self.token_exchange_status is not None:
                return httpx.Response(
                    self.token_exchange_status,
                    json={"detail": "auth failed"},
                )
            try:
                payload = json.loads(request.content.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                return httpx.Response(400, json={"detail": "bad request"})
            username = str(payload.get("username") or "")
            password = str(payload.get("password") or "")
            expected = self.valid_credentials.get(username)
            if expected is None or expected != password:
                return httpx.Response(401, json={"detail": "Unable to log in"})
            return httpx.Response(200, json={"token": self.next_token})

        if path.endswith("/api/documents/post_document") and request.method == "POST":
            if not self._authorized(request):
                return httpx.Response(401, json={"detail": "unauthorized"})
            if self.post_document_duplicate:
                return httpx.Response(400, json={"detail": "duplicate"})
            if self.post_document_server_error or self.post_document_status == 503:
                return httpx.Response(503, json={"detail": "unavailable"})
            if self.post_document_status is not None:
                return httpx.Response(self.post_document_status, json={"detail": "error"})
            body = request.read()
            filename = "upload.bin"
            title: str | None = None
            content_type = request.headers.get("content-type", "")
            text_head = body[:8000].decode("latin-1", errors="ignore")
            marker = 'filename="'
            if marker in text_head:
                start = text_head.index(marker) + len(marker)
                end = text_head.find('"', start)
                if end > start:
                    filename = text_head[start:end]
            title_marker = 'name="title"\r\n\r\n'
            if title_marker in text_head:
                start = text_head.index(title_marker) + len(title_marker)
                end = text_head.find("\r\n", start)
                if end > start:
                    title = text_head[start:end]
            task_id = str(uuid.uuid4())
            doc_id = self.next_document_id
            self.next_document_id += 1
            self.uploaded_files.append(
                {
                    "filename": filename,
                    "title": title,
                    "size": len(body),
                    "content_type": content_type,
                    "task_id": task_id,
                    "document_id": doc_id,
                }
            )
            status = "SUCCESS" if self.task_auto_succeed else "PENDING"
            task_row: dict = {"task_id": task_id, "status": status}
            if self.task_auto_succeed:
                if self.success_document_id_in_result_data:
                    task_row["result_data"] = {"document_id": doc_id}
                elif self.success_via_related_document_ids:
                    task_row["related_document_ids"] = [doc_id]
                elif self.success_via_json_result:
                    task_row["result"] = json.dumps({"document_id": doc_id})
                elif not self.omit_related_document_on_success:
                    task_row["related_document"] = doc_id
                    task_row["result"] = str(doc_id)
            self.tasks[task_id] = task_row
            if self.task_auto_succeed:
                indexed_title = filename if self.omit_related_document_on_success else (title or filename)
                self.documents[doc_id] = {
                    "id": doc_id,
                    "title": indexed_title,
                    "created_date": "2024-06-01",
                }
            return httpx.Response(200, content=f'"{task_id}"', headers={"content-type": "application/json"})

        if path.endswith("/api/tasks") and request.method == "GET":
            if not self._authorized(request):
                return httpx.Response(401, json={"detail": "unauthorized"})
            query = parse_qs(urlparse(str(request.url)).query)
            task_id = (query.get("task_id") or [None])[0]
            if not task_id or task_id not in self.tasks:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[self.tasks[task_id]])

        if "/api/correspondents/" in path:
            resource_id = int(path.split("/")[-1])
            payload = self.correspondents.get(resource_id)
            if payload is None:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(200, json=payload)

        if "/api/document_types/" in path:
            resource_id = int(path.split("/")[-1])
            payload = self.document_types.get(resource_id)
            if payload is None:
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(200, json=payload)

        if path.endswith("/api/documents"):
            if self.list_server_error:
                return httpx.Response(503, json={"detail": "unavailable"})
            if self.list_denied:
                return httpx.Response(403, json={"detail": "forbidden"})
            if not self._authorized(request):
                return httpx.Response(401, json={"detail": "unauthorized"})
            query = parse_qs(urlparse(str(request.url)).query)
            page = int(query.get("page", ["1"])[0])
            page_size = int(query.get("page_size", [str(UNCLASSIFIED_PAGE_SIZE)])[0])
            q = (query.get("query") or [""])[0].strip().lower()
            title_search = (query.get("title_search") or [""])[0]
            title_iexact = (query.get("title__iexact") or [""])[0]
            ordering = (query.get("ordering") or [""])[0]
            created_gte = (query.get("created__date__gte") or [""])[0]
            created_lte = (query.get("created__date__lte") or [""])[0]
            correspondent_q = (query.get("correspondent__name__icontains") or [""])[0].lower()
            doc_type_q = (query.get("document_type__name__icontains") or [""])[0].lower()
            ordered = list(self.documents.values())
            search_mode = False
            if title_search:
                search_mode = True
                needle = title_search.lower()
                ordered = [
                    item
                    for item in ordered
                    if needle in str(item.get("title") or "").lower()
                ]
            if title_iexact:
                ordered = [
                    item
                    for item in ordered
                    if str(item.get("title") or "").lower() == title_iexact.lower()
                ]
            if q:
                search_mode = True
                ordered = [
                    item
                    for item in ordered
                    if q in str(item.get("title") or "").lower()
                ]
            if created_gte:
                ordered = [
                    item
                    for item in ordered
                    if str(item.get("created_date") or "") >= created_gte
                ]
            if created_lte:
                ordered = [
                    item
                    for item in ordered
                    if str(item.get("created_date") or "") <= created_lte
                ]
            if correspondent_q:
                filtered = []
                for item in ordered:
                    cid = item.get("correspondent")
                    name = ""
                    if isinstance(cid, int):
                        name = str(self.correspondents.get(cid, {}).get("name") or "")
                    if correspondent_q in name.lower():
                        filtered.append(item)
                ordered = filtered
            if doc_type_q:
                filtered = []
                for item in ordered:
                    tid = item.get("document_type")
                    name = ""
                    if isinstance(tid, int):
                        name = str(self.document_types.get(tid, {}).get("name") or "")
                    if doc_type_q in name.lower():
                        filtered.append(item)
                ordered = filtered
            reverse = ordering.startswith("-")
            field = ordering.lstrip("-") or "id"
            if field in {"created", "created_date", "added"}:
                ordered.sort(key=lambda item: item.get("created_date") or "", reverse=reverse)
            elif field == "title":
                ordered.sort(key=lambda item: (item.get("title") or "").lower(), reverse=reverse)
            elif field == "correspondent__name":
                def _corr_name(item: dict) -> str:
                    cid = item.get("correspondent")
                    if isinstance(cid, int):
                        return str(self.correspondents.get(cid, {}).get("name") or "").lower()
                    return ""

                ordered.sort(key=_corr_name, reverse=reverse)
            else:
                ordered.sort(key=lambda item: item["id"], reverse=reverse)
            start = (page - 1) * page_size
            chunk = ordered[start : start + page_size]
            if search_mode:
                chunk = [
                    {**item, "__search_hit__": {"score": 1.0, "rank": idx}}
                    for idx, item in enumerate(chunk)
                ]
            return httpx.Response(
                200,
                json={
                    "count": len(ordered),
                    "next": "next" if start + page_size < len(ordered) else None,
                    "previous": "prev" if page > 1 else None,
                    "results": chunk,
                },
            )

        if "/api/documents/" not in path:
            return httpx.Response(404, json={"detail": "not found"})

        parts = path.split("/")
        if len(parts) >= 2 and parts[-1] in {"preview", "download"}:
            kind = parts[-1]
            document_id = int(parts[-2])
            if not self._authorized(request):
                return httpx.Response(401, json={"detail": "unauthorized"})
            if document_id in self.timeout:
                raise httpx.TimeoutException("timed out", request=request)
            if document_id in self.server_error:
                return httpx.Response(503, json={"detail": "unavailable"})
            if document_id in self.unauthorized:
                return httpx.Response(401, json={"detail": "unauthorized"})
            if document_id in self.denied:
                return httpx.Response(403, json={"detail": "forbidden"})
            if document_id not in self.documents:
                return httpx.Response(404, json={"detail": "not found"})
            doc = self.documents[document_id]
            filename = str(doc.get("title") or f"document-{document_id}.pdf")
            content = b"%PDF-fake-" + kind.encode("ascii") + b"-" + str(document_id).encode("ascii")
            content_type = self.preview_content_type or "application/pdf"
            headers = {
                "content-type": content_type,
                "content-disposition": f'attachment; filename="{filename}"',
            }
            return httpx.Response(200, content=content, headers=headers)

        document_id = int(path.split("/")[-1])
        if request.method == "DELETE":
            if not self._authorized(request):
                return httpx.Response(401, json={"detail": "unauthorized"})
            if document_id in self.delete_unauthorized:
                return httpx.Response(401, json={"detail": "unauthorized"})
            if document_id in self.delete_denied:
                return httpx.Response(403, json={"detail": "forbidden"})
            if document_id in self.delete_server_error:
                return httpx.Response(503, json={"detail": "unavailable"})
            if document_id not in self.documents:
                return httpx.Response(404, json={"detail": "not found"})
            del self.documents[document_id]
            self.deleted_document_ids.append(document_id)
            return httpx.Response(204)

        self.document_calls.append(document_id)
        if document_id in self.timeout:
            raise httpx.TimeoutException("timed out", request=request)
        if document_id in self.server_error:
            return httpx.Response(503, json={"detail": "unavailable"})
        if document_id in self.unauthorized:
            return httpx.Response(401, json={"detail": "unauthorized"})
        if document_id in self.denied:
            return httpx.Response(403, json={"detail": "forbidden"})
        if document_id not in self.documents:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(200, json=self.documents[document_id])
