# AtlasDocs API

Canonical HTTP surface for the current release. Runtime OpenAPI is available
from a running server at `/docs` and `/openapi.json`.

This document is hand-maintained from the FastAPI routers. It does not invent
endpoints.

## Auth models

| Client | Auth |
| --- | --- |
| JSON API (`/documents`, `/entities`, …) | `Authorization: Token …` or `Bearer …` on every request |
| Browser workbench | HttpOnly session + `X-CSRF-Token` on mutations via `/ui/api/*` |

Paperless tokens never appear in browser-visible responses. See
[frontend.md](frontend.md) and [paperless-integration.md](paperless-integration.md).

Denial or missing Paperless documents map to **404** (no semantic leak).
Duplicate relationships return **409**. Validation errors return **422**.

## Programmatic JSON API

Router: `src/atlasdocs/api/routes.py`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/documents` | List with `unclassified=true` and/or `classification`, `q`, `sort`, `order`, `page`, `completeness` |
| POST | `/documents/bulk-relationships` | Bulk assign (per-doc Paperless authz) |
| GET | `/documents/{paperless_document_id}` | Document facade + relationships |
| POST | `/documents/{paperless_document_id}/relationships` | Add relationship (document facade) |
| POST | `/ingest` | Multipart upload → durable job |
| GET | `/ingest/jobs` | Jobs for the calling token fingerprint |
| GET | `/ingest/jobs/{job_id}` | Job status |
| GET | `/explore` | Entity-oriented Explore page (`mode`, filters, sort, pagination) |
| GET | `/entity-types` | Entity type registry (display metadata) |
| GET | `/entities/search` | Entity search / autocomplete |
| GET | `/entities/{entity_id}` | Entity detail + outgoing relationships |
| GET | `/entities/{entity_id}/relationships` | Outgoing relationships |
| POST | `/entities/{entity_id}/relationships` | Create edge |
| DELETE | `/relationships/{relationship_id}` | Delete edge (+ companions) |
| GET | `/relationship-types` | Relationship type catalog (incl. source/target entity types) |
| GET | `/ontologies/{ontology_code}/concepts` | Concepts in an ontology |
| POST | `/reconcile` | Reconciliation (`dry_run`, optional `limit`) |

### Creating relationships

Provide **exactly one** target:

```json
{"relationship": "source-country", "target": "germany"}
{"relationship": "derived-from", "target_paperless_id": 185}
{"relationship": "related-to", "target_entity_id": "<uuid>"}
```

Optional fields: `origin`, `status` (defaults `manual` / `confirmed`).

Document facade example:

```bash
curl -X POST http://localhost:8080/documents/184/relationships \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN' \
  -d '{"relationship":"source-country","target":"Germany"}'

curl 'http://localhost:8080/documents?unclassified=true&page=1&page_size=25' \
  -H 'Authorization: Token YOUR_PAPERLESS_TOKEN'
```

### Document response notes

- `open_url` is set only when `PAPERLESS_PUBLIC_URL` is configured; it never
  embeds credentials or uses `PAPERLESS_BASE_URL`.

## UI BFF

Router: `src/atlasdocs/ui/routes.py`, prefix `/ui/api`.

Same semantic operations as the workbench needs, session-authenticated. Full
table: [frontend.md](frontend.md#bff-endpoints).

## Schemas

Pydantic models live in `src/atlasdocs/api/schemas.py`. Prefer `/openapi.json`
for field-level detail when implementing clients.
