import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiError, disconnect, getSession, type SessionInfo } from "./api/client";
import { ConnectPage } from "./pages/ConnectPage";
import { EntityDetailPage } from "./pages/EntityDetailPage";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { IngestPage } from "./pages/IngestPage";
import { ReconcilePage } from "./pages/ReconcilePage";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import markUrl from "./assets/atlas-docs-mark.svg";

export function App() {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();

  const refreshSession = useCallback(async () => {
    const next = await getSession();
    setSession(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await getSession();
        if (!cancelled) setSession(next);
      } catch (err) {
        if (!cancelled) {
          setBootError(err instanceof Error ? err.message : "Failed to load session");
        }
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function onDisconnect() {
    if (!session) return;
    try {
      const next = await disconnect(session.csrf_token);
      setSession(next);
      navigate("/connect");
    } catch (err) {
      setBootError(err instanceof ApiError ? err.message : "Disconnect failed");
    }
  }

  if (busy) {
    return (
      <div className="main" role="status" aria-live="polite">
        Loading AtlasDocs…
      </div>
    );
  }

  if (bootError && !session) {
    return (
      <div className="main">
        <div className="banner banner-error" role="alert">
          {bootError}
        </div>
      </div>
    );
  }

  const authenticated = Boolean(session?.authenticated);
  const path = location.pathname;

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link to={authenticated ? "/" : "/connect"} className="brand-block">
          <img src={markUrl} alt="" width={40} height={40} />
          <strong>AtlasDocs</strong>
        </Link>
        <nav className="site-nav" aria-label="Primary">
          {authenticated ? (
            <>
              <Link to="/" aria-current={path === "/" ? "page" : undefined}>
                Home
              </Link>
              <Link
                to="/explore"
                aria-current={path.startsWith("/explore") ? "page" : undefined}
              >
                Explore
              </Link>
              <Link
                to="/classify"
                aria-current={path.startsWith("/classify") || path.startsWith("/documents") ? "page" : undefined}
              >
                Classify
              </Link>
              <Link
                to="/ingest"
                aria-current={path.startsWith("/ingest") ? "page" : undefined}
              >
                Ingest
              </Link>
              <Link
                to="/reconcile"
                aria-current={path.startsWith("/reconcile") ? "page" : undefined}
              >
                Reconcile
              </Link>
              <button type="button" onClick={onDisconnect}>
                Disconnect
              </button>
            </>
          ) : (
            <Link to="/connect" aria-current="page">
              Connect
            </Link>
          )}
        </nav>
      </header>
      <main className="main">
        {bootError && session ? (
          <div className="banner banner-error" role="alert">
            {bootError}
          </div>
        ) : null}
        <Routes>
          <Route
            path="/connect"
            element={
              <ConnectPage
                session={session}
                onConnected={async () => {
                  await refreshSession();
                  navigate("/");
                }}
              />
            }
          />
          <Route
            path="/reconcile"
            element={
              authenticated && session ? (
                <ReconcilePage session={session} onSession={setSession} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/ingest"
            element={
              authenticated && session ? (
                <IngestPage session={session} onSession={setSession} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/explore"
            element={
              authenticated && session ? (
                <ExplorePage session={session} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/entities/:entityId"
            element={
              authenticated && session ? (
                <EntityDetailPage session={session} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/classify"
            element={
              authenticated && session ? (
                <WorkbenchPage session={session} onSession={setSession} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/documents/:paperlessId"
            element={
              authenticated && session ? (
                <WorkbenchPage session={session} onSession={setSession} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route
            path="/"
            element={
              authenticated && session ? (
                <HomePage session={session} />
              ) : (
                <Navigate to="/connect" replace />
              )
            }
          />
          <Route path="*" element={<Navigate to={authenticated ? "/" : "/connect"} replace />} />
        </Routes>
      </main>
    </div>
  );
}
