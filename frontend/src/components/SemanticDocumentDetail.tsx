import { useEffect, useRef, useState } from "react";
import { Download, ExternalLink, Eye, FileInput, Link2, RotateCcw, Trash2 } from "lucide-react";
import {
  deleteDocument,
  documentDownloadUrl,
  documentPreviewUrl,
  fetchDocument,
  fetchIngestJob,
  jobNeedsPolling,
  removeRelationship,
  replaceDocument,
  restoreDocument,
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
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [replaceBusy, setReplaceBusy] = useState(false);
  const [replaceReason, setReplaceReason] = useState("");
  const [showReplace, setShowReplace] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<number | "">("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement>(null);
  const confirmDeleteRef = useRef<HTMLButtonElement>(null);

  const versions = document.versions ?? [];
  const history = document.replacement_history ?? [];
  const firstVersionId = versions[0]?.id;
  const isEvidence = (document.lifecycle_category ?? "evidence") === "evidence";

  useEffect(() => {
    if (confirmDelete) {
      confirmDeleteRef.current?.focus();
    }
  }, [confirmDelete]);

  useEffect(() => {
    setSelectedVersionId(firstVersionId ?? "");
  }, [document.paperless_document_id, firstVersionId]);

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
      await deleteDocument(document.paperless_document_id, csrfToken, {
        confirm: true,
        permanent: Boolean(document.trashed),
      });
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

  async function onRestoreDocument() {
    setRestoreBusy(true);
    try {
      await restoreDocument(document.paperless_document_id, csrfToken);
      const next = await fetchDocument(document.paperless_document_id);
      await onRemoved(next, "Document restored from trash");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to restore document");
    } finally {
      setRestoreBusy(false);
    }
  }

  function onCancelDelete() {
    setConfirmDelete(false);
    deleteTriggerRef.current?.focus();
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
  const versionDownloadHref =
    selectedVersionId === ""
      ? null
      : documentDownloadUrl(document.paperless_document_id, { version: selectedVersionId });

  return (
    <div>
      <header className="doc-header">
        <p className="muted">
          <span className="entity-chip" data-kind="document">
            Evidence
          </span>
          {document.trashed ? " · In trash" : null}
        </p>
        <h1 id="detail-title" className="doc-title">
          {documentDisplayTitle(document)}
        </h1>
        {context ? <p className="doc-context">{context}</p> : null}
        <div className="doc-actions">
          <a className="btn btn-secondary" href={downloadHref} download>
            <Download size={16} aria-hidden /> Download
          </a>
          <a
            className="btn btn-ghost"
            href={documentDownloadUrl(document.paperless_document_id, { original: true })}
            download
          >
            <Download size={16} aria-hidden /> Download original
          </a>
          {versionDownloadHref ? (
            <a className="btn btn-ghost" href={versionDownloadHref} download>
              <Download size={16} aria-hidden /> Download selected version
            </a>
          ) : null}
          {onAddRelationship ? (
            <button type="button" className="btn btn-secondary" onClick={onAddRelationship}>
              <Link2 size={16} aria-hidden /> Add relationship
            </button>
          ) : (
            <a className="btn btn-secondary" href="#relationship-composer">
              <Link2 size={16} aria-hidden /> Add relationship
            </a>
          )}
          {isEvidence && !document.trashed ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowReplace((value) => !value)}
              aria-expanded={showReplace}
            >
              <FileInput size={16} aria-hidden /> Replace document
            </button>
          ) : null}
          {isEvidence && document.trashed ? (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={restoreBusy}
              onClick={() => void onRestoreDocument()}
            >
              <RotateCcw size={16} aria-hidden /> Restore
            </button>
          ) : null}
          {isEvidence ? (
            <button
              ref={deleteTriggerRef}
              type="button"
              className="btn btn-danger"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 size={16} aria-hidden />{" "}
              {document.trashed ? "Delete permanently" : "Move to trash"}
            </button>
          ) : null}
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
              {document.trashed
                ? "Permanently delete this document from Paperless? This cannot be undone from AtlasDocs."
                : "Move this document to Paperless trash? It will leave normal AtlasDocs views until restored or permanently deleted."}
            </p>
            <div className="doc-actions">
              <button
                ref={confirmDeleteRef}
                type="button"
                className="btn btn-danger"
                disabled={deleteBusy}
                onClick={() => void onConfirmDeleteDocument()}
              >
                {document.trashed ? "Confirm permanent delete" : "Confirm move to trash"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={deleteBusy}
                onClick={onCancelDelete}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}

        <div className="doc-disclosure-stack">
          <details className="tech-details">
            <summary>Metadata</summary>
            <dl>
              <div>
                <dt>Created</dt>
                <dd>{document.created_date || "—"}</dd>
              </div>
              <div>
                <dt>Correspondent</dt>
                <dd>{document.correspondent || "—"}</dd>
              </div>
              <div>
                <dt>Document type</dt>
                <dd>{document.document_type || "—"}</dd>
              </div>
              <div>
                <dt>Lifecycle</dt>
                <dd>{document.lifecycle_category || "evidence"}</dd>
              </div>
            </dl>
          </details>
          <details className="tech-details">
            <summary>OCR</summary>
            <p className="muted">
              OCR text remains authoritative in Paperless. Use preview above or open the source
              document when configured.
            </p>
          </details>
          <details className="tech-details">
            <summary>History</summary>
            {history.length === 0 ? (
              <p className="muted">No replacement history yet.</p>
            ) : (
              <ul className="rel-list">
                {history.map((row) => (
                  <li key={`${row.previous_external_id}-${row.new_external_id}-${row.created_at}`}>
                    Paperless {row.previous_external_id} → {row.new_external_id}
                    <div className="meta muted">
                      {[row.created_at, row.actor_label, row.reason].filter(Boolean).join(" · ")}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </details>
          <details className="tech-details" open={versions.length > 0}>
            <summary>Versions</summary>
            {versions.length === 0 ? (
              <p className="muted">No Paperless version metadata available.</p>
            ) : (
              <label className="field">
                <span>Paperless version</span>
                <select
                  value={selectedVersionId === "" ? "" : String(selectedVersionId)}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedVersionId(value ? Number(value) : "");
                  }}
                >
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      Version {version.id}
                      {version.created ? ` · ${version.created}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </details>
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
        </div>
      </header>

      <div className="doc-detail-layout">
        <section className="doc-preview-pane" aria-label="Document preview">
          <iframe
            className="doc-preview-frame"
            src={previewHref}
            title={`Preview of ${documentDisplayTitle(document)}`}
            sandbox=""
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
