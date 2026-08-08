# Roadmap

Forward-looking milestones and explicitly deferred work. Implemented behavior
is documented in [architecture.md](architecture.md) and related canonical docs.
Historical milestone plans live under [archive/](archive/).

## Current baseline (v0.4)

- Entity + ExternalReference core (v0.3 schema)
- Entity relationship API and document facade
- Deterministic Paperless reconciliation without auto-delete
- React + TypeScript + Vite classification workbench with BFF session/CSRF

## Next (v0.5 candidates)

Exact scope is not locked. Sensible candidates (any subset):

- Hardening and operator ergonomics (reconcile UX, clearer orphan workflows)
- Broader seed / relationship catalog without new infrastructure
- Documentation and release packaging polish
- Optional background-friendly reconcile *design* (implementation may stay deferred)

Do not treat this list as committed delivery.

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
- Background workers and webhook ingestion (ReconcileService is ready to call)
- Private-deployment-specific scheduling, tunnels, or secret wiring

## Public product rule

AtlasDocs must remain deployable without any particular private infrastructure.
Private deployments consume released images or pins; they do not redefine the
public product surface.
