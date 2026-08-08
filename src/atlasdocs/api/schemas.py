from pydantic import BaseModel, Field


class CreateRelationshipRequest(BaseModel):
    relationship: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class RelationshipResponse(BaseModel):
    id: str
    type: str
    target: str
    origin: str
    status: str


class DocumentResponse(BaseModel):
    paperless_document_id: int
    entity_id: str | None = None
    title: str | None = None
    open_url: str | None = None
    relationships: list[RelationshipResponse]


class UnclassifiedDocumentResponse(BaseModel):
    paperless_document_id: int
    title: str | None = None


class UnclassifiedPageResponse(BaseModel):
    items: list[UnclassifiedDocumentResponse]
    page: int
    page_size: int
    paperless_count: int
    has_next: bool
    has_previous: bool
    next_page: int | None = None


class RelationshipTypeResponse(BaseModel):
    code: str
    name: str
    target_ontology: str | None = None
    directionality: str = "directed"
    inverse: str | None = None


class ConceptResponse(BaseModel):
    code: str
    name: str
