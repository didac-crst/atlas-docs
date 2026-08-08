import { FormEvent, useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { Waypoints } from "lucide-react";
import {
  bulkAddRelationships,
  searchConcepts,
  summarizeBulkResults,
  type ClassificationFilter,
  type Concept,
  type DocumentSort,
  type QueuePage,
  type RelationshipType,
  type SortOrder,
} from "../api/client";

export type QueueFilters = {
  q: string;
  classification: ClassificationFilter;
  sort: DocumentSort;
  order: SortOrder;
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

const DOCUMENT_TARGET_CODES = new Set([
  "derived-from",
  "has-derivative",
  "replies-to",
  "answered-by",
]);

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

  useEffect(() => {
    setDraftQ(filters.q);
  }, [filters.q]);

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

  return (
    <div>
      <form
        className="queue-filters"
        onSubmit={(event) => {
          event.preventDefault();
          onFiltersChange({ q: draftQ, page: 1 });
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
          <label htmlFor="queue-sort">Sort</label>
          <select
            id="queue-sort"
            value={filters.sort}
            onChange={(event) =>
              onFiltersChange({ sort: event.target.value as DocumentSort, page: 1 })
            }
          >
            <option value="created">Created</option>
            <option value="title">Title</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="queue-order">Order</label>
          <select
            id="queue-order"
            value={filters.order}
            onChange={(event) =>
              onFiltersChange({ order: event.target.value as SortOrder, page: 1 })
            }
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </div>
        <button className="btn btn-secondary" type="submit">
          Apply search
        </button>
      </form>

      {!queue ? (
        <p className="empty">No queue loaded.</p>
      ) : (
        <>
          <p className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
            Page {queue.page} · {queue.items.length} shown · Paperless {queue.paperless_count}
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
                {queue.items.map((item) => (
                  <li key={item.paperless_document_id} className="queue-row">
                    <label className="queue-check">
                      <span className="sr-only">
                        Select {item.title || `Document ${item.paperless_document_id}`}
                      </span>
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
                      <strong>{item.title || `Document ${item.paperless_document_id}`}</strong>
                      <span className="meta">
                        {[item.created_date, item.correspondent, item.document_type]
                          .filter(Boolean)
                          .join(" · ") || `Paperless #${item.paperless_document_id}`}
                      </span>
                    </button>
                  </li>
                ))}
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
  const [relationship, setRelationship] = useState(types[0]?.code || "");
  const [query, setQuery] = useState("");
  const [concept, setConcept] = useState<Concept | null>(null);
  const [paperlessTarget, setPaperlessTarget] = useState("");
  const [suggestions, setSuggestions] = useState<Concept[]>([]);
  const [highlight, setHighlight] = useState(0);
  const [busy, setBusy] = useState(false);

  const selectedType = types.find((item) => item.code === relationship) || types[0];
  const documentMode = Boolean(selectedType && DOCUMENT_TARGET_CODES.has(selectedType.code));
  const conceptMode = !documentMode;

  useEffect(() => {
    if (!types.length) return;
    if (!types.some((item) => item.code === relationship)) {
      setRelationship(types[0].code);
    }
  }, [types, relationship]);

  useEffect(() => {
    if (!conceptMode) {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    const handle = window.setTimeout(async () => {
      try {
        const results = await searchConcepts(query, selectedType?.target_ontology);
        if (!cancelled) {
          setSuggestions(results);
          setHighlight(0);
        }
      } catch {
        if (!cancelled) setSuggestions([]);
      }
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [query, conceptMode, selectedType?.target_ontology]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      let body: {
        paperless_document_ids: number[];
        relationship: string;
        target?: string;
        target_paperless_id?: number;
        csrf_token: string;
      } = {
        paperless_document_ids: selectedIds,
        relationship,
        csrf_token: csrfToken,
      };
      if (conceptMode) {
        if (!concept) {
          throw new Error("Select a concept from the suggestions");
        }
        body = { ...body, target: concept.code };
      } else {
        const id = Number(paperlessTarget);
        if (!Number.isInteger(id) || id < 1) {
          throw new Error("Enter a Paperless document id");
        }
        body = { ...body, target_paperless_id: id };
      }
      const response = await bulkAddRelationships(body, csrfToken);
      setQuery("");
      setConcept(null);
      setPaperlessTarget("");
      await onDone(`Bulk assign: ${summarizeBulkResults(response.results)}`);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Bulk assign failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="composer bulk-assign" onSubmit={onSubmit} aria-labelledby="bulk-title">
      <h2 id="bulk-title">
        <Waypoints size={18} aria-hidden /> Bulk assign ({selectedIds.length})
      </h2>
      <div className="composer-actions">
        <div className="field">
          <label htmlFor="bulk-rel-type">Relationship type</label>
          <select
            id="bulk-rel-type"
            value={relationship}
            onChange={(event) => {
              setRelationship(event.target.value);
              setConcept(null);
              setQuery("");
            }}
          >
            {types.map((item) => (
              <option key={item.code} value={item.code}>
                {item.name} ({item.code})
              </option>
            ))}
          </select>
        </div>

        {conceptMode ? (
          <div className="field">
            <label htmlFor="bulk-concept-q">Concept</label>
            <input
              id="bulk-concept-q"
              role="combobox"
              aria-expanded={suggestions.length > 0 && !concept}
              aria-controls={suggestions.length > 0 && !concept ? listId : undefined}
              aria-autocomplete="list"
              aria-activedescendant={
                suggestions.length > 0 && !concept ? `${listId}-option-${highlight}` : undefined
              }
              value={concept ? concept.name : query}
              onChange={(event) => {
                setConcept(null);
                setQuery(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setHighlight((value) => Math.min(value + 1, Math.max(suggestions.length - 1, 0)));
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setHighlight((value) => Math.max(value - 1, 0));
                } else if (event.key === "Enter" && !concept && suggestions[highlight]) {
                  event.preventDefault();
                  setConcept(suggestions[highlight]);
                  setQuery(suggestions[highlight].name);
                }
              }}
              placeholder="Type to search concepts"
            />
            {suggestions.length > 0 && !concept ? (
              <ul className="suggestions" id={listId} role="listbox">
                {suggestions.map((item, index) => (
                  <li
                    key={item.code}
                    id={`${listId}-option-${index}`}
                    role="option"
                    aria-selected={index === highlight}
                  >
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => {
                        setConcept(item);
                        setQuery(item.name);
                      }}
                    >
                      {item.name} <span className="muted">({item.code})</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <div className="field">
            <label htmlFor="bulk-paperless-target">Target Paperless id</label>
            <input
              id="bulk-paperless-target"
              inputMode="numeric"
              value={paperlessTarget}
              onChange={(event) => setPaperlessTarget(event.target.value)}
              placeholder="e.g. 185"
            />
          </div>
        )}

        <button className="btn btn-primary" type="submit" disabled={busy || !types.length}>
          {busy ? "Assigning…" : "Assign to selected"}
        </button>
      </div>
    </form>
  );
}
