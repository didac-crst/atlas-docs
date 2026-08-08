# AtlasDocs - v0.1 Product Architecture and Semantic Core

## Objective

Build a reusable semantic document layer on top of Paperless-ngx. AtlasDocs adds meaning and relationships without replacing the Paperless document engine or depending on any particular deployment environment.

AtlasDocs must never depend on Satellite. Satellite depends on AtlasDocs.

## Canonical integration boundary

Paperless-ngx owns the original document, archived/OCR version, OCR text, previews, basic metadata, full-text search, ingestion, and document authorization. AtlasDocs must use supported Paperless REST API and webhook mechanisms. It must never query or modify Paperless internal PostgreSQL tables.

The canonical adapter boundary should provide operations equivalent to:

```text
get_document(id)
document_exists(id)
can_access_document(id, user_context)
search_documents(query, user_context)
get_document_content(id, user_context)
get_document_metadata(id, user_context)
```

The adapter may have different implementations for local HTTP, a remote deployment, or tests, but the semantic domain must not know how Paperless is hosted. This preserves deployment portability, but means AtlasDocs must not depend on Paperless database internals, filesystem paths, internal task tables, or undocumented behavior. Some low-level capabilities may be unavailable through the public API; those must be represented as explicit adapter limitations rather than implemented through coupling.

If a user cannot access a Paperless document, AtlasDocs must not expose its existence, metadata, relationships, OCR, summaries, search results, or aggregate counts derived from it.

## Semantic model

AtlasDocs owns entities, ontologies, concepts, relationship types, relationships, provenance, and semantic metadata. An AtlasDocs entity UUID is independent from the external Paperless document ID.

Minimum conceptual model:

```text
Entity
DocumentReference -> paperless_document_id
Ontology
Concept
RelationshipType
Relationship
RelationshipProvenance
```

Relationships should retain:

```text
origin: manual | legacy-path | deterministic-rule | external-automation
status: suggested | confirmed
created_by
created_at
```

Do not add tax-specific tables or a graph database in Phase 1.

## Semantic core v0.1

Use version-controlled seed/configuration files instead of a complete ontology editor. Initial concepts are Document, Person, Organization, Country, and Case/Collection. Initial vocabularies are document type, domain, country, and status. Initial relationships are concerns, issued_by, source_country, jurisdiction, belongs_to, and document_type.

The first proof should be:

```text
Paperless document 184
        -> AtlasDocs document entity UUID
        -> source-country: Germany
        -> document-type: Payslip
```

The Paperless ID is an external reference, never the AtlasDocs entity primary key.

## REST API Phase 1

Provide only the smallest useful API:

```text
GET    /documents/{paperless_id}/semantics
POST   /documents/{paperless_id}/relationships
DELETE /relationships/{id}
GET    /ontologies
GET    /ontologies/{code}/concepts
GET    /relationship-types
```

The API must validate Paperless access before returning or mutating document-derived semantic data. It must reject invalid targets and handle duplicate relationships deterministically.

## Legacy migration boundary

A deterministic migration CLI may later inventory a deployment-supplied source archive without modifying it. It should record relative path, MIME type, size, SHA-256, modification time, Paperless task/document IDs, attempts, errors, and idempotent migration state.

The source location, concurrency, Paperless URL, and storage paths belong to the deployment repository, not this public product repository. Legacy path parsing creates provenance-bearing suggestions and must not silently create confirmed relationships.

## UI and synchronization

The UI is a later phase. It should not rebuild Paperless; it may provide an Inbox/Needs Classification view, semantic document detail, relationship classification, batch classification, and a link to Paperless.

Synchronization may later discover new Paperless documents, create/match AtlasDocs document entities, detect unavailable documents, and provide a reconciliation command. It must use the Paperless API/webhooks rather than database access.

## Out of scope for Phase 1

Do not build a frontend, ontology visual editor, graph visualization, custom PDF viewer, Paperless UI replacement, MCP server, LLM classification, LLM summaries, embeddings/vector databases, complex semantic ACLs, automatic deletion, or Supernova orchestration.

## Phase 1 acceptance criteria

1. AtlasDocs runs independently of Satellite.
2. PostgreSQL migrations are reproducible.
3. Entities, document references, ontologies, concepts, relationship types, and relationships can be created.
4. Seed data creates country and document-type concepts.
5. A document reference points to a Paperless document ID without using it as the AtlasDocs entity ID.
6. The Paperless adapter retrieves document metadata through the supported API.
7. Authorization is checked before document-derived semantic data is returned.
8. Duplicate relationships and invalid targets are rejected or handled deterministically.
9. Tests cover the semantic model and Paperless adapter using mocks.
10. No frontend, LLM, MCP, embedding, graph database, or Supernova code is required for completion.
