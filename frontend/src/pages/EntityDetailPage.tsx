import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  archiveEntity,
  fetchEntity,
  getSession,
  mergeEntityPlaceholder,
  renameEntity,
  restoreEntity,
  type EntityDetail,
  type SessionInfo,
} from "../api/client";

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
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

function categoryLabel(value: string | undefined): string {
  switch (value) {
    case "evidence":
      return "Evidence";
    case "organizational":
      return "Organizational";
    default:
      return "Master Data";
  }
}

export function EntityDetailPage({ session, onSession }: Props) {
  const { entityId } = useParams();
  const navigate = useNavigate();
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      setEntity(null);
      try {
        const next = await fetchEntity(entityId);
        if (!cancelled) {
          setEntity(next);
          setRenameValue(next.label);
        }
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

  const canMutate =
    entity != null &&
    (entity.lifecycle_category === "master_data" ||
      entity.lifecycle_category === "organizational" ||
      entity.lifecycle_category == null);

  async function runMutation(action: () => Promise<EntityDetail>, message: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const next = await action();
      setEntity(next);
      setRenameValue(next.label);
      setNotice(message);
      onSession(await getSession());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
      try {
        onSession(await getSession());
      } catch {
        /* keep prior session on refresh failure */
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="entity-detail-page" aria-labelledby="entity-title">
      <p className="entity-detail-back">
        <Link to="/explore?mode=knowledge">← Back to Explore</Link>
      </p>

      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="banner" role="status">
          {notice}
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
            <span className="entity-chip" data-kind="concept">
              {categoryLabel(entity.lifecycle_category)}
            </span>
            {entity.archived ? <span className="muted">Archived</span> : null}
            <h1 id="entity-title">{entity.label}</h1>
            <p className="muted">
              Semantic completeness: {completenessLabel(entity.semantic_completeness)}
            </p>
            {entity.merged_into_entity_id ? (
              <p className="muted">
                Merge redirect recorded toward{" "}
                <Link to={`/entities/${entity.merged_into_entity_id}`}>
                  {entity.merged_into_entity_id}
                </Link>
                . Full merge UI is not available in v0.7.
              </p>
            ) : null}

            {canMutate ? (
              <div className="doc-actions" role="group" aria-label="Master Data actions">
                <label className="field">
                  <span>Display name</span>
                  <input
                    type="text"
                    value={renameValue}
                    disabled={busy || Boolean(entity.archived)}
                    onChange={(event) => setRenameValue(event.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy || Boolean(entity.archived) || !renameValue.trim()}
                  onClick={() =>
                    void runMutation(
                      () => renameEntity(entity.id, renameValue.trim(), session.csrf_token),
                      "Entity renamed",
                    )
                  }
                >
                  Rename
                </button>
                {entity.archived ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      void runMutation(
                        () => restoreEntity(entity.id, session.csrf_token),
                        "Entity restored",
                      )
                    }
                  >
                    Restore
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled={busy}
                    onClick={() =>
                      void runMutation(
                        () => archiveEntity(entity.id, session.csrf_token),
                        "Entity archived",
                      )
                    }
                  >
                    Archive
                  </button>
                )}
              </div>
            ) : null}

            {canMutate ? (
              <details className="tech-details">
                <summary>Merge (placeholder)</summary>
                <p className="muted">
                  Records a redirect target only. Relationship rewiring is not implemented yet.
                  Casual delete is blocked while relationships exist — use archive or this
                  placeholder instead of a destructive delete control.
                </p>
                <label className="field">
                  <span>Target entity UUID</span>
                  <input
                    type="text"
                    value={mergeTarget}
                    disabled={busy}
                    onChange={(event) => setMergeTarget(event.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={busy || !mergeTarget.trim()}
                  onClick={() =>
                    void runMutation(
                      () =>
                        mergeEntityPlaceholder(
                          entity.id,
                          mergeTarget.trim(),
                          session.csrf_token,
                        ),
                      "Merge redirect recorded",
                    )
                  }
                >
                  Record merge redirect
                </button>
              </details>
            ) : null}

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
                <div>
                  <dt>Lifecycle category</dt>
                  <dd>
                    <code>{entity.lifecycle_category || "master_data"}</code>
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
