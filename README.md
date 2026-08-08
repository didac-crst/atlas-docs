# AtlasDocs

<p align="center">
  <img src="assets/atlas-docs-wordmark.svg" alt="AtlasDocs" width="480">
</p>

AtlasDocs is a reusable semantic document layer built on top of Paperless-ngx.

AtlasDocs adds entities, concepts, typed relationships, provenance, and classification workflows while Paperless-ngx remains authoritative for document storage, OCR, search, previews, and document authorization.

This repository is the public product. It must be deployable independently of Satellite, NAS layouts, Cloudflare, Bitwarden, Raspberry Pi hardware, or any personal infrastructure.

## Status

v0.3 generalizes persistence to Entity + ExternalReference (concepts as
entities, entity-to-entity relationships) while keeping the
`/documents/{paperless_id}` API as a compatibility facade. See
`docs/architecture-assessment.md`, `docs/v0.3-roadmap.md`, and
`docs/v0.3-migration-plan.md`.

v0.2 adds a small server-rendered classification workbench on the v0.1 API: needs-classification queue, document detail, and relationship create/delete.

See also `docs/ROADMAP.md` and `docs/v0.2-ui-design-proposal.md`.

## Quick start (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# API/UI tests use SQLite and a mocked Paperless client
pytest

# Full stack with PostgreSQL
docker compose up --build
```

Open the workbench at `http://localhost:8080/ui` and paste a Paperless API token. The token is stored server-side; the browser only keeps an opaque HttpOnly session cookie.

Example JSON API:

```bash
curl -X POST http://localhost:8080/documents/184/relationships \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN' \
  -d '{"relationship":"source-country","target":"Germany"}'

curl 'http://localhost:8080/documents?unclassified=true&page=1&page_size=25' \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN'
```

## Layout

- `src/atlasdocs/` — FastAPI service, domain model, Paperless REST client, Jinja UI
- `config/seed/` — version-controlled ontology seed data
- `alembic/` — reproducible PostgreSQL migrations
- `docs/` — product architecture and roadmap
- `.github/workflows/ci.yml` — tests (including Postgres migration), container build, and gated GHCR publish
- `migration/`, `semantic/` — reserved future boundaries

## Configuration

Environment variables:

| Variable | Meaning |
| --- | --- |
| `DATABASE_HOST` | PostgreSQL host (default `db`) |
| `DATABASE_PORT` | PostgreSQL port (default `5432`) |
| `DATABASE_NAME` | Database name (default `atlasdocs`) |
| `DATABASE_USER` | Database user (default `atlasdocs`) |
| `DATABASE_PASSWORD` | Database password (default `atlasdocs`; must be non-default in production) |
| `PAPERLESS_BASE_URL` | Paperless origin, no trailing path |
| `PAPERLESS_TIMEOUT_SECONDS` | Upstream timeout |
| `ATLASDOCS_ENV` | **Required.** `development` or `production` (no silent default) |
| `SESSION_SECRET` | Required non-default secret in production |
| `SESSION_SECURE` | Set cookie `Secure` (required true in production) |
| `SESSION_MAX_AGE_SECONDS` | Server-side session expiry (default 8 hours) |
| `SEED_PATH` | Seed YAML path |

The SQLAlchemy URL is built at runtime with `URL.create()` from the split `DATABASE_*` settings so passwords with special characters are escaped safely. Production should not rely on a single `DATABASE_URL` with embedded credentials. Production also rejects the default `DATABASE_PASSWORD` and default `SESSION_SECRET`.

`ATLASDOCS_ENV` must be set explicitly. Omitting it fails startup instead of falling back to development defaults.

The UI keeps Paperless tokens in a server-side session. The browser only receives an opaque HttpOnly session id (`SameSite=Lax`). Document JSON endpoints require an `Authorization` header on every request and forward it to Paperless. There is no service-token fallback for document access. When Paperless denies access, AtlasDocs returns 404 and does not disclose document-derived semantics.

Unclassified listing fetches one Paperless page (`page_size` default/max 25) and filters with a single AtlasDocs query for confirmed relationships.

Duplicate relationships for the same document, type, and target are rejected with HTTP 409. Browser mutations use CSRF-protected POST forms.

The private Satellite deployment lives separately in `satlas-docs` and consumes AtlasDocs through a pinned release or container image.

## Brand assets

- `assets/atlas-docs-wordmark.svg` — README and full-width product identity.
- `assets/atlas-docs-mark.svg` — compact icon, favicon, and app-icon contexts.
