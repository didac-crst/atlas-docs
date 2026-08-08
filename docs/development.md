# Development

Local setup for AtlasDocs as a public, standalone product. Do not assume any
private deployment host, tunnel, or secret store.

## Prerequisites

- Python 3.13+
- Node.js 22+ (frontend and docs checks)
- Docker (optional; Compose for PostgreSQL + full stack)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# API/BFF tests use SQLite and a mocked Paperless client
pytest

# Frontend unit tests + SPA build (copies into src/atlasdocs/ui/spa)
cd frontend && npm install && npm test && npm run build && cd ..

# Playwright smoke (desktop + mobile) against mocked Paperless
npm install && npx playwright install chromium
npm run test:e2e

# Full stack with PostgreSQL
docker compose up --build
```

Open the workbench at `http://localhost:8080/ui` and paste a Paperless API
token. The token is stored server-side; the browser only keeps an opaque
HttpOnly session cookie.

API-only reload during UI work:

```bash
uvicorn atlasdocs.main:app --reload --port 8080
cd frontend && npm run dev   # proxies /ui/api to :8080
```

## Configuration

| Variable | Meaning |
| --- | --- |
| `DATABASE_HOST` | PostgreSQL host (default `db`) |
| `DATABASE_PORT` | PostgreSQL port (default `5432`) |
| `DATABASE_NAME` | Database name (default `atlasdocs`) |
| `DATABASE_USER` | Database user (default `atlasdocs`) |
| `DATABASE_PASSWORD` | Database password (default `atlasdocs`; must be non-default in production) |
| `PAPERLESS_BASE_URL` | Paperless origin for **server-to-server REST** (may be an internal Docker hostname) |
| `PAPERLESS_PUBLIC_URL` | Optional browser-facing Paperless origin for **Open in Paperless**. Never falls back to `PAPERLESS_BASE_URL`. When unset, the action is hidden/disabled. |
| `PAPERLESS_TIMEOUT_SECONDS` | Upstream timeout |
| `ATLASDOCS_ENV` | **Required.** `development` or `production` (no silent default) |
| `SESSION_SECRET` | Required non-default secret in production |
| `SESSION_SECURE` | Set cookie `Secure` (required true in production) |
| `SESSION_MAX_AGE_SECONDS` | Server-side session expiry (default 8 hours) |
| `SEED_PATH` | Seed YAML path |

The SQLAlchemy URL is built at runtime with `URL.create()` from the split
`DATABASE_*` settings so passwords with special characters are escaped safely.
Production rejects the default `DATABASE_PASSWORD` and default `SESSION_SECRET`.

`ATLASDOCS_ENV` must be set explicitly. Omitting it fails startup.

## Layout

- `src/atlasdocs/` — FastAPI service, domain model, Paperless REST client, UI BFF + SPA assets
- `frontend/` — React + TypeScript + Vite workbench
- `e2e/` — Playwright smoke tests
- `config/seed/` — version-controlled ontology seed data
- `alembic/` — reproducible PostgreSQL migrations
- `docs/` — product documentation
- `scripts/` — docs validation helpers
- `migration/`, `semantic/` — reserved future boundaries

## Seeds and migrations

- Seeds: see [config/README.md](../config/README.md)
- Migrations: `alembic upgrade head` (CI also exercises PostgreSQL migrations)

## Related

- [testing.md](testing.md)
- [frontend.md](frontend.md)
- [paperless-integration.md](paperless-integration.md)
