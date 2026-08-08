import { FormEvent, useEffect, useId, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Waypoints } from "lucide-react";
import {
  bulkAddRelationships,
  relationshipTargetPayload,
  relationshipTypesForTarget,
  searchEntities,
  summarizeBulkResults,
  type ClassificationFilter,
  type CompletenessFilter,
  type DocumentSort,
  type EntitySearchHit,
  type QueuePage,
  type RelationshipType,
  type SortOrder,
} from "../api/client";

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
  queue: QueuePage | null;
  selectedId: number | null;
  page: number;
  filters: QueueFilters;
  types: RelationshipType[];
  csrfToken: string;
  pageHref: (page: number) => string;
  onSelect: (id: number) => void;
  onFiltersChange: (next: Partial<QueueFilters> & { page?: number }) => void;
  onBulkDone: (message: string) => Promise<void>;
  onError: (message: string) => void;
};

type TargetKind = "concept" | "document";

type SortPreset = "newest" | "oldest" | "title" | "correspondent";

function sortPresetFromFilters(sort: DocumentSort, order: SortOrder): SortPreset {
  if (sort === "title") return "title";
  if (sort === "correspondent") return "correspondent";
  if (sort === "created" && order === "asc") return "oldest";
  return "newest";
}

function filtersFromSortPreset(preset: SortPreset): Pick<QueueFilters, "sort" | "order"> {
  switch (preset) {
    case "oldest":
      return { sort: "created", order: "asc" };
    case "title":
      return { sort: "title", order: "asc" };
    case "correspondent":
      return { sort: "correspondent", order: "asc" };
    case "newest":
    default:
      return { sort: "created", order: "desc" };
  }
}

function queueItemTitle(title: string | null): string {
  return title?.trim() || "Untitled document";
}

export function DocumentQueue({
  queue,
  selectedId,
  page,
  filters,
  types,
  csrfToken,
  pageHref,
  onSelect,
  onFiltersChange,
  onBulkDone,
  onError,
}: Props) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [draftQ, setDraftQ] = useState(filters.q);
  const [draftCreatedGte, setDraftCreatedGte] = useState(filters.created_gte);
  const [draftCreatedLte, setDraftCreatedLte] = useState(filters.created_lte);
  const [draftCorrespondent, setDraftCorrespondent] = useState(filters.correspondent);
  const [draftDocumentType, setDraftDocumentType] = useState(filters.document_type);
  const [draftTag, setDraftTag] = useState(filters.tag);

  useEffect(() => {
    setDraftQ(filters.q);
    setDraftCreatedGte(filters.created_gte);
    setDraftCreatedLte(filters.created_lte);
    setDraftCorrespondent(filters.correspondent);
    setDraftDocumentType(filters.document_type);
    setDraftTag(filters.tag);
  }, [
    filters.q,
    filters.created_gte,
    filters.created_lte,
    filters.correspondent,
    filters.document_type,
    filters.tag,
  ]);

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

  const emptyLabel =
    filters.classification === "classified"
      ? "No classified documents in this page."
      : filters.classification === "any"
        ? "No documents in this page."
        : "No unclassified documents in this page.";

  const sortPreset = sortPresetFromFilters(filters.sort, filters.order);

  return (
    <div>
      <form
        className="queue-filters"
        onSubmit={(event) => {
          event.preventDefault();
          onFiltersChange({
            q: draftQ,
            created_gte: draftCreatedGte,
            created_lte: draftCreatedLte,
            correspondent: draftCorrespondent,
            document_type: draftDocumentType,
            tag: draftTag,
            page: 1,
          });
        }}
      >
        <div className="field">
          <label htmlFor="queue-q">Search</label>
          <input
            id="queue-q"
            value={draftQ}
            onChange={(event) => setDraftQ(event.target.value)}
            placeholder="Title or text"
          />
        </div>
        <div className="field">
          <label htmlFor="queue-created-gte">Date from</label>
          <input
            id="queue-created-gte"
            type="date"
            value={draftCreatedGte}
            onChange={(event) => setDraftCreatedGte(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="queue-created-lte">Date to</label>
          <input
            id="queue-created-lte"
            type="date"
            value={draftCreatedLte}
            onChange={(event) => setDraftCreatedLte(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="queue-correspondent">Correspondent</label>
          <input
            id="queue-correspondent"
            value={draftCorrespondent}
            onChange={(event) => setDraftCorrespondent(event.target.value)}
            placeholder="Name"
          />
        </div>
        <div className="field">
          <label htmlFor="queue-document-type">Document type</label>
          <input
            id="queue-document-type"
            value={draftDocumentType}
            onChange={(event) => setDraftDocumentType(event.target.value)}
            placeholder="Type"
          />
        </div>
        <div className="field">
          <label htmlFor="queue-tag">Tag</label>
          <input
            id="queue-tag"
            value={draftTag}
            onChange={(event) => setDraftTag(event.target.value)}
            placeholder="Tag"
          />
        </div>
        <div className="field">
          <label htmlFor="queue-classification">Classification</label>
          <select
            id="queue-classification"
            value={filters.classification}
            onChange={(event) =>
              onFiltersChange({
                classification: event.target.value as ClassificationFilter,
                page: 1,
              })
            }
          >
            <option value="unclassified">Unclassified</option>
            <option value="classified">Classified</option>
            <option value="any">Any</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="queue-completeness">Completeness</label>
          <select
            id="queue-completeness"
            value={filters.completeness}
            onChange={(event) =>
              onFiltersChange({
                completeness: event.target.value as CompletenessFilter,
                page: 1,
              })
            }
          >
            <option value="any">Any</option>
            <option value="empty">Empty</option>
            <option value="partial">Partial</option>
            <option value="complete">Complete</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="queue-sort">Sort</label>
          <select
            id="queue-sort"
            value={sortPreset}
            onChange={(event) =>
              onFiltersChange({
                ...filtersFromSortPreset(event.target.value as SortPreset),
                page: 1,
              })
            }
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="title">Title</option>
            <option value="correspondent">Correspondent</option>
          </select>
        </div>
        <button className="btn btn-secondary" type="submit">
          Apply filters
        </button>
      </form>

      {!queue ? (
        <p className="empty">No queue loaded.</p>
      ) : (
        <>
          <p className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
            Page {queue.page} · {queue.items.length} shown · {queue.paperless_count} total
          </p>
          {queue.items.length === 0 ? (
            <p className="empty">{emptyLabel}</p>
          ) : (
            <>
              <div className="queue-select-bar">
                <label>
                  <input
                    type="checkbox"
                    checked={
                      queue.items.length > 0 &&
                      queue.items.every((item) => selected.has(item.paperless_document_id))
                    }
                    onChange={toggleAll}
                  />{" "}
                  Select page
                </label>
                <span className="muted">{selected.size} selected</span>
              </div>
              <ul className="queue-list">
                {queue.items.map((item) => {
                  const title = queueItemTitle(item.title);
                  const meta = [item.created_date, item.correspondent, item.document_type]
                    .filter(Boolean)
                    .join(" · ");
                  return (
                    <li key={item.paperless_document_id} className="queue-row">
                      <label className="queue-check">
                        <span className="sr-only">Select {title}</span>
                        <input
                          type="checkbox"
                          checked={selected.has(item.paperless_document_id)}
                          onChange={() => toggle(item.paperless_document_id)}
                        />
                      </label>
                      <button
                        type="button"
                        className="queue-item"
                        aria-current={
                          selectedId === item.paperless_document_id ? "true" : undefined
                        }
                        onClick={() => onSelect(item.paperless_document_id)}
                      >
                        <strong>{title}</strong>
                        {meta ? <span className="meta">{meta}</span> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          <div className="site-nav" style={{ marginTop: "1rem" }}>
            {queue.has_previous ? (
              <Link to={pageHref(page - 1)}>Previous</Link>
            ) : (
              <span className="muted">Previous</span>
            )}
            {queue.has_next && queue.next_page ? (
              <Link to={pageHref(queue.next_page)}>Next</Link>
            ) : (
              <span className="muted">Next</span>
            )}
          </div>
        </>
      )}

      {selected.size > 0 ? (
        <BulkAssignForm
          selectedIds={[...selected]}
          types={types}
          csrfToken={csrfToken}
          onDone={async (message) => {
            setSelected(new Set());
            await onBulkDone(message);
          }}
          onError={onError}
        />
      ) : null}
    </div>
  );
}

type BulkProps = {
  selectedIds: number[];
  types: RelationshipType[];
  csrfToken: string;
  onDone: (message: string) => Promise<void>;
  onError: (message: string) => void;
};

function BulkAssignForm({ selectedIds, types, csrfToken, onDone, onError }: BulkProps) {
  const listId = useId();
  const [targetKind, setTargetKind] = useState<TargetKind>("concept");
  const filteredTypes = useMemo(
    () => relationshipTypesForTarget(types, targetKind),
    [types, targetKind],
  );
  const [relationship, setRelationship] = useState(filteredTypes[0]?.code || "");
  const [query, setQuery] = useState("");
  const [selectedEntity, setSelectedEntity] = useState<EntitySearchHit | null>(null);
  const [suggestions, setSuggestions] = useState<EntitySearchHit[]>([]);
  const [searchState, setSearchState] = useState<"idle" | "loading" | "error" | "ready">("idle");
  const [highlight, setHighlight] = useState(0);
  const [busy, setBusy] = useState(false);

  const selectedType = filteredTypes.find((item) => item.code === relationship) || filteredTypes[0];

  useEffect(() => {
    if (!filteredTypes.length) {
      setRelationship("");
      return;
    }
    if (!filteredTypes.some((item) => item.code === relationship)) {
      setRelationship(filteredTypes[0].code);
    }
  }, [filteredTypes, relationship]);

  useEffect(() => {
    if (selectedEntity) {
      setSuggestions([]);
      setSearchState("idle");
      return;
    }
    let cancelled = false;
    setSearchState("loading");
    const handle = window.setTimeout(async () => {
      try {
        const results = await searchEntities(query, {
          entity_type: targetKind,
          ontology: targetKind === "concept" ? selectedType?.target_ontology : null,
        });
        if (!cancelled) {
          setSuggestions(results);
          setHighlight(0);
          setSearchState("ready");
        }
      } catch {
        if (!cancelled) {
          setSuggestions([]);
          setSearchState("error");
        }
      }
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [query, selectedEntity, targetKind, selectedType?.target_ontology]);

  function resetTarget() {
    setSelectedEntity(null);
    setQuery("");
    setSuggestions([]);
    setSearchState("idle");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!relationship) {
      onError("Choose a relationship type");
      return;
    }
    if (!selectedEntity) {
      onError("Select a target entity from the suggestions");
      return;
    }
    setBusy(true);
    try {
      const response = await bulkAddRelationships(
        {
          paperless_document_ids: selectedIds,
          relationship,
          ...relationshipTargetPayload(selectedEntity),
          csrf_token: csrfToken,
        },
        csrfToken,
      );
      resetTarget();
      await onDone(`Bulk assign: ${summarizeBulkResults(response.results)}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Bulk assign failed");
    } finally {
      setBusy(false);
    }
  }

  const showList = !selectedEntity && searchState === "ready" && suggestions.length > 0;
  const showEmpty =
    !selectedEntity &&
    searchState === "ready" &&
    suggestions.length === 0 &&
    query.trim().length > 0;

  return (
    <form className="composer composer-stacked bulk-assign" onSubmit={onSubmit} aria-labelledby="bulk-title">
      <h2 id="bulk-title">
        <Waypoints size={18} aria-hidden /> Bulk assign ({selectedIds.length})
      </h2>

      <div className="field">
        <label htmlFor="bulk-target-kind">Target entity type</label>
        <select
          id="bulk-target-kind"
          value={targetKind}
          onChange={(event) => {
            setTargetKind(event.target.value as TargetKind);
            resetTarget();
          }}
        >
          <option value="concept">Concept</option>
          <option value="document">Document</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="bulk-rel-type">Relationship type</label>
        <select
          id="bulk-rel-type"
          value={relationship}
          disabled={!filteredTypes.length}
          onChange={(event) => {
            setRelationship(event.target.value);
            resetTarget();
          }}
        >
          {filteredTypes.length === 0 ? (
            <option value="">No types for this target</option>
          ) : (
            filteredTypes.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name} ({item.code})
              </option>
            ))
          )}
        </select>
      </div>

      <div className="field">
        <label htmlFor="bulk-entity-q">Target</label>
        <input
          id="bulk-entity-q"
          role="combobox"
          aria-expanded={showList}
          aria-controls={showList ? listId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={showList ? `${listId}-option-${highlight}` : undefined}
          value={selectedEntity ? selectedEntity.label : query}
          onChange={(event) => {
            setSelectedEntity(null);
            setQuery(event.target.value);
          }}
          onKeyDown={(event) => {
            if (!showList) return;
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setHighlight((value) => Math.min(value + 1, Math.max(suggestions.length - 1, 0)));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setHighlight((value) => Math.max(value - 1, 0));
            } else if (event.key === "Enter" && suggestions[highlight]) {
              event.preventDefault();
              setSelectedEntity(suggestions[highlight]);
              setQuery(suggestions[highlight].label);
            } else if (event.key === "Escape") {
              event.preventDefault();
              resetTarget();
            }
          }}
          placeholder="Search AtlasDocs…"
          disabled={!relationship}
        />
        {searchState === "loading" && !selectedEntity ? (
          <p className="field-status muted" role="status">
            Searching…
          </p>
        ) : null}
        {searchState === "error" && !selectedEntity ? (
          <p className="field-status field-status-error" role="alert">
            Could not search entities. Try again.
          </p>
        ) : null}
        {showEmpty ? (
          <p className="field-status muted" role="status">
            No matching entities.
          </p>
        ) : null}
        {showList ? (
          <ul className="suggestions" id={listId} role="listbox">
            {suggestions.map((item, index) => (
              <li
                key={item.id}
                id={`${listId}-option-${index}`}
                role="option"
                aria-selected={index === highlight}
              >
                <button
                  type="button"
                  tabIndex={-1}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => {
                    setSelectedEntity(item);
                    setQuery(item.label);
                  }}
                >
                  {item.label}
                  {item.subtitle ? <span className="muted"> · {item.subtitle}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {selectedEntity ? (
        <div className="composer-confirm" aria-live="polite">
          <p>
            <strong>{selectedType?.name || relationship}</strong>
            {" → "}
            <strong>{selectedEntity.label}</strong>
          </p>
        </div>
      ) : null}

      <button
        className="btn btn-primary"
        type="submit"
        disabled={busy || !types.length || !relationship || !selectedEntity}
      >
        {busy ? "Assigning…" : "Assign to selected"}
      </button>
    </form>
  );
}
