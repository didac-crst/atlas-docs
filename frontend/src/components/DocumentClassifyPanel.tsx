import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  ApiError,
  fetchDocument,
  removeRelationship,
  type DocumentDetail,
  type RelationshipType,
  type SessionInfo,
} from "../api/client";
import { DocumentActions } from "./DocumentActions";
import { documentContextLine, documentDisplayTitle } from "./documentLabels";
import { EntityReference } from "./EntityReference";
import { RelationshipComposer } from "./RelationshipComposer";

type Props = {
  paperlessDocumentId: number;
  csrfToken: string;
  types: RelationshipType[];
  onSession?: (session: SessionInfo) => void;
  onChanged?: () => void | Promise<void>;
  onError: (message: string) => void;
  onDocumentDeleted?: () => void | Promise<void>;
};

/**
 * Classification context for the shared document viewer modal.
 * Preview stays in the modal frame; this panel is actions + relationships only.
 */
export function DocumentClassifyPanel({
  paperlessDocumentId,
  csrfToken,
  types,
  onChanged,
  onError,
  onDocumentDeleted,
}: Props) {
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [composerKey, setComposerKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const next = await fetchDocument(paperlessDocumentId);
        if (!cancelled) setDocument(next);
      } catch (err) {
        if (!cancelled) {
          onError(err instanceof ApiError ? err.message : "Failed to load document");
          setDocument(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Intentionally omit onError — parent setters are stable enough; avoid reload loops.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperlessDocumentId]);

  async function refresh() {
    const next = await fetchDocument(paperlessDocumentId);
    setDocument(next);
    await onChanged?.();
  }

  async function onRemoveRelationship(relationshipId: string) {
    try {
      await removeRelationship(relationshipId, csrfToken);
      await refresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  if (loading && !document) {
    return (
      <p className="muted" role="status">
        Loading classification…
      </p>
    );
  }

  if (!document) {
    return (
      <p className="empty" role="status">
        Document details unavailable.
      </p>
    );
  }

  const context = documentContextLine(document);

  return (
    <div className="document-classify-panel">
      <header className="doc-header">
        <p className="muted">
          <span className="entity-chip" data-kind="document">
            Classification
          </span>
          {document.trashed ? " · In trash" : null}
        </p>
        <h3 className="doc-title">{documentDisplayTitle(document)}</h3>
        {context ? <p className="doc-context">{context}</p> : null}
        <DocumentActions
          document={document}
          csrfToken={csrfToken}
          onRemoved={async (next) => {
            setDocument(next);
            await onChanged?.();
          }}
          onError={onError}
          onAddRelationship={() => {
            window.document
              .getElementById("relationship-composer")
              ?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          onDocumentDeleted={onDocumentDeleted}
          onReplaced={async (next) => {
            setDocument(next);
            await onChanged?.();
          }}
          preferPreview={false}
        />
        <details className="tech-details">
          <summary>Technical details</summary>
          <dl>
            <div>
              <dt>Paperless document id</dt>
              <dd>
                <code>{document.paperless_document_id}</code>
              </dd>
            </div>
            {document.entity_id ? (
              <div>
                <dt>Entity UUID</dt>
                <dd>
                  <code>{document.entity_id}</code>
                </dd>
              </div>
            ) : null}
          </dl>
        </details>
      </header>

      <section className="doc-context-pane" aria-label="Relationships">
        <h3>Relationships</h3>
        {document.relationships.length === 0 ? (
          <p className="empty">No relationships yet.</p>
        ) : (
          <ul className="rel-list">
            {document.relationships.map((rel) => (
              <li key={rel.id} className="rel-item">
                <div>
                  <strong>{rel.type}</strong>{" "}
                  <EntityReference
                    label={rel.target}
                    relationshipType={rel.type}
                    entityId={rel.target_entity_id}
                  />
                  <div className="meta muted">
                    Provenance: {rel.origin} · Status: {rel.status}
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => void onRemoveRelationship(rel.id)}
                  aria-label={`Remove ${rel.type} ${rel.target}`}
                >
                  <Trash2 size={16} aria-hidden /> Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <RelationshipComposer
        key={composerKey}
        documentId={document.paperless_document_id}
        types={types}
        csrfToken={csrfToken}
        onSaved={async (next) => {
          setDocument(next);
          setComposerKey((value) => value + 1);
          await onChanged?.();
        }}
        onError={onError}
      />
    </div>
  );
}
