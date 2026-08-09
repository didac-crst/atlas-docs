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
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


def _task_fp(task_id: str) -> str:
    return hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:8]


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    req = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except HTTPError as exc:
        raw = exc.read() if exc.fp is not None else b""
        status = exc.code
    except URLError as exc:
        _die(f"request failed: {type(exc.reason).__name__ if exc.reason else 'URLError'}")
    if not raw:
        return status, None
    ctype_hint = raw[:1]
    try:
        return status, json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # Never print bodies; only length for non-JSON.
        return status, {"_non_json_bytes": len(raw), "_starts_with": ctype_hint.decode("latin-1", "replace")}


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


def _paperless_token(base: str) -> str:
    token = _env("PAPERLESS_TOKEN")
    if token:
        return token if token.lower().startswith(("token ", "bearer ")) else f"Token {token}"
    user = _env("PAPERLESS_USERNAME")
    password = _env("PAPERLESS_PASSWORD")
    if not user or not password:
        _die("set PAPERLESS_TOKEN or PAPERLESS_USERNAME+PAPERLESS_PASSWORD")
    status, payload = _request(
        "POST",
        f"{base.rstrip('/')}/api/token/",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": user, "password": password}).encode(),
    )
    if status >= 400 or not isinstance(payload, dict) or not payload.get("token"):
        _die("paperless token exchange failed")
    return f"Token {payload['token']}"


def _emit(**fields: object) -> None:
    print(json.dumps(fields, sort_keys=True))


def smoke_paperless(base: str, fixture: Path, timeout: int) -> int:
    auth = {"Authorization": _paperless_token(base)}
    correlation = f"atlasdocs:{uuid.uuid4()}"
    body, content_type = _multipart(
        {"title": correlation},
        {"document": (fixture.name, fixture.read_bytes(), "application/pdf")},
    )
    status, task_body = _request(
        "POST",
        f"{base.rstrip('/')}/api/documents/post_document/",
        headers={**auth, "Content-Type": content_type},
        data=body,
        timeout=120,
    )
    if status >= 400:
        _die("paperless upload failed")
    if isinstance(task_body, str):
        task_id = task_body.strip().strip('"')
    elif isinstance(task_body, dict):
        task_id = str(task_body.get("task_id") or task_body.get("id") or "").strip()
    else:
        task_id = ""
    if not task_id:
        _die("paperless upload missing task id")

    deadline = time.time() + timeout
    state = "PROCESSING"
    error_code = None
    doc_id = None
    while time.time() < deadline:
        status, payload = _request(
            "GET",
            f"{base.rstrip('/')}/api/tasks/?{urlencode({'task_id': task_id})}",
            headers=auth,
        )
        rows = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not rows:
            time.sleep(1)
            continue
        row = rows[0] if isinstance(rows[0], dict) else {}
        task_status = str(row.get("status") or row.get("state") or "").upper()
        related = row.get("related_document_ids") if isinstance(row.get("related_document_ids"), list) else []
        result_data = row.get("result_data") if isinstance(row.get("result_data"), dict) else {}
        if related:
            doc_id = related[0]
        elif result_data.get("document_id") is not None:
            doc_id = result_data.get("document_id")
        if task_status in {"SUCCESS", "FAILURE"}:
            if task_status == "FAILURE":
                state = "FAILED"
                error_code = "paperless_task_failed"
            elif doc_id is not None:
                state = "READY"
            else:
                state = "RESOLVING_DOCUMENT"
            break
        time.sleep(1)
    else:
        state = "FAILED"
        error_code = "timeout"

    if state == "RESOLVING_DOCUMENT":
        status, payload = _request(
            "GET",
            f"{base.rstrip('/')}/api/documents/?{urlencode({'title_search': correlation, 'page_size': 25})}",
            headers=auth,
        )
        results = payload.get("results") if isinstance(payload, dict) else []
        exact = [
            item.get("id")
            for item in (results or [])
            if isinstance(item, dict) and str(item.get("title") or "").strip() == correlation
        ]
        if len(exact) == 1:
            doc_id = exact[0]
            state = "READY"
            error_code = None
        else:
            state = "RETRYABLE_FAILURE"
            error_code = "missing_document"

    _emit(
        mode="paperless",
        job_id=None,
        task_fingerprint=_task_fp(task_id),
        state=state,
        error_code=error_code,
        resolved=doc_id is not None,
    )
    # Best-effort cleanup of smoke document (never print title/body).
    if doc_id is not None:
        _request("DELETE", f"{base.rstrip('/')}/api/documents/{int(doc_id)}/", headers=auth)
    return 0 if state == "READY" else 1


def smoke_atlasdocs(atlas_base: str, fixture: Path, timeout: int) -> int:
    user = _env("ATLASDOCS_USERNAME") or _env("PAPERLESS_USERNAME")
    password = _env("ATLASDOCS_PASSWORD") or _env("PAPERLESS_PASSWORD")
    token = _env("PAPERLESS_TOKEN")
    if not ((user and password) or token):
        _die("AtlasDocs mode needs username/password or PAPERLESS_TOKEN")

    base = atlas_base.rstrip("/")
    status, session = _request("GET", f"{base}/ui/api/session")
    if status >= 400 or not isinstance(session, dict):
        _die("atlasdocs session failed")
    csrf = session.get("csrf_token")

    if user and password:
        status, connected = _request(
            "POST",
            f"{base}/ui/api/login",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"csrf_token": csrf, "username": user, "password": password}).encode(),
        )
    else:
        status, connected = _request(
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
    status, job = _request(
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
        status, last = _request("GET", f"{base}/ui/api/ingest/jobs/{job_id}")
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
        return smoke_atlasdocs(atlas, fixture, timeout)
    if not paperless:
        _die("set ATLASDOCS_BASE_URL or PAPERLESS_BASE_URL")
    return smoke_paperless(paperless, fixture, timeout)


if __name__ == "__main__":
    raise SystemExit(main())
