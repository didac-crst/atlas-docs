"""Browser workbench routes: server-side session, CSRF, Jinja UI."""

from __future__ import annotations

import secrets
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from atlasdocs.api.routes import get_paperless_client
from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE
from atlasdocs.db.session import get_db
from atlasdocs.services.documents import (
    ConflictError,
    DocumentService,
    ForbiddenDocumentError,
    NotFoundError,
    UnauthorizedError,
    UpstreamError,
    ValidationError,
)
from atlasdocs.services.paperless import PaperlessClient
from atlasdocs.services.reconcile import ReconcileService
from atlasdocs.ui.sessions import (
    clear_session_cookie,
    ensure_session,
    get_request_session,
    session_store,
    set_session_cookie,
)

router = APIRouter(prefix="/ui", tags=["ui"])
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def get_ui_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> DocumentService:
    return DocumentService(session, paperless)


def get_ui_reconcile_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> ReconcileService:
    return ReconcileService(session, paperless)


def _validate_csrf(session_csrf: str, csrf_token: str) -> bool:
    if not session_csrf or csrf_token is None:
        return False
    try:
        return secrets.compare_digest(
            session_csrf.encode("utf-8"),
            csrf_token.encode("utf-8"),
        )
    except (TypeError, AttributeError):
        return False


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ForbiddenDocumentError):
        return "Document not found"
    return str(exc)


def _redirect_notice(paperless_document_id: int, page: int, notice: str) -> RedirectResponse:
    return RedirectResponse(
        url=(
            f"/ui/documents/{paperless_document_id}"
            f"?page={page}&notice={quote(notice)}"
        ),
        status_code=HTTP_303_SEE_OTHER,
    )


def _concepts_map(service: DocumentService) -> dict[str, list[dict[str, str]]]:
    mapping: dict[str, list[dict[str, str]]] = {}
    for ontology_code in service.list_ontology_codes():
        try:
            mapping[ontology_code] = [
                {"code": item.code, "name": item.name}
                for item in service.list_concepts(ontology_code)
            ]
        except NotFoundError:
            mapping[ontology_code] = []
    all_concepts: list[dict[str, str]] = []
    for concepts in mapping.values():
        all_concepts.extend(concepts)
    mapping["*"] = all_concepts
    return mapping


@router.get("/connect", response_class=HTMLResponse)
def connect_form(request: Request) -> HTMLResponse:
    ui_session = ensure_session(request)
    response = templates.TemplateResponse(
        request,
        "connect.html",
        {
            "csrf_token": ui_session.csrf_token,
            "error": None,
            "authenticated": ui_session.authenticated,
        },
    )
    set_session_cookie(response, ui_session)
    return response


@router.post("/connect", response_class=HTMLResponse)
async def connect_submit(
    request: Request,
    csrf_token: str = Form(...),
    paperless_token: str = Form(...),
):
    ui_session = ensure_session(request)
    if not _validate_csrf(ui_session.csrf_token, csrf_token):
        response = templates.TemplateResponse(
            request,
            "connect.html",
            {
                "csrf_token": ui_session.csrf_token,
                "error": "Invalid CSRF token",
                "authenticated": False,
            },
            status_code=400,
        )
        set_session_cookie(response, ui_session)
        return response

    token = paperless_token.strip()
    if not token:
        response = templates.TemplateResponse(
            request,
            "connect.html",
            {
                "csrf_token": ui_session.csrf_token,
                "error": "Paperless token is required",
                "authenticated": False,
            },
            status_code=400,
        )
        set_session_cookie(response, ui_session)
        return response

    if not token.lower().startswith("token ") and not token.lower().startswith("bearer "):
        token = f"Token {token}"

    # Replace any prior session so logout/reuse cannot revive old credentials casually.
    session_store.delete(ui_session.id)
    ui_session = session_store.create(paperless_authorization=token)
    response = RedirectResponse(url="/ui", status_code=HTTP_303_SEE_OTHER)
    set_session_cookie(response, ui_session)
    return response


@router.post("/disconnect")
def disconnect(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    ui_session = get_request_session(request)
    if ui_session is not None and _validate_csrf(ui_session.csrf_token, csrf_token):
        session_store.delete(ui_session.id)
    response = RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def workbench(
    request: Request,
    page: int = 1,
    service: DocumentService = Depends(get_ui_service),
) -> Response:
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)

    auth = ui_session.paperless_authorization
    error = None
    queue = None
    try:
        queue = service.list_unclassified(auth, page=page, page_size=UNCLASSIFIED_PAGE_SIZE)
    except (UnauthorizedError, ForbiddenDocumentError, NotFoundError, UpstreamError, ValidationError) as exc:
        error = _error_message(exc)

    response = templates.TemplateResponse(
        request,
        "workbench.html",
        {
            "csrf_token": ui_session.csrf_token,
            "queue": queue,
            "document": None,
            "relationship_types": service.list_relationship_types(),
            "concepts_by_ontology": _concepts_map(service),
            "error": error,
            "notice": None,
            "selected_id": None,
            "page": page,
            "authenticated": True,
        },
    )
    set_session_cookie(response, ui_session)
    return response


@router.get("/documents/{paperless_document_id}", response_class=HTMLResponse)
def document_detail(
    request: Request,
    paperless_document_id: int,
    page: int = 1,
    service: DocumentService = Depends(get_ui_service),
) -> Response:
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)

    auth = ui_session.paperless_authorization
    error = None
    notice = request.query_params.get("notice")
    queue = None
    document = None
    try:
        queue = service.list_unclassified(auth, page=page, page_size=UNCLASSIFIED_PAGE_SIZE)
        document = service.get_document(paperless_document_id, token=auth)
    except (UnauthorizedError, ForbiddenDocumentError, NotFoundError, UpstreamError, ValidationError) as exc:
        error = _error_message(exc)

    response = templates.TemplateResponse(
        request,
        "workbench.html",
        {
            "csrf_token": ui_session.csrf_token,
            "queue": queue,
            "document": document,
            "relationship_types": service.list_relationship_types(),
            "concepts_by_ontology": _concepts_map(service),
            "error": error,
            "notice": notice,
            "selected_id": paperless_document_id,
            "page": page,
            "authenticated": True,
        },
    )
    set_session_cookie(response, ui_session)
    return response


@router.post("/documents/{paperless_document_id}/relationships")
def classify_document(
    request: Request,
    paperless_document_id: int,
    csrf_token: str = Form(...),
    relationship: str = Form(...),
    target: str = Form(...),
    page: int = Form(default=1),
    service: DocumentService = Depends(get_ui_service),
):
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
    if not _validate_csrf(ui_session.csrf_token, csrf_token):
        return _redirect_notice(paperless_document_id, page, "Invalid CSRF token")

    try:
        service.add_relationship(
            paperless_document_id,
            relationship,
            target,
            token=ui_session.paperless_authorization,
        )
        notice = "Relationship saved"
        if not session_store.rotate_csrf(ui_session):
            response = RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
            clear_session_cookie(response)
            return response
    except (ConflictError, ValidationError, ForbiddenDocumentError, NotFoundError, UpstreamError) as exc:
        notice = _error_message(exc)

    response = _redirect_notice(paperless_document_id, page, notice)
    set_session_cookie(response, ui_session)
    return response


@router.post("/relationships/{relationship_id}/delete")
def delete_relationship_form(
    request: Request,
    relationship_id: str,
    csrf_token: str = Form(...),
    paperless_document_id: int = Form(...),
    page: int = Form(default=1),
    service: DocumentService = Depends(get_ui_service),
):
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
    if not _validate_csrf(ui_session.csrf_token, csrf_token):
        return _redirect_notice(paperless_document_id, page, "Invalid CSRF token")

    try:
        service.delete_relationship(relationship_id, token=ui_session.paperless_authorization)
        notice = "Relationship removed"
        if not session_store.rotate_csrf(ui_session):
            response = RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
            clear_session_cookie(response)
            return response
    except (ValidationError, ForbiddenDocumentError, NotFoundError, UpstreamError) as exc:
        notice = _error_message(exc)

    response = _redirect_notice(paperless_document_id, page, notice)
    set_session_cookie(response, ui_session)
    return response


@router.get("/reconcile", response_class=HTMLResponse)
def reconcile_page(request: Request) -> Response:
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)

    response = templates.TemplateResponse(
        request,
        "reconcile.html",
        {
            "csrf_token": ui_session.csrf_token,
            "authenticated": True,
            "error": None,
            "notice": None,
            "summary": None,
            "dry_run_default": True,
        },
    )
    set_session_cookie(response, ui_session)
    return response


@router.post("/reconcile", response_class=HTMLResponse)
def reconcile_submit(
    request: Request,
    csrf_token: str = Form(...),
    dry_run: str | None = Form(default=None),
    limit: str | None = Form(default=None),
    service: ReconcileService = Depends(get_ui_reconcile_service),
) -> Response:
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        return RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)

    error = None
    notice = None
    summary_view = None
    if not _validate_csrf(ui_session.csrf_token, csrf_token):
        error = "Invalid CSRF token"
    else:
        parsed_limit = None
        if limit and limit.strip():
            try:
                parsed_limit = int(limit.strip())
                if parsed_limit < 1:
                    raise ValueError
            except ValueError:
                error = "Limit must be a positive integer"
        if error is None:
            try:
                result = service.reconcile(
                    ui_session.paperless_authorization or "",
                    dry_run=bool(dry_run),
                    limit=parsed_limit,
                )
                summary_view = SimpleNamespace(
                    human_summary=result.human_summary(),
                    created=result.created,
                    missing_in_paperless=result.missing_in_paperless,
                    inaccessible_in_paperless=result.inaccessible_in_paperless,
                    already_present=result.already_present,
                    errors=result.errors,
                )
                notice = "Dry-run complete" if result.dry_run else "Reconciliation applied"
                if not session_store.rotate_csrf(ui_session):
                    response = RedirectResponse(url="/ui/connect", status_code=HTTP_303_SEE_OTHER)
                    clear_session_cookie(response)
                    return response
            except Exception as exc:  # noqa: BLE001 - surface as UI error state
                error = str(exc)

    response = templates.TemplateResponse(
        request,
        "reconcile.html",
        {
            "csrf_token": ui_session.csrf_token,
            "authenticated": True,
            "error": error,
            "notice": notice,
            "summary": summary_view,
            "dry_run_default": bool(dry_run) if dry_run is not None else True,
        },
        status_code=400 if error else 200,
    )
    set_session_cookie(response, ui_session)
    return response
