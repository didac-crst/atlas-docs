# AtlasDocs

AtlasDocs is a reusable semantic document layer built on top of Paperless-ngx.

AtlasDocs adds entities, concepts, typed relationships, provenance, and classification workflows while Paperless-ngx remains authoritative for document storage, OCR, search, previews, and document authorization.

This repository is the public product. It must be deployable independently of Satellite, NAS layouts, Cloudflare, Bitwarden, Raspberry Pi hardware, or any personal infrastructure.

## Status

v0.1 is a vertical slice: verify a Paperless document via its REST API, persist a document reference and typed relationships in PostgreSQL, and return them through a minimal AtlasDocs API.

See `docs/ROADMAP.md` for scope and acceptance tests.

## Quick start (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# API tests use an in-memory SQLite stand-in and a mocked Paperless client
pytest

# Full stack with PostgreSQL
docker compose up --build
```

Example against a reachable Paperless instance:

```bash
curl -X POST http://localhost:8080/documents/184/relationships \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN' \
  -d '{"relationship":"source-country","target":"Germany"}'

curl http://localhost:8080/documents/184 \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN'
```

## Layout

- `src/atlasdocs/` — FastAPI service, domain model, Paperless REST client
- `config/seed/` — version-controlled ontology seed data
- `alembic/` — reproducible PostgreSQL migrations
- `docs/` — product architecture and roadmap
- `migration/`, `semantic/` — reserved future boundaries (not implemented in v0.1)

## Configuration

Environment variables:

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL (default local Postgres) |
| `PAPERLESS_BASE_URL` | Paperless origin, no trailing path |
| `PAPERLESS_TOKEN` | Optional default Paperless token |
| `PAPERLESS_TIMEOUT_SECONDS` | Upstream timeout |
| `SEED_PATH` | Seed YAML path |

Request `Authorization` headers are forwarded to Paperless. When Paperless denies access, AtlasDocs returns 404 and does not disclose document-derived semantics.

Duplicate relationships for the same document, type, and target are rejected with HTTP 409.

The private Satellite deployment lives separately in `satlas-docs` and consumes AtlasDocs through a pinned release or container image.
