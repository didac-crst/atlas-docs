# AtlasDocs

AtlasDocs is a reusable semantic document layer built on top of Paperless-ngx.

AtlasDocs adds entities, concepts, typed relationships, provenance, and classification workflows while Paperless-ngx remains authoritative for document storage, OCR, search, previews, and document authorization.

This repository is the public product. It must be deployable independently of Satellite, NAS layouts, Cloudflare, Bitwarden, Raspberry Pi hardware, or any personal infrastructure.

Read:

- `docs/atlasdocs-spec.md` for the product architecture and Phase 1 scope;
- `docs/ui-ux-design-spec.md` for frontend design rules;
- `migration/README.md` and `semantic/README.md` for future component boundaries.

The private Satellite deployment lives separately in `satlas-docs` and consumes AtlasDocs through a pinned release or container image.
