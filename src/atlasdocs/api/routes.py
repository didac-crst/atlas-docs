from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from atlasdocs.api.schemas import (
    ConceptResponse,
    CreateRelationshipRequest,
    DocumentResponse,
    RelationshipResponse,
    RelationshipTypeResponse,
    UnclassifiedDocumentResponse,
    UnclassifiedPageResponse,
)
from atlasdocs.config import UNCLASSIFIED_PAGE_SIZE, get_settings
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

router = APIRouter()


def get_paperless_client() -> PaperlessClient:
    settings = get_settings()
    # Never inject a shared service token for document access.
    return PaperlessClient(
        base_url=settings.paperless_base_url,
        timeout_seconds=settings.paperless_timeout_seconds,
    )


def get_document_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> DocumentService:
    return DocumentService(session, paperless)


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
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
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


def _serialize(document) -> DocumentResponse:
    return DocumentResponse(
        paperless_document_id=document.paperless_document_id,
        title=document.title,
        open_url=document.open_url,
        relationships=[
            RelationshipResponse(
                id=item.id,
                type=item.type,
                target=item.target,
                origin=item.origin,
                status=item.status,
            )
            for item in document.relationships
        ],
    )


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
            detail="Only unclassified=true listing is supported in v0.2",
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
    return _serialize(document)


@router.post(
    "/documents/{paperless_document_id}/relationships",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    paperless_document_id: int,
    body: CreateRelationshipRequest,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = service.add_relationship(
            paperless_document_id,
            body.relationship,
            body.target,
            token=authorization,
        )
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return _serialize(document)


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
    _ = authorization
    return [
        RelationshipTypeResponse(
            code=item.code,
            name=item.name,
            target_ontology=item.target_ontology,
        )
        for item in service.list_relationship_types()
    ]


@router.get("/ontologies/{ontology_code}/concepts", response_model=list[ConceptResponse])
def list_concepts(
    ontology_code: str,
    authorization: str = Depends(require_authorization),
    service: DocumentService = Depends(get_document_service),
) -> list[ConceptResponse]:
    _ = authorization
    try:
        concepts = service.list_concepts(ontology_code)
    except _DOMAIN_ERRORS as exc:
        raise _to_http_error(exc) from exc
    return [ConceptResponse(code=item.code, name=item.name) for item in concepts]
