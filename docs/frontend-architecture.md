# AtlasDocs Frontend Architecture

## Overview

The classification workbench is a thin React + TypeScript + Vite SPA served
same-origin from the AtlasDocs FastAPI container under `/ui`.

FastAPI remains authoritative for sessions, CSRF, Paperless authorization,
semantic persistence, and the programmatic REST facade (`/documents`,
`/entities`, `/reconcile`, …).

Jinja server-rendered interaction was retired in v0.4. There is no production
Jinja fallback for `/ui`.

## Security boundary

- Paperless tokens are accepted only by `POST /ui/api/connect` and stored in
  the server-side HttpOnly session. Tokens never appear in HTML, JavaScript,
  browser storage, or API responses.
- Mutating BFF calls require the session cookie and `X-CSRF-Token`. CSRF rotates
  after successful mutations.
- Unauthorized or inaccessible Paperless documents return 404 from the BFF with
  no semantic leakage (same rule as the Authorization-header API).

## Request flow

```text
Browser (SPA)  --cookie + CSRF-->  /ui/api/* (BFF)
                                      |
                                      v
                               DocumentService / ReconcileService
                                      |
                                      v
                               Paperless REST (server-side token)
```

Programmatic clients continue to use `/documents` and `/entities` with an
`Authorization` header; the SPA does not call those paths with the token.

## BFF endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/ui/api/session` | `{authenticated, csrf_token}` |
| POST | `/ui/api/connect` | Store Paperless token server-side |
| POST | `/ui/api/disconnect` | Invalidate session |
| GET | `/ui/api/documents` | Unclassified queue |
| GET | `/ui/api/documents/{id}` | Document detail + relationships |
| POST | `/ui/api/documents/{id}/relationships` | Add relationship |
| DELETE | `/ui/api/relationships/{id}` | Remove relationship |
| GET | `/ui/api/relationship-types` | Typed relationship catalog |
| GET | `/ui/api/concepts` | Concept autocomplete (`q`, `ontology`) |
| POST | `/ui/api/reconcile` | Dry-run / apply reconciliation |

## Serving the SPA

- Vite builds with `base: '/ui/'` into `src/atlasdocs/ui/spa` (copied in Docker).
- FastAPI serves hashed assets from `/ui/assets/*` and returns `index.html` for
  client routes (`/ui`, `/ui/connect`, `/ui/documents/:id`, `/ui/reconcile`).
- `/ui/api/*` is never shadowed by the SPA fallback.

## Frontend package

Located in `frontend/`:

- React + TypeScript + Vite
- `react-router-dom` for workbench routes
- `lucide-react` for labeled icons
- Design tokens from `docs/atlasdocs-ui-brand-direction.md`
- Product components: `DocumentQueue`, `SemanticDocumentDetail`,
  `RelationshipComposer`, `EntityReference`, `ReconcilePanel`

No Redux, Next.js, graph visualization, LLMs, or MCP.

## Local development

```bash
# API (serves built SPA if present)
pip install -e '.[dev]'
uvicorn atlasdocs.main:app --reload --port 8080

# Frontend (Vite proxies /ui/api to :8080 during `npm run dev`)
cd frontend && npm install && npm run dev
```

Production images run a multi-stage Docker build: Node builds the SPA, then the
Python image copies `dist` and serves it.

## Tests

- Vitest unit tests in `frontend/`
- Pytest BFF/API tests in `tests/`
- Playwright smoke tests in `e2e/` (desktop + mobile viewports)
