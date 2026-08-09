import { Link } from "react-router-dom";
import type { ExploreResultItem } from "../api/client";
import { documentPreviewUrl } from "../api/client";
import type { KeyboardEvent, MouseEvent } from "react";
import { AtlasIcon } from "./atlasIcons";
import { DocumentActionBar } from "./DocumentActionBar";
import { DocumentMetaItem } from "./DocumentMetaItem";
import { toDocumentPresentation } from "./documentPresentation";

type Props = {
  item: ExploreResultItem;
  view: "list" | "grid";
  /** Opens the shared document modal (details). */
  onPreview?: (paperlessDocumentId: number, title: string) => void;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: () => void;
};

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

/** Shared document/entity result card — compact grid or scan-oriented list. */
export function DocumentCard({
  item,
  view,
  onPreview,
  selectable = false,
  selected = false,
  onToggleSelect,
}: Props) {
  const doc = toDocumentPresentation(item);
  const isDocument = item.entity_type === "document" && doc.paperlessDocumentId != null;
  const href = isDocument
    ? `/documents/${doc.paperlessDocumentId}`
    : doc.entityId
      ? `/entities/${doc.entityId}`
      : null;
  const showThumb = isDocument && doc.thumbnailAvailable;

  function openDetails() {
    if (isDocument && onPreview && doc.paperlessDocumentId != null) {
      onPreview(doc.paperlessDocumentId, doc.title);
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

  const titleNode =
    isDocument && onPreview ? (
      <button
        type="button"
        className="doc-card-title doc-card-title-btn"
        title={doc.title}
        onClick={(event) => {
          event.stopPropagation();
          openDetails();
        }}
      >
        {doc.title}
      </button>
    ) : href ? (
      <Link to={href} className="doc-card-title" title={doc.title}>
        {doc.title}
      </Link>
    ) : (
      <strong className="doc-card-title" title={doc.title}>
        {doc.title}
      </strong>
    );

  const meta = (
    <div className="doc-card-meta-row">
      {doc.correspondent ? (
        <DocumentMetaItem icon="organization" label="Organization" value={doc.correspondent} />
      ) : null}
      {doc.createdDateLabel ? (
        <DocumentMetaItem icon="date" label="Created date" value={doc.createdDateLabel} />
      ) : null}
      {isDocument ? (
        <DocumentMetaItem
          icon="relationship"
          label="Relationships"
          value={`${doc.relationshipCount} relationship${doc.relationshipCount === 1 ? "" : "s"}`}
        />
      ) : (
        <DocumentMetaItem
          icon="knowledge"
          label="Relationships"
          value={`${doc.relationshipCount} relationship${doc.relationshipCount === 1 ? "" : "s"}`}
        />
      )}
      {!doc.correspondent && !doc.createdDateLabel && item.subtitle ? (
        <span className="doc-meta-item muted">{item.subtitle}</span>
      ) : null}
    </div>
  );

  if (view === "list") {
    return (
      <article
        className={`doc-card doc-card-list${selected ? " doc-card-selected" : ""}${
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
            <AtlasIcon name="select" size={14} />
          </span>
        ) : null}

        {isDocument ? (
          <div className="doc-card-thumb doc-card-thumb-list" aria-hidden>
            {showThumb ? (
              <img src={documentPreviewUrl(doc.paperlessDocumentId!)} alt="" loading="lazy" />
            ) : (
              <span className="doc-card-thumb-fallback">
                <AtlasIcon name="document" size={18} />
              </span>
            )}
          </div>
        ) : (
          <div className="doc-card-thumb doc-card-thumb-list doc-card-thumb-entity" aria-hidden>
            <span className="entity-chip" data-kind={item.entity_type}>
              {typeLabel(item.entity_type)}
            </span>
          </div>
        )}

        <div className="doc-card-main">
          {titleNode}
          {meta}
          {doc.knowledgeContext ? (
            <p className="doc-card-knowledge muted" title={doc.knowledgeContext}>
              <AtlasIcon name="knowledge" size={14} />
              <span>{doc.knowledgeContext}</span>
            </p>
          ) : null}
        </div>

        {isDocument ? (
          <DocumentActionBar
            paperlessDocumentId={doc.paperlessDocumentId!}
            title={doc.title}
            previewAvailable={doc.previewAvailable}
            downloadAvailable={doc.downloadAvailable}
            onDetails={onPreview ? openDetails : undefined}
            compact
          />
        ) : null}
      </article>
    );
  }

  return (
    <article
      className={`doc-card doc-card-grid${selected ? " doc-card-selected" : ""}${
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
          <AtlasIcon name="select" size={14} />
        </span>
      ) : null}

      {isDocument ? (
        <div className="doc-card-preview">
          {(doc.documentType || typeLabel(item.entity_type)) ? (
            <span className="entity-chip doc-card-type-pill" data-kind="document">
              {doc.documentType || typeLabel(item.entity_type)}
            </span>
          ) : null}
          <button
            type="button"
            className="doc-card-thumb"
            aria-label={`Document details for ${doc.title}`}
            onClick={(event) => {
              event.stopPropagation();
              openDetails();
            }}
          >
            {showThumb ? (
              <img src={documentPreviewUrl(doc.paperlessDocumentId!)} alt="" loading="lazy" />
            ) : (
              <span className="doc-card-thumb-fallback" aria-hidden>
                <AtlasIcon name="document" size={22} />
              </span>
            )}
          </button>
        </div>
      ) : (
        <div className="doc-card-preview">
          <span className="entity-chip doc-card-type-pill" data-kind={item.entity_type}>
            {typeLabel(item.entity_type)}
          </span>
          <div className="doc-card-thumb doc-card-thumb-entity" aria-hidden>
            <AtlasIcon name="knowledge" size={22} />
          </div>
        </div>
      )}

      <div className="doc-card-main">
        {titleNode}
        {meta}
      </div>

      {isDocument ? (
        <DocumentActionBar
          paperlessDocumentId={doc.paperlessDocumentId!}
          title={doc.title}
          previewAvailable={doc.previewAvailable}
          downloadAvailable={doc.downloadAvailable}
          onDetails={onPreview ? openDetails : undefined}
        />
      ) : null}
    </article>
  );
}

/** @deprecated Prefer DocumentCard — kept as a thin alias for existing imports. */
export function ExploreResultCard(props: Props) {
  return <DocumentCard {...props} />;
}
