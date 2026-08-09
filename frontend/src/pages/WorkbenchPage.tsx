import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { LayoutGrid, List } from "lucide-react";
import {
  ApiError,
  fetchDocuments,
  fetchRelationshipTypes,
  getSession,
  type ClassificationFilter,
  type CompletenessFilter,
  type DocumentSort,
  type ExploreResultItem,
  type ExploreView,
  type QueueItem,
  type QueuePage,
  type RelationshipType,
  type SessionInfo,
  type SortOrder,
} from "../api/client";
import { BulkRelationshipForm } from "../components/BulkRelationshipForm";
import { ClassifyBatchBar } from "../components/ClassifyBatchBar";
import { Dialog } from "../components/Dialog";
import { DocumentCard } from "../components/DocumentCard";
import { DocumentModal } from "../components/DocumentModal";
import { FilterChips } from "../components/FilterChips";
import { PageLayout } from "../components/PageLayout";
import { AtlasIcon } from "../components/atlasIcons";

export type QueueFilters = {
  q: string;
  classification: ClassificationFilter;
  sort: DocumentSort;
  order: SortOrder;
  created_gte: string;
  created_lte: string;
  correspondent: string;
  document_type: string;
  tag: string;
  completeness: CompletenessFilter;
};

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
};

function parseClassification(value: string | null): ClassificationFilter {
  if (value === "classified" || value === "any" || value === "unclassified") return value;
  return "unclassified";
}

function parseCompleteness(value: string | null): CompletenessFilter {
  if (
    value === "empty" ||
    value === "partial" ||
    value === "classified" ||
    value === "needs_review" ||
    value === "complete" ||
    value === "any"
  ) {
    return value;
  }
  return "any";
}

function parseSort(value: string | null): DocumentSort {
  if (value === "title" || value === "correspondent" || value === "added" || value === "created") {
    return value;
  }
  return "created";
}

function parseOrder(value: string | null): SortOrder {
  return value === "asc" ? "asc" : "desc";
}

function parseView(value: string | null): ExploreView {
  return value === "list" ? "list" : "grid";
}

function sortPreset(sort: DocumentSort, order: SortOrder): string {
  if (sort === "created" && order === "desc") return "newest";
  if (sort === "created" && order === "asc") return "oldest";
  if (sort === "title") return "title";
  if (sort === "correspondent") return "correspondent";
  return "newest";
}

function queueItemToCard(item: QueueItem): ExploreResultItem {
  const label = item.title?.trim() || "Untitled document";
  return {
    id: null,
    label,
    entity_type: "document",
    semantic_completeness: "empty",
    subtitle: [item.document_type, item.correspondent, item.created_date].filter(Boolean).join(" · ") || null,
    paperless_document_id: item.paperless_document_id,
    open_url: null,
    preview_available: true,
    download_available: true,
    relationship_summary: [],
    created_date: item.created_date,
    correspondent: item.correspondent,
    document_type: item.document_type,
    thumbnail_available: true,
    relationship_count: 0,
  };
}

/** Deep link `/documents/:id` → Classify collection + shared viewer modal. */
export function DocumentDeepLink() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const id = Number(params.paperlessId);
  if (!Number.isFinite(id) || id <= 0) {
    return <Navigate to="/classify" replace />;
  }
  const next = new URLSearchParams(searchParams);
  next.set("preview", String(id));
  if (!next.get("classification")) next.set("classification", "any");
  return <Navigate to={`/classify?${next.toString()}`} replace />;
}

/**
 * Classify is a specialized document collection view — sibling of Explore —
 * with multi-selection and batch actions. Documents open in the shared viewer modal.
 */
export function WorkbenchPage({ session, onSession }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const page = Number(searchParams.get("page") || "1") || 1;
  const view = parseView(searchParams.get("view"));
  const previewId = Number(searchParams.get("preview") || "") || null;
  const previewTitle = searchParams.get("preview_title") || "Document preview";

  const filters: QueueFilters = useMemo(
    () => ({
      q: searchParams.get("q") || "",
      classification: parseClassification(searchParams.get("classification")),
      sort: parseSort(searchParams.get("sort")),
      order: parseOrder(searchParams.get("order")),
      created_gte: searchParams.get("created_gte") || "",
      created_lte: searchParams.get("created_lte") || "",
      correspondent: searchParams.get("correspondent") || "",
      document_type: searchParams.get("document_type") || "",
      tag: searchParams.get("tag") || "",
      completeness: parseCompleteness(searchParams.get("completeness")),
    }),
    [searchParams],
  );

  const [draft, setDraft] = useState(filters);
  const [queue, setQueue] = useState<QueuePage | null>(null);
  const [types, setTypes] = useState<RelationshipType[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [batchOpen, setBatchOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    setDraft(filters);
  }, [filters]);

  useEffect(() => {
    if (!queue) return;
    const visible = new Set(queue.items.map((item) => item.paperless_document_id));
    setSelected((prev) => {
      const next = new Set<number>();
      for (const id of prev) {
        if (visible.has(id)) next.add(id);
      }
      return next;
    });
  }, [queue]);

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
      created_gte: overrides.created_gte ?? filters.created_gte,
      created_lte: overrides.created_lte ?? filters.created_lte,
      correspondent: overrides.correspondent ?? filters.correspondent,
      document_type: overrides.document_type ?? filters.document_type,
      tag: overrides.tag ?? filters.tag,
      completeness: overrides.completeness ?? filters.completeness,
    };
  }

  function writeParams(
    next: Partial<QueueFilters> & { page?: number; view?: ExploreView; preview?: number | null; preview_title?: string | null },
  ) {
    const merged = buildListParams(next);
    const params = new URLSearchParams();
    if ((next.page ?? page) > 1) params.set("page", String(next.page ?? page));
    if (merged.q.trim()) params.set("q", merged.q.trim());
    if (merged.classification !== "unclassified") {
      params.set("classification", merged.classification);
    }
    if (merged.sort !== "created") params.set("sort", merged.sort);
    if (merged.order !== "desc") params.set("order", merged.order);
    if (merged.created_gte.trim()) params.set("created_gte", merged.created_gte.trim());
    if (merged.created_lte.trim()) params.set("created_lte", merged.created_lte.trim());
    if (merged.correspondent.trim()) params.set("correspondent", merged.correspondent.trim());
    if (merged.document_type.trim()) params.set("document_type", merged.document_type.trim());
    if (merged.tag.trim()) params.set("tag", merged.tag.trim());
    if (merged.completeness !== "any") params.set("completeness", merged.completeness);
    const nextView = next.view ?? view;
    if (nextView === "list") params.set("view", "list");
    const nextPreview = next.preview === undefined ? previewId : next.preview;
    if (nextPreview) {
      params.set("preview", String(nextPreview));
      const title =
        next.preview_title === undefined ? previewTitle : next.preview_title;
      if (title && title !== "Document preview") params.set("preview_title", title);
    }
    setSearchParams(params, { replace: true });
  }

  function openPreview(paperlessDocumentId: number, title: string) {
    writeParams({ preview: paperlessDocumentId, preview_title: title });
  }

  function closePreview() {
    writeParams({ preview: null, preview_title: null });
  }

  async function reloadQueue() {
    const next = await fetchDocuments(buildListParams());
    setQueue(next);
    return next;
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
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load Classify");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on filter identity
  }, [
    page,
    filters.q,
    filters.classification,
    filters.sort,
    filters.order,
    filters.created_gte,
    filters.created_lte,
    filters.correspondent,
    filters.document_type,
    filters.tag,
    filters.completeness,
    navigate,
  ]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (!queue) return;
    const ids = queue.items.map((item) => item.paperless_document_id);
    const allSelected = ids.length > 0 && ids.every((id) => selected.has(id));
    setSelected(allSelected ? new Set() : new Set(ids));
  }

  const allVisibleSelected =
    Boolean(queue) &&
    queue!.items.length > 0 &&
    queue!.items.every((item) => selected.has(item.paperless_document_id));

  const activeChips = useMemo(() => {
    const chips: { id: string; label: string }[] = [];
    if (filters.q.trim()) chips.push({ id: "q", label: filters.q.trim() });
    if (filters.correspondent.trim()) {
      chips.push({ id: "correspondent", label: filters.correspondent.trim() });
    }
    if (filters.document_type.trim()) {
      chips.push({ id: "document_type", label: filters.document_type.trim() });
    }
    if (filters.tag.trim()) chips.push({ id: "tag", label: `Tag: ${filters.tag.trim()}` });
    if (filters.created_gte.trim()) {
      chips.push({ id: "created_gte", label: `From ${filters.created_gte}` });
    }
    if (filters.created_lte.trim()) {
      chips.push({ id: "created_lte", label: `To ${filters.created_lte}` });
    }
    if (filters.classification !== "unclassified") {
      chips.push({ id: "classification", label: `Classification: ${filters.classification}` });
    }
    if (filters.completeness !== "any") {
      chips.push({ id: "completeness", label: `Completeness: ${filters.completeness}` });
    }
    return chips;
  }, [filters]);

  function removeChip(id: string) {
    const next: Partial<QueueFilters> & { page?: number } = { page: 1 };
    if (id === "q") next.q = "";
    if (id === "correspondent") next.correspondent = "";
    if (id === "document_type") next.document_type = "";
    if (id === "tag") next.tag = "";
    if (id === "created_gte") next.created_gte = "";
    if (id === "created_lte") next.created_lte = "";
    if (id === "classification") next.classification = "unclassified";
    if (id === "completeness") next.completeness = "any";
    writeParams({ ...filters, ...next });
  }

  function clearAllFilters() {
    writeParams({
      q: "",
      correspondent: "",
      document_type: "",
      tag: "",
      created_gte: "",
      created_lte: "",
      classification: "unclassified",
      completeness: "any",
      page: 1,
    });
  }

  function onApplyFilters(event: FormEvent) {
    event.preventDefault();
    writeParams({ ...draft, page: 1 });
  }

  function onSortPreset(value: string) {
    if (value === "newest") writeParams({ sort: "created", order: "desc", page: 1 });
    else if (value === "oldest") writeParams({ sort: "created", order: "asc", page: 1 });
    else if (value === "title") writeParams({ sort: "title", order: "asc", page: 1 });
    else if (value === "correspondent") {
      writeParams({ sort: "correspondent", order: "asc", page: 1 });
    }
  }

  const emptyLabel =
    filters.classification === "classified"
      ? "No classified documents in this page."
      : filters.classification === "any"
        ? "No documents in this page."
        : "No unclassified documents in this page.";

  const panelTitle =
    filters.classification === "classified"
      ? "Classified documents"
      : filters.classification === "any"
        ? "Documents"
        : "Needs classification";

  const queryForPage = (targetPage: number) => {
    const params = new URLSearchParams(searchParams);
    if (targetPage <= 1) params.delete("page");
    else params.set("page", String(targetPage));
    const query = params.toString();
    return query ? `?${query}` : "";
  };

  return (
    <PageLayout width="wide">
      <section className="explore-page classify-page" aria-labelledby="classify-title">
        <header className="explore-header">
          <div>
            <h1 id="classify-title">Classify</h1>
            <p className="muted">
              Browse the classification queue with multi-select. Open any document in the shared
              viewer.
            </p>
          </div>
          <div className="explore-view-toggle" role="group" aria-label="Result layout">
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={view === "list"}
              onClick={() => writeParams({ view: "list" })}
            >
              <List size={16} aria-hidden /> List
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              aria-pressed={view === "grid"}
              onClick={() => writeParams({ view: "grid" })}
            >
              <LayoutGrid size={16} aria-hidden /> Grid
            </button>
          </div>
        </header>

        {error ? (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="banner banner-success" role="status">
            {notice}
          </div>
        ) : null}

        <p className="muted classify-queue-label">{panelTitle}</p>

        <form className="explore-filter-shell" onSubmit={onApplyFilters}>
          <div className="explore-filter-primary">
            <div className="field field-grow">
              <label htmlFor="classify-q" className="sr-only">
                Search
              </label>
              <div className="atlas-search">
                <AtlasIcon name="search" size={16} />
                <input
                  id="classify-q"
                  className="atlas-control"
                  value={draft.q}
                  onChange={(event) => setDraft({ ...draft, q: event.target.value })}
                  placeholder="Search title, metadata or document text…"
                />
              </div>
            </div>
            <button
              type="button"
              className="btn btn-secondary atlas-control"
              aria-expanded={filtersOpen}
              onClick={() => setFiltersOpen((value) => !value)}
            >
              <AtlasIcon name="filters" size={16} /> Filters
              {activeChips.length > 0 ? ` (${activeChips.length})` : ""}
            </button>
            <div className="field">
              <label htmlFor="classify-sort" className="sr-only">
                Sort
              </label>
              <select
                id="classify-sort"
                className="atlas-control"
                value={sortPreset(filters.sort, filters.order)}
                onChange={(event) => onSortPreset(event.target.value)}
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="title">Title</option>
                <option value="correspondent">Correspondent</option>
              </select>
            </div>
            <button type="submit" className="btn btn-primary atlas-control">
              Apply
            </button>
          </div>

          <FilterChips chips={activeChips} onRemove={removeChip} onClearAll={clearAllFilters} />

          {filtersOpen ? (
            <div className="explore-filter-panel">
              <fieldset className="explore-filter-group">
                <legend>Classification</legend>
                <div className="explore-filter-grid">
                  <div className="field">
                    <label htmlFor="classify-classification">Classification</label>
                    <select
                      id="classify-classification"
                      className="atlas-control"
                      value={draft.classification}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          classification: event.target.value as ClassificationFilter,
                        })
                      }
                    >
                      <option value="unclassified">Unclassified</option>
                      <option value="classified">Classified</option>
                      <option value="any">Any</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="classify-completeness">Completeness</label>
                    <select
                      id="classify-completeness"
                      className="atlas-control"
                      value={draft.completeness}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          completeness: event.target.value as CompletenessFilter,
                        })
                      }
                    >
                      <option value="any">Any</option>
                      <option value="empty">Empty</option>
                      <option value="partial">Partial</option>
                      <option value="classified">Classified</option>
                      <option value="needs_review">Needs review</option>
                      <option value="complete">Complete (legacy)</option>
                    </select>
                  </div>
                </div>
              </fieldset>
              <fieldset className="explore-filter-group">
                <legend>Document</legend>
                <div className="explore-filter-grid">
                  <div className="field">
                    <label htmlFor="classify-document-type">Document type</label>
                    <input
                      id="classify-document-type"
                      className="atlas-control"
                      value={draft.document_type}
                      onChange={(event) => setDraft({ ...draft, document_type: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="classify-correspondent">Correspondent</label>
                    <input
                      id="classify-correspondent"
                      className="atlas-control"
                      value={draft.correspondent}
                      onChange={(event) => setDraft({ ...draft, correspondent: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="classify-tag">Tag</label>
                    <input
                      id="classify-tag"
                      className="atlas-control"
                      value={draft.tag}
                      onChange={(event) => setDraft({ ...draft, tag: event.target.value })}
                    />
                  </div>
                </div>
              </fieldset>
              <fieldset className="explore-filter-group">
                <legend>Date</legend>
                <div className="explore-filter-grid">
                  <div className="field">
                    <label htmlFor="classify-created-gte">Created from</label>
                    <input
                      id="classify-created-gte"
                      className="atlas-control"
                      type="date"
                      value={draft.created_gte}
                      onChange={(event) => setDraft({ ...draft, created_gte: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="classify-created-lte">Created to</label>
                    <input
                      id="classify-created-lte"
                      className="atlas-control"
                      type="date"
                      value={draft.created_lte}
                      onChange={(event) => setDraft({ ...draft, created_lte: event.target.value })}
                    />
                  </div>
                </div>
              </fieldset>
            </div>
          ) : null}
        </form>

        <ClassifyBatchBar
          selectedCount={selected.size}
          onClear={() => setSelected(new Set())}
          onAddRelationship={() => setBatchOpen(true)}
        />

        {loading && !queue ? (
          <p className="muted" role="status">
            Loading Classify…
          </p>
        ) : null}

        {queue ? (
          <>
            <div className="classify-select-bar">
              {allVisibleSelected ? (
                <button type="button" className="btn btn-secondary atlas-control" onClick={toggleAll}>
                  {selected.size} selected · Clear selection
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-secondary atlas-control"
                  onClick={toggleAll}
                  disabled={queue.items.length === 0}
                >
                  Select visible
                </button>
              )}
              <span className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
                Page {queue.page} · {queue.items.length} shown · {queue.paperless_count} total
              </span>
            </div>

            {queue.items.length === 0 ? (
              <p className="empty">{emptyLabel}</p>
            ) : (
              <div
                className={`explore-results explore-results-${view}`}
                aria-busy={loading}
                aria-live="polite"
              >
                {queue.items.map((item) => {
                  const card = queueItemToCard(item);
                  return (
                    <DocumentCard
                      key={item.paperless_document_id}
                      item={card}
                      view={view}
                      onPreview={openPreview}
                      selectable
                      selected={selected.has(item.paperless_document_id)}
                      onToggleSelect={() => toggle(item.paperless_document_id)}
                    />
                  );
                })}
              </div>
            )}

            <nav className="explore-pagination" aria-label="Classify pagination">
              {queue.has_previous ? (
                <Link className="btn btn-secondary" to={`/classify${queryForPage(page - 1)}`}>
                  Previous
                </Link>
              ) : (
                <button type="button" className="btn btn-secondary" disabled>
                  Previous
                </button>
              )}
              <span className="muted">Page {queue.page}</span>
              {queue.has_next && queue.next_page ? (
                <Link
                  className="btn btn-secondary"
                  to={`/classify${queryForPage(queue.next_page)}`}
                >
                  Next
                </Link>
              ) : (
                <button type="button" className="btn btn-secondary" disabled>
                  Next
                </button>
              )}
            </nav>
          </>
        ) : null}

        {previewId ? (
          <DocumentModal
            paperlessDocumentId={previewId}
            title={previewTitle}
            mode="classify"
            onClose={closePreview}
            csrfToken={session.csrf_token}
            types={types}
            onError={setError}
            onChanged={async () => {
              await refreshCsrf();
              await reloadQueue();
            }}
            onDocumentDeleted={async () => {
              setNotice("Document deleted");
              closePreview();
              await refreshCsrf();
              await reloadQueue();
            }}
          />
        ) : null}

        {batchOpen ? (
          <Dialog title="Batch classification" onClose={() => setBatchOpen(false)}>
            <BulkRelationshipForm
              selectedIds={[...selected]}
              types={types}
              csrfToken={session.csrf_token}
              onDone={async (message) => {
                setNotice(message);
                setSelected(new Set());
                setBatchOpen(false);
                await refreshCsrf();
                await reloadQueue();
              }}
              onError={setError}
            />
          </Dialog>
        ) : null}
      </section>
    </PageLayout>
  );
}
