from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from atlasdocs.api.schemas import (
    ConceptResponse,
    CreateDocumentRelationshipRequest,
    CreateRelationshipRequest,
    DocumentResponse,
    EntityResponse,
    ReconcileRequest,
    ReconcileResponse,
    RelationshipResponse,
    RelationshipTypeResponse,
    UnclassifiedDocumentResponse,
    UnclassifiedPageResponse,
)
from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE, get_settings
from atlasdocs.db.models import RelationshipOrigin, RelationshipStatus, parse_relationship_origin
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

router = APIRouter()


def get_paperless_client() -> PaperlessClient:
    settings = get_settings()
    return PaperlessClient(
        base_url=settings.paperless_base_url,
        timeout_seconds=settings.paperless_timeout_seconds,
    )


def get_document_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> DocumentService:
    return DocumentService(session, paperless)


def get_reconcile_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> ReconcileService:
    return ReconcileService(session, paperless)


def require_authorization(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    return authorization


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


def _serialize_entity(entity) -> EntityResponse:
    return EntityResponse(
        id=entity.id,
        entity_type=entity.entity_type,
        label=entity.label,
        paperless_document_id=entity.paperless_document_id,
        title=entity.title,
        created_date=entity.created_date,
        correspondent=entity.correspondent,
        document_type=entity.document_type,
        open_url=entity.open_url,
        relationships=[_serialize_relationship(item) for item in (entity.relationships or [])],
    )


def _parse_origin_status(payload: CreateRelationshipRequest) -> tuple[RelationshipOrigin, RelationshipStatus]:
    origin = RelationshipOrigin.manual
    status_value = RelationshipStatus.confirmed
    if payload.origin:
        try:
            origin = parse_relationship_origin(payload.origin)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
    if payload.status:
        try:
            status_value = RelationshipStatus(payload.status)
        except ValueError as exc:
            raise ValidationError(f"Unknown relationship status '{payload.status}'") from exc
    return origin, status_value


@router.get("/documents", response_model=UnclassifiedPageResponse)
def list_unclassified_documents(
    unclassified: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=UNCLASSIFIED_PAGE_SIZE, ge=1, le=UNCLASSIFIED_PAGE_SIZE),
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> UnclassifiedPageResponse:
    if not unclassified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only unclassified=true listing is supported",
        )
    try:
        result = service.list_unclassified(authorization, page=page, page_size=page_size)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return UnclassifiedPageResponse(
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


@router.get("/documents/{paperless_document_id}", response_model=DocumentResponse)
def get_document(
    paperless_document_id: int,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = service.get_document(paperless_document_id, token=authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _serialize_document(document)


@router.post(
    "/documents/{paperless_document_id}/relationships",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    paperless_document_id: int,
    payload: CreateDocumentRelationshipRequest,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = service.add_relationship(
            paperless_document_id,
            payload.relationship,
            payload.target,
            token=authorization,
        )
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _serialize_document(document)


@router.get("/entities/{entity_id}", response_model=EntityResponse)
def get_entity(
    entity_id: str,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> EntityResponse:
    try:
        entity = service.get_entity(entity_id, token=authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _serialize_entity(entity)


@router.get("/entities/{entity_id}/relationships", response_model=list[RelationshipResponse])
def list_entity_relationships(
    entity_id: str,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> list[RelationshipResponse]:
    try:
        relationships = service.list_entity_relationships(entity_id, token=authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return [_serialize_relationship(item) for item in relationships]


@router.post(
    "/entities/{entity_id}/relationships",
    response_model=EntityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_entity_relationship(
    entity_id: str,
    payload: CreateRelationshipRequest,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> EntityResponse:
    try:
        origin, rel_status = _parse_origin_status(payload)
        entity = service.add_entity_relationship(
            entity_id,
            payload.relationship,
            token=authorization,
            target=payload.target,
            target_entity_id=payload.target_entity_id,
            target_paperless_id=payload.target_paperless_id,
            origin=origin,
            status=rel_status,
        )
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _serialize_entity(entity)


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: str,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> None:
    try:
        service.delete_relationship(relationship_id, token=authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc


@router.get("/relationship-types", response_model=list[RelationshipTypeResponse])
def list_relationship_types(
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> list[RelationshipTypeResponse]:
    try:
        items = service.list_relationship_types(authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return [
        RelationshipTypeResponse(
            code=item.code,
            name=item.name,
            target_ontology=item.target_ontology,
            directionality=item.directionality,
            inverse=item.inverse,
        )
        for item in items
    ]


@router.get("/ontologies/{ontology_code}/concepts", response_model=list[ConceptResponse])
def list_concepts(
    ontology_code: str,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> list[ConceptResponse]:
    try:
        concepts = service.list_concepts(ontology_code, token=authorization)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return [ConceptResponse(code=item.code, name=item.name) for item in concepts]


@router.post("/reconcile", response_model=ReconcileResponse)
def reconcile_paperless(
    payload: ReconcileRequest,
    authorization: str = Depends(require_authorization),
    service: ReconcileService = Depends(get_reconcile_service),
) -> ReconcileResponse:
    try:
        summary = service.reconcile(
            authorization,
            dry_run=payload.dry_run,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ReconcileResponse(
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
