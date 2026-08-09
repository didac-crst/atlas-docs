"""UI BFF + SPA shell: HttpOnly session, CSRF, never expose Paperless tokens."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from atlasdocs.api.routes import get_paperless_client
from atlasdocs.api.schemas import (
    BulkRelationshipResultResponse,
    BulkRelationshipsRequest,
    BulkRelationshipsResponse,
    ConceptResponse,
    CreateRelationshipRequest,
    DocumentResponse,
    EntitySearchHitResponse,
    HomeSummaryResponse,
    CountStatResponse,
    RecentDocumentResponse,
    RecentKnowledgeResponse,
    IngestionJobResponse,
    IngestionJobsResponse,
    ReconcileRequest,
    ReconcileResponse,
    RelationshipResponse,
    RelationshipTypeResponse,
    UnclassifiedDocumentResponse,
    UnclassifiedPageResponse,
)
from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE
from atlasdocs.db.session import get_db
from atlasdocs.security.redact import redact_secrets
from atlasdocs.services.documents import (
    ConflictError,
    DocumentService,
    ForbiddenDocumentError,
    NotFoundError,
    UnauthorizedError,
    UpstreamError,
    ValidationError,
)
from atlasdocs.services.home import HomeService
from atlasdocs.services.ingest import DuplicateIngestError, IngestionService
from atlasdocs.services.login_rate_limit import login_rate_limiter
from atlasdocs.services.paperless import (
    PaperlessAuthError,
    PaperlessClient,
    PaperlessError,
    PaperlessNotFoundError,
    PaperlessUnavailableError,
)
from atlasdocs.services.reconcile import ReconcileService
from atlasdocs.ui.sessions import (
    DbSessionStore,
    ensure_session,
    get_request_session,
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


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
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


def get_ui_ingest_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> IngestionService:
    return IngestionService(session, paperless)


def get_ui_home_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> HomeService:
    return HomeService(session, paperless)


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


def _to_http_error(exc: Exception) -> HTTPException:
    detail = redact_secrets(str(exc))
    if isinstance(exc, UnauthorizedError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    if isinstance(exc, ForbiddenDocumentError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if isinstance(exc, DuplicateIngestError):
        msg = detail
        if exc.paperless_document_id is not None:
            msg = f"{msg}; paperless_document_id={exc.paperless_document_id}"
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    if isinstance(exc, UpstreamError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error")


_DOMAIN_ERRORS = (
    UnauthorizedError,
    NotFoundError,
    ForbiddenDocumentError,
    ConflictError,
    ValidationError,
    UpstreamError,
)


def _require_ui_auth(request: Request, db: Session) -> tuple:
    ui_session = get_request_session(request, db)
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


def _serialize_job(job) -> IngestionJobResponse:
    return IngestionJobResponse(
        id=job.id,
        state=job.state,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        paperless_document_id=job.paperless_document_id,
        paperless_task_id=job.paperless_task_id,
        error_code=job.error_code,
        error_message=job.error_message,
        original_filename=job.original_filename,
        content_sha256=job.content_sha256,
    )


def _json_with_session(payload: dict | BaseModel, ui_session, status_code: int = 200) -> JSONResponse:
    body = payload.model_dump() if isinstance(payload, BaseModel) else payload
    response = JSONResponse(content=body, status_code=status_code)
    set_session_cookie(response, ui_session)
    return response


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For from the client; rate limits must use the
    # direct peer address unless a trusted reverse proxy strips/rewrites it.
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@api_router.get("/session", response_model=SessionResponse)
def get_session(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    ui_session = ensure_session(request, db)
    return _json_with_session(
        SessionResponse(
            authenticated=ui_session.authenticated,
            csrf_token=ui_session.csrf_token,
        ),
        ui_session,
    )


@api_router.post("/login", response_model=SessionResponse)
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> JSONResponse:
    store = DbSessionStore(db)
    ui_session = ensure_session(request, db)
    if not _validate_csrf(ui_session.csrf_token, payload.csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")

    client_ip = _client_ip(request)
    username = payload.username.strip()
    if not login_rate_limiter.check(client_ip=client_ip, username=username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts",
            headers={"Retry-After": "600"},
        )

    try:
        raw_token = paperless.exchange_password(username, payload.password)
    except PaperlessAuthError:
        login_rate_limiter.record_failure(client_ip=client_ip, username=username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from None
    except PaperlessError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication upstream error",
        ) from None

    authorization = f"Token {raw_token}"
    store.delete(ui_session.id)
    ui_session = store.create(
        paperless_authorization=authorization,
        username_label=username,
    )
    return _json_with_session(
        SessionResponse(authenticated=True, csrf_token=ui_session.csrf_token),
        ui_session,
    )


@api_router.post("/connect", response_model=SessionResponse)
def connect(
    request: Request,
    payload: ConnectRequest,
    db: Session = Depends(get_db),
) -> JSONResponse:
    store = DbSessionStore(db)
    ui_session = ensure_session(request, db)
    if not _validate_csrf(ui_session.csrf_token, payload.csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")

    token = payload.paperless_token.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paperless token is required")
    if not token.lower().startswith("token ") and not token.lower().startswith("bearer "):
        token = f"Token {token}"

    store.delete(ui_session.id)
    ui_session = store.create(paperless_authorization=token)
    return _json_with_session(
        SessionResponse(authenticated=True, csrf_token=ui_session.csrf_token),
        ui_session,
    )


@api_router.post("/disconnect", response_model=SessionResponse)
def disconnect(
    request: Request,
    payload: DisconnectRequest,
    db: Session = Depends(get_db),
) -> Response:
    store = DbSessionStore(db)
    ui_session = get_request_session(request, db)
    if ui_session is not None and _validate_csrf(ui_session.csrf_token, payload.csrf_token):
        store.delete(ui_session.id)
    fresh = store.create()
    return _json_with_session(
        SessionResponse(authenticated=False, csrf_token=fresh.csrf_token),
        fresh,
    )


@api_router.get("/home", response_model=HomeSummaryResponse)
def get_home_summary(
    request: Request,
    db: Session = Depends(get_db),
    service: HomeService = Depends(get_ui_home_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    try:
        summary = service.summarize(auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    body = HomeSummaryResponse(
        needs_classification=CountStatResponse(
            count=summary.needs_classification.count,
            capped=summary.needs_classification.capped,
            unavailable=summary.needs_classification.unavailable,
        ),
        needs_review=CountStatResponse(
            count=summary.needs_review.count,
            capped=summary.needs_review.capped,
            unavailable=summary.needs_review.unavailable,
        ),
        failed_ingestion=CountStatResponse(
            count=summary.failed_ingestion.count,
            capped=summary.failed_ingestion.capped,
            unavailable=summary.failed_ingestion.unavailable,
        ),
        reconciliation_issues=CountStatResponse(
            count=summary.reconciliation_issues.count,
            capped=summary.reconciliation_issues.capped,
            unavailable=summary.reconciliation_issues.unavailable,
        ),
        recent_documents=[
            RecentDocumentResponse(
                label=item.label,
                entity_id=item.entity_id,
                href=item.href,
                created_date=item.created_date,
            )
            for item in summary.recent_documents
        ],
        recent_knowledge=[
            RecentKnowledgeResponse(
                label=item.label,
                relationship_type=item.relationship_type,
                href=item.href,
            )
            for item in summary.recent_knowledge
        ],
    )
    return _json_with_session(body, ui_session)


@api_router.get("/entities/search", response_model=list[EntitySearchHitResponse])
def search_entities(
    request: Request,
    q: str = Query(default=""),
    entity_type: str | None = Query(default=None),
    ontology: str | None = Query(default=None),
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    try:
        hits = service.search_entities(
            auth, q=q, entity_type=entity_type, ontology_code=ontology
        )
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    payload = [
        EntitySearchHitResponse(
            id=item.id,
            label=item.label,
            entity_type=item.entity_type,
            paperless_document_id=item.paperless_document_id,
            subtitle=item.subtitle,
            open_url=item.open_url,
        )
        for item in hits
    ]
    response = JSONResponse(content=[item.model_dump() for item in payload])
    set_session_cookie(response, ui_session)
    return response


@api_router.get("/documents", response_model=UnclassifiedPageResponse)
def list_documents(
    request: Request,
    unclassified: bool | None = Query(default=None),
    classification: str | None = Query(default=None),
    q: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    order: str = Query(default="desc"),
    created_gte: str | None = Query(default=None),
    created_lte: str | None = Query(default=None),
    correspondent: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    completeness: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=UNCLASSIFIED_PAGE_SIZE, ge=1, le=UNCLASSIFIED_PAGE_SIZE),
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    if classification is None:
        if unclassified is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="classification or unclassified=true required",
            )
        classification = "unclassified" if unclassified in (None, True) else "any"
    try:
        result = service.list_documents(
            auth,
            page=page,
            page_size=page_size,
            q=q,
            classification=classification,
            sort=sort,
            order=order,
            created_gte=created_gte,
            created_lte=created_lte,
            correspondent=correspondent,
            document_type=document_type,
            tag=tag,
            completeness=completeness,
        )
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


@api_router.post("/documents/bulk-relationships", response_model=BulkRelationshipsResponse)
def bulk_relationships(
    request: Request,
    payload: BulkRelationshipsRequest,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    csrf = x_csrf_token or payload.csrf_token
    if not _validate_csrf(ui_session.csrf_token, csrf):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        results = service.bulk_add_relationships(
            payload.paperless_document_ids,
            payload.relationship,
            token=auth,
            target=payload.target,
            target_entity_id=payload.target_entity_id,
            target_paperless_id=payload.target_paperless_id,
            strict=payload.strict,
        )
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    body = BulkRelationshipsResponse(
        results=[
            BulkRelationshipResultResponse(
                paperless_document_id=item.paperless_document_id,
                status=item.status,
                relationship_id=item.relationship_id,
            )
            for item in results
        ]
    )
    return _json_with_session(body, ui_session)


@api_router.get("/documents/{paperless_document_id}", response_model=DocumentResponse)
def get_document(
    request: Request,
    paperless_document_id: int,
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
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
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
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
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc

    return _json_with_session(_serialize_document(document), ui_session, status_code=201)


@api_router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    request: Request,
    relationship_id: str,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> Response:
    ui_session, auth = _require_ui_auth(request, db)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        service.delete_relationship(relationship_id, token=auth)
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, ui_session)
    return response


@api_router.get("/relationship-types", response_model=list[RelationshipTypeResponse])
def list_relationship_types(
    request: Request,
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
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
    db: Session = Depends(get_db),
    service: DocumentService = Depends(get_ui_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    try:
        concepts = service.search_concepts(q=q, ontology_code=ontology, token=auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    payload = [ConceptResponse(code=item.code, name=item.name) for item in concepts]
    response = JSONResponse(content=[item.model_dump() for item in payload])
    set_session_cookie(response, ui_session)
    return response


@api_router.post("/ingest", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_upload(
    request: Request,
    document: UploadFile = File(...),
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ui_ingest_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        job = service.enqueue(
            authorization=auth,
            filename=document.filename or "upload.bin",
            file_obj=document.file,
            content_type=document.content_type or "application/octet-stream",
            session_id=ui_session.id,
            created_by_label=ui_session.username_label,
        )
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _json_with_session(_serialize_job(job), ui_session, status_code=202)


@api_router.get("/ingest/jobs", response_model=IngestionJobsResponse)
def list_ingest_jobs(
    request: Request,
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ui_ingest_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    jobs = service.list_jobs(auth)
    body = IngestionJobsResponse(items=[_serialize_job(job) for job in jobs])
    return _json_with_session(body, ui_session)


@api_router.get("/ingest/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingest_job(
    request: Request,
    job_id: str,
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ui_ingest_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    try:
        job = service.get_job(job_id, auth)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _json_with_session(_serialize_job(job), ui_session)


@api_router.post("/ingest/jobs/{job_id}/retry", response_model=IngestionJobResponse)
def retry_ingest_job(
    request: Request,
    job_id: str,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ui_ingest_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        job = service.retry_job(job_id, auth)
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _json_with_session(_serialize_job(job), ui_session)


def _safe_download_filename(name: str | None, fallback: str) -> str:
    base = (name or fallback).replace('"', "").replace("\n", " ").replace("\r", " ").strip()
    base = base.split("/")[-1].split("\\")[-1] or fallback
    return base[:180]


def _stream_paperless_document(
    *,
    auth: str,
    paperless: PaperlessClient,
    paperless_document_id: int,
    kind: str,
    disposition: str,
) -> StreamingResponse:
    try:
        # Authz probe first so we never leak existence via stream errors.
        paperless.assert_accessible(paperless_document_id, auth)
        chunks, content_type, filename = paperless.stream_document_file(
            auth, paperless_document_id, kind=kind  # type: ignore[arg-type]
        )
    except (PaperlessAuthError, PaperlessNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from None
    except PaperlessUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream document unavailable"
        ) from None
    except PaperlessError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream document unavailable"
        ) from None

    media = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if kind == "preview" and media not in {"application/pdf"} and not media.startswith("image/"):
        # Drain/close the upstream stream without exposing bytes to the client.
        for _ in chunks:
            break
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Preview is only available for PDF and images",
        )

    safe_name = _safe_download_filename(filename, f"document-{paperless_document_id}")
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": f'{disposition}; filename="{safe_name}"',
    }
    return StreamingResponse(chunks, media_type=content_type or "application/octet-stream", headers=headers)


@api_router.get("/documents/{paperless_document_id}/preview")
def preview_document(
    request: Request,
    paperless_document_id: int,
    db: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> StreamingResponse:
    _ui_session, auth = _require_ui_auth(request, db)
    return _stream_paperless_document(
        auth=auth,
        paperless=paperless,
        paperless_document_id=paperless_document_id,
        kind="preview",
        disposition="inline",
    )


@api_router.get("/documents/{paperless_document_id}/download")
def download_document(
    request: Request,
    paperless_document_id: int,
    db: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> StreamingResponse:
    _ui_session, auth = _require_ui_auth(request, db)
    return _stream_paperless_document(
        auth=auth,
        paperless=paperless,
        paperless_document_id=paperless_document_id,
        kind="download",
        disposition="attachment",
    )


@api_router.post("/reconcile", response_model=ReconcileResponse)
def reconcile(
    request: Request,
    payload: ReconcileRequest,
    x_csrf_token: str | None = Header(default=None, alias=CSRF_HEADER),
    db: Session = Depends(get_db),
    service: ReconcileService = Depends(get_ui_reconcile_service),
) -> JSONResponse:
    ui_session, auth = _require_ui_auth(request, db)
    if not _validate_csrf(ui_session.csrf_token, x_csrf_token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CSRF token")
    try:
        summary = service.reconcile(auth, dry_run=payload.dry_run, limit=payload.limit)
        store = DbSessionStore(db)
        if not store.rotate_csrf(ui_session):
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
@router.get("/classify")
@router.get("/ingest")
@router.get("/documents/{paperless_document_id}")
def spa_client_routes(paperless_document_id: int | None = None) -> Response:
    _ = paperless_document_id
    return spa_index_response()


router.include_router(api_router)
