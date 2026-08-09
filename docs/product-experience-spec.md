# AtlasDocs Product Experience Specification

## Status

Product architecture specification for the public AtlasDocs repository.

This document defines the long-term user experience, navigation philosophy, and entity lifecycle model. It is not a deployment specification.

## Core principles

1. Documents are evidence, not the center of AtlasDocs.
2. Entities and relationships are the primary navigation model.
3. Reuse Paperless wherever it already solves a problem well.

The central distinction is:

```text
Evidence answers: “How do we know this?”
Master Data answers: “What do we know?”
```

Evidence is the foundation of trust. Master Data is the foundation of knowledge.

## 1. Product vision

AtlasDocs is the primary interface for exploring knowledge, understanding relationships, organizing semantic information, classifying documents, and discovering context.

Paperless remains authoritative for OCR, storage, document versions, permissions, previews, downloads, and physical document lifecycle.

AtlasDocs is authoritative for semantic identity, relationships, ontology, navigation, provenance, and knowledge discovery.

AtlasDocs must not become a second Paperless or bypass Paperless authorization.

## 2. Entity model and lifecycle categories

Everything in the semantic graph is an AtlasDocs Entity with:

- UUID;
- entity type;
- lifecycle category;
- display name;
- metadata;
- relationships;
- provenance.

The graph is homogeneous: every entity is a first-class node. The lifecycle is heterogeneous: entities do not all support the same operations.

### Evidence

Evidence originates from an external source and supports or justifies knowledge.

Examples:

- PDF;
- image;
- email;
- text document;
- spreadsheet;
- audio or video;
- web snapshot;
- Paperless-backed document.

Typical lifecycle:

```text
Create -> Replace -> Move to Trash -> Restore -> Delete Permanently
```

Deleting evidence removes supporting material. It must not automatically delete the knowledge or master entities that referenced it, although provenance and confidence may change.

### Master Data

Master Data represents shared semantic knowledge created and managed by AtlasDocs.

Examples:

- Person;
- Organization;
- Country;
- Product;
- Vehicle;
- Property;
- Concept;
- Policy;
- Case-related semantic object.

Typical lifecycle:

```text
Create -> Rename -> Merge -> Archive -> Restore
```

Deletion should be exceptional and generally prohibited while relationships exist.

### Organizational entities

Organizational entities arrange work and context.

Examples:

- Case;
- Project;
- Collection;
- Investigation;
- Tax year;
- House purchase.

They may be archived or reorganized more freely, but graph integrity and provenance must remain intact.

### Explicit category rule

Lifecycle category must be stored or deterministically derived from configuration. It must not be inferred only from the storage format or display label.

For example, “Contract” may mean a Master Data object describing an active agreement, or an Evidence document containing a signed contract. The entity’s semantic role must be explicit.

## 3. Navigation philosophy

AtlasDocs distinguishes:

### Operational work

- Classify;
- Ingest;
- Reconcile;
- Review;
- Bulk operations.

### Knowledge exploration

- Browse documents;
- Search entities;
- Navigate relationships;
- Understand context;
- Discover knowledge.

These modes must not be merged into one overloaded screen.

## 4. Home and primary navigation

Primary navigation:

```text
Home | Explore | Classify | Ingest
```

Home is an entry point, not a generic dashboard. Its primary component should be:

```text
Search anything…
```

Search results are grouped by entity type:

- Documents;
- People;
- Organizations;
- Countries;
- Cases;
- Concepts;
- Notes when supported.

Work queues remain visible below global search.

Reconcile, connection management, and Disconnect belong under profile/settings/administration rather than primary navigation.

## 5. Explore

Explore is for browsing and discovery, not classification.

Initial categories:

```text
Documents | Knowledge
```

Knowledge contains semantic entities such as People, Organizations, Countries, Cases, and Concepts.

Document filters and entity filters should remain distinct. Explore should support list/grid views, thumbnails, sorting, filters, multi-selection where useful, and stable pagination.

The old generic “All” tab should not become a meaningless mixed result list; grouped global search is preferred.

## 6. Canonical entity cards

Every entity type must have a reusable visual representation:

- Document card;
- Person card;
- Organization card;
- Country card;
- Case card;
- Concept card.

Reuse canonical cards across Explore, search, relationship picker, side panels, graphs, and classification. Entity type should be recognizable visually before reading the label.

Document cards prioritize thumbnail, title, date, type, primary organization, primary country, and relationship count.

## 7. Entity pages and semantic side panels

Every important entity should eventually have a dedicated page.

Entity pages may show:

- identity and type;
- neighboring entities grouped by type;
- related documents;
- organizations;
- people;
- cases;
- concepts;
- recent activity;
- backlinks;
- timeline when supported;
- relationship statistics;
- provenance.

Neighbors are graph relationships, not ownership. Germany does not contain documents; documents reference Germany.

## 8. Document experience

Document detail should provide:

```text
Preview | Download | Add relationship | Replace document
Delete/Trash | Open in Paperless
```

Preview is inline by default on desktop and full-screen on mobile. Paperless remains responsible for the actual viewer, OCR, storage, versions, and permissions. AtlasDocs may provide an authenticated lightweight preview BFF but must not reimplement the full Paperless viewer.

Technical sections such as Metadata, OCR Content, History, and Versions should be collapsible.

## 9. Relationship editor

Relationship creation is entity-centric:

```text
Add relationship
  -> choose relationship type
  -> Search AtlasDocs…
  -> select a valid entity
  -> save
```

Users should not manually enter Paperless IDs or choose low-level foreign keys. Relationship types determine valid target entity types, with server-side validation as the authority.

When no suitable entity exists, future versions may allow creation inline from the search flow.

## 10. Document replacement and deletion

### Replacement

Replacing another representation of the same real-world document preserves the AtlasDocs entity UUID and all semantic relationships. The Paperless external reference may change.

The old representation must remain usable until the replacement is successfully ingested, resolved, authorized, and validated.

### New document

A revised assessment, contract amendment, insurer response, or medical follow-up is a new real-world document and receives a new AtlasDocs entity. It may be linked with typed relationships such as `superseded-by`, `amended-by`, `answered-by`, or `follows-up`.

### Deletion and Paperless trash

Document deletion must use supported Paperless API permissions. The UI should distinguish:

```text
Move to Trash | Restore | Delete Permanently
```

AtlasDocs should derive active/trashed/purged state from Paperless rather than inventing an independent trash system.

Deleted entities should retain a historical tombstone internally, but must disappear from normal unauthorized or unavailable queries.

## 11. Shared and personal knowledge

Future authorization should distinguish:

### System layer

Core administrator-managed ontology, such as Country and basic entity types.

### Shared workspace

Family or team semantic knowledge, such as Airbus, Germany, and Tax Case 2026.

### Personal workspace

Private entities such as reminders, temporary concepts, and personal notes.

This affects visibility, editing, merge, archive, and relationship permissions. It should be designed before multi-user features are implemented.

## 12. Reconciliation

Reconciliation should compare Paperless collections rather than poll every document individually.

It should understand:

- active documents;
- trashed documents;
- purged documents;
- Atlas external references;
- tombstones;
- replacement history;
- orphan references;
- missing previews;
- future checksum inconsistencies.

## 13. Design system

Create reusable domain components and primitives for buttons, cards, pills, inputs, dropdowns, date pickers, side panels, relationship lists, preview panes, and entity results.

Controls must share height, spacing, typography, focus, hover, loading, success, error, and disabled states. User actions must always receive visible feedback.

## 14. Architectural compass

```text
Evidence is the foundation of trust.
Master Data is the foundation of knowledge.
Entities and relationships are the primary navigation model.
Paperless is reused wherever it already solves the problem well.
```

## 15. Paperless file and version actions

Paperless supports selecting the file representation returned by the download endpoint. AtlasDocs should preserve this capability through its authenticated server-side BFF.

Examples:

```text
Original source file:
/api/documents/{paperless_id}/download/?original=true&version={version_id}

Selected Paperless version:
/api/documents/{paperless_id}/download/?version={version_id}
```

Rules:

- `version_id` is a Paperless version identifier, not an AtlasDocs UUID.
- The browser must call AtlasDocs BFF endpoints rather than receiving a Paperless token or direct authenticated API URL.
- AtlasDocs should expose clear actions such as Download original and Download selected version when version metadata is available.
- Preview and download must preserve Paperless authorization and no-store behavior.
- Replacement workflows should reuse Paperless versions where appropriate instead of inventing an independent binary versioning system.
- Tests must verify original-file and selected-version requests against the supported Paperless API contract.
