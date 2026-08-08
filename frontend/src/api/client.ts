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
  if (init.body && !headers.has("Content-Type")) {
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

export function getSession() {
  return apiFetch<SessionInfo>("/ui/api/session");
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

export function fetchQueue(page = 1) {
  return apiFetch<QueuePage>(`/ui/api/documents?unclassified=true&page=${page}`);
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

export function removeRelationship(relationshipId: string, csrfToken: string) {
  return apiFetch<void>(
    `/ui/api/relationships/${relationshipId}`,
    { method: "DELETE" },
    csrfToken,
  );
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
