import { Download, Eye } from "lucide-react";
import { Link } from "react-router-dom";
import {
  documentDownloadUrl,
  documentPreviewUrl,
  type ExploreResultItem,
} from "../api/client";

type Props = {
  item: ExploreResultItem;
  view: "list" | "grid";
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
    default:
      return value;
  }
}

export function ExploreResultCard({ item, view }: Props) {
  const isDocument = item.entity_type === "document" && item.paperless_document_id != null;
  const href = isDocument
    ? `/documents/${item.paperless_document_id}`
    : item.id
      ? `/entities/${item.id}`
      : null;
  const meta =
    item.subtitle ||
    [item.created_date, item.correspondent, item.document_type].filter(Boolean).join(" · ");

  return (
    <article className={`explore-card explore-card-${view}`}>
      <div className="explore-card-main">
        <span className="entity-chip" data-kind={item.entity_type}>
          {item.entity_type}
        </span>
        {href ? (
          <Link to={href} className="explore-card-title">
            {item.label || "Untitled"}
          </Link>
        ) : (
          <strong className="explore-card-title">{item.label || "Untitled"}</strong>
        )}
        {meta ? <p className="explore-card-meta muted">{meta}</p> : null}
        {item.relationship_summary.length > 0 ? (
          <ul className="explore-card-rels">
            {item.relationship_summary.slice(0, 3).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}
        <p className="explore-card-state muted">{completenessLabel(item.semantic_completeness)}</p>
      </div>
      {isDocument ? (
        <div className="explore-card-actions">
          {item.preview_available ? (
            <a
              className="btn btn-ghost"
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
