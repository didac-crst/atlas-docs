export type SessionInfo = {
  authenticated: boolean;
  csrf_token: string;
};

export type Relationship = {
  id: string;
  type: string;
  target: string;
  target_entity_id: string | null;
  origin: string;
  status: string;
  source_entity_id: string | null;
};

export type Backlink = {
  id: string;
  type: string;
  source: string;
  source_entity_id: string;
  origin: string;
  status: string;
  source_paperless_document_id: number | null;
};

export type RelatedDocument = {
  paperless_document_id: number;
  entity_id: string;
  label: string;
  created_date: string | null;
  relationship_type: string | null;
};

export type EntityDetail = {
  id: string;
  entity_type: string;
  label: string;
  paperless_document_id: number | null;
  title: string | null;
  created_date: string | null;
  correspondent: string | null;
  document_type: string | null;
  open_url: string | null;
  relationships: Relationship[];
  display_type: string | null;
  semantic_completeness: string;
  backlinks: Backlink[];
  related_documents: RelatedDocument[];
};

export type DocumentDetail = {
  paperless_document_id: number;
  entity_id: string | null;
  title: string | null;
  created_date: string | null;
  correspondent: string | null;
  document_type: string | null;
  open_url: string | null;
  relationships: Relationship[];
};

export type QueueItem = {
  paperless_document_id: number;
  title: string | null;
  created_date: string | null;
  correspondent: string | null;
  document_type: string | null;
};

export type QueuePage = {
  items: QueueItem[];
  page: number;
  page_size: number;
  paperless_count: number;
  has_next: boolean;
  has_previous: boolean;
  next_page: number | null;
};

export type ClassificationFilter = "unclassified" | "classified" | "any";
export type CompletenessFilter =
  | "empty"
  | "partial"
  | "classified"
  | "needs_review"
  | "complete"
  | "any";
export type DocumentSort = "created" | "title" | "correspondent" | "added";
export type SortOrder = "asc" | "desc";

export type DocumentListParams = {
  page?: number;
  q?: string;
  classification?: ClassificationFilter;
  sort?: DocumentSort;
  order?: SortOrder;
  created_gte?: string;
  created_lte?: string;
  correspondent?: string;
  document_type?: string;
  tag?: string;
  completeness?: CompletenessFilter;
  /** Legacy flag when `classification` is omitted. */
  unclassified?: boolean;
};

export type RelationshipType = {
  code: string;
  name: string;
  target_ontology: string | null;
  directionality: string;
  inverse: string | null;
  source_entity_types?: string[] | null;
  target_entity_types?: string[] | null;
};

export type Concept = {
  code: string;
  name: string;
};

export type CountStat = {
  count: number;
  capped: boolean;
  unavailable?: boolean;
};

export type RecentDocument = {
  label: string;
  entity_id: string | null;
  href: string;
  created_date: string | null;
};

export type RecentKnowledge = {
  label: string;
  relationship_type: string;
  href: string;
};

export type HomeSummary = {
  needs_classification: CountStat;
  needs_review: CountStat;
  failed_ingestion: CountStat;
  reconciliation_issues: CountStat;
  recent_documents: RecentDocument[];
  recent_knowledge: RecentKnowledge[];
};

export type EntitySearchType =
  | "document"
  | "concept"
  | "any"
  | "person"
  | "organization"
  | "country"
  | "case";

export type ExploreMode =
  | "all"
  | "documents"
  | "people"
  | "organizations"
  | "countries"
  | "cases"
  | "concepts";

export type ExploreView = "list" | "grid";

export type ExploreResultItem = {
  id: string | null;
  label: string;
  entity_type: string;
  semantic_completeness: string;
  subtitle: string | null;
  paperless_document_id: number | null;
  open_url: string | null;
  preview_available: boolean;
  download_available: boolean;
  relationship_summary: string[];
  created_date: string | null;
  correspondent: string | null;
  document_type: string | null;
};

export type ExplorePage = {
  items: ExploreResultItem[];
  page: number;
  page_size: number;
  mode: string;
  has_next: boolean;
  has_previous: boolean;
  next_page: number | null;
  total_hint: number | null;
};

export type EntityTypeInfo = {
  code: string;
  label: string;
  icon: string;
  searchable: boolean;
  valid_relationship_target: boolean;
  has_dedicated_page: boolean;
};

export type ExploreListParams = {
  mode?: ExploreMode;
  page?: number;
  page_size?: number;
  q?: string;
  sort?: DocumentSort;
  order?: SortOrder;
  created_gte?: string;
  created_lte?: string;
  correspondent?: string;
  document_type?: string;
  tag?: string;
  completeness?: CompletenessFilter;
  relationship_type?: string;
};

export type EntitySearchHit = {
  id: string | null;
  label: string;
  entity_type: string;
  paperless_document_id?: number | null;
  subtitle: string | null;
  open_url: string | null;
};

export type ReconcileSummary = {
  dry_run: boolean;
  limit: number | null;
  paperless_documents_seen: number;
  created: number[];
  already_present: number[];
  missing_in_paperless: number[];
  inaccessible_in_paperless: number[];
  errors: string[];
  human_summary: string;
};

export type IngestJobState =
  | "UPLOADING"
  | "PROCESSING"
  | "RESOLVING_DOCUMENT"
  | "RETRYABLE_FAILURE"
  | "READY"
  | "FAILED";

export type IngestJob = {
  id: string;
  state: IngestJobState;
  created_at: string;
  updated_at: string;
  paperless_document_id: number | null;
  paperless_task_id: string | null;
  error_code: string | null;
  error_message: string | null;
  original_filename: string | null;
  content_sha256: string | null;
  user_title?: string | null;
};

export type IngestJobsPage = {
  items: IngestJob[];
};

export type BulkRelationshipStatus =
  | "created"
  | "skipped_duplicate"
  | "forbidden_or_missing"
  | "validation_error";

export type BulkRelationshipResult = {
  paperless_document_id: number;
  status: BulkRelationshipStatus;
  relationship_id?: string;
};

export type BulkRelationshipsResponse = {
  results: BulkRelationshipResult[];
};

export type BulkRelationshipsBody = {
  paperless_document_ids: number[];
  relationship: string;
  target?: string;
  target_entity_id?: string;
  target_paperless_id?: number;
  strict?: boolean;
  csrf_token: string;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let detail = response.statusText;
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") {
      detail = body.detail;
    }
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, detail);
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  csrfToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Build query string for GET /ui/api/documents. */
export function buildDocumentsQuery(params: DocumentListParams = {}): string {
  const search = new URLSearchParams();
  const page = params.page ?? 1;
  search.set("page", String(page));

  if (params.q?.trim()) search.set("q", params.q.trim());

  if (params.classification) {
    search.set("classification", params.classification);
  } else if (params.unclassified) {
    search.set("unclassified", "true");
  }

  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);
  if (params.created_gte?.trim()) search.set("created_gte", params.created_gte.trim());
  if (params.created_lte?.trim()) search.set("created_lte", params.created_lte.trim());
  if (params.correspondent?.trim()) search.set("correspondent", params.correspondent.trim());
  if (params.document_type?.trim()) search.set("document_type", params.document_type.trim());
  if (params.tag?.trim()) search.set("tag", params.tag.trim());
  if (params.completeness && params.completeness !== "any") {
    search.set("completeness", params.completeness);
  }

  return search.toString();
}

export function getSession() {
  return apiFetch<SessionInfo>("/ui/api/session");
}

export function login(username: string, password: string, csrfToken: string) {
  return apiFetch<SessionInfo>("/ui/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password, csrf_token: csrfToken }),
  });
}

export function connect(paperlessToken: string, csrfToken: string) {
  return apiFetch<SessionInfo>("/ui/api/connect", {
    method: "POST",
    body: JSON.stringify({ paperless_token: paperlessToken, csrf_token: csrfToken }),
  });
}

export function disconnect(csrfToken: string) {
  return apiFetch<SessionInfo>(
    "/ui/api/disconnect",
    {
      method: "POST",
      body: JSON.stringify({ csrf_token: csrfToken }),
    },
    csrfToken,
  );
}

export function fetchHome() {
  return apiFetch<HomeSummary>("/ui/api/home");
}

export function searchEntities(
  q: string,
  options: { entity_type?: EntitySearchType; ontology?: string | null } = {},
) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (options.entity_type) params.set("entity_type", options.entity_type);
  if (options.ontology) params.set("ontology", options.ontology);
  const query = params.toString();
  return apiFetch<EntitySearchHit[]>(`/ui/api/entities/search${query ? `?${query}` : ""}`);
}

export function fetchDocuments(params: DocumentListParams = {}) {
  const query = buildDocumentsQuery(params);
  return apiFetch<QueuePage>(`/ui/api/documents?${query}`);
}

/** Build query string for GET /ui/api/explore. */
export function buildExploreQuery(params: ExploreListParams = {}): string {
  const search = new URLSearchParams();
  search.set("mode", params.mode ?? "documents");
  search.set("page", String(params.page ?? 1));
  if (params.page_size) search.set("page_size", String(params.page_size));
  if (params.q?.trim()) search.set("q", params.q.trim());
  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);
  if (params.created_gte?.trim()) search.set("created_gte", params.created_gte.trim());
  if (params.created_lte?.trim()) search.set("created_lte", params.created_lte.trim());
  if (params.correspondent?.trim()) search.set("correspondent", params.correspondent.trim());
  if (params.document_type?.trim()) search.set("document_type", params.document_type.trim());
  if (params.tag?.trim()) search.set("tag", params.tag.trim());
  if (params.completeness && params.completeness !== "any") {
    search.set("completeness", params.completeness);
  }
  if (params.relationship_type?.trim()) {
    search.set("relationship_type", params.relationship_type.trim());
  }
  return search.toString();
}

export function fetchExplore(params: ExploreListParams = {}) {
  const query = buildExploreQuery(params);
  return apiFetch<ExplorePage>(`/ui/api/explore?${query}`);
}

export function fetchEntityTypes() {
  return apiFetch<EntityTypeInfo[]>("/ui/api/entity-types");
}

/** Legacy helper: unclassified queue page. Prefer `fetchDocuments`. */
export function fetchQueue(page = 1) {
  return fetchDocuments({ page, unclassified: true });
}

export function fetchDocument(id: number) {
  return apiFetch<DocumentDetail>(`/ui/api/documents/${id}`);
}

export function fetchEntity(entityId: string) {
  return apiFetch<EntityDetail>(`/ui/api/entities/${encodeURIComponent(entityId)}`);
}

export function fetchRelationshipTypes() {
  return apiFetch<RelationshipType[]>("/ui/api/relationship-types");
}

export function searchConcepts(q: string, ontology?: string | null) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (ontology) params.set("ontology", ontology);
  const query = params.toString();
  return apiFetch<Concept[]>(`/ui/api/concepts${query ? `?${query}` : ""}`);
}

export function addRelationship(
  documentId: number,
  body: {
    relationship: string;
    target?: string;
    target_entity_id?: string;
    target_paperless_id?: number;
  },
  csrfToken: string,
) {
  return apiFetch<DocumentDetail>(
    `/ui/api/documents/${documentId}/relationships`,
    { method: "POST", body: JSON.stringify(body) },
    csrfToken,
  );
}

export function bulkAddRelationships(body: BulkRelationshipsBody, csrfToken: string) {
  return apiFetch<BulkRelationshipsResponse>(
    "/ui/api/documents/bulk-relationships",
    { method: "POST", body: JSON.stringify(body) },
    csrfToken,
  );
}

export function removeRelationship(relationshipId: string, csrfToken: string) {
  return apiFetch<void>(
    `/ui/api/relationships/${relationshipId}`,
    { method: "DELETE" },
    csrfToken,
  );
}

export function ingestDocument(file: File, title: string | undefined, csrfToken: string) {
  const form = new FormData();
  form.append("document", file);
  if (title?.trim()) {
    form.append("title", title.trim());
  }
  return apiFetch<IngestJob>(
    "/ui/api/ingest",
    {
      method: "POST",
      body: form,
    },
    csrfToken,
  );
}

export function fetchIngestJobs() {
  return apiFetch<IngestJobsPage>("/ui/api/ingest/jobs");
}

export function fetchIngestJob(id: string) {
  return apiFetch<IngestJob>(`/ui/api/ingest/jobs/${id}`);
}

export function runReconcile(body: { dry_run: boolean; limit?: number | null }, csrfToken: string) {
  return apiFetch<ReconcileSummary>(
    "/ui/api/reconcile",
    { method: "POST", body: JSON.stringify(body) },
    csrfToken,
  );
}

/** Pure helper for autocomplete filtering tests and client-side narrowing. */
export function filterConcepts(concepts: Concept[], query: string): Concept[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return concepts;
  return concepts.filter(
    (item) =>
      item.code.toLowerCase().includes(needle) || item.name.toLowerCase().includes(needle),
  );
}

export function summarizeBulkResults(results: BulkRelationshipResult[]): string {
  const counts: Record<BulkRelationshipStatus, number> = {
    created: 0,
    skipped_duplicate: 0,
    forbidden_or_missing: 0,
    validation_error: 0,
  };
  for (const item of results) {
    counts[item.status] += 1;
  }
  const parts: string[] = [];
  if (counts.created) parts.push(`${counts.created} created`);
  if (counts.skipped_duplicate) parts.push(`${counts.skipped_duplicate} skipped`);
  if (counts.forbidden_or_missing) parts.push(`${counts.forbidden_or_missing} forbidden/missing`);
  if (counts.validation_error) parts.push(`${counts.validation_error} validation error`);
  return parts.length ? parts.join(" · ") : "No results";
}

export function jobNeedsPolling(job: Pick<IngestJob, "state">): boolean {
  return (
    job.state === "UPLOADING" ||
    job.state === "PROCESSING" ||
    job.state === "RESOLVING_DOCUMENT"
  );
}

export function documentPreviewUrl(paperlessDocumentId: number): string {
  return `/ui/api/documents/${paperlessDocumentId}/preview`;
}

export function documentDownloadUrl(paperlessDocumentId: number): string {
  return `/ui/api/documents/${paperlessDocumentId}/download`;
}

export async function retryIngestJob(jobId: string, csrfToken: string): Promise<IngestJob> {
  return apiFetch<IngestJob>(`/ui/api/ingest/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
  });
}

/** @deprecated Prefer API `target_entity_types`; kept for older payloads. */
export const DOCUMENT_TARGET_RELATIONSHIP_CODES = new Set([
  "derived-from",
  "has-derivative",
  "replies-to",
  "answered-by",
]);

export function relationshipTypesForTarget(
  types: RelationshipType[],
  targetKind: string,
): RelationshipType[] {
  const wanted = targetKind.trim().toLowerCase();
  return types.filter((item) => {
    const targets = item.target_entity_types;
    if (targets && targets.length > 0) {
      return targets.map((code) => code.toLowerCase()).includes(wanted);
    }
    // Legacy fallback when seed constraints are absent.
    if (wanted === "document") {
      return DOCUMENT_TARGET_RELATIONSHIP_CODES.has(item.code);
    }
    return !DOCUMENT_TARGET_RELATIONSHIP_CODES.has(item.code);
  });
}

export function formatCountStat(stat: CountStat): string {
  if (stat.unavailable) return "unavailable";
  return `${stat.count}${stat.capped ? "+" : ""}`;
}

export function relationshipTargetPayload(selected: EntitySearchHit): {
  target_entity_id?: string;
  target_paperless_id?: number;
} {
  if (selected.id) {
    return { target_entity_id: selected.id };
  }
  if (selected.paperless_document_id != null) {
    return { target_paperless_id: selected.paperless_document_id };
  }
  throw new Error("Selected target is missing an Atlas entity or Paperless document id");
}
