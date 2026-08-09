import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LayoutGrid, List } from "lucide-react";
import {
  ApiError,
  fetchExplore,
  fetchRelationshipTypes,
  type CompletenessFilter,
  type DocumentSort,
  type ExploreMode,
  type ExplorePage as ExplorePageData,
  type ExploreView,
  type RelationshipType,
  type SessionInfo,
  type SortOrder,
} from "../api/client";
import { ExploreResultCard } from "../components/ExploreResultCard";
import { DocumentModal } from "../components/DocumentModal";
import { FilterChips } from "../components/FilterChips";
import { PageLayout } from "../components/PageLayout";
import { AtlasIcon } from "../components/atlasIcons";

type Props = {
  session: SessionInfo;
};

const TOP_MODES: { value: ExploreMode; label: string }[] = [
  { value: "documents", label: "Documents" },
  { value: "knowledge", label: "Knowledge" },
];

const KNOWLEDGE_MODES: { value: ExploreMode; label: string }[] = [
  { value: "knowledge", label: "All knowledge" },
  { value: "people", label: "People" },
  { value: "organizations", label: "Organizations" },
  { value: "countries", label: "Countries" },
  { value: "cases", label: "Cases" },
  { value: "concepts", label: "Concepts" },
];

const ALL_MODES = [...TOP_MODES, ...KNOWLEDGE_MODES.slice(1)];

type ExploreFilters = {
  q: string;
  sort: DocumentSort;
  order: SortOrder;
  created_gte: string;
  created_lte: string;
  correspondent: string;
  document_type: string;
  tag: string;
  completeness: CompletenessFilter;
  relationship_type: string;
};

function parseMode(value: string | null): ExploreMode {
  const allowed = ALL_MODES.map((item) => item.value);
  if (value && (allowed as string[]).includes(value)) return value as ExploreMode;
  return "documents";
}

function parseView(value: string | null): ExploreView {
  return value === "list" ? "list" : "grid";
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

function sortPreset(sort: DocumentSort, order: SortOrder): string {
  if (sort === "created" && order === "desc") return "newest";
  if (sort === "created" && order === "asc") return "oldest";
  if (sort === "added" && order === "desc") return "added";
  if (sort === "title") return "title";
  if (sort === "correspondent") return "correspondent";
  return "newest";
}

export function ExplorePage({ session: _session }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const page = Number(searchParams.get("page") || "1") || 1;
  const mode = parseMode(searchParams.get("mode"));
  const previewId = Number(searchParams.get("preview") || "") || null;
  const previewTitle = searchParams.get("preview_title") || "Document preview";

  function openPreview(paperlessDocumentId: number, title: string) {
    const next = new URLSearchParams(searchParams);
    next.set("preview", String(paperlessDocumentId));
    next.set("preview_title", title);
    setSearchParams(next);
  }

  function closePreview() {
    const next = new URLSearchParams(searchParams);
    next.delete("preview");
    next.delete("preview_title");
    setSearchParams(next);
  }
  const view = parseView(searchParams.get("view"));

  const filters: ExploreFilters = useMemo(
    () => ({
      q: searchParams.get("q") || "",
      sort: parseSort(searchParams.get("sort")),
      order: parseOrder(searchParams.get("order")),
      created_gte: searchParams.get("created_gte") || "",
      created_lte: searchParams.get("created_lte") || "",
      correspondent: searchParams.get("correspondent") || "",
      document_type: searchParams.get("document_type") || "",
      tag: searchParams.get("tag") || "",
      completeness: parseCompleteness(searchParams.get("completeness")),
      relationship_type: searchParams.get("relationship_type") || "",
    }),
    [searchParams],
  );

  const [draft, setDraft] = useState(filters);
  const [results, setResults] = useState<ExplorePageData | null>(null);
  const [relationshipTypes, setRelationshipTypes] = useState<RelationshipType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    setDraft(filters);
  }, [filters]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const types = await fetchRelationshipTypes();
        if (!cancelled) setRelationshipTypes(types);
      } catch {
        /* optional for filters */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const documentMode = mode === "documents";
        const next = await fetchExplore({
          mode,
          page,
          q: filters.q,
          sort: filters.sort,
          order: filters.order,
          completeness: filters.completeness,
          ...(documentMode
            ? {
                created_gte: filters.created_gte,
                created_lte: filters.created_lte,
                correspondent: filters.correspondent,
                document_type: filters.document_type,
                tag: filters.tag,
                relationship_type: filters.relationship_type,
              }
            : {}),
        });
        if (!cancelled) setResults(next);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load Explore");
        setResults(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, page, filters, navigate]);

  function writeParams(
    overrides: Partial<ExploreFilters> & {
      page?: number;
      mode?: ExploreMode;
      view?: ExploreView;
    } = {},
  ) {
    const nextMode = overrides.mode ?? mode;
    const nextView = overrides.view ?? view;
    const nextPage = overrides.page ?? page;
    const documentMode = nextMode === "documents";
    const nextFilters: ExploreFilters = {
      q: overrides.q ?? filters.q,
      sort: overrides.sort ?? filters.sort,
      order: overrides.order ?? filters.order,
      created_gte: documentMode ? (overrides.created_gte ?? filters.created_gte) : "",
      created_lte: documentMode ? (overrides.created_lte ?? filters.created_lte) : "",
      correspondent: documentMode
        ? (overrides.correspondent ?? filters.correspondent)
        : "",
      document_type: documentMode
        ? (overrides.document_type ?? filters.document_type)
        : "",
      tag: documentMode ? (overrides.tag ?? filters.tag) : "",
      completeness: overrides.completeness ?? filters.completeness,
      relationship_type: documentMode
        ? (overrides.relationship_type ?? filters.relationship_type)
        : "",
    };
    const params = new URLSearchParams();
    if (nextMode !== "documents") params.set("mode", nextMode);
    if (nextView === "list") params.set("view", "list");
    if (nextPage > 1) params.set("page", String(nextPage));
    if (nextFilters.q.trim()) params.set("q", nextFilters.q.trim());
    if (nextFilters.sort !== "created") params.set("sort", nextFilters.sort);
    if (nextFilters.order !== "desc") params.set("order", nextFilters.order);
    if (documentMode) {
      if (nextFilters.created_gte.trim()) {
        params.set("created_gte", nextFilters.created_gte.trim());
      }
      if (nextFilters.created_lte.trim()) {
        params.set("created_lte", nextFilters.created_lte.trim());
      }
      if (nextFilters.correspondent.trim()) {
        params.set("correspondent", nextFilters.correspondent.trim());
      }
      if (nextFilters.document_type.trim()) {
        params.set("document_type", nextFilters.document_type.trim());
      }
      if (nextFilters.tag.trim()) params.set("tag", nextFilters.tag.trim());
      if (nextFilters.relationship_type.trim()) {
        params.set("relationship_type", nextFilters.relationship_type.trim());
      }
    }
    if (nextFilters.completeness !== "any") {
      params.set("completeness", nextFilters.completeness);
    }
    setSearchParams(params, { replace: true });
  }

  function onApplyFilters(event: FormEvent) {
    event.preventDefault();
    writeParams({ ...draft, page: 1 });
  }

  function onSortPreset(value: string) {
    if (value === "newest") writeParams({ sort: "created", order: "desc", page: 1 });
    else if (value === "oldest") writeParams({ sort: "created", order: "asc", page: 1 });
    else if (value === "added") writeParams({ sort: "added", order: "desc", page: 1 });
    else if (value === "title") writeParams({ sort: "title", order: "asc", page: 1 });
    else if (value === "correspondent") {
      writeParams({ sort: "correspondent", order: "asc", page: 1 });
    }
  }

  const showDocumentFilters = mode === "documents";
  const knowledgeActive = mode !== "documents";
  const topMode: ExploreMode = knowledgeActive ? "knowledge" : "documents";
  const queryForPage = (targetPage: number) => {
    const params = new URLSearchParams(searchParams);
    if (targetPage <= 1) params.delete("page");
    else params.set("page", String(targetPage));
    const query = params.toString();
    return query ? `?${query}` : "";
  };

  const activeChips = useMemo(() => {
    const chips: { id: string; label: string }[] = [];
    if (filters.q.trim()) chips.push({ id: "q", label: filters.q.trim() });
    if (showDocumentFilters) {
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
      if (filters.relationship_type.trim()) {
        const rel = relationshipTypes.find((item) => item.code === filters.relationship_type);
        chips.push({
          id: "relationship_type",
          label: rel?.name || filters.relationship_type,
        });
      }
    }
    if (filters.completeness !== "any") {
      chips.push({ id: "completeness", label: `Completeness: ${filters.completeness}` });
    }
    return chips;
  }, [filters, relationshipTypes, showDocumentFilters]);

  function removeChip(id: string) {
    const next = { ...filters, page: 1 as const };
    if (id === "q") next.q = "";
    if (id === "correspondent") next.correspondent = "";
    if (id === "document_type") next.document_type = "";
    if (id === "tag") next.tag = "";
    if (id === "created_gte") next.created_gte = "";
    if (id === "created_lte") next.created_lte = "";
    if (id === "relationship_type") next.relationship_type = "";
    if (id === "completeness") next.completeness = "any";
    writeParams(next);
  }

  function clearAllFilters() {
    writeParams({
      q: "",
      correspondent: "",
      document_type: "",
      tag: "",
      created_gte: "",
      created_lte: "",
      relationship_type: "",
      completeness: "any",
      page: 1,
    });
  }

  return (
    <PageLayout width="wide">
      <section className="explore-page" aria-labelledby="explore-title">
      <header className="explore-header">
        <div>
          <h1 id="explore-title">Explore</h1>
          <p className="muted">Browse documents and concepts without bulk classification chrome.</p>
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

      <div className="explore-modes" role="tablist" aria-label="Explore modes">
        {TOP_MODES.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            className="explore-mode"
            aria-selected={topMode === item.value}
            onClick={() =>
              writeParams({
                mode: item.value,
                page: 1,
              })
            }
          >
            {item.label}
          </button>
        ))}
      </div>

      {knowledgeActive ? (
        <div className="explore-modes explore-knowledge-modes" role="tablist" aria-label="Knowledge types">
          {KNOWLEDGE_MODES.map((item) => (
            <button
              key={item.value}
              type="button"
              role="tab"
              className="explore-mode"
              aria-selected={mode === item.value}
              onClick={() => writeParams({ mode: item.value, page: 1 })}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}

      <form className="explore-filter-shell" onSubmit={onApplyFilters}>
        <div className="explore-filter-primary">
          <div className="field field-grow">
            <label htmlFor="explore-q" className="sr-only">
              Search
            </label>
            <div className="atlas-search">
              <AtlasIcon name="search" size={16} />
              <input
                id="explore-q"
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
            <label htmlFor="explore-sort" className="sr-only">
              Sort
            </label>
            <select
              id="explore-sort"
              className="atlas-control"
              value={sortPreset(filters.sort, filters.order)}
              onChange={(event) => onSortPreset(event.target.value)}
            >
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="added">Date added</option>
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
            {showDocumentFilters ? (
              <fieldset className="explore-filter-group">
                <legend>Document</legend>
                <div className="explore-filter-grid">
                  <div className="field">
                    <label htmlFor="explore-document-type">Document type</label>
                    <input
                      id="explore-document-type"
                      className="atlas-control"
                      value={draft.document_type}
                      onChange={(event) => setDraft({ ...draft, document_type: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="explore-correspondent">Correspondent</label>
                    <input
                      id="explore-correspondent"
                      className="atlas-control"
                      value={draft.correspondent}
                      onChange={(event) => setDraft({ ...draft, correspondent: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="explore-tag">Tag</label>
                    <input
                      id="explore-tag"
                      className="atlas-control"
                      value={draft.tag}
                      onChange={(event) => setDraft({ ...draft, tag: event.target.value })}
                    />
                  </div>
                </div>
              </fieldset>
            ) : null}
            {showDocumentFilters ? (
              <fieldset className="explore-filter-group">
                <legend>Date</legend>
                <div className="explore-filter-grid">
                  <div className="field">
                    <label htmlFor="explore-created-gte">Created from</label>
                    <input
                      id="explore-created-gte"
                      className="atlas-control"
                      type="date"
                      value={draft.created_gte}
                      onChange={(event) => setDraft({ ...draft, created_gte: event.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label htmlFor="explore-created-lte">Created to</label>
                    <input
                      id="explore-created-lte"
                      className="atlas-control"
                      type="date"
                      value={draft.created_lte}
                      onChange={(event) => setDraft({ ...draft, created_lte: event.target.value })}
                    />
                  </div>
                </div>
              </fieldset>
            ) : null}
            <fieldset className="explore-filter-group">
              <legend>Knowledge</legend>
              <div className="explore-filter-grid">
                <div className="field">
                  <label htmlFor="explore-completeness">Completeness</label>
                  <select
                    id="explore-completeness"
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
                {showDocumentFilters ? (
                  <div className="field">
                    <label htmlFor="explore-relationship-type">Relationship type</label>
                    <select
                      id="explore-relationship-type"
                      className="atlas-control"
                      value={draft.relationship_type}
                      onChange={(event) =>
                        setDraft({ ...draft, relationship_type: event.target.value })
                      }
                    >
                      <option value="">Any</option>
                      {relationshipTypes.map((item) => (
                        <option key={item.code} value={item.code}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}
              </div>
            </fieldset>
          </div>
        ) : null}
      </form>

      {loading && !results ? (
        <p className="muted" role="status">
          Loading Explore…
        </p>
      ) : null}

      {results && results.items.length === 0 ? (
        <p className="empty">No results for this Explore query.</p>
      ) : null}

      {results && results.items.length > 0 ? (
        <>
          <div
            className={`explore-results explore-results-${view}`}
            aria-busy={loading}
            aria-live="polite"
          >
            {results.items.map((item, index) => (
              <ExploreResultCard
                key={`${item.entity_type}-${item.id ?? item.paperless_document_id ?? index}`}
                item={item}
                view={view}
                onPreview={openPreview}
              />
            ))}
          </div>
          <nav className="explore-pagination" aria-label="Explore pagination">
            {results.has_previous ? (
              <Link className="btn btn-secondary" to={`/explore${queryForPage(page - 1)}`}>
                Previous
              </Link>
            ) : (
              <button type="button" className="btn btn-secondary" disabled>
                Previous
              </button>
            )}
            <span className="muted">
              Page {results.page}
              {results.total_hint != null ? ` · ~${results.total_hint}` : ""}
            </span>
            {results.has_next && results.next_page ? (
              <Link className="btn btn-secondary" to={`/explore${queryForPage(results.next_page)}`}>
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
          mode="explore"
          onClose={closePreview}
        />
      ) : null}
      </section>
    </PageLayout>
  );
}
