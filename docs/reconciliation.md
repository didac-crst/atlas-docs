# Paperless reconciliation

## Purpose

Keep AtlasDocs document entities aligned with Paperless without destroying
semantic knowledge.

Reconciliation:

1. Lists Paperless documents through the REST API (paginated).
2. Creates missing AtlasDocs `Entity(type=document)` rows and
   `ExternalReference(system=paperless, external_id=…)`.
3. Scans existing Paperless external references and reports documents that are
   missing (404) or inaccessible (401/403) to the supplied token.
4. **Never deletes** relationships, entities, or external references.

## Safety rule

Automatic deletion is forbidden. Operators must inspect
`missing_in_paperless` / `inaccessible_in_paperless` and decide manually.

## Service abstraction

`atlasdocs.services.reconcile.ReconcileService` is the reusable entry point for
the CLI, `POST /reconcile`, and the `/ui/reconcile` form. Future webhooks should
call the same service.

## CLI

```bash
# Required: database settings + Paperless base URL via env (see README).
# Token via PAPERLESS_TOKEN or --token.

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

Returns machine-readable lists plus `human_summary`.

## Authorization boundary

Uses the caller’s Paperless token. Documents the token cannot access are
reported as inaccessible ids only — no titles or relationships are returned for
them.

## Idempotency

Running reconcile repeatedly does not create duplicate external references
(`UNIQUE(system, external_id)` + get-or-create).

## Deferred

Background workers, webhooks, automatic cleanup, and Satlas-specific scheduling.
