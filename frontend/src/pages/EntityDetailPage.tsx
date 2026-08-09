import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  fetchEntity,
  type EntityDetail,
  type SessionInfo,
} from "../api/client";

type Props = {
  session: SessionInfo;
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

export function EntityDetailPage({ session: _session }: Props) {
  const { entityId } = useParams();
  const navigate = useNavigate();
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const next = await fetchEntity(entityId);
        if (!cancelled) setEntity(next);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load entity");
        setEntity(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [entityId, navigate]);

  if (entity?.paperless_document_id != null) {
    return <Navigate to={`/documents/${entity.paperless_document_id}`} replace />;
  }

  return (
    <section className="entity-detail-page" aria-labelledby="entity-title">
      <p className="entity-detail-back">
        <Link to="/explore">← Back to Explore</Link>
      </p>

      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}

      {loading && !entity ? (
        <p className="muted" role="status">
          Loading entity…
        </p>
      ) : null}

      {entity ? (
        <>
          <header className="entity-detail-header">
            <span className="entity-chip" data-kind={entity.display_type || entity.entity_type}>
              {entity.display_type || entity.entity_type}
            </span>
            <h1 id="entity-title">{entity.label}</h1>
            <p className="muted">
              Semantic completeness: {completenessLabel(entity.semantic_completeness)}
            </p>
            <details className="tech-details">
              <summary>Technical details</summary>
              <dl>
                <div>
                  <dt>Entity UUID</dt>
                  <dd>
                    <code>{entity.id}</code>
                  </dd>
                </div>
                <div>
                  <dt>Entity type</dt>
                  <dd>
                    <code>{entity.entity_type}</code>
                  </dd>
                </div>
              </dl>
            </details>
          </header>

          <section className="entity-detail-section" aria-labelledby="entity-related-docs">
            <h2 id="entity-related-docs">Related documents</h2>
            {entity.related_documents.length === 0 ? (
              <p className="empty">No related documents yet.</p>
            ) : (
              <ul className="entity-related-list">
                {entity.related_documents.map((doc) => (
                  <li key={`${doc.paperless_document_id}-${doc.relationship_type}`}>
                    <Link to={`/documents/${doc.paperless_document_id}`}>
                      <strong>{doc.label}</strong>
                      <span className="meta muted">
                        {[doc.relationship_type, doc.created_date].filter(Boolean).join(" · ")}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="entity-detail-section" aria-labelledby="entity-outgoing">
            <h2 id="entity-outgoing">Outgoing relationships</h2>
            {entity.relationships.length === 0 ? (
              <p className="empty">No outgoing relationships.</p>
            ) : (
              <ul className="entity-rel-list">
                {entity.relationships.map((rel) => (
                  <li key={rel.id}>
                    <strong>{rel.type}</strong>{" "}
                    {rel.target_entity_id ? (
                      <Link to={`/entities/${rel.target_entity_id}`}>{rel.target}</Link>
                    ) : (
                      rel.target
                    )}
                    <div className="meta muted">
                      Provenance: {rel.origin} · Status: {rel.status}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="entity-detail-section" aria-labelledby="entity-backlinks">
            <h2 id="entity-backlinks">Backlinks</h2>
            {entity.backlinks.length === 0 ? (
              <p className="empty">No backlinks yet.</p>
            ) : (
              <ul className="entity-rel-list">
                {entity.backlinks.map((rel) => (
                  <li key={rel.id}>
                    <strong>{rel.type}</strong> from{" "}
                    {rel.source_paperless_document_id != null ? (
                      <Link to={`/documents/${rel.source_paperless_document_id}`}>
                        {rel.source}
                      </Link>
                    ) : (
                      <Link to={`/entities/${rel.source_entity_id}`}>{rel.source}</Link>
                    )}
                    <div className="meta muted">
                      Provenance: {rel.origin} · Status: {rel.status}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </section>
  );
}
