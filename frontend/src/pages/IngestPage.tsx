import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FilePlus2 } from "lucide-react";
import {
  ApiError,
  clearCompletedIngestJobs,
  fetchIngestJobs,
  getSession,
  ingestDocument,
  jobNeedsPolling,
  retryIngestJob,
  type IngestJob,
  type SessionInfo,
} from "../api/client";
import { PageLayout } from "../components/PageLayout";

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
};

const POLL_MS = 2500;

export function IngestPage({ session, onSession }: Props) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pollFailed, setPollFailed] = useState(false);

  const refreshJobs = useCallback(async () => {
    const page = await fetchIngestJobs();
    setJobs(page.items);
    setPollFailed(false);
    return page.items;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        await refreshJobs();
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/connect");
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate, refreshJobs]);

  const hasActiveJobs = jobs.some(jobNeedsPolling);
  const needsPoll = hasActiveJobs && !pollFailed;

  useEffect(() => {
    if (!needsPoll) return;
    let failures = 0;
    const handle = window.setInterval(() => {
      void refreshJobs()
        .then(() => {
          failures = 0;
        })
        .catch((err) => {
          if (err instanceof ApiError && err.status === 401) {
            window.clearInterval(handle);
            navigate("/connect");
            return;
          }
          failures += 1;
          if (failures >= 5) {
            window.clearInterval(handle);
            setPollFailed(true);
            setError(err instanceof Error ? err.message : "Failed to refresh jobs");
          }
        });
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, [navigate, needsPoll, refreshJobs]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to upload");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const job = await ingestDocument(file, title || undefined, session.csrf_token);
      setFile(null);
      setTitle("");
      setNotice(`Upload accepted · job ${job.id.slice(0, 8)}… (${job.state})`);
      onSession(await getSession());
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      try {
        onSession(await getSession());
      } catch {
        /* ignore */
      }
    } finally {
      setBusy(false);
    }
  }

  async function onRetry(jobId: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const job = await retryIngestJob(jobId, session.csrf_token);
      setNotice(`Retry queued · job ${job.id.slice(0, 8)}… (${job.state})`);
      onSession(await getSession());
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retry failed");
      try {
        onSession(await getSession());
      } catch {
        /* ignore */
      }
    } finally {
      setBusy(false);
    }
  }

  async function onClearCompleted() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await clearCompletedIngestJobs(session.csrf_token);
      setNotice(
        result.cleared === 0
          ? "No completed imports to clear"
          : `Cleared ${result.cleared} completed import${result.cleared === 1 ? "" : "s"} from history`,
      );
      await refreshJobs();
      try {
        onSession(await getSession());
      } catch {
        setError("Import history was cleared, but session refresh failed.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to clear history");
      try {
        onSession(await getSession());
      } catch {
        /* ignore */
      }
    } finally {
      setBusy(false);
    }
  }

  const completedCount = jobs.filter((job) => job.state === "READY" || job.state === "FAILED").length;

  return (
    <PageLayout width="standard">
    <div className="ingest-layout">
      <section className="panel" aria-labelledby="ingest-title">
        <h1 id="ingest-title">
          <FilePlus2 size={20} aria-hidden /> Ingest document
        </h1>
        <p className="muted">
          Upload a file through AtlasDocs. Jobs continue on the server until ready or
          failed; the source document engine stores the file.
        </p>
        {error ? (
          <div className="banner banner-error" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="banner banner-success" role="status">
            {notice}
          </div>
        ) : null}
        <form className="composer" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="ingest-file">Document</label>
            <input
              id="ingest-file"
              type="file"
              required
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <div className="field">
            <label htmlFor="ingest-title-field">Title (optional)</label>
            <input
              id="ingest-title-field"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Overrides filename when supported"
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={busy || !file}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>
      </section>

      <section className="panel" aria-labelledby="jobs-title">
        <div className="ingest-history-header">
          <div>
            <h1 id="jobs-title">Recent imports</h1>
            <p className="muted">
              Your import history for this account. Clearing history does not delete documents.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary atlas-control"
            disabled={busy || completedCount === 0}
            onClick={() => void onClearCompleted()}
          >
            Clear completed
          </button>
        </div>
        {loading && jobs.length === 0 ? (
          <p role="status">Loading imports…</p>
        ) : jobs.length === 0 ? (
          <p className="empty">No recent imports yet.</p>
        ) : (
          <div className="job-table-wrap">
            <table className="job-table">
              <thead>
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">State</th>
                  <th scope="col">Updated</th>
                  <th scope="col">Document</th>
                  <th scope="col">Error</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{job.original_filename || job.id.slice(0, 8)}</td>
                    <td>
                      <span className={`job-state job-state-${job.state.toLowerCase()}`}>
                        {job.state}
                      </span>
                    </td>
                    <td className="muted" style={{ fontVariantNumeric: "tabular-nums" }}>
                      {formatTimestamp(job.updated_at)}
                    </td>
                    <td>
                      {job.paperless_document_id != null ? (
                        <Link to={`/documents/${job.paperless_document_id}`}>Open</Link>
                      ) : (
                        <span className="muted">Pending</span>
                      )}
                    </td>
                    <td className="muted">
                      {job.error_message || job.error_code || "—"}
                    </td>
                    <td>
                      {job.state === "RETRYABLE_FAILURE" ? (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busy}
                          onClick={() => void onRetry(job.id)}
                        >
                          Retry
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {needsPoll ? (
              <p className="muted" role="status">
                Refreshing active jobs…
              </p>
            ) : null}
          </div>
        )}
      </section>
    </div>
    </PageLayout>
  );
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
