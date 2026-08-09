#!/usr/bin/env python3
"""Manual live ingestion smoke against a real Paperless (+ optional AtlasDocs).

Credentials and endpoints come only from environment variables. Never pass
tokens on the CLI. Output is limited to job/task fingerprints, state, and
error codes — never tokens, document bytes, or raw HTTP bodies.

Required env (Paperless-only mode):
  PAPERLESS_BASE_URL
  PAPERLESS_TOKEN                 — or PAPERLESS_USERNAME + PAPERLESS_PASSWORD

Optional:
  ATLASDOCS_BASE_URL              — when set, exercise AtlasDocs UI ingest BFF
  ATLASDOCS_USERNAME / ATLASDOCS_PASSWORD — Paperless login via AtlasDocs connect
  INGEST_SMOKE_FIXTURE            — default: e2e/fixtures/ingest-smoke.pdf
  INGEST_SMOKE_TIMEOUT_SECONDS    — default: 180

Examples:
  PAPERLESS_BASE_URL=http://10.10.0.12:3040 \\
  PAPERLESS_USERNAME=... PAPERLESS_PASSWORD=... \\
  python scripts/live_ingest_smoke.py

  ATLASDOCS_BASE_URL=http://127.0.0.1:8080 \\
  PAPERLESS_USERNAME=... PAPERLESS_PASSWORD=... \\
  python scripts/live_ingest_smoke.py /path/to/file.pdf
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener


def _die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def _require_http_base(url: str, *, label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        _die(f"{label} must be an http(s) URL")
    return url.rstrip("/")


def _task_fp(task_id: str) -> str:
    return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:8]


def _looks_like_task_id(text: str) -> bool:
    stripped = text.strip().strip('"')
    return bool(stripped) and "\n" not in stripped and len(stripped) < 80 and "{" not in stripped


def _coerce_document_id(value: Any) -> int | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    return int(text)


class _DenyRedirects(HTTPRedirectHandler):
    """Refuse redirects so Authorization is never replayed to another origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise HTTPError(req.full_url, code, "redirect refused", headers, fp)


class _HttpClient:
    """Cookie-aware HTTP helper restricted to http(s) URLs without redirects."""

    def __init__(self) -> None:
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()), _DenyRedirects())

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        timeout: float = 60.0,
    ) -> tuple[int, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            _die("refusing non-http(s) request URL")
        req = Request(url, data=data, headers=headers or {}, method=method)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                status = getattr(resp, "status", None) or resp.getcode()
        except HTTPError as exc:
            raw = exc.read() if exc.fp is not None else b""
            status = exc.code
        except URLError as exc:
            _die(f"request failed: {type(exc.reason).__name__ if exc.reason else 'URLError'}")
        if not raw:
            return int(status), None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return int(status), {"_non_json_bytes": len(raw)}
        try:
            return int(status), json.loads(text)
        except json.JSONDecodeError:
            # Paperless post_document often returns a bare quoted UUID string.
            if _looks_like_task_id(text):
                return int(status), text.strip().strip('"')
            return int(status), {"_non_json_bytes": len(raw)}


def _multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = "----AtlasDocsSmoke" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    for name, (filename, content, content_type) in files.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
            + content
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _parse_task_id(task_body: Any) -> str:
    if isinstance(task_body, str):
        return task_body.strip().strip('"')
    if isinstance(task_body, dict):
        for key in ("task_id", "id", "task"):
            value = task_body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _paperless_token(http: _HttpClient, base: str) -> str:
    token = _env("PAPERLESS_TOKEN")
    if token:
        return token if token.lower().startswith(("token ", "bearer ")) else f"Token {token}"
    user = _env("PAPERLESS_USERNAME")
    password = _env("PAPERLESS_PASSWORD")
    if not user or not password:
        _die("set PAPERLESS_TOKEN or PAPERLESS_USERNAME+PAPERLESS_PASSWORD")
    status, payload = http.request(
        "POST",
        f"{base}/api/token/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": user, "password": password}).encode(),
    )
    if status >= 400 or not isinstance(payload, dict) or not payload.get("token"):
        _die("paperless token exchange failed")
    return f"Token {payload['token']}"


def _emit(**fields: object) -> None:
    print(json.dumps(fields, sort_keys=True))


def smoke_paperless(base: str, fixture: Path, timeout: int) -> int:
    http = _HttpClient()
    auth = {"Authorization": _paperless_token(http, base)}
    # Omit title so Paperless derives a normal title (matches AtlasDocs Phase A).
    body, content_type = _multipart(
        {},
        {"document": (fixture.name, fixture.read_bytes(), "application/pdf")},
    )
    status, task_body = http.request(
        "POST",
        f"{base}/api/documents/post_document/",
        headers={**auth, "Content-Type": content_type},
        data=body,
        timeout=120,
    )
    if status >= 400:
        _die("paperless upload failed")
    task_id = _parse_task_id(task_body)
    if not task_id:
        _die("paperless upload missing task id")

    deadline = time.time() + timeout
    state = "PROCESSING"
    error_code = None
    doc_id = None
    while time.time() < deadline:
        status, payload = http.request(
            "GET",
            f"{base}/api/tasks/?{urlencode({'task_id': task_id})}",
            headers=auth,
        )
        if status >= 400:
            _die("paperless task poll failed")
        rows = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not rows:
            time.sleep(1)
            continue
        row = rows[0] if isinstance(rows[0], dict) else {}
        task_status = str(row.get("status") or row.get("state") or "").upper()
        related = row.get("related_document")
        related_ids = row.get("related_document_ids") if isinstance(row.get("related_document_ids"), list) else []
        result_data = row.get("result_data") if isinstance(row.get("result_data"), dict) else {}
        candidates = [related, *related_ids, result_data.get("document_id"), result_data.get("duplicate_of")]
        for candidate in candidates:
            coerced = _coerce_document_id(candidate)
            if coerced is not None:
                doc_id = coerced
                break
        if task_status in {"SUCCESS", "FAILURE"}:
            if task_status == "FAILURE":
                state = "FAILED"
                error_code = "paperless_task_failed"
            elif doc_id is not None:
                state = "READY"
            else:
                # No title-search fallback: task payload must expose the document id.
                state = "RETRYABLE_FAILURE"
                error_code = "missing_document"
            break
        time.sleep(1)
    else:
        state = "FAILED"
        error_code = "timeout"

    _emit(
        mode="paperless",
        job_id=None,
        task_fingerprint=_task_fp(task_id),
        state=state,
        error_code=error_code,
        resolved=doc_id is not None,
    )
    if doc_id is not None:
        http.request("DELETE", f"{base}/api/documents/{int(doc_id)}/", headers=auth)
    return 0 if state == "READY" else 1


def smoke_atlasdocs(atlas_base: str, fixture: Path, timeout: int) -> int:
    user = _env("ATLASDOCS_USERNAME") or _env("PAPERLESS_USERNAME")
    password = _env("ATLASDOCS_PASSWORD") or _env("PAPERLESS_PASSWORD")
    token = _env("PAPERLESS_TOKEN")
    if not ((user and password) or token):
        _die("AtlasDocs mode needs username/password or PAPERLESS_TOKEN")

    http = _HttpClient()
    base = atlas_base
    status, session = http.request("GET", f"{base}/ui/api/session")
    if status >= 400 or not isinstance(session, dict):
        _die("atlasdocs session failed")
    csrf = session.get("csrf_token")

    if user and password:
        status, connected = http.request(
            "POST",
            f"{base}/ui/api/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"csrf_token": csrf, "username": user, "password": password}).encode(),
        )
    else:
        status, connected = http.request(
            "POST",
            f"{base}/ui/api/connect",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"csrf_token": csrf, "paperless_token": token}).encode(),
        )
    if status >= 400 or not isinstance(connected, dict):
        _die("atlasdocs authentication failed")
    csrf = connected.get("csrf_token") or csrf

    body, content_type = _multipart(
        {},
        {"document": (fixture.name, fixture.read_bytes(), "application/pdf")},
    )
    status, job = http.request(
        "POST",
        f"{base}/ui/api/ingest",
        headers={"Content-Type": content_type, "X-CSRF-Token": str(csrf)},
        data=body,
        timeout=120,
    )
    if status >= 400 or not isinstance(job, dict) or not job.get("id"):
        _die("atlasdocs ingest enqueue failed")
    job_id = str(job["id"])
    _emit(
        mode="atlasdocs",
        job_id=job_id,
        task_fingerprint=None,
        state=job.get("state"),
        error_code=job.get("error_code"),
    )

    deadline = time.time() + timeout
    last = job
    while time.time() < deadline:
        status, last = http.request("GET", f"{base}/ui/api/ingest/jobs/{job_id}")
        if status >= 400 or not isinstance(last, dict):
            _die("atlasdocs job poll failed")
        state = str(last.get("state") or "")
        _emit(
            mode="atlasdocs",
            job_id=job_id,
            task_fingerprint=_task_fp(str(last["paperless_task_id"]))
            if last.get("paperless_task_id")
            else None,
            state=state,
            error_code=last.get("error_code"),
        )
        if state in {"READY", "FAILED", "RETRYABLE_FAILURE"}:
            break
        time.sleep(2)
    else:
        _emit(
            mode="atlasdocs",
            job_id=job_id,
            task_fingerprint=None,
            state="TIMEOUT",
            error_code="timeout",
        )
        return 1
    return 0 if str(last.get("state")) == "READY" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture",
        nargs="?",
        default=_env("INGEST_SMOKE_FIXTURE", "e2e/fixtures/ingest-smoke.pdf"),
        help="Path to a real PDF fixture (default: e2e/fixtures/ingest-smoke.pdf)",
    )
    args = parser.parse_args(argv)
    fixture = Path(args.fixture)
    if not fixture.is_file():
        _die(f"fixture not found: {fixture}")
    timeout = int(_env("INGEST_SMOKE_TIMEOUT_SECONDS", "180") or "180")
    atlas = _env("ATLASDOCS_BASE_URL")
    paperless = _env("PAPERLESS_BASE_URL")
    if atlas:
        return smoke_atlasdocs(_require_http_base(atlas, label="ATLASDOCS_BASE_URL"), fixture, timeout)
    if not paperless:
        _die("set ATLASDOCS_BASE_URL or PAPERLESS_BASE_URL")
    return smoke_paperless(_require_http_base(paperless, label="PAPERLESS_BASE_URL"), fixture, timeout)


if __name__ == "__main__":
    raise SystemExit(main())
