# Roadmap

Forward-looking milestones and explicitly deferred work. Implemented behavior
is documented in [architecture.md](architecture.md) and related canonical docs.
Historical milestone plans live under [archive/](archive/).

## Current baseline (v0.5)

- Entity + ExternalReference core; entity relationship API and document facade
- Deterministic Paperless reconciliation without auto-delete
- React workbench with home, classify (search/filter/bulk), ingest, reconcile
- Password login → server-side token; PostgreSQL sessions; encrypted job tokens
- Durable async ingestion worker (`atlasdocs worker ingest`) with document
  resolution (`RESOLVING_DOCUMENT`), retryable failures, and spool retention
  until READY
- Document Preview / Download BFF proxies (session-authenticated; no Paperless
  token in the browser)

Design contracts:
[v0.5 ingestion & classification](v0.5-ingestion-classification-spec.md)
· [ADR 0002](adr/0002-v05-session-ingest-security.md)
· [v0.5 product UX refinement](v0.5-product-ux-refinement.md) (home summaries, entity autocomplete, document header).

## Next sprint (v0.6)

**Explore and semantic workbench** — make AtlasDocs the primary exploration and
classification interface while Paperless remains the document authority.

Contract: [v0.6 Explore and Semantic Workbench](v0.6-explore-semantic-workbench.md).

Phases (summary):

| Phase | Focus | Status |
| --- | --- | --- |
| A | Document experience: optional titles (no `atlasdocs:` UUID titles), inline preview | Done |
| B | Semantic API: entity search, type registry, relationship constraints, completeness | Done |
| C | Explore UI: nav, search/filters/sort/pagination, list/grid | Done |
| D | Entity detail foundation and related context | Done |
| E | Home launcher; move Reconcile/Disconnect out of primary nav; validation | Done |

Also in scope for v0.6: document delete/replace via Paperless (failure-safe),
and creation-time semantic completeness states (`empty` / `partial` /
`classified` / `needs_review`) — see [document-lifecycle.md](document-lifecycle.md).

## Explicitly deferred

Not implemented and not implied by current docs (still deferred after v0.6
unless a later milestone picks them up):

- LLMs / automatic classification agents
- MCP servers or tool bridges
- Embeddings / vector search
- Graph visualization as the primary UI (or graph editing)
- Full Perspectives / timeline engines
- Evidence entities; complex multi-user semantic ACLs
- Native notes / freeform annotation store
- Sidecar writers or filesystem sync
- Bulk legacy migration tooling beyond Alembic schema history
- Automatic deletion of semantic data when Paperless removes documents
  (intentional AtlasDocs delete/replace is separate and specified in v0.6)
- Background workers beyond the single ingest worker; webhook ingestion
- Private-deployment-specific scheduling, tunnels, or secret wiring

## Public product rule

AtlasDocs must remain deployable without any particular private infrastructure.
Private deployments consume released images or pins; they do not redefine the
public product surface.
