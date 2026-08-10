import { FormEvent, useState } from "react";
import { connect, login, type SessionInfo } from "../api/client";
import { PageLayout } from "../components/PageLayout";
import { ProductIdentity } from "../components/ProductIdentity";

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
      <PageLayout width="narrow">
      <section className="panel connect-panel" aria-labelledby="connect-title">
        <ProductIdentity titleId="connect-title" size="md" />
        <p className="muted">
          You are signed in. Use Disconnect in the account menu to sign out, or sign in again
          below with another identity.
        </p>
        <details className="advanced-connect">
          <summary>Sign in again</summary>
          <p className="muted">Replace the stored credentials for this AtlasDocs session.</p>
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
      </PageLayout>
    );
  }

  return (
    <PageLayout width="narrow">
    <section className="panel connect-panel" aria-labelledby="connect-title">
      <ProductIdentity titleId="connect-title" size="lg" />
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
      <p className="connect-auth-note muted">Secure authentication powered by Paperless.</p>

      <details className="advanced-connect">
        <summary>Advanced: paste API token</summary>
        <p className="muted">
          Development fallback. Prefer username and password in production.
        </p>
        <form className="composer" onSubmit={onTokenConnect}>
          <div className="field">
            <label htmlFor="paperless-token">API token</label>
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
    </PageLayout>
  );
}
