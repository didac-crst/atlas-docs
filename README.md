# AtlasDocs

<p align="center">
  <img src="assets/atlas-docs-wordmark.svg" alt="AtlasDocs" width="480">
</p>

AtlasDocs is a reusable semantic document layer built on top of Paperless-ngx.

AtlasDocs adds entities, concepts, typed relationships, provenance, and
classification workflows while Paperless-ngx remains authoritative for document
storage, OCR, search, previews, permissions, and document lifecycle.

This repository is the public product. It must be deployable independently of
any particular private infrastructure.

## Status

v0.4 provides a general entity relationship API, Paperless reconciliation, and
a React + TypeScript + Vite classification workbench on the v0.3 Entity +
ExternalReference core.

## Documentation

| Doc | Contents |
| --- | --- |
| [Architecture](docs/architecture.md) | Entities, references, relationships, ownership |
| [Frontend](docs/frontend.md) | React SPA, BFF auth, brand |
| [API](docs/api.md) | JSON API and BFF surfaces |
| [Paperless integration](docs/paperless-integration.md) | REST boundary, BASE vs PUBLIC URL |
| [Reconciliation](docs/reconciliation.md) | CLI / HTTP reconcile safety |
| [Development](docs/development.md) | Local setup, env, layout |
| [Testing](docs/testing.md) | Test layers and CI |
| [Roadmap](docs/roadmap.md) | Forward work and deferred features |
| [ADRs](docs/adr/) | Durable architecture decisions |
| [Archive](docs/archive/) | Historical milestone proposals |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest

cd frontend && npm install && npm test && npm run build && cd ..

docker compose up --build
```

Open `http://localhost:8080/ui`, paste a Paperless API token, and classify.
The token stays server-side; the browser only receives an opaque HttpOnly
session cookie.

Full setup and configuration: [docs/development.md](docs/development.md).

## Brand assets

- `assets/atlas-docs-wordmark.svg` — README and full-width product identity
- `assets/atlas-docs-mark.svg` — compact icon / favicon contexts
