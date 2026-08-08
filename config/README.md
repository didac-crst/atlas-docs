# Configuration

Reserved for non-secret configuration and version-controlled seed data.

Paperless non-secret runtime config currently lives next to Compose as
`paperless-ngx/paperless-ngx.env`. Secrets only:
`/srv/satellite/secrets/paperless-ngx.secret.env`.

## Paperless operational tags

Source of truth: `config/paperless/tags.yaml`

These are operational / workflow tags only. Semantic concepts (people,
organizations, countries, cases, domains) belong in AtlasDocs, not Paperless.

Apply (idempotent):

```sh
cd /srv/satellite/apps/atlas-docs/paperless-ngx
docker compose exec webserver python3 /usr/src/paperless/scripts/seed_tags.py
```

Never store credentials or document contents here.
