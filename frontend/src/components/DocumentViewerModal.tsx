import { useEffect, useState } from "react";
import { documentPreviewUrl } from "../api/client";
import { Dialog } from "./Dialog";

type Props = {
  paperlessDocumentId: number;
  title: string;
  onClose: () => void;
};

/**
 * Same-origin AtlasDocs BFF preview in a modal. Preserves underlying route;
 * Escape / backdrop / Close / browser-back (via parent search-param) dismiss it.
 */
export function DocumentViewerModal({ paperlessDocumentId, title, onClose }: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const src = documentPreviewUrl(paperlessDocumentId);

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
    <Dialog title={title || "Document preview"} onClose={onClose} fullScreenMobile className="document-viewer-dialog">
      {status === "loading" ? (
        <p className="muted" role="status">
          Loading preview…
        </p>
      ) : null}
      {status === "error" ? (
        <div className="banner banner-error" role="alert">
          Preview is unavailable. Try Download, or open the document from Classify.
        </div>
      ) : null}
      {status === "ready" ? (
        <iframe
          className="document-viewer-frame"
          src={src}
          title={`Preview of ${title || "document"}`}
        />
      ) : null}
    </Dialog>
  );
}
