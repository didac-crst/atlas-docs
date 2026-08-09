# Paperless reconciliation

## Purpose

Keep AtlasDocs document entities aligned with Paperless without destroying
semantic knowledge.

Reconciliation:

1. Lists Paperless documents through the REST API (paginated; optional `limit`).
2. Creates missing AtlasDocs `Entity(type=document)` rows and
   `ExternalReference(system=paperless, external_id=…)`.
3. Treats documents returned by the listing scan as already verified for that
   run (no redundant per-id GET).
4. On a **full** run (`limit` unset), GETs AtlasDocs Paperless references that
   were **not** seen in the listing and reports missing (404) or inaccessible
   (401/403) ids. Missing refs that are also absent from trash are reported in
   `purged_in_paperless` when they appear purged relative to prior Atlas state.
5. Scans Paperless trash and reports `trashed_in_paperless`, syncing Atlas
   `trashed_at` for Evidence still present in trash.
6. **Never deletes** relationships, entities, or external references.
7. Skips **tombstoned** entities (`deleted_at` set) when classifying
   `missing_in_paperless`, so intentional AtlasDocs permanent deletes are not
   reported as orphans.

Limited runs (`limit` set) focus on create/scan; orphan verification is deferred
to a full pass.

Intentional delete/replace flows are documented in
[document-lifecycle.md](document-lifecycle.md).

## Safety rule

Automatic deletion is forbidden. Operators must inspect
`missing_in_paperless` / `inaccessible_in_paperless` /
`trashed_in_paperless` / `purged_in_paperless` and decide manually.

## Service abstraction

`atlasdocs.services.reconcile.ReconcileService` is the reusable entry point for
the CLI, `POST /reconcile`, and the UI reconcile page. Future webhooks should
call the same service.

## CLI

```bash
# Required: database settings + Paperless base URL via env
# (see development.md). Token via PAPERLESS_TOKEN or --token.

atlasdocs reconcile --dry-run
atlasdocs reconcile --limit 50
atlasdocs reconcile --json
```

Exit code `1` if Paperless errors were recorded in the summary; otherwise `0`.

## HTTP API

```http
POST /reconcile
Authorization: Token …
Content-Type: application/json

{"dry_run": true, "limit": 100}
```

UI equivalent: `POST /ui/api/reconcile` (session + CSRF).

Returns machine-readable lists plus `human_summary`.

## Authorization boundary

Uses the caller’s Paperless token. Documents the token cannot access are
reported as inaccessible ids only — no titles or relationships are returned for
them.

## Idempotency

Running reconcile repeatedly does not create duplicate external references
(`UNIQUE(system, external_id)` + get-or-create).

## Deferred

Background workers, webhooks, automatic cleanup, and private-deployment
scheduling hooks. See [roadmap.md](roadmap.md).
