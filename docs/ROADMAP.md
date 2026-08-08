# AtlasDocs v0.1 Roadmap — Vertical Slice

> Historical planning note for the v0.1 API slice. The classification workbench
> delivered in v0.2 lives in `src/atlasdocs/ui/` and is described in
> `docs/v0.2-ui-design-proposal.md`.

## Goal

Prove that AtlasDocs can sit next to Paperless-ngx and add one typed relationship cleanly.

v0.1 is a vertical slice, not a semantic platform. It must produce architectural evidence for the acceptance scenario below. Do not expand into Cases, Organizations, Persons, graph databases, LLM features, UI, migration tooling, or deployment-specific infrastructure.

## Acceptance scenario

```text
Paperless document 184
        -> Paperless REST API
        -> AtlasDocs document reference/entity
        -> source-country: Germany
        -> document-type: Payslip
        -> PostgreSQL
        -> AtlasDocs REST API response
```

The complete flow must:

1. Verify the Paperless document exists through the supported REST API.
2. Persist an AtlasDocs document reference and typed relationships.
3. Return those relationships through the AtlasDocs API.

Minimal API evidence (exact paths may be refined; behavior must stay this small):

```bash
curl -X POST http://atlasdocs.local/documents/184/relationships \
  -H 'Content-Type: application/json' \
  -d '{"relationship":"source-country","target":"Germany"}'

curl http://atlasdocs.local/documents/184
```

Expected semantic result:

```json
{
  "paperless_document_id": 184,
  "relationships": [
    {
      "type": "source-country",
      "target": "Germany",
      "origin": "manual",
      "status": "confirmed"
    }
  ]
}
```

## Current repository state

Inspected files as of this roadmap:

| Path | Role |
| --- | --- |
| `README.md` | Public-product framing; correctly separates Satellite deployment |
| `docs/atlasdocs-spec.md` | Broader Phase 1 architecture; supersedes some details for v0.1 scope below |
| `docs/ui-ux-design-spec.md` | Future UI guidance; out of scope for v0.1 implementation |
| `config/README.md` | Placeholder for version-controlled seed/config |
| `migration/README.md` | Placeholder; deferred |
| `semantic/README.md` | Placeholder; deferred |
| `.coderabbit.yaml` | Review tooling only |
| `.gitignore` | Ignores env files |

There is no application code, migrations, Dockerfile, Compose file, or tests yet.

### What does not belong in the public product

Already removed or correctly excluded:

- Satellite, NAS layouts, Cloudflare, Bitwarden, Raspberry Pi, Supernova
- Paperless deployment compose and host-specific configuration
- Infrastructure opinion docs and burst-compute notes

Keep out of v0.1 product code and product assumptions:

- `_tmp/` working notes (local scratch; do not ship as product surface)
- Any credentials, document contents, or deployment URLs
- Direct Paperless PostgreSQL/filesystem access
- Frontend and UI packages (even though `docs/ui-ux-design-spec.md` may remain as future guidance)
- Migration CLI under `migration/` until a later phase

### Spec conflicts resolved for v0.1

`docs/atlasdocs-spec.md` describes a wider Phase 1 than this slice. For v0.1, the vertical-slice constraints win:

| Topic | Spec / scaffold | v0.1 decision |
| --- | --- | --- |
| Seed concepts | Document, Person, Organization, Country, Case | Only `country` and `document-type` concepts |
| Relationship types | concerns, issued_by, source_country, jurisdiction, belongs_to, document_type | Only `source-country`, `document-type`, `concerns` |
| Provenance origin | manual \| legacy-path \| deterministic-rule \| external-automation | manual \| rule \| import \| llm |
| Provenance fields | origin, status, created_by, created_at | origin, status, created_at (no created_by yet) |
| API shape | `/documents/{id}/semantics` plus ontology listing routes | Minimal document get + relationship create sufficient for the scenario |
| Cases / subtype tables | Mentioned as initial concepts | Deferred |

Update or annotate `docs/atlasdocs-spec.md` in a later docs pass so it does not contradict this roadmap; do not expand implementation to match the wider spec in v0.1.

## Unresolved assumptions

These must be decided during implementation without widening scope:

1. **Service layout** — Prefer a conventional Python package (for example `src/atlasdocs/` or `app/`) rather than filling the empty `semantic/` placeholder with a full application tree. Keep `semantic/` and `migration/` as deferred boundaries unless the package clearly belongs there.
2. **HTTP framework** — FastAPI is the default candidate for a typed minimal REST API; any equivalent is fine if tests and OpenAPI remain simple.
3. **ORM / migrations** — SQLAlchemy + Alembic (or equivalent) for reproducible PostgreSQL migrations.
4. **Authorization boundary** — v0.1 must check Paperless document access before returning or mutating document-derived semantics, but must not build sophisticated auth. Pass through a Paperless token or explicit user context to the Paperless API; deny when Paperless denies. Exact header/env contract is an implementation detail.
5. **Paperless client** — Thin HTTP client over the supported REST API (`document_exists` / `get_document` / access check). Mockable in tests. No webhooks in v0.1.
6. **Relationship uniqueness** — Duplicate of the same `(document, relationship_type, target_concept)` must be handled deterministically (reject or idempotent no-op; pick one and test it).
7. **Target resolution** — POST body `target` resolves to a Concept by stable code/name within the ontology implied by the relationship type.
8. **Compose** — Add development Compose only if needed to run PostgreSQL (and optionally a mock or local Paperless) reproducibly. No Satellite/NAS assumptions.
9. **Hostname** — `atlasdocs.local` is illustrative; local bind host/port via env is enough.

## v0.1 scope

### Include

- Conventional Python service skeleton
- PostgreSQL persistence
- Reproducible schema migrations
- Domain model:
  - `Entity`
  - `DocumentReference` with external `paperless_document_id` (never the AtlasDocs primary key)
  - `Ontology`
  - `Concept`
  - `RelationshipType`
  - `Relationship`
  - Minimal provenance: `origin`, `status`, `created_at`
- Tiny seed data (version-controlled under `config/`):

  ```text
  Ontology: country
    France
    Germany
    Spain

  Ontology: document-type
    Payslip
    Invoice

  Relationship types:
    source-country
    document-type
    concerns
  ```

- `PaperlessClient` using the supported REST API only
- Minimal REST API sufficient for create + retrieve of document relationships
- Validation and automated tests
- Dockerfile
- Development Compose only if required for local PostgreSQL/service boot

### Explicitly defer

Frontend, ontology editor, graph visualization, LLMs, summaries, embeddings, MCP, backlog/legacy migration, Supernova, burst compute, sync automation, webhooks, sophisticated authentication integration, Case/Organization/Person/subtype tables, graph database, validation DSL, cardinality framework, generic metadata systems, confidence scoring.

Do not create generic infrastructure unless the acceptance scenario requires it.

## Implementation sequence

1. **Skeleton** — Python project metadata, package layout, settings via environment, health endpoint optional.
2. **Database** — PostgreSQL connection, migrations for the v0.1 tables only, seed loader for ontologies/concepts/relationship types.
3. **Domain + repository** — Create/get document reference by Paperless ID; create/list relationships with provenance defaults (`origin=manual`, `status=confirmed` for the manual API path).
4. **PaperlessClient** — Existence and access checks; map HTTP failures to clear API errors; never touch Paperless DB.
5. **REST API** — POST relationship; GET document semantics by Paperless ID; validate targets and duplicates.
6. **Container** — Dockerfile; optional Compose for Postgres + app.
7. **Tests** — Acceptance suite below with Paperless mocked.

## Out of scope reminders

- No Satellite, NAS, Cloudflare, Bitwarden, Raspberry Pi, or Supernova references in code or runtime assumptions
- No Paperless internal table access
- No UI implementation in v0.1
- No expansion of `docs/atlasdocs-spec.md` Phase 1 breadth into this slice

## Acceptance tests

v0.1 is done only when these pass:

1. **Reproducible database setup** — Fresh PostgreSQL + migrations yield the expected schema; seed load is idempotent and creates the country/document-type concepts and the three relationship types.
2. **Paperless document existence verification** — Creating or reading semantics for document `184` calls the Paperless client; a missing document yields a clear not-found (or equivalent) response without creating orphan semantics.
3. **Document reference creation** — A successful flow persists an AtlasDocs entity/document reference whose primary key is not `184`, while storing `paperless_document_id=184`.
4. **Ontology and seed loading** — Germany, France, Spain, Payslip, and Invoice are available as concepts; relationship types `source-country`, `document-type`, and `concerns` exist.
5. **Relationship creation and retrieval** — POST `source-country` → Germany for document `184`, then GET returns that relationship with `origin` and `status`.
6. **Duplicate relationship handling** — Repeating the same relationship for the same document and target is deterministic (documented reject or idempotent success) and covered by a test.
7. **Invalid concept/target handling** — Unknown relationship type or unknown target (for example `Atlantis`) is rejected without writing a relationship.
8. **Paperless API failure handling** — Timeouts, 5xx, and auth failures from Paperless surface as controlled AtlasDocs errors; no partial silent success.
9. **Authorization boundary behavior** — When Paperless denies access to document `184`, AtlasDocs does not return relationships, metadata, or existence details derived from that document.
10. **No direct Paperless database access** — Adapter and codebase use only the supported REST API (or test doubles); no Paperless SQL, internal table names, or filesystem path coupling.
