import { FormEvent, useState } from "react";
import { connect, type SessionInfo } from "../api/client";

type Props = {
  session: SessionInfo | null;
  onConnected: () => Promise<void>;
};

export function ConnectPage({ session, onConnected }: Props) {
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      await connect(token, session.csrf_token);
      setToken("");
      await onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel connect-panel" aria-labelledby="connect-title">
      <h1 id="connect-title">Connect to Paperless</h1>
      <p className="muted">
        Paste a Paperless API token. It stays on the server in an HttpOnly session and is never
        sent back to the browser.
      </p>
      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}
      <form className="composer" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="paperless-token">Paperless token</label>
          <input
            id="paperless-token"
            name="paperless_token"
            type="password"
            autoComplete="off"
            required
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={saving || !session}>
          {saving ? "Connecting…" : "Connect"}
        </button>
      </form>
    </section>
  );
}
