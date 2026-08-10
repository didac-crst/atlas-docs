# Testing and CI

## Layers

| Layer | Location | Role |
| --- | --- | --- |
| Pytest | `tests/` | API, BFF, domain, migrations, v0.6/v0.7 document + entity lifecycle; Paperless mocked via `FakePaperlessTransport` |
| Vitest | `frontend/` | React unit tests (identity, cards, home, connect, entity detail, document actions) |
| Playwright | `e2e/` | Browser smoke (desktop + mobile) against local app + mocked Paperless |
| Hygiene | CI | `git diff --check` + secret/credential scan on tracked source |
| Docs | `scripts/` | Mermaid fence syntax + internal Markdown link check |
| Container | CI | Docker image build (no push) |
| Publish | CI on `main` / `v*` tags | GHCR push after all gates pass |

## Local commands

Use **Node.js 22** (`nvm use` — see `.nvmrc`). Wrong majors (e.g. Homebrew Node 26) can hang Playwright at webServer startup.

```bash
nvm use
pytest
cd frontend && npm test && npm run build
PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright npm run test:e2e
node scripts/check_mermaid.mjs
node scripts/check_doc_links.mjs
docker build -t atlasdocs:local .
```

### Live Paperless ingestion smoke (manual)

Against a real Paperless-ngx (verified on 3.0.5 / API v10). Credentials only via
env vars; output is limited to job id, task fingerprint, state, and error code.

```bash
PAPERLESS_BASE_URL=http://10.10.0.12:3040 \
PAPERLESS_USERNAME=... PAPERLESS_PASSWORD=... \
python scripts/live_ingest_smoke.py e2e/fixtures/ingest-smoke.pdf
```

Optional AtlasDocs UI path: set `ATLASDOCS_BASE_URL` (and the same Paperless
login env) so the script enqueues through `/ui/api/ingest` and polls the job.

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

## v0.7 acceptance coverage

Primary modules:

- `tests/test_v07_lifecycle.py` — lifecycle categories; Evidence trash/restore/
  permanent delete; Master Data blocked delete / archive / rename / merge
  placeholder; Organizational archive; Explore Documents | Knowledge; creation
  and mutation completeness; version-aware BFF downloads (`original`, `version`)
  with `no-store` / `nosniff`; reconcile `trashed_in_paperless` /
  `purged_in_paperless`; tombstone non-leakage
- `tests/test_v06_document_lifecycle.py` — replace preserves UUID/relationships;
  failed replace keeps old Paperless ref; completeness on remove/permanent delete
- `tests/test_v06_phase_b_semantic_api.py` — completeness transitions; Explore
  filters; relationship target-type constraints
- `tests/test_v06_phase_d_entity_detail.py` — entity detail, backlinks, authz
- `tests/test_document_content_bff.py` / `tests/test_bff_security.py` — preview/
  download authz, redirect/403/404 handling, PDF sniffing, token non-leakage
- Frontend Vitest — product identity/slogan, About, footer, Explore cards,
  Connect, Home, document trash confirmation, same-origin preview iframe (no
  empty `sandbox`)
- Playwright desktop/mobile — Home | Explore | Classify | Ingest navigation,
  Documents | Knowledge Explore, About/slogan/footer, destructive confirmation
  cancel, no credential leakage
- Playwright focused — `e2e/embedded-preview.spec.ts` same-origin BFF PDF
  preview, download intact, logout blocks preview

Full semantic-navigation / graph / Perspectives behavior is **not** asserted as
implemented; those remain future direction (see
[product-experience-spec.md](product-experience-spec.md)).
