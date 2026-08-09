import { Check, Download, Eye } from "lucide-react";
import { Link } from "react-router-dom";
import {
  documentDownloadUrl,
  type ExploreResultItem,
} from "../api/client";
import { documentPreviewUrl } from "../api/client";
import type { KeyboardEvent, MouseEvent } from "react";

type Props = {
  item: ExploreResultItem;
  view: "list" | "grid";
  /** Prefer opening the in-app preview modal instead of navigating away. */
  onPreview?: (paperlessDocumentId: number, title: string) => void;
  /** Classify (and other queues): whole-card multi-select. */
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
};

function completenessLabel(value: string): string {
  switch (value) {
    case "empty":
      return "Empty";
    case "partial":
      return "Partial";
    case "classified":
      return "Classified";
    case "needs_review":
      return "Needs review";
    case "complete":
      return "Complete (legacy)";
    default:
      return value;
  }
}

function typeLabel(entityType: string): string {
  switch (entityType) {
    case "document":
      return "Document";
    case "person":
      return "Person";
    case "organization":
      return "Organization";
    case "country":
      return "Country";
    case "case":
      return "Case";
    case "concept":
      return "Concept";
    default:
      return entityType;
  }
}

function isInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return Boolean(
    target.closest("a, button, input, select, textarea, label, [role='button']"),
  );
}

/** Shared document/entity result card for Explore, Classify, search, and relationship picks. */
export function DocumentCard({
  item,
  view,
  onPreview,
  selectable = false,
  selected = false,
  onToggleSelect,
}: Props) {
  const isDocument = item.entity_type === "document" && item.paperless_document_id != null;
  const href = isDocument
    ? `/documents/${item.paperless_document_id}`
    : item.id
      ? `/entities/${item.id}`
      : null;
  const title = item.label || "Untitled";
  const documentType = item.document_type;
  const organization = item.correspondent;
  const date = item.created_date;
  const relationshipCount = item.relationship_count ?? item.relationship_summary.length;
  const showThumb = isDocument && item.thumbnail_available !== false && item.preview_available;

  function openDocument() {
    if (isDocument && onPreview && item.paperless_document_id != null) {
      onPreview(item.paperless_document_id, title);
    }
  }

  function onCardClick(event: MouseEvent) {
    if (!selectable || !isDocument) return;
    if (isInteractiveTarget(event.target)) return;
    onToggleSelect?.();
  }

  function onCardKeyDown(event: KeyboardEvent) {
    if (!selectable || !isDocument) return;
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      onToggleSelect?.();
    }
  }

  return (
    <article
      className={`doc-card doc-card-${view}${selected ? " doc-card-selected" : ""}${
        selectable && isDocument ? " doc-card-selectable" : ""
      }`}
      data-entity-type={item.entity_type}
      aria-selected={selectable && isDocument ? selected : undefined}
      tabIndex={selectable && isDocument ? 0 : undefined}
      onClick={onCardClick}
      onKeyDown={onCardKeyDown}
    >
      {selectable && isDocument && selected ? (
        <span className="doc-card-selected-mark" aria-hidden>
          <Check size={16} />
        </span>
      ) : null}

      {isDocument ? (
        <button
          type="button"
          className="doc-card-thumb"
          aria-label={item.preview_available ? `Preview ${title}` : title}
          disabled={!item.preview_available && !onPreview}
          onClick={() => {
            if (onPreview && item.paperless_document_id != null) {
              openDocument();
            }
          }}
        >
          {showThumb ? (
            <img
              src={documentPreviewUrl(item.paperless_document_id!)}
              alt=""
              loading="lazy"
            />
          ) : (
            <span className="doc-card-thumb-fallback" aria-hidden>
              PDF
            </span>
          )}
        </button>
      ) : (
        <div className="doc-card-thumb doc-card-thumb-entity" aria-hidden>
          <span className="entity-chip" data-kind={item.entity_type}>
            {typeLabel(item.entity_type)}
          </span>
        </div>
      )}

      <div className="doc-card-main">
        <span className="entity-chip" data-kind={item.entity_type}>
          {documentType || typeLabel(item.entity_type)}
        </span>
        {isDocument && onPreview ? (
          <button type="button" className="doc-card-title doc-card-title-btn" onClick={openDocument}>
            {title}
          </button>
        ) : href ? (
          <Link to={href} className="doc-card-title">
            {title}
          </Link>
        ) : (
          <strong className="doc-card-title">{title}</strong>
        )}
        <dl className="doc-card-facts">
          {documentType ? (
            <div>
              <dt>Type</dt>
              <dd>{documentType}</dd>
            </div>
          ) : null}
          {date ? (
            <div>
              <dt>Date</dt>
              <dd>{date}</dd>
            </div>
          ) : null}
          {organization ? (
            <div>
              <dt>Organization</dt>
              <dd>{organization}</dd>
            </div>
          ) : null}
          {item.subtitle && !documentType && !organization ? (
            <div>
              <dt>Context</dt>
              <dd>{item.subtitle}</dd>
            </div>
          ) : null}
        </dl>
        <p className="doc-card-meta muted">
          {relationshipCount} relationship{relationshipCount === 1 ? "" : "s"}
          {" · "}
          {completenessLabel(item.semantic_completeness)}
        </p>
      </div>

      {isDocument ? (
        <div className="doc-card-actions">
          {onPreview ? (
            <button type="button" className="btn btn-secondary" onClick={openDocument}>
              <Eye size={16} aria-hidden /> Preview
            </button>
          ) : item.preview_available ? (
            <a
              className="btn btn-secondary"
              href={documentPreviewUrl(item.paperless_document_id!)}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Eye size={16} aria-hidden /> Preview
            </a>
          ) : null}
          {item.download_available ? (
            <a
              className="btn btn-ghost"
              href={documentDownloadUrl(item.paperless_document_id!)}
              download
            >
              <Download size={16} aria-hidden /> Download
            </a>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

/** @deprecated Prefer DocumentCard — kept as a thin alias for existing imports. */
export function ExploreResultCard(props: Props) {
  return <DocumentCard {...props} />;
}
