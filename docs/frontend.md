# AtlasDocs frontend

Canonical description of the classification workbench (post-v0.4).

## Stack

The workbench is a **React + TypeScript + Vite** SPA served same-origin from
the AtlasDocs FastAPI container under `/ui`.

- Package root: `frontend/`
- Router: `react-router-dom`
- Icons: `lucide-react` (labeled controls)
- Build `base: '/ui/'` → assets under `src/atlasdocs/ui/spa` (copied in Docker)

Jinja server-rendered interaction was **retired** in v0.4. There is no
production Jinja fallback for `/ui`.

No Redux, Next.js, graph visualization libraries, LLMs, or MCP in the UI.

## Security

- Paperless tokens are accepted only by `POST /ui/api/connect` and stored in
  the **server-side** HttpOnly session.
- Tokens never appear in HTML, JavaScript, browser storage, or API JSON
  responses to the browser.
- Mutating BFF calls require the session cookie and `X-CSRF-Token`. CSRF
  rotates after successful mutations.
- Unauthorized or inaccessible Paperless documents return 404 from the BFF
  with no semantic leakage.

## Paperless links

AtlasDocs does not embed a viewer. **Open in Paperless** uses
`PAPERLESS_PUBLIC_URL` only — never `PAPERLESS_BASE_URL` or Docker hostnames —
and never includes tokens. When `PAPERLESS_PUBLIC_URL` is unset, the action is
disabled.

See [paperless-integration.md](paperless-integration.md).

## Request flow

```mermaid
sequenceDiagram
  participant Browser
  participant BFF as UI_BFF
  participant Domain as DocumentService
  participant Paperless as Paperless_REST
  Browser->>BFF: cookie_plus_CSRF_/ui/api
  BFF->>Domain: session_token_server_side
  Domain->>Paperless: Authorization_Token
  Paperless-->>Domain: document_or_404
  Domain-->>BFF: semantics
  BFF-->>Browser: JSON_no_token
```

Programmatic clients use `/documents` and `/entities` with an `Authorization`
header. The SPA does not send the Paperless token to those paths.

## BFF endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/ui/api/session` | `{authenticated, csrf_token}` |
| POST | `/ui/api/connect` | Store Paperless token server-side |
| POST | `/ui/api/disconnect` | Invalidate session |
| GET | `/ui/api/documents` | Unclassified queue |
| GET | `/ui/api/documents/{id}` | Document detail + relationships |
| POST | `/ui/api/documents/{id}/relationships` | Add relationship |
| DELETE | `/ui/api/relationships/{id}` | Remove relationship |
| GET | `/ui/api/relationship-types` | Typed relationship catalog |
| GET | `/ui/api/concepts` | Concept autocomplete (`q`, `ontology`) |
| POST | `/ui/api/reconcile` | Dry-run / apply reconciliation |

SPA shell routes (`/ui`, `/ui/connect`, `/ui/documents/:id`, `/ui/reconcile`)
serve `index.html`. `/ui/api/*` is never shadowed by the SPA fallback.

## Product character and brand

AtlasDocs should feel like a semantic engineering tool: calm technical
workspace, strong hierarchy, restrained surfaces, visible relationships.

Visual families:

- Deep navy — primary text, document identity
- Blue-to-cyan — relationships, active states
- White / light gray — workspace surfaces

Suggested CSS tokens (applied in the SPA):

```css
:root {
  --brand-start: #0d6cb6;
  --brand-middle: #3a4ccd;
  --brand-end: #08afc6;
  --brand-900: #102644;
  --background: #f7f9fc;
  --surface: #ffffff;
  --text-primary: #102644;
  --text-secondary: #4f647b;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #dc2626;
}
```

Avoid generic sidebar-plus-card-grid dashboards, decorative gradients as page
backgrounds, and cream/terracotta “archival” skins from the retired Jinja UI.

## UI quality bar

- One dominant purpose per screen; classify-first hierarchy.
- Prefer whitespace and typography over cards and chrome.
- Keyboard and touch targets matter; do not use color as the only state cue.
- Distinguish confirmed relationships from suggestions (when suggestions exist).
- Before large UI changes, write a short design proposal (goal, hierarchy,
  product-specific idea) — see archived process notes under
  [archive/v0.2/ui-ux-design-spec.md](archive/v0.2/ui-ux-design-spec.md).

## Local development

```bash
# API (serves built SPA if present)
pip install -e '.[dev]'
uvicorn atlasdocs.main:app --reload --port 8080

# Frontend (Vite proxies /ui/api to :8080 during npm run dev)
cd frontend && npm install && npm run dev
```

Production images use a multi-stage Docker build: Node builds the SPA, then the
Python image copies `dist` and serves it.

More: [development.md](development.md), [testing.md](testing.md).

## History

Prior frontend architecture and brand drafts:
[archive/v0.4/](archive/v0.4/). Jinja proposal: [archive/v0.2/ui-design-proposal.md](archive/v0.2/ui-design-proposal.md).
