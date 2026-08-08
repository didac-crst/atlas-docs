import { FormEvent, useEffect, useId, useState } from "react";
import { Waypoints } from "lucide-react";
import {
  addRelationship,
  searchConcepts,
  type Concept,
  type DocumentDetail,
  type RelationshipType,
} from "../api/client";

type Props = {
  documentId: number;
  types: RelationshipType[];
  csrfToken: string;
  onSaved: (document: DocumentDetail) => Promise<void>;
  onError: (message: string) => void;
};

export function RelationshipComposer({
  documentId,
  types,
  csrfToken,
  onSaved,
  onError,
}: Props) {
  const listId = useId();
  const [relationship, setRelationship] = useState(types[0]?.code || "");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Concept | null>(null);
  const [paperlessTarget, setPaperlessTarget] = useState("");
  const [suggestions, setSuggestions] = useState<Concept[]>([]);
  const [highlight, setHighlight] = useState(0);
  const [busy, setBusy] = useState(false);

  const selectedType = types.find((item) => item.code === relationship) || types[0];
  const documentTargetCodes = new Set([
    "derived-from",
    "has-derivative",
    "replies-to",
    "answered-by",
  ]);
  const documentMode = Boolean(selectedType && documentTargetCodes.has(selectedType.code));
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
        relationship: string;
        target?: string;
        target_paperless_id?: number;
      };
      if (conceptMode) {
        if (!selected) {
          throw new Error("Select a concept from the suggestions");
        }
        body = { relationship, target: selected.code };
      } else {
        const id = Number(paperlessTarget);
        if (!Number.isInteger(id) || id < 1) {
          throw new Error("Enter a Paperless document id");
        }
        body = { relationship, target_paperless_id: id };
      }
      const document = await addRelationship(documentId, body, csrfToken);
      setQuery("");
      setSelected(null);
      setPaperlessTarget("");
      await onSaved(document);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save relationship");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="composer" onSubmit={onSubmit} aria-labelledby="composer-title">
      <h2 id="composer-title">
        <Waypoints size={18} aria-hidden /> Assign relationship
      </h2>
      <div className="composer-actions">
        <div className="field">
          <label htmlFor="rel-type">Relationship type</label>
          <select
            id="rel-type"
            value={relationship}
            onChange={(event) => {
              setRelationship(event.target.value);
              setSelected(null);
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
            <label htmlFor="concept-q">Concept</label>
            <input
              id="concept-q"
              role="combobox"
              aria-expanded={suggestions.length > 0 && !selected}
              aria-controls={listId}
              aria-autocomplete="list"
              aria-activedescendant={
                suggestions.length > 0 && !selected
                  ? `${listId}-option-${highlight}`
                  : undefined
              }
              value={selected ? selected.name : query}
              onChange={(event) => {
                setSelected(null);
                setQuery(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setHighlight((value) => Math.min(value + 1, Math.max(suggestions.length - 1, 0)));
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setHighlight((value) => Math.max(value - 1, 0));
                } else if (event.key === "Enter" && !selected && suggestions[highlight]) {
                  event.preventDefault();
                  setSelected(suggestions[highlight]);
                  setQuery(suggestions[highlight].name);
                }
              }}
              placeholder="Type to search concepts"
            />
            {suggestions.length > 0 && !selected ? (
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
                        setSelected(item);
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
            <label htmlFor="paperless-target">Target Paperless id</label>
            <input
              id="paperless-target"
              inputMode="numeric"
              value={paperlessTarget}
              onChange={(event) => setPaperlessTarget(event.target.value)}
              placeholder="e.g. 185"
            />
          </div>
        )}

        <button className="btn btn-primary" type="submit" disabled={busy || !types.length}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
      {!documentMode ? null : (
        <p className="muted">Document-to-document edges use a Paperless id as the target.</p>
      )}
    </form>
  );
}
