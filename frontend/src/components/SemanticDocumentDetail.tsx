import { useRef, useState } from "react";
import { Download, ExternalLink, Eye, FileInput, Link2, Trash2 } from "lucide-react";
import {
  deleteDocument,
  documentDownloadUrl,
  documentPreviewUrl,
  fetchDocument,
  fetchIngestJob,
  jobNeedsPolling,
  removeRelationship,
  replaceDocument,
  type DocumentDetail,
  type SessionInfo,
} from "../api/client";
import { EntityReference } from "./EntityReference";

type Props = {
  document: DocumentDetail;
  csrfToken: string;
  onRemoved: (document: DocumentDetail, message: string) => Promise<void>;
  onError: (message: string) => void;
  onAddRelationship?: () => void;
  onDocumentDeleted?: () => Promise<void> | void;
  onReplaced?: (document: DocumentDetail, message: string) => Promise<void>;
  onSession?: (session: SessionInfo) => void;
};

const CONTEXT_RELATIONSHIP_PRIORITY = ["source-country", "document-type", "issued-by"] as const;
const REPLACE_POLL_MS = 1500;
const REPLACE_POLL_MAX = 40;

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
  onDocumentDeleted,
  onReplaced,
}: Props) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [replaceBusy, setReplaceBusy] = useState(false);
  const [replaceReason, setReplaceReason] = useState("");
  const [showReplace, setShowReplace] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function onRemoveRelationship(relationshipId: string) {
    try {
      await removeRelationship(relationshipId, csrfToken);
      const next = await fetchDocument(document.paperless_document_id);
      await onRemoved(next, "Relationship removed");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove relationship");
    }
  }

  async function onConfirmDeleteDocument() {
    setDeleteBusy(true);
    try {
      await deleteDocument(document.paperless_document_id, csrfToken, { confirm: true });
      setConfirmDelete(false);
      if (onDocumentDeleted) {
        await onDocumentDeleted();
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to delete document");
    } finally {
      setDeleteBusy(false);
    }
  }

  async function pollReplaceJob(jobId: string) {
    for (let attempt = 0; attempt < REPLACE_POLL_MAX; attempt += 1) {
      const job = await fetchIngestJob(jobId);
      if (!jobNeedsPolling(job)) {
        return job;
      }
      await new Promise((resolve) => window.setTimeout(resolve, REPLACE_POLL_MS));
    }
    throw new Error("Replacement is still processing; check Ingest for status");
  }

  async function onReplaceFileSelected(file: File | null) {
    if (!file) return;
    setReplaceBusy(true);
    try {
      const job = await replaceDocument(document.paperless_document_id, file, csrfToken, {
        reason: replaceReason,
      });
      const finished = await pollReplaceJob(job.id);
      if (finished.state !== "READY" || finished.paperless_document_id == null) {
        throw new Error(finished.error_message || "Replacement failed");
      }
      const next = await fetchDocument(finished.paperless_document_id);
      setShowReplace(false);
      setReplaceReason("");
      if (onReplaced) {
        await onReplaced(next, "Document replaced");
      } else {
        await onRemoved(next, "Document replaced");
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to replace document");
    } finally {
      setReplaceBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowReplace((value) => !value)}
            aria-expanded={showReplace}
          >
            <FileInput size={16} aria-hidden /> Replace document
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 size={16} aria-hidden /> Delete document
          </button>
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

        {showReplace ? (
          <div className="doc-replace-panel" role="region" aria-label="Replace document">
            <p className="muted">
              Upload another representation of the same document. Atlas identity and relationships
              are preserved.
            </p>
            <label className="field">
              <span>Reason (optional)</span>
              <input
                type="text"
                value={replaceReason}
                onChange={(event) => setReplaceReason(event.target.value)}
                disabled={replaceBusy}
              />
            </label>
            <input
              ref={fileInputRef}
              type="file"
              disabled={replaceBusy}
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null;
                void onReplaceFileSelected(file);
              }}
            />
            {replaceBusy ? (
              <p className="muted" role="status">
                Replacing document…
              </p>
            ) : null}
          </div>
        ) : null}

        {confirmDelete ? (
          <div className="banner banner-error" role="alertdialog" aria-labelledby="delete-confirm-title">
            <p id="delete-confirm-title">
              Delete this document? The original file will be deleted from Paperless and removed from
              normal AtlasDocs views. This cannot be undone from AtlasDocs.
            </p>
            <div className="doc-actions">
              <button
                type="button"
                className="btn btn-danger"
                disabled={deleteBusy}
                onClick={() => void onConfirmDeleteDocument()}
              >
                Confirm delete
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={deleteBusy}
                onClick={() => setConfirmDelete(false)}
              >
                Cancel
              </button>
            </div>
          </div>
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
                    onClick={() => onRemoveRelationship(rel.id)}
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
