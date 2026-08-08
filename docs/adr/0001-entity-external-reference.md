# ADR 0001: Entity + ExternalReference

- **Status:** Accepted (implemented in v0.3; Alembic `0002_v03_entity_external_reference`)
- **Date:** 2026

## Context

Early AtlasDocs bound Paperless documents through a `document_references`
table and targeted concepts via `relationships.target_concept_id`. That model
could not express document↔document edges, general entity identity, or
non-Paperless external systems cleanly.

## Decision

1. Every semantic object is an `Entity` (`document` | `concept` for now).
2. Upstream ids bind through `ExternalReference(system, external_id)` with
   `UNIQUE(system, external_id)`. Paperless uses `system=paperless`.
3. Concepts are entities: `concepts.id` is the same UUID as `entities.id`.
4. Relationships are entity→entity (`target_entity_id`), with relationship-type
   directionality and optional inverse pairs.
5. Origin vocabulary stores `deterministic-rule` (accept legacy `"rule"` on write).

## Consequences

- `/documents/{paperless_id}` remains a facade; `/entities/{uuid}` is the general API.
- Reconciliation creates missing document entities + Paperless external references
  and never auto-deletes.
- Person/Organization are concept entities, not separate entity types (for now).

## History

Full expand/backfill plan: [archive/v0.3/migration-plan.md](../archive/v0.3/migration-plan.md).
Planning notes: [archive/v0.3/roadmap.md](../archive/v0.3/roadmap.md).
