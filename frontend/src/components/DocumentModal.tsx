import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import {
  ApiError,
  documentPreviewUrl,
  fetchDocument,
  removeRelationship,
  type DocumentDetail,
  type RelationshipType,
} from "../api/client";
import { Dialog } from "./Dialog";
import { DocumentActions } from "./DocumentActions";
import { documentContextLine, documentDisplayTitle } from "./documentLabels";
import { EntityReference } from "./EntityReference";
import { RelationshipComposer } from "./RelationshipComposer";

export type DocumentModalMode = "explore" | "classify";

type Props = {
  paperlessDocumentId: number;
  title?: string;
  mode: DocumentModalMode;
  onClose: () => void;
  csrfToken?: string;
  types?: RelationshipType[];
  onChanged?: () => void | Promise<void>;
  onError?: (message: string) => void;
  onDocumentDeleted?: () => void | Promise<void>;
};

/**
 * Unified document modal for Explore and Classify.
 * Same preview chrome; mode controls editing vs read-only actions.
 */
export function DocumentModal({
  paperlessDocumentId,
  title,
  mode,
  onClose,
  csrfToken = "",
  types = [],
  onChanged,
  onError = () => undefined,
  onDocumentDeleted,
}: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [composerKey, setComposerKey] = useState(0);
  const src = documentPreviewUrl(paperlessDocumentId);
  const editable = mode === "classify";

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    (async () => {
      try {
        const response = await fetch(src, { credentials: "same-origin" });
        if (cancelled) return;
        if (!response.ok) {
          setStatus("error");
          return;
        }
        const type = response.headers.get("content-type") || "";
        if (!type.startsWith("application/pdf") && !type.startsWith("image/")) {
          setStatus("error");
          return;
        }
        setStatus("ready");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [src]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setDetailLoading(true);
      try {
        const next = await fetchDocument(paperlessDocumentId);
        if (!cancelled) setDocument(next);
      } catch (err) {
        if (!cancelled) {
          onError(err instanceof ApiError ? err.message : "Failed to load document");
          setDocument(null);
        }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperlessDocumentId]);

  async function refresh() {
    const next = await fetchDocument(paperlessDocumentId);
    setDocument(next);
    await onChanged?.();
  }

  async function onRemoveRelationship(relationshipId: string) {
    if (!editable || !csrfToken) return;
    try {
      await removeRelationship(relationshipId, csrfToken);
      await refresh();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  const heading =
    title ||
    (document ? documentDisplayTitle(document) : null) ||
    "Document preview";
  const context = document ? documentContextLine(document) : null;

  return (
    <Dialog
      title={heading}
      onClose={onClose}
      fullScreenMobile
      className="document-viewer-dialog document-viewer-dialog-with-panel"
    >
      <div className="document-viewer-layout">
        <div className="document-viewer-preview">
          {status === "loading" ? (
            <p className="muted" role="status">
              Loading preview…
            </p>
          ) : null}
          {status === "error" ? (
            <div className="banner banner-error" role="alert">
              Preview is unavailable. Try Download from the document actions.
            </div>
          ) : null}
          {status === "ready" ? (
            <iframe
              className="document-viewer-frame"
              src={src}
              title={`Preview of ${heading}`}
            />
          ) : null}
        </div>

        <aside className="document-viewer-side" aria-label="Document details">
          {detailLoading && !document ? (
            <p className="muted" role="status">
              Loading details…
            </p>
          ) : null}
          {!detailLoading && !document ? (
            <p className="empty" role="status">
              Document details unavailable.
            </p>
          ) : null}
          {document ? (
            <div className="document-modal-panel">
              <header className="doc-header">
                <p className="muted">
                  <span className="entity-chip" data-kind="document">
                    {editable ? "Classification" : "Document"}
                  </span>
                  {document.trashed ? " · In trash" : null}
                </p>
                <h3 className="doc-title">{documentDisplayTitle(document)}</h3>
                {context ? <p className="doc-context">{context}</p> : null}
                <DocumentActions
                  document={document}
                  csrfToken={csrfToken}
                  mode={mode}
                  onRemoved={async (next) => {
                    setDocument(next);
                    await onChanged?.();
                  }}
                  onError={onError}
                  onAddRelationship={
                    editable
                      ? () => {
                          window.document
                            .getElementById("relationship-composer")
                            ?.scrollIntoView({ behavior: "smooth", block: "start" });
                        }
                      : undefined
                  }
                  onDocumentDeleted={editable ? onDocumentDeleted : undefined}
                  onReplaced={
                    editable
                      ? async (next) => {
                          setDocument(next);
                          await onChanged?.();
                        }
                      : undefined
                  }
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
                    {document.created_date ? (
                      <div>
                        <dt>Created</dt>
                        <dd>{document.created_date}</dd>
                      </div>
                    ) : null}
                    {document.correspondent ? (
                      <div>
                        <dt>Organization</dt>
                        <dd>{document.correspondent}</dd>
                      </div>
                    ) : null}
                    {document.document_type ? (
                      <div>
                        <dt>Document type</dt>
                        <dd>{document.document_type}</dd>
                      </div>
                    ) : null}
                  </dl>
                </details>
              </header>

              <section className="doc-context-pane" aria-label="Relationships">
                <h3>Relationships</h3>
                {document.relationships.length === 0 ? (
                  <p className="empty">
                    {editable ? "No relationships yet." : "No relationships."}
                  </p>
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
                        {editable ? (
                          <button
                            type="button"
                            className="btn btn-danger"
                            onClick={() => void onRemoveRelationship(rel.id)}
                            aria-label={`Remove ${rel.type} ${rel.target}`}
                          >
                            <Trash2 size={16} aria-hidden /> Remove
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {editable && csrfToken ? (
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
              ) : null}
            </div>
          ) : null}
        </aside>
      </div>
    </Dialog>
  );
}
