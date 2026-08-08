from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from atlasdocs.api.schemas import (
    CreateRelationshipRequest,
    DocumentResponse,
    RelationshipResponse,
)
from atlasdocs.config import get_settings
from atlasdocs.db.session import get_db
from atlasdocs.services.documents import (
    ConflictError,
    DocumentService,
    ForbiddenDocumentError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)
from atlasdocs.services.paperless import PaperlessClient

router = APIRouter()


def get_paperless_client() -> PaperlessClient:
    settings = get_settings()
    return PaperlessClient(
        base_url=settings.paperless_base_url,
        timeout_seconds=settings.paperless_timeout_seconds,
        token=settings.paperless_token,
    )


def get_document_service(
    session: Session = Depends(get_db),
    paperless: PaperlessClient = Depends(get_paperless_client),
) -> DocumentService:
    return DocumentService(session, paperless)


def _token_from_header(authorization: str | None) -> str | None:
    return authorization


def _to_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenDocumentError):
        # Do not disclose existence when Paperless denies access.
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, UpstreamError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error")


def _serialize(document) -> DocumentResponse:
    return DocumentResponse(
        paperless_document_id=document.paperless_document_id,
        relationships=[
            RelationshipResponse(
                type=item.type,
                target=item.target,
                origin=item.origin,
                status=item.status,
            )
            for item in document.relationships
        ],
    )


@router.get("/documents/{paperless_document_id}", response_model=DocumentResponse)
def get_document(
    paperless_document_id: int,
    authorization: str | None = Header(default=None),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = service.get_document(
            paperless_document_id, token=_token_from_header(authorization)
        )
    except Exception as exc:
        if isinstance(
            exc,
            (NotFoundError, ForbiddenDocumentError, ConflictError, ValidationError, UpstreamError),
        ):
            raise _to_http_error(exc) from exc
        raise
    return _serialize(document)


@router.post(
    "/documents/{paperless_document_id}/relationships",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship(
    paperless_document_id: int,
    body: CreateRelationshipRequest,
    authorization: str | None = Header(default=None),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        document = service.add_relationship(
            paperless_document_id,
            body.relationship,
            body.target,
            token=_token_from_header(authorization),
        )
    except Exception as exc:
        if isinstance(
            exc,
            (NotFoundError, ForbiddenDocumentError, ConflictError, ValidationError, UpstreamError),
        ):
            raise _to_http_error(exc) from exc
        raise
    return _serialize(document)
