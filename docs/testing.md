# Testing and CI

## Layers

| Layer | Location | Role |
| --- | --- | --- |
| Pytest | `tests/` | API, BFF, domain, migrations; Paperless mocked via `FakePaperlessTransport` |
| Vitest | `frontend/` | React unit tests |
| Playwright | `e2e/` | Browser smoke (desktop + mobile) against local app + mocked Paperless |
| Hygiene | CI | `git diff --check` + secret/credential scan on tracked source |
| Docs | `scripts/` | Mermaid fence syntax + internal Markdown link check |
| Container | CI | Docker image build (no push) |
| Publish | CI on `main` / `v*` tags | GHCR push after all gates pass |

## Local commands

```bash
pytest
cd frontend && npm test && npm run build
npm run test:e2e
node scripts/check_mermaid.mjs
node scripts/check_doc_links.mjs
```

## CI expectations

Workflow: `.github/workflows/ci.yml`.

- Pull requests run hygiene, pytest, frontend, e2e, and container.
- **Publish is skipped on pull requests** by design; it runs only on push to
  `main` or version tags after dependent jobs succeed.
- CI does **not** call live Paperless, Cloudflare, Bitwarden, or any private
  deployment. HTTPS smoke against real Paperless stays manual.

## Auth and secrets in tests

- Fixtures use obvious development values (`test-secret`,
  `production-db-password`, …). The hygiene allowlist matches **exact** quoted
  credential values, not substrings of the line.
- E2E asserts passwords and Paperless tokens never land in `localStorage` /
  `sessionStorage` or visible page text.
- Contract tests pin FakePaperless shapes for `/api/token/`, `post_document`,
  and tasks before worker behavior is trusted.
- Ingest tests cover duplicate checksum (409), Paperless duplicate → FAILED,
  ciphertext wipe on READY/FAILED, and stale lease reclaim.
