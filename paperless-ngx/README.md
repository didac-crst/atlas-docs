# Paperless-ngx pilot (Satellite)

Pilot stack for validating Paperless-ngx against the shared Satellite PostgreSQL
service and the NAS `AtlasDocs` share.

## Config vs secrets

| Kind | Where | Tracked in git? |
|---|---|---|
| Non-secret config | `paperless-ngx/paperless-ngx.env` | yes |
| Secrets only | `/srv/satellite/secrets/paperless-ngx.secret.env` | **never** |
| Secret key names | `paperless-ngx.secret.env.example` | yes (placeholders) |

Compose loads config first, then secrets:

```yaml
env_file:
  - ./paperless-ngx.env
  - /srv/satellite/secrets/paperless-ngx.secret.env
```

Secret keys (credentials only):

```text
PAPERLESS_SECRET_KEY
PAPERLESS_DBNAME
PAPERLESS_DBUSER
PAPERLESS_DBPASS
PAPERLESS_ADMIN_USER
PAPERLESS_ADMIN_PASSWORD
PAPERLESS_ADMIN_MAIL
PAPERLESS_XMP_UPDATE_TOKEN
```

## Post-consume enrichment

`scripts/enrich_document.py` runs after each consume (read-only mount).

v0.1 behavior: if a PDF has a trustworthy XMP/CreateDate far from ingestion time, set Paperless `created` to that date via the API. Failures are logged and never abort consumption.

Service account: Paperless user `enrich` (token only).

## Operational tags (seeded)

Source of truth: `config/paperless/tags.yaml` (mounted read-only at
`/usr/src/paperless/seeds/tags.yaml`).

Hierarchical, human-readable, lowercase, hyphenated paths such as
`workflow/inbox` and `action/follow-up`. Semantic taxonomy stays in AtlasDocs.

```sh
cd /srv/satellite/apps/atlas-docs/paperless-ngx
docker compose exec webserver python3 /usr/src/paperless/scripts/seed_tags.py --dry-run
docker compose exec webserver python3 /usr/src/paperless/scripts/seed_tags.py
```

Idempotent: safe to re-run. Does not delete unknown tags.
`workflow/inbox` is marked as the Paperless inbox tag.

## Storage layout

| Path | Purpose |
|---|---|
| `/mnt/atlas-docs` | CIFS mount of `//10.10.0.2/AtlasDocs` |
| `/mnt/atlas-docs/media` | Document media (NAS) |
| `/mnt/atlas-docs/export` | Exports (NAS) |
| `/mnt/atlas-docs/consume` | Isolated consume inbox (NAS; **not** legacy archive) |
| `/srv/satellite/data/paperless-ngx/data` | Paperless search index / app data (local SSD) |
| `/srv/satellite/data/paperless-ngx/redis` | Valkey data (local SSD) |

Postgres stays on `satellite-postgres-timescale` (local SSD-backed).

## Database

Dedicated Postgres DB/role (names and password live in the secrets file):

```text
Host: satellite-postgres-timescale:5432 (docker network satellite-databases)
```

## LAN / public access

```text
LAN (active):     http://10.10.0.12:3040
Public (pending): https://paperless-ngx.didac-crst.com
```

Cloudflare Tunnel is not configured yet. Planned origin once approved:
`http://10.10.0.12:3040`. Until then, use LAN only.

## Start

```sh
cd /srv/satellite/apps/atlas-docs/paperless-ngx
# Preflight: external Postgres network must already exist.
docker network inspect satellite-databases >/dev/null
docker inspect satellite-postgres-timescale \
  --format '{{json .NetworkSettings.Networks}}' | grep -q '"satellite-databases"'
docker compose pull
docker compose up -d
docker compose logs -f webserver
```

## Pilot checklist

- [ ] Login as admin
- [ ] Upload sample PDFs/images (OCR, preview, search, download)
- [ ] Confirm files land under `/mnt/atlas-docs/media`
- [ ] Confirm DB objects in database `paperless`
- [ ] Restart containers; data persists
- [ ] Consume path is not the legacy archive
- [ ] Run tag seeding with `--dry-run`, then apply; verify `workflow/inbox`
- [ ] Verify XMP/CreateDate enrichment on a known PDF
- [ ] Force token/API/source failure; verify consumption still completes
- [ ] Verify LAN port `3040`, external network membership, NAS mounts, and no secrets in git
