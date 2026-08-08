# Satellite Infrastructure Opinion

## Recommended placement

Use `/srv/satellite/apps/atlas-docs` as the pilot checkout root. Current Paperless
Compose lives at `/srv/satellite/apps/atlas-docs/paperless-ngx`. Standalone deploy
roots remain a future decision (see `docs/paperless-pilot.md`):

```text
/srv/satellite/apps/paperless-ngx
/srv/satellite/apps/document-migrator
/srv/satellite/apps/document-semantic
```

## Reuse

- Reuse the existing PostgreSQL service with a dedicated Paperless database and role. Do not share application credentials.
- Reuse Cloudflare Tunnel for HTTPS instead of exposing a new public host port.
- Reuse the existing Bitwarden rendering flow for Paperless, migrator, and semantic secrets.
- Extend the existing backup process for the Paperless database and media/export data.

## Storage boundary

Dedicated NAS share: `//10.10.0.2/AtlasDocs` mounted at `/mnt/atlas-docs` (CIFS, `satellite` credentials). Pilot layout:

- `/mnt/atlas-docs/media` — Paperless media/documents
- `/mnt/atlas-docs/export` — Paperless export
- `/mnt/atlas-docs/consume` — isolated temporary consumption
- Legacy source archive remains separate (read-only); never use it as the consumption directory

Never allow the migrator to modify the legacy archive. Keep PostgreSQL data on the local SSD-backed PostgreSQL service unless restore and performance tests prove otherwise; store large document media on NAS. Local SSD also holds Paperless search index + Valkey under `/srv/satellite/data/paperless-ngx/`.

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

Settled for pilot: NAS share `AtlasDocs` → `/mnt/atlas-docs`; DB `paperless` / role `paperless_app`; dedicated Valkey in Compose; LAN port `3040` (`3030` is scanner-profile-ui).

Leave explicit TODOs for Cloudflare/Paperless hostname, image digests, admin account policy after first boot, backup retention and restore test for media, legacy archive path, semantic authentication, and multi-user permission requirements.
