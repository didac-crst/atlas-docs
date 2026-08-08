import { FormEvent, useState } from "react";
import { connect, login, type SessionInfo } from "../api/client";

type Props = {
  session: SessionInfo | null;
  onConnected: () => Promise<void>;
};

export function ConnectPage({ session, onConnected }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onLogin(event: FormEvent) {
    event.preventDefault();
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      await login(username, password, session.csrf_token);
      setPassword("");
      await onConnected();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSaving(false);
    }
  }

  async function onTokenConnect(event: FormEvent) {
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

  if (session?.authenticated) {
    return (
      <section className="panel connect-panel" aria-labelledby="connect-title">
        <h1 id="connect-title">Connected</h1>
        <p className="muted">
          Your Paperless session is active. Use Disconnect in the header to sign out, or reconnect
          below with another identity.
        </p>
        <details className="advanced-connect">
          <summary>Reconnect</summary>
          <p className="muted">Sign in again to replace the stored Paperless credentials.</p>
          {error ? (
            <div className="banner banner-error" role="alert">
              {error}
            </div>
          ) : null}
          <form className="composer" onSubmit={onLogin}>
            <div className="field">
              <label htmlFor="paperless-username">Username</label>
              <input
                id="paperless-username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="paperless-password">Password</label>
              <input
                id="paperless-password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </details>
      </section>
    );
  }

  return (
    <section className="panel connect-panel" aria-labelledby="connect-title">
      <h1 id="connect-title">Connect to Paperless</h1>
      <p className="muted">
        Sign in with your Paperless username and password. Credentials stay on the server in an
        HttpOnly session and are never sent back to the browser.
      </p>
      {error ? (
        <div className="banner banner-error" role="alert">
          {error}
        </div>
      ) : null}
      <form className="composer" onSubmit={onLogin}>
        <div className="field">
          <label htmlFor="paperless-username">Username</label>
          <input
            id="paperless-username"
            name="username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="paperless-password">Password</label>
          <input
            id="paperless-password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={saving || !session}>
          {saving ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <details className="advanced-connect">
        <summary>Advanced: paste API token</summary>
        <p className="muted">
          Development fallback. Prefer username and password in production.
        </p>
        <form className="composer" onSubmit={onTokenConnect}>
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
          <button className="btn btn-secondary" type="submit" disabled={saving || !session}>
            {saving ? "Connecting…" : "Connect with token"}
          </button>
        </form>
      </details>
    </section>
  );
}
