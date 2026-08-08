"""UI BFF + SPA shell: HttpOnly session, CSRF, never expose Paperless tokens."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from atlasdocs.api.routes import get_paperless_client
from atlasdocs.api.schemas import (
    ConceptResponse,
    CreateRelationshipRequest,
    DocumentResponse,
    ReconcileRequest,
    ReconcileResponse,
    RelationshipResponse,
    RelationshipTypeResponse,
    UnclassifiedDocumentResponse,
    UnclassifiedPageResponse,
)
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
    ensure_session,
    get_request_session,
    session_store,
    set_session_cookie,
)

router = APIRouter(prefix="/ui", tags=["ui"])
api_router = APIRouter(prefix="/api", tags=["ui-api"])

SPA_DIR = Path(__file__).resolve().parent / "spa"
SPA_INDEX = SPA_DIR / "index.html"

CSRF_HEADER = "X-CSRF-Token"


class SessionResponse(BaseModel):
    authenticated: bool
    csrf_token: str


class ConnectRequest(BaseModel):
    paperless_token: str = Field(..., min_length=1)
    csrf_token: str = Field(..., min_length=1)


class DisconnectRequest(BaseModel):
    csrf_token: str = Field(..., min_length=1)


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


def _validate_csrf(session_csrf: str, csrf_token: str | None) -> bool:
    if not session_csrf or csrf_token is None:
        return False
    try:
        return secrets.compare_digest(
            session_csrf.encode("utf-8"),
            csrf_token.encode("utf-8"),
        )
    except (TypeError, AttributeError):
        return False


def _csrf_from_request(
    csrf_token: str | None = None,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
) -> str | None:
    return x_csrf_token or csrf_token


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, UnauthorizedError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenDocumentError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, UpstreamError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error")


_DOMAIN_ERRORS = (
    UnauthorizedError,
    NotFoundError,
    ForbiddenDocumentError,
    ConflictError,
    ValidationError,
    UpstreamError,
)


def _require_ui_auth(request: Request) -> tuple:
    ui_session = get_request_session(request)
    if ui_session is None or not ui_session.authenticated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return ui_session, ui_session.paperless_authorization or ""


def _serialize_relationship(item) -> RelationshipResponse:
    return RelationshipResponse(
        id=item.id,
        type=item.type,
        target=item.target,
        target_entity_id=getattr(item, "target_entity_id", None),
        origin=item.origin,
        status=item.status,
        source_entity_id=getattr(item, "source_entity_id", None),
    )


def _serialize_document(document) -> DocumentResponse:
    return DocumentResponse(
        paperless_document_id=document.paperless_document_id,
        entity_id=document.entity_id or None,
        title=document.title,
        created_date=document.created_date,
        correspondent=document.correspondent,
        document_type=document.document_type,
        open_url=document.open_url,
        relationships=[_serialize_relationship(item) for item in document.relationships],
    )


def _json_with_session(payload: dict | BaseModel, ui_session, status_code: int = 200) -> JSONResponse:
    body = payload.model_dump() if isinstance(payload, BaseModel) else payload
    response = JSONResponse(content=body, status_code=status_code)
    set_session_cookie(response, ui_session)
    return response


@api_router.get("/session", response_model=SessionResponse)
def get_session(request: Request) -> JSONResponse:
    ui_session = ensure_session(request)
    return _json_with_session(
        SessionResponse(
            authenticated=ui_session.authenticated,
            csrf_token=ui_session.csrf_token,
        ),
        ui_session,
    )


@api_router.post("/connect", response_model=SessionResponse)
def connect(request: Request, payload: ConnectRequest) -> JSONResponse:
    ui_session = ensure_session(request)
    if not _validate_csrf(ui_session.csrf_token, payload.csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")

    token = payload.paperless_token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paperless token is required")
    if not token.lower().startswith("token ") and not token.lower().startswith("bearer "):
        token = f"Token {token}"

    session_store.delete(ui_session.id)
    ui_session = session_store.create(paperless_authorization=token)
    return _json_with_session(
        SessionResponse(authenticated=True, csrf_token=ui_session.csrf_token),
        ui_session,
    )


@api_router.post("/disconnect", response_model=SessionResponse)
def disconnect(request: Request, payload: DisconnectRequest) -> Response:
    ui_session = get_request_session(request)
    if ui_session is not None and _validate_csrf(ui_session.csrf_token, payload.csrf_token):
        session_store.delete(ui_session.id)
    fresh = session_store.create()
    # _json_with_session sets the replacement cookie; no clear/set dance needed.
    return _json_with_session(
        SessionResponse(authenticated=False, csrf_token=fresh.csrf_token),
        fresh,
    )


@api_router.get("/documents", response_model=UnclassifiedPageResponse)
def list_unclassified(
    request: Request,
    unclassified: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=UNCLASSIFIED_PAGE_SIZE, ge=1, le=UNCLASSIFIED_PAGE_SIZE),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    if not unclassified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only unclassified=true listing is supported",
        )
    try:
        result = service.list_unclassified(auth, page=page, page_size=page_size)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    payload = UnclassifiedPageResponse(
        items=[
            UnclassifiedDocumentResponse(
                paperless_document_id=item.paperless_document_id,
                title=item.title,
                created_date=item.created_date,
                correspondent=item.correspondent,
                document_type=item.document_type,
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        paperless_count=result.paperless_count,
        has_next=result.has_next,
        has_previous=result.has_previous,
        next_page=result.next_page,
    )
    return _json_with_session(payload, ui_session)


@api_router.get("/documents/{paperless_document_id}", response_model=DocumentResponse)
def get_document(
    request: Request,
    paperless_document_id: int,
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    try:
        document = service.get_document(paperless_document_id, token=auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _json_with_session(_serialize_document(document), ui_session)


@api_router.post(
    "/documents/{paperless_document_id}/relationships",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_relationship(
    request: Request,
    paperless_document_id: int,
    payload: CreateRelationshipRequest,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")

    provided = sum(
        1
        for value in (payload.target, payload.target_entity_id, payload.target_paperless_id)
        if value is not None
    )
    if provided != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of target, target_entity_id, or target_paperless_id",
        )

    try:
        document = service.add_document_relationship(
            paperless_document_id,
            payload.relationship,
            token=auth,
            target=payload.target,
            target_entity_id=payload.target_entity_id,
            target_paperless_id=payload.target_paperless_id,
        )
        if not session_store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc

    return _json_with_session(_serialize_document(document), ui_session, status_code=201)


@api_router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    request: Request,
    relationship_id: str,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    service: DocumentService = Depends(get_ui_service),
) -> Response:
    ui_session, auth = _require_ui_auth(request)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        service.delete_relationship(relationship_id, token=auth)
        if not session_store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, ui_session)
    return response


@api_router.get("/relationship-types", response_model=list[RelationshipTypeResponse])
def list_relationship_types(
    request: Request,
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    try:
        rows = service.list_relationship_types(auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    payload = [
        RelationshipTypeResponse(
            code=item.code,
            name=item.name,
            target_ontology=item.target_ontology,
            directionality=item.directionality,
            inverse=item.inverse,
        )
        for item in rows
    ]
    response = JSONResponse(content=[item.model_dump() for item in payload])
    set_session_cookie(response, ui_session)
    return response


@api_router.get("/concepts", response_model=list[ConceptResponse])
def search_concepts(
    request: Request,
    q: str = Query(default=""),
    ontology: str | None = Query(default=None),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    try:
        concepts = service.search_concepts(q=q, ontology_code=ontology, token=auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    payload = [ConceptResponse(code=item.code, name=item.name) for item in concepts]
    response = JSONResponse(content=[item.model_dump() for item in payload])
    set_session_cookie(response, ui_session)
    return response


@api_router.post("/reconcile", response_model=ReconcileResponse)
def reconcile(
    request: Request,
    payload: ReconcileRequest,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    service: ReconcileService = Depends(get_ui_reconcile_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        summary = service.reconcile(auth, dry_run=payload.dry_run, limit=payload.limit)
        if not session_store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc

    body = ReconcileResponse(
        dry_run=summary.dry_run,
        limit=summary.limit,
        paperless_documents_seen=summary.paperless_documents_seen,
        created=summary.created,
        already_present=summary.already_present,
        missing_in_paperless=summary.missing_in_paperless,
        inaccessible_in_paperless=summary.inaccessible_in_paperless,
        errors=summary.errors,
        human_summary=summary.human_summary(),
    )
    return _json_with_session(body, ui_session)


def spa_index_response() -> Response:
    if SPA_INDEX.is_file():
        return FileResponse(SPA_INDEX, media_type="text/html")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "UI assets not built. Run `cd frontend && npm run build` or use the Docker image."
        },
    )


@router.get("")
@router.get("/")
def spa_root() -> Response:
    return spa_index_response()


@router.get("/connect")
@router.get("/reconcile")
@router.get("/documents/{paperless_document_id}")
def spa_client_routes(paperless_document_id: int | None = None) -> Response:
    _ = paperless_document_id
    return spa_index_response()


router.include_router(api_router)
