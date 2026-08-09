import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FilePlus2, GitBranch, Compass, Search, Tags } from "lucide-react";
import {
  ApiError,
  fetchHome,
  formatCountStat,
  type HomeSummary,
  type SessionInfo,
} from "../api/client";
import markUrl from "../assets/atlas-docs-mark.svg";

type Props = {
  session?: SessionInfo | null;
};

export function HomePage({ session: _session }: Props) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const next = await fetchHome();
        if (!cancelled) setSummary(next);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load home");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  function onSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    navigate(q ? `/explore?${params.toString()}` : "/explore");
  }

  return (
    <section className="home-page" aria-labelledby="home-title">
      <div className="home-brand">
        <img src={markUrl} alt="" width={64} height={64} />
        <h1 id="home-title">AtlasDocs</h1>
        <p className="muted">Semantic work surface for your documents.</p>
      </div>

      <form className="home-search" role="search" onSubmit={onSearch}>
        <label htmlFor="home-global-search" className="sr-only">
          Search documents and concepts
        </label>
        <div className="home-search-row">
          <Search size={18} aria-hidden />
          <input
            id="home-global-search"
            type="search"
            name="q"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search documents and concepts"
            autoComplete="off"
          />
          <button type="submit" className="btn">
            Search
          </button>
        </div>
      </form>

      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}

      {loading && !summary ? (
        <p className="muted" role="status">
          Loading overview…
        </p>
      ) : null}

      {summary ? (
        <>
          <section className="home-section" aria-labelledby="home-tasks-title">
            <h2 id="home-tasks-title">Work areas</h2>
            <ul className="home-task-list">
              <li>
                <Link to="/explore" className="home-task-link">
                  <Compass size={20} aria-hidden />
                  <span>
                    <strong>Explore</strong>
                    <span className="meta">Browse documents and concepts.</span>
                  </span>
                </Link>
              </li>
              <li>
                <Link to="/classify?classification=unclassified" className="home-task-link">
                  <Tags size={20} aria-hidden />
                  <span>
                    <strong>Needs classification</strong>
                    <span className="home-count">{formatCountStat(summary.needs_classification)}</span>
                    <span className="meta">Open the classification workbench.</span>
                  </span>
                </Link>
              </li>
              <li>
                <Link to="/classify?classification=any" className="home-task-link">
                  <Tags size={20} aria-hidden />
                  <span>
                    <strong>Needs review</strong>
                    <span className="home-count">{formatCountStat(summary.needs_review)}</span>
                    <span className="meta">Suggested relationships waiting for confirmation.</span>
                  </span>
                </Link>
              </li>
              <li>
                <Link to="/ingest" className="home-task-link">
                  <FilePlus2 size={20} aria-hidden />
                  <span>
                    <strong>Failed ingestion</strong>
                    <span className="home-count">{formatCountStat(summary.failed_ingestion)}</span>
                    <span className="meta">Retry or inspect upload jobs.</span>
                  </span>
                </Link>
              </li>
              <li>
                <Link to="/reconcile" className="home-task-link">
                  <GitBranch size={20} aria-hidden />
                  <span>
                    <strong>Reconciliation issues</strong>
                    <span className="home-count">
                      {formatCountStat(summary.reconciliation_issues)}
                    </span>
                    <span className="meta">Bind missing AtlasDocs entities.</span>
                  </span>
                </Link>
              </li>
            </ul>
          </section>

          <section className="home-section" aria-labelledby="home-recent-docs-title">
            <h2 id="home-recent-docs-title">Recently added documents</h2>
            {summary.recent_documents.length === 0 ? (
              <p className="empty">No recent documents yet.</p>
            ) : (
              <ul className="home-recent-list">
                {summary.recent_documents.map((item) => (
                  <li key={`${item.href}-${item.label}`}>
                    <Link to={item.href}>
                      <strong>{item.label || "Untitled document"}</strong>
                      {item.created_date ? (
                        <span className="meta muted">{item.created_date}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="home-section" aria-labelledby="home-recent-knowledge-title">
            <h2 id="home-recent-knowledge-title">Recently changed knowledge</h2>
            {summary.recent_knowledge.length === 0 ? (
              <p className="empty">No recent relationship changes.</p>
            ) : (
              <ul className="home-recent-list">
                {summary.recent_knowledge.map((item) => (
                  <li key={`${item.href}-${item.relationship_type}-${item.label}`}>
                    <Link to={item.href}>
                      <strong>{item.label}</strong>
                      <span className="meta muted">{item.relationship_type}</span>
                    </Link>
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
