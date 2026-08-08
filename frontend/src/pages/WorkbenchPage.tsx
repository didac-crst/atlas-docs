import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ApiError,
  fetchDocument,
  fetchQueue,
  fetchRelationshipTypes,
  getSession,
  type DocumentDetail,
  type QueuePage,
  type RelationshipType,
  type SessionInfo,
} from "../api/client";
import { DocumentQueue } from "../components/DocumentQueue";
import { RelationshipComposer } from "../components/RelationshipComposer";
import { SemanticDocumentDetail } from "../components/SemanticDocumentDetail";

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
};

export function WorkbenchPage({ session, onSession }: Props) {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const page = Number(searchParams.get("page") || "1") || 1;
  const selectedId = params.paperlessId ? Number(params.paperlessId) : null;

  const [queue, setQueue] = useState<QueuePage | null>(null);
  const [document, setDocument] = useState<DocumentDetail | null>(null);
  const [types, setTypes] = useState<RelationshipType[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshCsrf() {
    const next = await getSession();
    onSession(next);
    return next;
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [queuePage, relTypes] = await Promise.all([
          fetchQueue(page),
          fetchRelationshipTypes(),
        ]);
        if (cancelled) return;
        setQueue(queuePage);
        setTypes(relTypes);
        if (selectedId) {
          const detail = await fetchDocument(selectedId);
          if (!cancelled) setDocument(detail);
        } else {
          setDocument(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load workbench");
        setDocument(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, selectedId, navigate]);

  return (
    <div className={`workbench${selectedId ? " detail-open" : ""}`}>
      {error ? (
        <div className="banner banner-error" role="alert" style={{ gridColumn: "1 / -1" }}>
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="banner banner-success" role="status" style={{ gridColumn: "1 / -1" }}>
          {notice}
        </div>
      ) : null}

      <section className="panel queue-panel" aria-labelledby="queue-title">
        <h1 id="queue-title">Needs classification</h1>
        {loading && !queue ? (
          <p role="status">Loading queue…</p>
        ) : (
          <DocumentQueue
            queue={queue}
            selectedId={selectedId}
            page={page}
            onSelect={(id) => navigate(`/documents/${id}?page=${page}`)}
          />
        )}
      </section>

      <section className="panel detail-panel" aria-labelledby="detail-title">
        {selectedId && document ? (
          <>
            <div className="sticky-actions" style={{ top: 0 }}>
              <Link className="btn btn-secondary" to={`/?page=${page}`}>
                Back to queue
              </Link>
            </div>
            <SemanticDocumentDetail
              document={document}
              csrfToken={session.csrf_token}
              onRemoved={async (nextDoc, message) => {
                setDocument(nextDoc);
                setNotice(message);
                await refreshCsrf();
                const queuePage = await fetchQueue(page);
                setQueue(queuePage);
              }}
              onError={setError}
            />
            <RelationshipComposer
              documentId={document.paperless_document_id}
              types={types}
              csrfToken={session.csrf_token}
              onSaved={async (nextDoc) => {
                setDocument(nextDoc);
                setNotice("Relationship saved");
                await refreshCsrf();
                const queuePage = await fetchQueue(page);
                setQueue(queuePage);
              }}
              onError={setError}
            />
          </>
        ) : selectedId && loading ? (
          <p role="status">Loading document…</p>
        ) : (
          <>
            <h1 id="detail-title">Select a document</h1>
            <p className="empty">
              Choose an unclassified Paperless document from the queue to assign typed
              relationships.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
