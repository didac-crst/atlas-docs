# Roadmap

Forward-looking milestones and explicitly deferred work. Implemented behavior
is documented in [architecture.md](architecture.md) and related canonical docs.
Historical milestone plans live under [archive/](archive/).

## Current baseline (v0.5)

- Entity + ExternalReference core; entity relationship API and document facade
- Deterministic Paperless reconciliation without auto-delete
- React workbench with home, classify (search/filter/bulk), ingest, reconcile
- Password login → server-side token; PostgreSQL sessions; encrypted job tokens
- Durable async ingestion worker (`atlasdocs worker ingest`)

Design contracts:
[v0.5 ingestion & classification](v0.5-ingestion-classification-spec.md)
· [ADR 0002](adr/0002-v05-session-ingest-security.md)
· [v0.5 product UX refinement](v0.5-product-ux-refinement.md) (home summaries, entity autocomplete, document header).

## Explicitly deferred

Not implemented and not implied by current docs:

- LLMs / automatic classification agents
- MCP servers or tool bridges
- Embeddings / vector search
- Graph visualization as the primary UI
- Native notes / freeform annotation store
- Sidecar writers or filesystem sync
- Evidence / case management product surface
- Bulk legacy migration tooling beyond Alembic schema history
- Automatic deletion of semantic data when Paperless removes documents
- Background workers beyond the single v0.5 ingest worker; webhook ingestion
- Private-deployment-specific scheduling, tunnels, or secret wiring

## Public product rule

AtlasDocs must remain deployable without any particular private infrastructure.
Private deployments consume released images or pins; they do not redefine the
public product surface.
