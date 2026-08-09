import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiError, disconnect, getSession, type SessionInfo } from "./api/client";
import { AccountMenu } from "./components/AccountMenu";
import { AppFooter } from "./components/AppFooter";
import { AtlasDocsWordmark } from "./components/AtlasDocsWordmark";
import { ProductIdentity } from "./components/ProductIdentity";
import { AboutPage } from "./pages/AboutPage";
import { ConnectPage } from "./pages/ConnectPage";
import { EntityDetailPage } from "./pages/EntityDetailPage";
import { ExplorePage } from "./pages/ExplorePage";
import { HomePage } from "./pages/HomePage";
import { IngestPage } from "./pages/IngestPage";
import { ReconcilePage } from "./pages/ReconcilePage";
import { DocumentDeepLink, WorkbenchPage } from "./pages/WorkbenchPage";
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
      <div className="main boot-screen" role="status" aria-live="polite">
        <ProductIdentity size="lg" status="Connecting…" />
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
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <header className="site-header">
        <Link to={authenticated ? "/" : "/connect"} className="brand-block">
          <img src={markUrl} alt="" width={40} height={40} />
          <AtlasDocsWordmark as="strong" />
        </Link>
        <div className="site-header-end">
          <nav className="site-nav" aria-label="Primary">
            {authenticated ? (
              <>
                <Link to="/" aria-current={path === "/" ? "page" : undefined}>
                  Home
                </Link>
                <Link
                  to="/explore"
                  aria-current={
                    path.startsWith("/explore") || path.startsWith("/entities/")
                      ? "page"
                      : undefined
                  }
                >
                  Explore
                </Link>
                <Link
                  to="/classify"
                  aria-current={
                    path.startsWith("/classify") || path.startsWith("/documents")
                      ? "page"
                      : undefined
                  }
                >
                  Classify
                </Link>
                <Link
                  to="/ingest"
                  aria-current={path.startsWith("/ingest") ? "page" : undefined}
                >
                  Ingest
                </Link>
              </>
            ) : (
              <Link to="/connect" aria-current={path.startsWith("/connect") ? "page" : undefined}>
                Sign in
              </Link>
            )}
          </nav>
          {authenticated ? (
            <AccountMenu
              usernameLabel={session?.username_label}
              onDisconnect={onDisconnect}
            />
          ) : null}
        </div>
      </header>
      <main id="main-content" className="main" tabIndex={-1}>
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
          <Route path="/about" element={<AboutPage />} />
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
                <EntityDetailPage session={session} onSession={setSession} />
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
              authenticated && session ? <DocumentDeepLink /> : <Navigate to="/connect" replace />
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
      <AppFooter />
    </div>
  );
}
