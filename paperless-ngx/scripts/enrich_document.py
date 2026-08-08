#!/usr/bin/env python3
"""Paperless post-consume enrichment (v0.1).

Currently: set document `created` from PDF XMP CreateDate when trustworthy.
AtlasDocs semantics stay out of this hook.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone


def log(msg: str) -> None:
    print(f"[enrich_document] {msg}", flush=True)


def parse_xmp_datetime(raw: str) -> datetime | None:
    """Parse XMP / PDF date strings into aware UTC datetimes."""
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None

    # PDF info style: D:20250531082332+01'00' or D:20230226133723Z00'00'
    if text.startswith("D:"):
        text = text[2:]
        # Split timezone: Z / Z00'00' / +01'00' / -05'00'
        tz = ""
        for sep in ("Z", "+", "-"):
            if sep in text[8:]:  # don't split the date itself
                idx = text.index(sep, 8)
                base, tz = text[:idx], text[idx:]
                break
        else:
            base, tz = text, ""

        base = base.replace("'", "")
        dt = None
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
            try:
                dt = datetime.strptime(base, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None

        if not tz or tz.startswith("Z"):
            return dt.replace(tzinfo=timezone.utc)

        # +01'00' / -05'00' → +0100
        tz_norm = tz.replace("'", "").replace(":", "")
        try:
            dt = datetime.strptime(base + tz_norm, "%Y%m%d%H%M%S%z")
            return dt.astimezone(timezone.utc)
        except ValueError:
            try:
                dt = datetime.strptime(base[:14] + tz_norm, "%Y%m%d%H%M%S%z")
                return dt.astimezone(timezone.utc)
            except ValueError:
                return dt.replace(tzinfo=timezone.utc)

    text = text.replace("Z", "+00:00")
    # Tolerate "+01:00" already; also "2025-03-21T05:10:00+01:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def read_pdf_create_date(path: str) -> date | None:
    import pikepdf

    with pikepdf.open(path) as pdf:
        meta = pdf.open_metadata()
        candidates = [
            meta.get("xmp:CreateDate"),
            meta.get("xmp:ModifyDate"),
        ]
        if pdf.docinfo is not None:
            candidates.append(pdf.docinfo.get("/CreationDate"))

    for raw in candidates:
        if not raw:
            continue
        dt = parse_xmp_datetime(str(raw))
        if dt is not None:
            return dt.date()
    return None


def parse_env_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    # DOCUMENT_CREATED may be "2026-08-07" or a datetime string
    text = text.replace("Z", "+00:00")
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def should_apply_xmp(*, xmp: date, current: date | None, added: date | None) -> bool:
    """Conservative rule for v0.1.

    Apply XMP when it exists and is not just "scanned/ingested now".
    That fixes born-digital payslips where OCR grabbed an unrelated historical date.
    """
    if current is not None and xmp == current:
        return False
    if added is not None and abs((xmp - added).days) <= 7:
        # XMP is near ingestion → likely scan-time metadata; keep Paperless date.
        return False
    return True


def patch_created(doc_id: str, created: date, token: str, base_url: str) -> None:
    import requests

    url = f"{base_url.rstrip('/')}/api/documents/{doc_id}/"
    response = requests.patch(
        url,
        headers={"Authorization": f"Token {token}"},
        json={"created": created.isoformat()},
        timeout=30,
    )
    if response.status_code >= 400:
        log(f"API {response.status_code}: {response.text[:300]}")
        response.raise_for_status()


def main() -> int:
    try:
        doc_id = os.environ["DOCUMENT_ID"]
        source_path = os.environ.get("DOCUMENT_SOURCE_PATH", "")
        token = os.environ.get("PAPERLESS_XMP_UPDATE_TOKEN", "")
        base_url = os.environ.get("PAPERLESS_ENRICH_API_URL", "http://127.0.0.1:8000")

        if not token:
            log("PAPERLESS_XMP_UPDATE_TOKEN missing; skipping")
            return 0

        if not source_path or not source_path.lower().endswith(".pdf"):
            log(f"skip non-pdf doc_id={doc_id}")
            return 0

        if not os.path.isfile(source_path):
            log(f"source missing: {source_path}")
            return 0

        xmp_date = read_pdf_create_date(source_path)
        if xmp_date is None:
            log(f"no XMP/create date doc_id={doc_id}")
            return 0

        current = parse_env_date(os.environ.get("DOCUMENT_CREATED"))
        added = parse_env_date(os.environ.get("DOCUMENT_ADDED"))

        if not should_apply_xmp(xmp=xmp_date, current=current, added=added):
            log(
                f"leave created untouched doc_id={doc_id} "
                f"xmp={xmp_date} current={current} added={added}"
            )
            return 0

        log(f"set created doc_id={doc_id} {current} -> {xmp_date}")
        patch_created(doc_id, xmp_date, token, base_url)
        return 0
    except Exception as exc:  # noqa: BLE001 — never fail consumption
        log(f"error (ignored): {type(exc).__name__}: {exc}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
