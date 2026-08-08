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
export type DocumentSort = "created" | "title";
export type SortOrder = "asc" | "desc";

export type DocumentListParams = {
  page?: number;
  q?: string;
  classification?: ClassificationFilter;
  sort?: DocumentSort;
  order?: SortOrder;
  /** Legacy flag when `classification` is omitted. */
  unclassified?: boolean;
};

export type RelationshipType = {
  code: string;
  name: string;
  target_ontology: string | null;
  directionality: string;
  inverse: string | null;
};

export type Concept = {
  code: string;
  name: string;
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

export type IngestJobState = "UPLOADING" | "PROCESSING" | "READY" | "FAILED";

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
  if (page !== 1) search.set("page", String(page));
  else search.set("page", String(page));

  if (params.q?.trim()) search.set("q", params.q.trim());

  if (params.classification) {
    search.set("classification", params.classification);
  } else if (params.unclassified) {
    search.set("unclassified", "true");
  }

  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);

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

export function fetchDocuments(params: DocumentListParams = {}) {
  const query = buildDocumentsQuery(params);
  return apiFetch<QueuePage>(`/ui/api/documents?${query}`);
}

/** Legacy helper: unclassified queue page. Prefer `fetchDocuments`. */
export function fetchQueue(page = 1) {
  return fetchDocuments({ page, unclassified: true });
}

export function fetchDocument(id: number) {
  return apiFetch<DocumentDetail>(`/ui/api/documents/${id}`);
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
  return job.state === "UPLOADING" || job.state === "PROCESSING";
}
