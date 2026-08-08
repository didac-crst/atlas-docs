import { ExternalLink, Trash2 } from "lucide-react";
import {
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
};

export function SemanticDocumentDetail({ document, csrfToken, onRemoved, onError }: Props) {
  async function onDelete(relationshipId: string) {
    try {
      await removeRelationship(relationshipId, csrfToken);
      const next = await fetchDocument(document.paperless_document_id);
      await onRemoved(next, "Relationship removed");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  return (
    <div>
      <h1 id="detail-title" className="doc-title">
        {document.title || `Document ${document.paperless_document_id}`}
      </h1>
      <div className="paperless-strip" aria-label="Paperless authority">
        <span className="label">Paperless authority</span>
        <div>
          {[document.created_date, document.correspondent, document.document_type]
            .filter(Boolean)
            .join(" · ") || "No metadata from Paperless"}
        </div>
        {document.open_url ? (
          <a href={document.open_url} target="_blank" rel="noreferrer">
            <ExternalLink size={16} aria-hidden /> Open in Paperless
          </a>
        ) : null}
        {document.entity_id ? (
          <details>
            <summary>Technical</summary>
            <code>{document.entity_id}</code>
          </details>
        ) : null}
      </div>

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
    </div>
  );
}
