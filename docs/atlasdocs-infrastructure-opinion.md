# Satellite Infrastructure Opinion

## Recommended placement

Use `/srv/satellite/apps/AtlasDocs` as the planning root. When implementation starts, keep deployable components separate:

```text
/srv/satellite/apps/paperless-ngx
/srv/satellite/apps/document-migrator
/srv/satellite/apps/document-semantic
```

The current scaffold is documentation only. Do not create a Compose stack until the storage and backup decisions are approved.

## Reuse

- Reuse the existing PostgreSQL service with a dedicated Paperless database and role. Do not share application credentials.
- Reuse Cloudflare Tunnel for HTTPS instead of exposing a new public host port.
- Reuse the existing Bitwarden rendering flow for Paperless, migrator, and semantic secrets.
- Extend the existing backup process for the Paperless database and media/export data.

## Storage boundary

The existing `/home/didac/Scans` CIFS mount is not an adequate definition of the new system's storage boundary. Create and document dedicated NAS locations for:

- Paperless media/documents
- Paperless export
- isolated temporary consumption
- read-only legacy source archive

Never use the legacy archive as the consumption directory and never allow the migrator to modify it. Keep PostgreSQL data on the local SSD-backed PostgreSQL service unless restore and performance tests prove otherwise; store large document media on NAS.

## Dependencies

Paperless normally requires Paperless-ngx, PostgreSQL, a Redis-compatible broker, and document conversion services such as Gotenberg and Tika depending on the selected image/version. Prefer a dedicated Redis/Valkey instance or an explicitly isolated logical namespace. Do not silently reuse MockExchange's Valkey.

Pin image versions after the pilot; do not use `latest`.

## Raspberry Pi constraints

OCR and conversion can be CPU- and memory-intensive. Start with the pilot, one or two migrator workers, and backpressure. Measure OCR time, memory, NAS latency, search responsiveness, database growth, and recovery after container/host restart before bulk migration.

## Security

- Keep PostgreSQL and Redis private.
- Mount the legacy source read-only.
- Do not store documents, OCR, tokens, passwords, or database credentials in Git.
- Enforce Paperless authorization before returning semantic data.
- Design authenticated identity propagation before building the semantic UI.
- Do not add a second semantic ACL system in v0.1.

## Recommended order

1. Decide NAS directories, ownership, capacity, and backup/restore testing.
2. Create the dedicated Paperless database and role.
3. Choose and pin Paperless dependency versions.
4. Deploy Paperless and validate HTTPS, users, permissions, and the pilot.
5. Build the deterministic migrator separately.
6. Add the semantic database and synchronization boundary.
7. Add the small classification UI.

## Decisions Cursor must not invent

Leave explicit TODOs for real NAS paths, Paperless hostname, image versions, database and role names, Redis choice, admin account creation, backup retention and restore test, legacy archive path, semantic authentication, and multi-user permission requirements.
