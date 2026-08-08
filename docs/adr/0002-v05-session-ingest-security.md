# ADR 0002: v0.5 session and ingestion token security

- **Status:** Accepted (design; implementation follows `docs/v0.5-ingestion-classification-spec.md`)
- **Date:** 2026-08-08

## Context

v0.5 adds Paperless username/password login, durable asynchronous ingestion
jobs, and multi-instance-friendly deployment. v0.4 kept Paperless tokens only in
an **in-memory** UI session store. Ingestion jobs that outlive a request (and
possibly a process restart or logout) need a defined rule for where tokens live,
how they are encrypted, and when they are destroyed.

## Decision

1. **Durable PostgreSQL sessions and jobs.** UI sessions and `ingestion_jobs`
   are stored in PostgreSQL. AtlasDocs does **not** rely on sticky load
   balancing or process-local session maps for correctness.

2. **Required `TOKEN_ENCRYPTION_KEY`.** Paperless authorization material stored
   for sessions and for in-flight jobs is encrypted at rest with a dedicated
   `TOKEN_ENCRYPTION_KEY`. Production must set a non-default key; do not derive
   this solely from `SESSION_SECRET`.

3. **Job token lifecycle.** When an ingestion job is accepted, AtlasDocs may
   persist an encrypted Paperless token snapshot on the job so the worker can
   finish after UI logout or API restart. When the job reaches **`READY` or
   `FAILED`**, delete `token_ciphertext` (NULL it). Logout deletes the UI
   session immediately and does **not** cancel already-accepted jobs.

4. **Login UX.** Production operators authenticate with Paperless
   username/password exchanged server-side via `POST /api/token/`. Pasting an
   API token remains an **advanced development fallback** only.

5. **Duplicate detection.** AtlasDocs computes SHA-256 of uploaded content for
   enqueue-time duplicate detection. Paperless remains the authority for
   document-level duplicates during consume; both paths are required.

6. **Filter split.** Document metadata search/filter/sort uses Paperless
   queries. Semantic filters (e.g. classified vs unclassified) use AtlasDocs
   queries, intersected with Paperless-authorized document ids.

7. **Upload size.** `INGEST_MAX_UPLOAD_BYTES` is configurable; initial default
   is **50 MiB**.

8. **Contract tests first.** Pin and verify Paperless `token`, `post_document`,
   and task payload shapes with mocked contract tests before implementing the
   worker against those fields.

## Consequences

- Alembic migrations add `ui_sessions` and `ingestion_jobs` (and remove
  dependence on in-memory session process state for multi-replica deploys).
- Operators must provision `TOKEN_ENCRYPTION_KEY` for production.
- Rotating `TOKEN_ENCRYPTION_KEY` invalidates existing session ciphertext and
  any in-flight job ciphertext that has not yet been wiped.
- After logout, job status may still be observable after re-login under the same
  token fingerprint; ciphertext is gone once the job is terminal.
- Implementation must not start until this ADR and the v0.5 spec decision table
  are merged.

## References

- [v0.5 ingestion & classification spec](../v0.5-ingestion-classification-spec.md)
- [ADR 0001 — Entity + ExternalReference](0001-entity-external-reference.md)
