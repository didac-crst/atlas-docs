import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ApiError,
  fetchDocument,
  fetchDocuments,
  fetchRelationshipTypes,
  getSession,
  type ClassificationFilter,
  type DocumentDetail,
  type DocumentSort,
  type QueuePage,
  type RelationshipType,
  type SessionInfo,
  type SortOrder,
} from "../api/client";
import { DocumentQueue, type QueueFilters } from "../components/DocumentQueue";
import { RelationshipComposer } from "../components/RelationshipComposer";
import { SemanticDocumentDetail } from "../components/SemanticDocumentDetail";

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
};

function parseClassification(value: string | null): ClassificationFilter {
  if (value === "classified" || value === "any" || value === "unclassified") return value;
  return "unclassified";
}

function parseSort(value: string | null): DocumentSort {
  return value === "title" ? "title" : "created";
}

function parseOrder(value: string | null): SortOrder {
  return value === "asc" ? "asc" : "desc";
}

export function WorkbenchPage({ session, onSession }: Props) {
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const page = Number(searchParams.get("page") || "1") || 1;
  const selectedId = params.paperlessId ? Number(params.paperlessId) : null;

  const filters: QueueFilters = useMemo(
    () => ({
      q: searchParams.get("q") || "",
      classification: parseClassification(searchParams.get("classification")),
      sort: parseSort(searchParams.get("sort")),
      order: parseOrder(searchParams.get("order")),
    }),
    [searchParams],
  );

  const [queue, setQueue] = useState<QueuePage | null>(null);
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [types, setTypes] = useState<RelationshipType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshCsrf() {
    const next = await getSession();
    onSession(next);
    return next;
  }

  function buildListParams(overrides: Partial<QueueFilters> & { page?: number } = {}) {
    return {
      page: overrides.page ?? page,
      q: overrides.q ?? filters.q,
      classification: overrides.classification ?? filters.classification,
      sort: overrides.sort ?? filters.sort,
      order: overrides.order ?? filters.order,
    };
  }

  function listSearchString(overrides: Partial<QueueFilters> & { page?: number } = {}) {
    const next = buildListParams(overrides);
    const params = new URLSearchParams();
    if (next.page > 1) params.set("page", String(next.page));
    if (next.q.trim()) params.set("q", next.q.trim());
    if (next.classification !== "unclassified") {
      params.set("classification", next.classification);
    }
    if (next.sort !== "created") params.set("sort", next.sort);
    if (next.order !== "desc") params.set("order", next.order);
    const query = params.toString();
    return query ? `?${query}` : "";
  }

  function pageHref(targetPage: number) {
    return `/classify${listSearchString({ page: targetPage })}`;
  }

  function onFiltersChange(next: Partial<QueueFilters> & { page?: number }) {
    const query = listSearchString(next);
    setSearchParams(new URLSearchParams(query.startsWith("?") ? query.slice(1) : query), {
      replace: true,
    });
  }

  async function reloadQueue() {
    return fetchDocuments(buildListParams());
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [queuePage, relTypes] = await Promise.all([
          fetchDocuments(buildListParams()),
          fetchRelationshipTypes(),
        ]);
        if (cancelled) return;
        setQueue(queuePage);
        setTypes(relTypes);
        if (selectedId) {
          const detail = await fetchDocument(selectedId);
          if (!cancelled) setDocument(detail);
        } else {
          setDocument(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workbench");
        setDocument(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, selectedId, filters.q, filters.classification, filters.sort, filters.order, navigate]);

  const panelTitle =
    filters.classification === "classified"
      ? "Classified documents"
      : filters.classification === "any"
        ? "Documents"
        : "Needs classification";

  return (
    <div className={`workbench${selectedId ? " detail-open" : ""}`}>
      {error ? (
        <div className="banner banner-error" role="alert" style={{ gridColumn: "1 / -1" }}>
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="banner banner-success" role="status" style={{ gridColumn: "1 / -1" }}>
          {notice}
        </div>
      ) : null}

      <section className="panel queue-panel" aria-labelledby="queue-title">
        <h1 id="queue-title">{panelTitle}</h1>
        {loading && !queue ? (
          <p role="status">Loading queue…</p>
        ) : (
          <DocumentQueue
            queue={queue}
            selectedId={selectedId}
            page={page}
            filters={filters}
            types={types}
            csrfToken={session.csrf_token}
            pageHref={pageHref}
            onSelect={(id) => navigate(`/documents/${id}${listSearchString()}`)}
            onFiltersChange={onFiltersChange}
            onBulkDone={async (message) => {
              setNotice(message);
              await refreshCsrf();
              setQueue(await reloadQueue());
            }}
            onError={setError}
          />
        )}
      </section>

      <section className="panel detail-panel" aria-labelledby="detail-title">
        {selectedId && document ? (
          <>
            <div className="sticky-actions" style={{ top: 0 }}>
              <Link className="btn btn-secondary" to={`/classify${listSearchString()}`}>
                Back to queue
              </Link>
            </div>
            <SemanticDocumentDetail
              document={document}
              csrfToken={session.csrf_token}
              onRemoved={async (nextDoc, message) => {
                setDocument(nextDoc);
                setNotice(message);
                await refreshCsrf();
                setQueue(await reloadQueue());
              }}
              onError={setError}
            />
            <RelationshipComposer
              documentId={document.paperless_document_id}
              types={types}
              csrfToken={session.csrf_token}
              onSaved={async (nextDoc) => {
                setDocument(nextDoc);
                setNotice("Relationship saved");
                await refreshCsrf();
                setQueue(await reloadQueue());
              }}
              onError={setError}
            />
          </>
        ) : selectedId && loading ? (
          <p role="status">Loading document…</p>
        ) : (
          <>
            <h1 id="detail-title">Select a document</h1>
            <p className="empty">
              Choose a Paperless document from the queue to assign typed relationships.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
