import { useEffect, useRef, useState, type ReactNode } from "react";
import { Download, ExternalLink, Eye, FileInput, Link2, RotateCcw, Trash2 } from "lucide-react";
import {
  deleteDocument,
  documentDownloadUrl,
  documentPreviewUrl,
  fetchDocument,
  fetchIngestJob,
  jobNeedsPolling,
  replaceDocument,
  restoreDocument,
  type DocumentDetail,
} from "../api/client";
import { Dialog } from "./Dialog";
import { OverflowMenu } from "./OverflowMenu";

type Props = {
  document: DocumentDetail;
  csrfToken: string;
  onRemoved: (document: DocumentDetail, message: string) => Promise<void>;
  onError: (message: string) => void;
  onAddRelationship?: () => void;
  onDocumentDeleted?: () => Promise<void> | void;
  onReplaced?: (document: DocumentDetail, message: string) => Promise<void>;
  /** Open in-app preview modal when available. */
  onPreview?: () => void;
  /** When true, Preview is primary; otherwise Download. */
  preferPreview?: boolean;
  /** Explore = safe read actions only; Classify = full classification chrome. */
  mode?: "explore" | "classify";
};

const REPLACE_POLL_MS = 1500;
const REPLACE_POLL_MAX = 40;

export function DocumentActions({
  document,
  csrfToken,
  onRemoved,
  onError,
  onAddRelationship,
  onDocumentDeleted,
  onReplaced,
  onPreview,
  preferPreview = true,
  mode = "classify",
}: Props) {
  const exploreOnly = mode === "explore";
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceBusy, setReplaceBusy] = useState(false);
  const [replaceReason, setReplaceReason] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState<number | "">("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement>(null);

  const versions = document.versions ?? [];
  const firstVersionId = versions[0]?.id;
  const isEvidence = (document.lifecycle_category ?? "evidence") === "evidence";
  const previewHref = documentPreviewUrl(document.paperless_document_id);
  const downloadHref = documentDownloadUrl(document.paperless_document_id);

  useEffect(() => {
    setSelectedVersionId(firstVersionId ?? "");
  }, [document.paperless_document_id, firstVersionId]);

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
      setReplaceOpen(false);
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

  const versionDownloadHref =
    selectedVersionId === ""
      ? null
      : documentDownloadUrl(document.paperless_document_id, { version: selectedVersionId });

  const primaryPreview = preferPreview ? (
    onPreview ? (
      <button type="button" className="btn btn-primary" onClick={onPreview}>
        <Eye size={16} aria-hidden /> Preview
      </button>
    ) : (
      <a className="btn btn-primary" href={previewHref} target="_blank" rel="noopener noreferrer">
        <Eye size={16} aria-hidden /> Preview
      </a>
    )
  ) : (
    <a className="btn btn-primary" href={downloadHref} download>
      <Download size={16} aria-hidden /> Download
    </a>
  );

  const secondaryDownload = preferPreview ? (
    <a className="btn btn-secondary" href={downloadHref} download>
      <Download size={16} aria-hidden /> Download
    </a>
  ) : onPreview ? (
    <button type="button" className="btn btn-secondary" onClick={onPreview}>
      <Eye size={16} aria-hidden /> Preview
    </button>
  ) : (
    <a className="btn btn-secondary" href={previewHref} target="_blank" rel="noopener noreferrer">
      <Eye size={16} aria-hidden /> Preview
    </a>
  );

  return (
    <>
      <div className="doc-actions">
        {exploreOnly ? (
          <a className="btn btn-primary" href={downloadHref} download>
            <Download size={16} aria-hidden /> Download
          </a>
        ) : (
          <>
            {primaryPreview}
            {secondaryDownload}
            {onAddRelationship ? (
              <button type="button" className="btn btn-secondary" onClick={onAddRelationship}>
                <Link2 size={16} aria-hidden /> Add relationship
              </button>
            ) : (
              <a className="btn btn-secondary" href="#relationship-composer">
                <Link2 size={16} aria-hidden /> Add relationship
              </a>
            )}
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
          </>
        )}

        <OverflowMenu>
          {exploreOnly ? null : (
            <>
              <OverflowItem
                href={documentDownloadUrl(document.paperless_document_id, { original: true })}
                download
              >
                <Download size={16} aria-hidden /> Download original
              </OverflowItem>
              {versions.length > 0 ? (
                <div className="overflow-menu-section" role="none">
                  <label className="field overflow-version-field">
                    <span>Version</span>
                    <select
                      value={selectedVersionId === "" ? "" : String(selectedVersionId)}
                      onChange={(event) => {
                        const value = event.target.value;
                        setSelectedVersionId(value ? Number(value) : "");
                      }}
                      onClick={(event) => event.stopPropagation()}
                    >
                      {versions.map((version) => (
                        <option key={version.id} value={version.id}>
                          Version {version.id}
                          {version.created ? ` · ${version.created}` : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  {versionDownloadHref ? (
                    <OverflowItem href={versionDownloadHref} download>
                      <Download size={16} aria-hidden /> Download selected version
                    </OverflowItem>
                  ) : null}
                </div>
              ) : null}
              {isEvidence && !document.trashed ? (
                <OverflowItem onSelect={() => setReplaceOpen(true)}>
                  <FileInput size={16} aria-hidden /> Replace document
                </OverflowItem>
              ) : null}
            </>
          )}
          {document.open_url ? (
            <OverflowItem href={document.open_url} external>
              <ExternalLink size={16} aria-hidden /> Open in Paperless
            </OverflowItem>
          ) : (
            <button type="button" role="menuitem" className="overflow-menu-item" disabled>
              <ExternalLink size={16} aria-hidden /> Open in Paperless
            </button>
          )}
          <OverflowItem href={previewHref} external>
            <Eye size={16} aria-hidden /> Open preview in new tab
          </OverflowItem>
        </OverflowMenu>

        {!exploreOnly && isEvidence ? (
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
      </div>

      {!exploreOnly && replaceOpen ? (
        <Dialog title="Replace document" onClose={() => setReplaceOpen(false)} role="dialog">
          <p className="muted">
            Upload another representation of the same document. Atlas identity and relationships are
            preserved.
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
        </Dialog>
      ) : null}

      {confirmDelete ? (
        <Dialog
          title={document.trashed ? "Delete permanently" : "Move to trash"}
          onClose={() => {
            setConfirmDelete(false);
            deleteTriggerRef.current?.focus();
          }}
          role="alertdialog"
        >
          <p>
            {document.trashed
              ? "Permanently delete this document? This cannot be undone from AtlasDocs."
              : "Move this document to trash? It will leave normal AtlasDocs views until restored or permanently deleted."}
          </p>
          <div className="doc-actions">
            <button
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
              onClick={() => {
                setConfirmDelete(false);
                deleteTriggerRef.current?.focus();
              }}
            >
              Cancel
            </button>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}

function OverflowItem({
  children,
  href,
  download,
  external,
  onSelect,
}: {
  children: ReactNode;
  href?: string;
  download?: boolean;
  external?: boolean;
  onSelect?: () => void;
}) {
  if (href) {
    return (
      <a
        role="menuitem"
        className="overflow-menu-item"
        href={href}
        download={download || undefined}
        target={external ? "_blank" : undefined}
        rel={external ? "noopener noreferrer" : undefined}
      >
        {children}
      </a>
    );
  }
  return (
    <button type="button" role="menuitem" className="overflow-menu-item" onClick={onSelect}>
      {children}
    </button>
  );
}
