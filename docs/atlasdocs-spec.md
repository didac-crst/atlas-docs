# AtlasDocs - v0.1 Architecture and Pilot

## Objective

Build a personal document-management system using Paperless-ngx as the authoritative document engine and a separate semantic layer for relationships between documents, people, organizations, countries, cases, and other concepts.

The initial goal is to validate Paperless-ngx, establish a stable integration boundary, and prove safe, automatic migration of legacy documents. This is not a replacement for the Paperless UI.

## Architecture

Paperless owns the original document, archived/OCR version, OCR text, previews, basic metadata, search, ingestion, permissions, and users/groups. Never modify Paperless internal PostgreSQL tables; use its supported API and webhook mechanisms.

The semantic application owns entities, concepts, ontologies, relationship types, relationships, cases/collections, and semantic metadata. A semantic document references a Paperless document ID.

Paperless is the authorization authority. If a user cannot access a Paperless document, the semantic application must not expose its existence, metadata, relationships, OCR, summaries, search results, or aggregate counts derived from it. Filter authorization before returning semantic data.

## Paperless pilot

Deploy Paperless-ngx on Satellite using PostgreSQL, expose it through the existing HTTPS/Cloudflare infrastructure, and do not expose PostgreSQL externally. Use dedicated persistent NAS storage. Do not use the existing legacy archive as the Paperless consumption directory.

Create a test user and validate authentication and permissions. Import approximately 50-100 representative files: scanned and born-digital PDFs, medical, tax, payslip, insurance, invoice, image, multi-page, selectable-text, and OCR-required documents.

Validate ingestion, OCR quality, search, preview, download, mobile usability, permissions, NAS storage, backup, and restore. Do not begin bulk migration until the pilot is accepted.

## Legacy migration CLI

Provide a deterministic, standalone CLI such as:

```text
document-migrator scan /nas/legacy-documents
```

The source archive must never be modified. Recursively inventory supported files and persist relative source path, filename, extension/MIME type, size, SHA-256, modification time, and migration state.

States should include:

```text
DISCOVERED QUEUED UPLOADING PROCESSING IMPORTED FAILED SKIPPED DUPLICATE
```

Store source path, checksum, Paperless task UUID, Paperless document ID, error details, attempt count, and timestamps. The process must be restartable and idempotent; interruption must not cause duplicate imports.

Upload through the supported Paperless ingestion API or an isolated temporary staging area. Never configure the legacy archive as the consumption directory. Record task UUID, poll processing, record the Paperless document ID, and continue after failures.

Support:

```text
--dry-run  --limit N  --path PREFIX  --retry-failed  --status  --workers N
```

Use conservative configurable concurrency for Raspberry Pi hardware.

## Preserve legacy knowledge

Retain every document's original relative NAS path. Parse folder and filename information only into optional metadata suggestions with provenance and deterministic confidence. Suggestions must not silently become authoritative relationships.

## Semantic layer v0.1

Use version-controlled seed/configuration files instead of a complete ontology editor. Initial concepts are Document, Person, Organization, Country, and Case/Collection. Initial vocabularies are document type, domain, country, and status. Initial relationships are concerns, issued_by, source_country, jurisdiction, belongs_to, and document_type.

## Semantic UI v0.1

Do not rebuild Paperless. Provide an Inbox/Needs Classification view, a semantic document page showing Paperless title/date and semantic relationships, an Open in Paperless link, a classification form with predefined/context-aware relationships, batch classification, and an optional advanced Add relationship action.

Batch classification is required for legacy migration, for example assigning Domain=Tax, Country=Germany, Period=2023, and Tax concept=Employment income to a group.

## Synchronization

Discover newly created Paperless documents, create or match semantic entities, detect deleted/unavailable Paperless documents, and prevent orphaned semantic results. Prefer supported Paperless webhooks where appropriate and provide:

```text
semantic-sync reconcile
```

The command compares Paperless document IDs with semantic references and reports inconsistencies.

## Out of scope for v0.1

Do not build an ontology visual editor, graph visualization, custom PDF viewer, Paperless UI replacement, MCP server, LLM classification, LLM summaries, embeddings/vector database, complex semantic ACLs, or automatic deletion of legacy documents.

## Acceptance criteria

1. Paperless runs reliably on Satellite and works through secure HTTPS.
2. Representative documents ingest, OCR, preview, download, and search correctly.
3. Paperless permissions behave correctly.
4. A migration dry-run inventories the legacy archive.
5. At least 100 legacy documents migrate automatically.
6. Interrupted migration resumes without duplicates.
7. Each migrated document maps source path, checksum, and Paperless ID.
8. The semantic database attaches relationships to Paperless documents.
9. A small semantic UI classifies documents and links to Paperless.
10. Semantic results never expose documents unavailable to the authenticated user.

Only after these criteria are met should ontology expansion, automatic classification, LLM enrichment, or MCP integration begin.
