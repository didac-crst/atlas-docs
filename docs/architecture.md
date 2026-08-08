# AtlasDocs architecture

Canonical description of the current semantic layer (post-v0.4).

## Ownership boundary

| Concern | Owner |
| --- | --- |
| Document storage, OCR, search, previews, permissions, lifecycle | **Paperless-ngx** |
| Typed entities, concepts, relationships, provenance, classification workflows | **AtlasDocs** |

AtlasDocs never embeds a document viewer, never touches Paperless databases or
filesystems, and integrates only through the Paperless **REST API**.

See [paperless-integration.md](paperless-integration.md) for authorization and
URL rules.

## System boundaries

```mermaid
flowchart LR
  subgraph clients [Clients]
    Browser[Browser_SPA]
    ApiClient[API_client]
  end
  subgraph atlas [AtlasDocs]
    BFF[UI_BFF]
    REST[JSON_API]
    Domain[DocumentService]
    DB[(PostgreSQL)]
  end
  Paperless[Paperless_ngx]
  Browser -->|"HttpOnly_session_CSRF"| BFF
  ApiClient -->|"Authorization_Token"| REST
  BFF --> Domain
  REST --> Domain
  Domain --> DB
  Domain -->|"server_side_token"| Paperless
```

## Core model

### Entities

Every semantic object is an `Entity` with an AtlasDocs UUID.

| `entity_type` | Meaning |
| --- | --- |
| `document` | A document known to AtlasDocs (usually bound to Paperless) |
| `concept` | A coded concept in an ontology (country, document-type, person, organization, …) |

Person and organization are **concept entities** today, not separate
`EntityType` values.

### External references

Paperless document ids are never AtlasDocs primary keys. Binding is via:

`ExternalReference(system=paperless, external_id="<paperless_id>")`

Constraints:

- `UNIQUE(system, external_id)`
- One primary external binding per entity for the current schema

### Concepts and ontologies

Concepts belong to version-controlled ontologies loaded from seed YAML
(`config/seed/`). Concept rows share the same UUID as their entity
(`concepts.id` → `entities.id`).

### Relationships

Relationships are entity→entity edges:

- Typed by `RelationshipType` (optional target ontology, directionality, inverse)
- Provenance: `origin` (`manual`, `import`, `deterministic-rule`, `llm`, `mcp`, …)
- Status: typically `confirmed` for workbench writes
- Unique on `(source_entity_id, relationship_type_id, target_entity_id)`
- Symmetric / inverse companions are maintained when the type requires them

The document facade (`/documents/{paperless_id}`) remains for callers that
think in Paperless ids. General work uses `/entities/{uuid}`.

```mermaid
flowchart TB
  DocEntity[Entity_document]
  ExtRef[ExternalReference_paperless]
  ConceptEntity[Entity_concept]
  ConceptRow[Concept_ontology_code]
  Rel[Relationship]
  RelType[RelationshipType]
  DocEntity --> ExtRef
  ConceptEntity --> ConceptRow
  DocEntity -->|"source"| Rel
  Rel -->|"target"| ConceptEntity
  Rel --> RelType
```

## Authorization

- JSON API: every document/entity request requires `Authorization` (Paperless token or Bearer). There is no service-token fallback for document access.
- UI: Paperless token is stored **server-side** in an HttpOnly session; the browser never receives the token.
- When Paperless denies access (401/403) or the document is missing (404), AtlasDocs returns **404** and does not leak titles or relationships.

## Surfaces

| Surface | Role |
| --- | --- |
| JSON API | Programmatic clients (`/documents`, `/entities`, `/reconcile`, …) |
| UI BFF + SPA | Classification workbench under `/ui` |
| CLI | `atlasdocs reconcile` and related commands |

Details: [api.md](api.md), [frontend.md](frontend.md), [reconciliation.md](reconciliation.md).

## Known limitations (current)

- Correspondent / document-type labels resolve from Paperless payloads (including integer id lookups when needed).
- Document↔document edges in the UI target a Paperless id for types such as `derived-from` / `has-derivative`.
- Background workers, webhooks, and automatic deletion are **not** implemented — see [roadmap.md](roadmap.md).

## History

Milestone proposals live under [archive/](archive/). The Entity + ExternalReference
decision is recorded in [adr/0001-entity-external-reference.md](adr/0001-entity-external-reference.md).
