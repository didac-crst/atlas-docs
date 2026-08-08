"""Deterministic Paperless REST stand-in for API and browser smoke tests."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE


class FakePaperlessTransport(httpx.BaseTransport):
    """Deterministic Paperless REST stand-in. No real HTTP or Paperless DB."""

    def __init__(self) -> None:
        self.documents: dict[int, dict] = {
            184: {
                "id": 184,
                "title": "Payslip Germany",
                "created_date": "2024-01-15",
                "correspondent": {"name": "Acme Payroll"},
                "document_type": {"name": "Payslip"},
            },
            185: {
                "id": 185,
                "title": "Invoice Spain",
                "created_date": "2024-02-01",
                "correspondent": {"name": "Contoso"},
                "document_type": {"name": "Invoice"},
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

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        self.calls.append(f"{request.method} {request.url.path}?{request.url.query}")

        if path.endswith("/api/documents"):
            if self.list_server_error:
                return httpx.Response(503, json={"detail": "unavailable"})
            if self.list_denied:
                return httpx.Response(403, json={"detail": "forbidden"})
            query = parse_qs(urlparse(str(request.url)).query)
            page = int(query.get("page", ["1"])[0])
            page_size = int(query.get("page_size", [str(UNCLASSIFIED_PAGE_SIZE)])[0])
            ordered = sorted(self.documents.values(), key=lambda item: item["id"])
            start = (page - 1) * page_size
            chunk = ordered[start : start + page_size]
            return httpx.Response(
                200,
                json={
                    "count": len(ordered),
                    "next": "next" if start + page_size < len(ordered) else None,
                    "previous": "prev" if page > 1 else None,
                    "results": chunk,
                },
            )

        document_id = int(path.split("/")[-1])
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
