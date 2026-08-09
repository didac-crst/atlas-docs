import { Download, ExternalLink, Eye, Link2, Trash2 } from "lucide-react";
import {
  documentDownloadUrl,
  documentPreviewUrl,
  fetchDocument,
  removeRelationship,
  type DocumentDetail,
} from "../api/client";
import { EntityReference } from "./EntityReference";

type Props = {
  document: DocumentDetail;
  csrfToken: string;
  onRemoved: (document: DocumentDetail, message: string) => Promise<void>;
  onError: (message: string) => void;
  onAddRelationship?: () => void;
};

const CONTEXT_RELATIONSHIP_PRIORITY = ["source-country", "document-type", "issued-by"] as const;

export function documentDisplayTitle(document: Pick<DocumentDetail, "title">): string {
  const title = document.title?.trim();
  return title || "Untitled document";
}

export function documentContextLine(document: DocumentDetail): string {
  const parts: string[] = [];
  const used = new Set<string>();

  for (const code of CONTEXT_RELATIONSHIP_PRIORITY) {
    const rel = document.relationships.find((item) => item.type === code);
    if (rel?.target) {
      parts.push(rel.target);
      used.add(code);
    }
  }

  if (!used.has("document-type") && document.document_type) {
    parts.push(document.document_type);
  }
  if (!used.has("issued-by") && document.correspondent) {
    parts.push(document.correspondent);
  }

  if (document.created_date) {
    const year = document.created_date.slice(0, 4);
    if (/^\d{4}$/.test(year)) parts.push(year);
  }

  return parts.join(" · ");
}

export function SemanticDocumentDetail({
  document,
  csrfToken,
  onRemoved,
  onError,
  onAddRelationship,
}: Props) {
  async function onDelete(relationshipId: string) {
    try {
      await removeRelationship(relationshipId, csrfToken);
      const next = await fetchDocument(document.paperless_document_id);
      await onRemoved(next, "Relationship removed");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  const context = documentContextLine(document);
  const previewHref = documentPreviewUrl(document.paperless_document_id);
  const downloadHref = documentDownloadUrl(document.paperless_document_id);

  return (
    <div>
      <header className="doc-header">
        <h1 id="detail-title" className="doc-title">
          {documentDisplayTitle(document)}
        </h1>
        {context ? <p className="doc-context">{context}</p> : null}
        <div className="doc-actions">
          <a className="btn btn-secondary" href={downloadHref} download>
            <Download size={16} aria-hidden /> Download
          </a>
          {onAddRelationship ? (
            <button type="button" className="btn btn-secondary" onClick={onAddRelationship}>
              <Link2 size={16} aria-hidden /> Add relationship
            </button>
          ) : (
            <a className="btn btn-secondary" href="#relationship-composer">
              <Link2 size={16} aria-hidden /> Add relationship
            </a>
          )}
          <a
            className="btn btn-ghost"
            href={previewHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Eye size={16} aria-hidden /> Open preview in new tab
          </a>
          {document.open_url ? (
            <a
              href={document.open_url}
              target="_blank"
              rel="noreferrer noopener"
              className="btn btn-ghost doc-action-advanced"
              title="Advanced: open the source document in Paperless"
            >
              <ExternalLink size={16} aria-hidden /> Open original in Paperless
            </a>
          ) : (
            <button
              type="button"
              className="btn btn-ghost doc-action-advanced"
              disabled
              title="PAPERLESS_PUBLIC_URL is not configured"
            >
              <ExternalLink size={16} aria-hidden /> Open original in Paperless
            </button>
          )}
        </div>
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

      <div className="doc-detail-layout">
        <section className="doc-preview-pane" aria-label="Document preview">
          <iframe
            className="doc-preview-frame"
            src={previewHref}
            title={`Preview of ${documentDisplayTitle(document)}`}
          />
        </section>
        <section className="doc-context-pane">
          <h2>Relationships</h2>
          {document.relationships.length === 0 ? (
            <p className="empty">No relationships yet. Assign a typed concept below.</p>
          ) : (
            <ul className="rel-list">
              {document.relationships.map((rel) => (
                <li key={rel.id} className="rel-item">
                  <div>
                    <strong>{rel.type}</strong>{" "}
                    <EntityReference label={rel.target} relationshipType={rel.type} />
                    <div className="meta muted">
                      Provenance: {rel.origin} · Status: {rel.status}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => onDelete(rel.id)}
                    aria-label={`Remove ${rel.type} ${rel.target}`}
                  >
                    <Trash2 size={16} aria-hidden /> Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
