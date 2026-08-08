from pydantic import BaseModel, Field


class CreateRelationshipRequest(BaseModel):
    relationship: str = Field(..., min_length=1)
    target: str | None = Field(default=None, min_length=1)
    target_entity_id: str | None = Field(default=None, min_length=1)
    target_paperless_id: int | None = None
    origin: str | None = None
    status: str | None = None


class CreateDocumentRelationshipRequest(BaseModel):
    relationship: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class RelationshipResponse(BaseModel):
    id: str
    type: str
    target: str
    target_entity_id: str | None = None
    origin: str
    status: str
    source_entity_id: str | None = None


class DocumentResponse(BaseModel):
    paperless_document_id: int
    entity_id: str | None = None
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    open_url: str | None = None
    relationships: list[RelationshipResponse]


class EntityResponse(BaseModel):
    id: str
    entity_type: str
    label: str
    paperless_document_id: int | None = None
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    open_url: str | None = None
    relationships: list[RelationshipResponse] = Field(default_factory=list)


class UnclassifiedDocumentResponse(BaseModel):
    paperless_document_id: int
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None


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


class ReconcileRequest(BaseModel):
    dry_run: bool = True
    limit: int | None = Field(default=None, ge=1)


class ReconcileResponse(BaseModel):
    dry_run: bool
    limit: int | None
    paperless_documents_seen: int
    created: list[int]
    already_present: list[int]
    missing_in_paperless: list[int]
    inaccessible_in_paperless: list[int]
    errors: list[str]
    human_summary: str
