# AtlasDocs

Planning scaffold for Paperless-ngx, the deterministic document migrator, and the semantic layer.

Read `docs/atlasdocs-spec.md` and `docs/atlasdocs-infrastructure-opinion.md` before implementation. For UI work, also read docs/ui-ux-design-spec.md.

The `paperless-pilot` branch adds a Satellite-oriented Paperless-ngx Compose stack under `paperless-ngx/`. See `docs/paperless-pilot.md`.

**Public repo:** commit non-secret config only. Secrets (passwords, `PAPERLESS_SECRET_KEY`, tokens) live exclusively under `/srv/satellite/secrets/` on the host. Never commit document media, dumps, or secret env files.

Read docs/BURST_COMPUTE.md for the burst-compute architecture.
