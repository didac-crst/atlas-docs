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


class BacklinkResponse(BaseModel):
    id: str
    type: str
    source: str
    source_entity_id: str
    origin: str
    status: str
    source_paperless_document_id: int | None = None


class RelatedDocumentResponse(BaseModel):
    paperless_document_id: int
    entity_id: str
    label: str
    created_date: str | None = None
    relationship_type: str | None = None


class DocumentVersionResponse(BaseModel):
    id: int
    created: str | None = None


class DocumentReplacementHistoryResponse(BaseModel):
    previous_external_id: str
    new_external_id: str
    actor_label: str | None = None
    reason: str | None = None
    created_at: str | None = None


class DocumentResponse(BaseModel):
    paperless_document_id: int
    entity_id: str | None = None
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    open_url: str | None = None
    relationships: list[RelationshipResponse]
    semantic_completeness: str = "empty"
    lifecycle_category: str = "evidence"
    trashed: bool = False
    versions: list[DocumentVersionResponse] = Field(default_factory=list)
    replacement_history: list[DocumentReplacementHistoryResponse] = Field(
        default_factory=list
    )


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
    display_type: str | None = None
    semantic_completeness: str = "empty"
    lifecycle_category: str = "master_data"
    archived: bool = False
    trashed: bool = False
    merged_into_entity_id: str | None = None
    backlinks: list[BacklinkResponse] = Field(default_factory=list)
    related_documents: list[RelatedDocumentResponse] = Field(default_factory=list)
    backlinks_truncated: bool = False


class UnclassifiedDocumentResponse(BaseModel):
    paperless_document_id: int
    title: str | None = None
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    semantic_completeness: str | None = None
    entity_id: str | None = None


class UnclassifiedPageResponse(BaseModel):
    items: list[UnclassifiedDocumentResponse]
    page: int
    page_size: int
    paperless_count: int
    has_next: bool
    has_previous: bool
    next_page: int | None = None


class BulkRelationshipsRequest(BaseModel):
    paperless_document_ids: list[int] = Field(..., min_length=1)
    relationship: str = Field(..., min_length=1)
    target: str | None = Field(default=None, min_length=1)
    target_entity_id: str | None = Field(default=None, min_length=1)
    target_paperless_id: int | None = None
    strict: bool = False
    csrf_token: str | None = None


class BulkRelationshipResultResponse(BaseModel):
    paperless_document_id: int
    status: str
    relationship_id: str | None = None


class BulkRelationshipsResponse(BaseModel):
    results: list[BulkRelationshipResultResponse]


class IngestionJobResponse(BaseModel):
    id: str
    state: str
    created_at: str
    updated_at: str
    paperless_document_id: int | None = None
    paperless_task_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    original_filename: str | None = None
    content_sha256: str | None = None
    user_title: str | None = None


class IngestionJobsResponse(BaseModel):
    items: list[IngestionJobResponse]


class CountStatResponse(BaseModel):
    count: int
    capped: bool = False
    unavailable: bool = False


class RecentDocumentResponse(BaseModel):
    label: str
    entity_id: str | None = None
    href: str
    created_date: str | None = None


class RecentKnowledgeResponse(BaseModel):
    label: str
    relationship_type: str
    href: str


class HomeSummaryResponse(BaseModel):
    needs_classification: CountStatResponse
    needs_review: CountStatResponse
    failed_ingestion: CountStatResponse
    reconciliation_issues: CountStatResponse
    recent_documents: list[RecentDocumentResponse]
    recent_knowledge: list[RecentKnowledgeResponse]


class EntitySearchHitResponse(BaseModel):
    id: str | None = None
    label: str
    entity_type: str
    paperless_document_id: int | None = None
    subtitle: str | None = None
    open_url: str | None = None
    semantic_completeness: str | None = None


class RelationshipTypeResponse(BaseModel):
    code: str
    name: str
    target_ontology: str | None = None
    directionality: str = "directed"
    inverse: str | None = None
    source_entity_types: list[str] | None = None
    target_entity_types: list[str] | None = None


class EntityTypeRegistryResponse(BaseModel):
    code: str
    label: str
    icon: str
    searchable: bool
    valid_relationship_target: bool
    has_dedicated_page: bool
    lifecycle_category: str = "master_data"


class ExploreResultItemResponse(BaseModel):
    id: str | None = None
    label: str
    entity_type: str
    semantic_completeness: str
    subtitle: str | None = None
    paperless_document_id: int | None = None
    open_url: str | None = None
    preview_available: bool = False
    download_available: bool = False
    relationship_summary: list[str] = Field(default_factory=list)
    created_date: str | None = None
    correspondent: str | None = None
    document_type: str | None = None
    lifecycle_category: str | None = None
    thumbnail_available: bool = False
    relationship_count: int = 0


class ExplorePageResponse(BaseModel):
    items: list[ExploreResultItemResponse]
    page: int
    page_size: int
    mode: str
    has_next: bool
    has_previous: bool
    next_page: int | None = None
    total_hint: int | None = None


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
    trashed_in_paperless: list[int] = Field(default_factory=list)
    purged_in_paperless: list[int] = Field(default_factory=list)
    errors: list[str]
    human_summary: str


class DeleteDocumentRequest(BaseModel):
    confirm: bool = False
    permanent: bool = False


class DeleteEntityRequest(BaseModel):
    confirm: bool = False


class RenameEntityRequest(BaseModel):
    display_name: str = Field(..., min_length=1)


class MergeEntityRequest(BaseModel):
    target_entity_id: str = Field(..., min_length=1)
