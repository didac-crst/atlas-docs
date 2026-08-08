# Paperless-ngx pilot branch

Branch: `paperless-pilot`

Goal: deploy Paperless-ngx on Satellite, connect it to the shared PostgreSQL
service with a dedicated database/role, store documents on the NAS `AtlasDocs`
share, and validate ingestion/OCR/search before any bulk migration.

Compose and runbook live under `paperless-ngx/`.

## Config vs secrets

- **Git:** non-secret config (`paperless-ngx/paperless-ngx.env`)
- **Host only:** credentials (`/srv/satellite/secrets/paperless-ngx.secret.env`) — DB name/user/password, admin user/password/mail, and `PAPERLESS_SECRET_KEY`
- Never commit passwords, usernames used as credentials, tokens, dumps, or document media

## Storage

- NAS share: `//10.10.0.2/AtlasDocs` → `/mnt/atlas-docs`
- Media / export / consume on NAS
- Search index + Valkey on local SSD under `/srv/satellite/data/paperless-ngx`

## Open decisions

- Cloudflare Tunnel for planned hostname `paperless-ngx.didac-crst.com` (LAN-only until validated)
- Image digests after pilot acceptance
- Whether this stack later moves to `/srv/satellite/apps/paperless-ngx` as its own deploy root
- Bitwarden manifest entry for `paperless-ngx.secret.env` (render from Secure Note)
