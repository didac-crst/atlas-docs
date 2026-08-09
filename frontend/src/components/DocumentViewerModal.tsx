import { documentPreviewUrl } from "../api/client";
import { useEffect, useState, type ReactNode } from "react";
import { Dialog } from "./Dialog";

type Props = {
  paperlessDocumentId: number;
  title: string;
  onClose: () => void;
  /** Optional side panel (e.g. Classify actions) — same viewer, contextual chrome. */
  sidePanel?: ReactNode;
};

/**
 * Same-origin AtlasDocs BFF preview in a modal. Preserves underlying route;
 * Escape / backdrop / Close / browser-back (via parent search-param) dismiss it.
 */
export function DocumentViewerModal({
  paperlessDocumentId,
  title,
  onClose,
  sidePanel,
}: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const src = documentPreviewUrl(paperlessDocumentId);
  const withPanel = Boolean(sidePanel);

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

  return (
    <Dialog
      title={title || "Document preview"}
      onClose={onClose}
      fullScreenMobile
      className={[
        "document-viewer-dialog",
        withPanel ? "document-viewer-dialog-with-panel" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className={withPanel ? "document-viewer-layout" : undefined}>
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
              title={`Preview of ${title || "document"}`}
            />
          ) : null}
        </div>
        {sidePanel ? (
          <aside className="document-viewer-side" aria-label="Document actions">
            {sidePanel}
          </aside>
        ) : null}
      </div>
    </Dialog>
  );
}
