import { Trash2 } from "lucide-react";
import { removeRelationship, fetchDocument, type DocumentDetail, type SessionInfo } from "../api/client";
import { DocumentActions } from "./DocumentActions";
import { documentContextLine, documentDisplayTitle } from "./documentLabels";
import { EntityReference } from "./EntityReference";
import { documentPreviewUrl } from "../api/client";

type Props = {
  document: DocumentDetail;
  csrfToken: string;
  onRemoved: (document: DocumentDetail, message: string) => Promise<void>;
  onError: (message: string) => void;
  onAddRelationship?: () => void;
  onDocumentDeleted?: () => Promise<void> | void;
  onReplaced?: (document: DocumentDetail, message: string) => Promise<void>;
  onSession?: (session: SessionInfo) => void;
  /** Classify workbench: preview left, context right — no stacked duplicate viewer. */
  layout?: "workbench" | "stacked";
  onPreview?: () => void;
};

export { documentDisplayTitle, documentContextLine } from "./documentLabels";

export function SemanticDocumentDetail({
  document,
  csrfToken,
  onRemoved,
  onError,
  onAddRelationship,
  onDocumentDeleted,
  onReplaced,
  layout = "workbench",
  onPreview,
}: Props) {
  const history = document.replacement_history ?? [];
  const versions = document.versions ?? [];
  const context = documentContextLine(document);
  const previewHref = documentPreviewUrl(document.paperless_document_id);
  const hasMetadata =
    Boolean(document.created_date) ||
    Boolean(document.correspondent) ||
    Boolean(document.document_type) ||
    Boolean(document.lifecycle_category);

  async function onRemoveRelationship(relationshipId: string) {
    try {
      await removeRelationship(relationshipId, csrfToken);
      const next = await fetchDocument(document.paperless_document_id);
      await onRemoved(next, "Relationship removed");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  const header = (
    <header className="doc-header">
      <p className="muted">
        <span className="entity-chip" data-kind="document">
          {document.lifecycle_category === "organizational"
            ? "Organizational"
            : document.lifecycle_category === "master_data"
              ? "Master Data"
              : "Evidence"}
        </span>
        {document.trashed ? " · In trash" : null}
      </p>
      <h1 id="detail-title" className="doc-title">
        {documentDisplayTitle(document)}
      </h1>
      {context ? <p className="doc-context">{context}</p> : null}
      <DocumentActions
        document={document}
        csrfToken={csrfToken}
        onRemoved={onRemoved}
        onError={onError}
        onAddRelationship={onAddRelationship}
        onDocumentDeleted={onDocumentDeleted}
        onReplaced={onReplaced}
        onPreview={onPreview}
        preferPreview
      />

      <div className="doc-disclosure-stack">
        {hasMetadata ? (
          <details className="tech-details">
            <summary>Metadata</summary>
            <dl>
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
              {document.lifecycle_category ? (
                <div>
                  <dt>Lifecycle</dt>
                  <dd>{document.lifecycle_category}</dd>
                </div>
              ) : null}
            </dl>
          </details>
        ) : null}
        {history.length > 0 ? (
          <details className="tech-details">
            <summary>History</summary>
            <ul className="rel-list">
              {history.map((row) => (
                <li key={`${row.previous_external_id}-${row.new_external_id}-${row.created_at}`}>
                  Previous representation replaced
                  <div className="meta muted">
                    {[row.created_at, row.actor_label, row.reason].filter(Boolean).join(" · ")}
                  </div>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {versions.length > 0 ? (
          <details className="tech-details">
            <summary>Versions</summary>
            <ul className="rel-list">
              {versions.map((version) => (
                <li key={version.id}>
                  Version {version.id}
                  {version.created ? ` · ${version.created}` : ""}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
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
            {history.length > 0 ? (
              <div>
                <dt>Replacement identifiers</dt>
                <dd>
                  <ul className="rel-list">
                    {history.map((row) => (
                      <li key={`tech-${row.previous_external_id}-${row.new_external_id}`}>
                        <code>{row.previous_external_id}</code> → <code>{row.new_external_id}</code>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            ) : null}
          </dl>
        </details>
      </div>
    </header>
  );

  const relationships = (
    <section className="doc-context-pane" aria-label="Relationships">
      <h2>Relationships</h2>
      {document.relationships.length === 0 ? (
        <p className="empty">No relationships yet. Assign a typed concept below.</p>
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
  );

  const preview = (
    <section className="doc-preview-pane" aria-label="Document preview">
      {/*
        Same-origin AtlasDocs BFF URL only — never iframe Paperless UI.
        Do not set sandbox="" here: an empty sandbox blocks the browser PDF viewer.
      */}
      <iframe
        className="doc-preview-frame"
        src={previewHref}
        title={`Preview of ${documentDisplayTitle(document)}`}
      />
    </section>
  );

  if (layout === "workbench") {
    return (
      <div className="doc-workbench">
        {preview}
        <div className="doc-workbench-context">
          {header}
          {relationships}
        </div>
      </div>
    );
  }

  return (
    <div>
      {header}
      <div className="doc-detail-layout">
        {preview}
        {relationships}
      </div>
    </div>
  );
}
