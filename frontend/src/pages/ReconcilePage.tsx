import { FormEvent, useState } from "react";
import { GitBranch } from "lucide-react";
import {
  getSession,
  runReconcile,
  type ReconcileSummary,
  type SessionInfo,
} from "../api/client";

type Props = {
  session: SessionInfo;
  onSession: (session: SessionInfo) => void;
};

export function ReconcilePage({ session, onSession }: Props) {
  const [dryRun, setDryRun] = useState(true);
  const [limit, setLimit] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [summary, setSummary] = useState<ReconcileSummary | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const parsedLimit = limit.trim() ? Number(limit.trim()) : null;
      if (parsedLimit !== null && (!Number.isInteger(parsedLimit) || parsedLimit < 1)) {
        throw new Error("Limit must be a positive integer");
      }
      const result = await runReconcile(
        { dry_run: dryRun, limit: parsedLimit },
        session.csrf_token,
      );
      setSummary(result);
      setNotice(result.dry_run ? "Dry-run complete" : "Reconciliation applied");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reconcile failed");
    } finally {
      try {
        onSession(await getSession());
      } catch {
        setError((prev) =>
          prev
            ? `${prev}. Session refresh failed — reload before running again.`
            : "Session refresh failed — reload before running again.",
        );
      }
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="reconcile-title">
      <h1 id="reconcile-title">
        <GitBranch size={20} aria-hidden /> Paperless reconciliation
      </h1>
      <p className="muted">
        Creates missing AtlasDocs document entities and Paperless external references. Missing or
        inaccessible Paperless documents are reported; semantic data is never deleted.
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
        <label>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(event) => setDryRun(event.target.checked)}
          />{" "}
          Dry run
        </label>
        <div className="field">
          <label htmlFor="limit">Limit (optional)</label>
          <input
            id="limit"
            inputMode="numeric"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            placeholder="e.g. 100"
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Running…" : "Run reconciliation"}
        </button>
      </form>
      {summary ? (
        <div className="reconcile-lists" aria-live="polite">
          <p>{summary.human_summary}</p>
          <div>
            <h2>Missing in Paperless</h2>
            {summary.missing_in_paperless.length === 0 ? (
              <p className="empty">None</p>
            ) : (
              <ul>
                {summary.missing_in_paperless.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h2>Inaccessible in Paperless</h2>
            {summary.inaccessible_in_paperless.length === 0 ? (
              <p className="empty">None</p>
            ) : (
              <ul>
                {summary.inaccessible_in_paperless.map((id) => (
                  <li key={id}>{id}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : (
        <p className="empty">Run reconciliation to see creates and missing/inaccessible references.</p>
      )}
    </section>
  );
}
