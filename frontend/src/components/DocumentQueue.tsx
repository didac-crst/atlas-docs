import { Link } from "react-router-dom";
import type { QueuePage } from "../api/client";

type Props = {
  queue: QueuePage | null;
  selectedId: number | null;
  page: number;
  onSelect: (id: number) => void;
};

export function DocumentQueue({ queue, selectedId, page, onSelect }: Props) {
  if (!queue) {
    return <p className="empty">No queue loaded.</p>;
  }

  return (
    <div>
      <p className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
        Page {queue.page} · {queue.items.length} shown · Paperless {queue.paperless_count}
      </p>
      {queue.items.length === 0 ? (
        <p className="empty">No unclassified documents in this page.</p>
      ) : (
        <ul className="queue-list">
          {queue.items.map((item) => (
            <li key={item.paperless_document_id}>
              <button
                type="button"
                className="queue-item"
                aria-current={selectedId === item.paperless_document_id ? "true" : undefined}
                onClick={() => onSelect(item.paperless_document_id)}
              >
                <strong>{item.title || `Document ${item.paperless_document_id}`}</strong>
                <span className="meta">
                  {[item.created_date, item.correspondent, item.document_type]
                    .filter(Boolean)
                    .join(" · ") || `Paperless #${item.paperless_document_id}`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="site-nav" style={{ marginTop: "1rem" }}>
        {queue.has_previous ? (
          <Link to={`/?page=${page - 1}`}>Previous</Link>
        ) : (
          <span className="muted">Previous</span>
        )}
        {queue.has_next && queue.next_page ? (
          <Link to={`/?page=${queue.next_page}`}>Next</Link>
        ) : (
          <span className="muted">Next</span>
        )}
      </div>
    </div>
  );
}
