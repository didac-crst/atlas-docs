# AtlasDocs Architecture Assessment (post-v0.2)

## Status

Assessment only. No schema, API, or UI changes are authorized by this document.
Implementation, tests, and a concrete migration plan wait for approval of this
assessment and of `docs/v0.3-roadmap.md`.

Compared against:

- `_tmp/atlasdocs-core-architecture-v01.md` (strategic invariants)
- `docs/ROADMAP.md` (v0.1 vertical-slice decisions)
- `docs/v0.2-ui-design-proposal.md` (delivered workbench)
- current `main` (`20274b0` / merge of PR #2)

## Verdict

v0.1–v0.2 successfully proved the Paperless-adjacent vertical slice: REST-only
Paperless access, UUID-backed internal rows, typed relationships with minimal
provenance, authorization boundary, and a classification workbench.

They did **not** yet implement the entity-first core described in the
architecture specification. The largest structural debt is that Paperless
identity and concept targets are still first-class schema shapes, not instances
of a generic `Entity` + `ExternalReference` + entity-to-entity relationship
model.

That debt is expected given the explicit v0.1 narrowing in `docs/ROADMAP.md`.
v0.3 should close the identity gap without breaking the existing
`/documents/{paperless_id}` API.

## What already aligns

| Invariant | Current evidence |
| --- | --- |
| Paperless owns documents | No PDF/OCR storage; viewer links out to Paperless |
| AtlasDocs owns semantics | Relationships and seed ontologies live in AtlasDocs PostgreSQL |
| AtlasDocs UUIDs are internal identities | `entities.id` and `document_references.id` are UUIDs; Paperless id is not the PK |
| Paperless integration via APIs only | `PaperlessClient` over REST; no Paperless SQL/paths |
| No unauthorized Paperless disclosure | Token required; auth denial maps to not-found semantics |
| Minimal provenance on relationships | `origin`, `status`, `created_at` on `relationships` |
| Evidence not prematurely required | Schema does not force a single supporting document |
| Public product vs Satlas | Compose/Dockerfile generic; Satlas stays on a pinned image outside this repo |
| UI auth boundary | Opaque HttpOnly session; token never in cookie/HTML/JS |

## Gap analysis

### 1. Generic Entity identity

**Architecture:** Every meaningful graph participant is an AtlasDocs `Entity`
with an AtlasDocs-owned UUID.

**Current:** An `entities` table exists, but it is only a thin wrapper created
when a `DocumentReference` is first needed. There is no entity type, no
lifecycle beyond `created_at`, and no path to create an entity that is not a
Paperless-backed document.

**Gap:** Entity is present as a table, not yet as the product’s primary
identity abstraction.

### 2. ExternalReference instead of Paperless-specific identity

**Architecture:**

```text
Entity: UUID
ExternalReference:
  system: paperless
  external_id: 184
```

**Current:** `document_references.paperless_document_id` is a dedicated integer
column. The public API and UI are keyed exclusively by that Paperless id
(`GET/POST /documents/{paperless_document_id}`, unclassified listing, Jinja
routes).

**What is correct:** Paperless ids are not AtlasDocs primary keys.

**Gap:** External identity is Paperless-shaped in schema and service code, so
adding another system (or AtlasDocs-native content) requires a new table rather
than another `ExternalReference` row.

### 3. Entity types

**Architecture:** Document, Concept, Person, Organization, Country, NativeNote
(and similar) participate as typed entities.

**Current:**

- Documents are `Entity` + `DocumentReference`.
- Concepts are standalone `concepts` rows under `ontologies`; they are **not**
  entities and cannot be relationship sources.
- Person / Organization / Country / NativeNote entity types do not exist.
  Country and document-type values exist only as ontology concepts.

**Gap:** The graph cannot treat concepts (or future people/orgs/notes) as
first-class entities with the same identity rules as documents.

### 4. N:N directed / symmetric relationships

**Architecture:** Relationships are typed, directed or symmetric, and N:N.
They must not assume parent/child or one-to-one structure. Targets may be any
entity (document↔document, document↔person, note↔concept, etc.).

**Current:** `relationships` are always:

```text
source_entity (document) --type--> target_concept
```

Uniqueness is `(source_entity_id, relationship_type_id, target_concept_id)`.
There is no `target_entity_id`, no symmetry flag, and no directed/symmetric
metadata on `relationship_types`. Seeded types (`source-country`,
`document-type`, `concerns`) only make sense as document→concept edges.

**Gap:** Document→concept classification works; general semantic N:N does not.

### 5. Inverse relationship types

**Architecture:** Types may declare inverses (e.g. `replies-to` ↔
`answered-by`); some types are symmetric (`related-to`).

**Current:** `relationship_types` has `code`, `name`, optional
`target_ontology_id` only. No inverse link, no symmetry marker, and no seed
examples that need inverses.

**Gap:** Inverse/symmetric semantics are undefined in schema and API.

### 6. Provenance

**Architecture:** At least `origin` (`manual | import | deterministic-rule |
llm | mcp`) and `status` (`suggested | confirmed`). Room for model / prompt
version / generation time later. Evidence is separate and deferred.

**Current:** Relationships store `origin` (`manual | rule | import | llm`),
`status` (`suggested | confirmed`), and `created_at`. Manual API paths default
to `manual` / `confirmed`. UI shows origin/status as text.

**Gaps (non-blocking for v0.3 identity work, but real):**

- Origin vocabulary differs slightly from the architecture doc (`rule` vs
  `deterministic-rule`; no `mcp`).
- No fields reserved for derived-knowledge metadata.
- Provenance is relationship-only; entities themselves have none.

### 7. Native notes

**Architecture:** AtlasDocs-owned content entities with
`content_owner = atlasdocs`, Markdown materialization, optional deploy-specific
sync—not automatic Paperless ingestion.

**Current:** Absent. No `content_owner`, no note entity type, no Markdown
paths.

**Gap:** Full product capability; correctly out of scope until a dedicated
milestone.

### 8. Portable Markdown and future `.atlas.json` sidecars

**Architecture:** Valuable knowledge must not live only in PostgreSQL.
Sidecars are recovery artifacts (schema version, entity UUID, revision, export
timestamp, source reference, relationships, provenance)—not primary storage
and not PDF/OCR duplicates.

**Current:** Semantics exist only in the database. No export layout, no
`atlas/sidecars/` or `atlas/native/` contract in the public product.

**Gap:** Portable recovery is unimplemented. Schema generalization in v0.3
should avoid designs that make sidecars impossible later.

### 9. Future Evidence support

**Architecture:** Deferred to ~v1.0. Do not require a single supporting
document for a fact; preserve room for multi-source evidence.

**Current:** Compliant by omission—no evidence table, and relationships do not
encode a mandatory evidence document.

**Risk to avoid:** Binding relationship validity to “the Paperless document
that owns the edge” in a way that cannot later attach additional sources.

## Product / API surface vs core model

The v0.2 workbench and JSON API are intentionally Paperless-document-centric.
That is fine as a **facade** over a more general model. The problem is that the
persistence layer mirrors the facade:

- Lookup keys and uniqueness are `paperless_document_id`.
- Relationship targets are hard-wired to `concepts.id`.
- Unclassified listing is defined as “Paperless page minus docs with confirmed
  relationships,” which remains valid as a Paperless-facing query even after
  identity generalization.

Preserving the existing API means keeping paths and response fields such as
`paperless_document_id` while resolving them through
`ExternalReference(system=paperless, external_id=…)`.

## Brand / UI note (non-blocking)

`_tmp/atlasdocs-ui-brand-direction.md` describes a later visual system
(semantic color by entity type, product components, restrained brand accent).
The current workbench matches the v0.2 archival proposal and does not need a
redesign before the identity milestone. UI work that assumes Person /
Organization / Evidence components should wait until those entities exist.

## Recommended direction (summary)

Smallest useful next step: **generalize identity and relationship endpoints in
the schema** so Paperless documents become `Entity` + `ExternalReference`, and
relationship targets can become entities—while keeping today’s HTTP contract
stable. Defer notes, evidence, LLMs, MCP, embeddings, graph UI, migration
tooling productization, and Supernova.

Details and acceptance criteria: `docs/v0.3-roadmap.md`.
