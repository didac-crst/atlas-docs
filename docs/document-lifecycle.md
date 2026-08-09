# Document lifecycle

AtlasDocs separates **logical semantic identity** from **Paperless backing files**.

```text
AtlasDocs UUID  = logical semantic identity
Paperless ID    = external backing representation
```

They are never interchangeable.

## Create

Normal ingestion (`POST /ui/api/ingest` or `/ingest`) uploads a new file through Paperless, waits for task resolution, then creates:

- a document `Entity` (Atlas UUID)
- an `ExternalReference` (`system=paperless`, `external_id=<Paperless id>`)
- initial `semantic_completeness` (normally `empty`)

A new real-world document always gets a **new** Atlas entity.

## Replace

Replacement means another physical representation of the **same** logical document (better scan, OCR fix, corrupted PDF repair).

```text
Existing Atlas entity
  -> upload replacement through Paperless (async job, kind=replace)
  -> wait for successful ingestion + authorization
  -> switch ExternalReference to the new Paperless id
  -> record DocumentReplacementHistory
  -> delete the old Paperless document
  -> preserve Atlas UUID and relationships
```

Rules:

- Atlas UUID and relationships stay on the same entity.
- The external reference switches **only after** the new Paperless document is validated.
- If replacement fails before the switch, the old Paperless document and Atlas state remain unchanged.
- Replacement history stores previous/new external ids, checksums, actor, optional reason, and timestamp. It is provenance, not a semantic relationship.

UI action: **Replace document** on document detail.

## Delete (Evidence trash lifecycle)

Evidence deletion follows Paperless trash semantics (no independent Atlas trash):

```text
Move to Trash  -> Paperless DELETE (soft) + Atlas trashed_at
Restore        -> Paperless trash restore + clear trashed_at
Delete Permanently -> Paperless trash empty + Atlas tombstone (deleted_at)
```

Rules:

- Default `DELETE /documents/{id}` with `{"confirm": true}` moves to trash.
- Permanent purge requires `{"confirm": true, "permanent": true}` (typically after trash).
- A user who cannot delete in Paperless cannot trash or purge through AtlasDocs.
- Confirmation copy must not rely on exposing raw Paperless IDs.
- Atlas does **not** hard-delete the entity UUID on permanent delete (relationships remain for audit; normal queries hide them).
- Trashed documents leave Explore / normal lists but remain loadable on detail for restore.

UI actions: **Move to trash**, **Restore**, **Delete permanently**.

## Tombstone

Tombstoned entities (after permanent delete):

- keep their Atlas UUID and last external reference for audit
- are hidden from normal list/detail/explore/search/home/preview/download
- are skipped by reconciliation when classifying missing Paperless refs (intentional delete ≠ orphan)

## Replace cleanup

After a successful replace switch, Atlas moves the previous Paperless id to trash
and permanently deletes it when the API supports that flow, preserving the Atlas
UUID and relationships on the surviving entity.

## Reconcile

Reconciliation still never auto-deletes semantic data.

- Creates missing bindings for live Paperless documents.
- Tracks documents in Paperless trash (`trashed_in_paperless`) and syncs `trashed_at`.
- Reports purged/missing refs (`purged_in_paperless` / `missing_in_paperless`) without metadata leakage.
- Ignores tombstoned entities when reporting `missing_in_paperless`.
- After replacement, the live external reference is the new Paperless id; the old id is gone from Paperless.

## Replace vs new semantic document

| Situation | Action |
| --- | --- |
| Corrected/better scan of the same document | **Replace** |
| Revised tax assessment, amended contract, follow-up report | **New entity** (+ typed relationship such as `superseded-by` when modeled) |

```text
Another representation of the same real-world document -> REPLACE
New real-world document -> NEW ENTITY
```

## Semantic completeness

States (derived, not viewer-owned):

- `empty` — no confirmed semantic relationships
- `partial` — some semantics; configured requirements incomplete
- `classified` — configured minimum semantics present
- `needs_review` — suggestions/conflicts/unresolved review work

Recalculated on:

- entity creation
- relationship add / bulk assign
- relationship removal
- successful replacement
- trash / restore / permanent delete (tombstone path)
- Master Data archive / restore / rename

See also [v0.6 Explore and Semantic Workbench](v0.6-explore-semantic-workbench.md) and migration `0008_document_lifecycle`.
