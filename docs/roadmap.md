# Roadmap

Forward-looking milestones and explicitly deferred work. Implemented behavior
is documented in [architecture.md](architecture.md) and related canonical docs.
Historical milestone plans live under [archive/](archive/).

## Current baseline (v0.6)

- Entity + ExternalReference core; entity relationship API and document facade
- Deterministic Paperless reconciliation without auto-delete
- React workbench: Home | Explore | Classify | Ingest; Account menu for
  Reconcile / Disconnect
- Password login → server-side token; PostgreSQL sessions; encrypted job tokens
- Durable async ingestion worker with document resolution and spool retention
- Document Preview / Download BFF proxies (session-authenticated; no Paperless
  token in the browser)
- Explore (documents and concepts), entity detail with backlinks, semantic
  completeness, document delete/replace with tombstones and replacement history

Design contracts:
[v0.6 Explore and Semantic Workbench](v0.6-explore-semantic-workbench.md)
· [document lifecycle](document-lifecycle.md)
· [v0.5 ingestion & classification](v0.5-ingestion-classification-spec.md)
· [ADR 0002](adr/0002-v05-session-ingest-security.md).

## Next sprint (v0.7)

**Product experience and entity lifecycle** — make AtlasDocs feel like an
entity-centered semantic application rather than a document queue with semantic
fields. Establish lifecycle categories and navigation foundations without the
full future knowledge graph.

Contracts:

- [Product experience specification](product-experience-spec.md) (long-term UX /
  lifecycle model)
- [v0.7 Product Experience and Entity Lifecycle](v0.7-product-experience.md)
  (sprint scope, order, tests, acceptance)

Focus areas (summary): lifecycle categories (Evidence / Master Data /
Organizational); Explore Documents | Knowledge with canonical cards; evidence
trash/restore/purge via Paperless; Master Data archive/merge safeguards;
collection-level reconciliation; version-aware Paperless downloads through the
BFF (`original` / `version` — Paperless version ids, not Atlas UUIDs).

## Explicitly deferred

Not implemented and not implied by current docs (still deferred after v0.7
unless a later milestone picks them up):

- LLMs / automatic classification agents
- MCP servers or tool bridges
- Embeddings / vector search
- Graph visualization as the primary UI (or graph editing)
- Full Perspectives / timeline engines
- Evidence entity model beyond the lifecycle foundation
- Complex multi-user workspace ACLs / personal vs shared knowledge layers
- Native notes / freeform annotation store
- Sidecar writers or filesystem sync
- Bulk legacy migration tooling beyond Alembic schema history
- Automatic deletion of semantic data when Paperless removes documents
  (intentional AtlasDocs delete/replace is separate and specified in v0.6+)
- Background workers beyond the single ingest worker; webhook ingestion
- Private-deployment-specific scheduling, tunnels, or secret wiring
- Full ontology editor; Supernova workloads

## Public product rule

AtlasDocs must remain deployable without any particular private infrastructure.
Private deployments consume released images or pins; they do not redefine the
public product surface.
