import { documentDownloadUrl, documentPreviewUrl } from "../api/client";
import { AtlasIcon } from "./atlasIcons";

type Props = {
  paperlessDocumentId: number;
  title: string;
  previewAvailable: boolean;
  downloadAvailable: boolean;
  onDetails?: () => void;
  compact?: boolean;
};

/** Centered glyph-only document actions shared by grid and list. */
export function DocumentActionBar({
  paperlessDocumentId,
  title,
  previewAvailable,
  downloadAvailable,
  onDetails,
  compact = false,
}: Props) {
  const previewHref = documentPreviewUrl(paperlessDocumentId);
  const downloadHref = documentDownloadUrl(paperlessDocumentId);

  return (
    <div className={`doc-action-bar${compact ? " doc-action-bar-compact" : ""}`} role="group" aria-label="Document actions">
      {onDetails ? (
        <button
          type="button"
          className="btn btn-icon"
          title="Document details"
          aria-label="Document details"
          onClick={(event) => {
            event.stopPropagation();
            onDetails();
          }}
        >
          <AtlasIcon name="details" size={compact ? 15 : 16} />
        </button>
      ) : null}
      {previewAvailable ? (
        <a
          className="btn btn-icon"
          href={previewHref}
          target="_blank"
          rel="noopener noreferrer"
          title="Open preview in new tab"
          aria-label="Open preview in new tab"
          onClick={(event) => event.stopPropagation()}
        >
          <AtlasIcon name="preview" size={compact ? 15 : 16} />
        </a>
      ) : (
        <button type="button" className="btn btn-icon" disabled title="Preview unavailable" aria-label="Preview unavailable">
          <AtlasIcon name="preview" size={compact ? 15 : 16} />
        </button>
      )}
      {downloadAvailable ? (
        <a
          className="btn btn-icon"
          href={downloadHref}
          download
          title="Download document"
          aria-label={`Download ${title}`}
          onClick={(event) => event.stopPropagation()}
        >
          <AtlasIcon name="download" size={compact ? 15 : 16} />
        </a>
      ) : (
        <button type="button" className="btn btn-icon" disabled title="Download unavailable" aria-label="Download unavailable">
          <AtlasIcon name="download" size={compact ? 15 : 16} />
        </button>
      )}
    </div>
  );
}
