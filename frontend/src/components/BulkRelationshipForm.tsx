import { useEffect, useId, useMemo, useState, type FormEvent } from "react";
import { Waypoints } from "lucide-react";
import {
  bulkAddRelationships,
  relationshipTargetPayload,
  relationshipTypesForTarget,
  searchEntities,
  summarizeBulkResults,
  type EntitySearchHit,
  type RelationshipType,
} from "../api/client";

type TargetKind = "concept" | "document";

type Props = {
  selectedIds: number[];
  types: RelationshipType[];
  csrfToken: string;
  onDone: (message: string) => Promise<void>;
  onError: (message: string) => void;
};

/** Batch relationship assign for the current Classify selection. */
export function BulkRelationshipForm({
  selectedIds,
  types,
  csrfToken,
  onDone,
  onError,
}: Props) {
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
        <Waypoints size={18} aria-hidden /> Add relationship ({selectedIds.length})
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
                key={item.id ?? `paperless-${item.paperless_document_id ?? index}`}
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
