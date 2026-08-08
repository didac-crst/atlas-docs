> **Historical document.** This file is archived and does not describe current AtlasDocs behavior.
> Read [../../frontend.md](../../frontend.md) instead.
> Approved React replacement of Jinja; now historical.

# AtlasDocs v0.4 React UI Proposal

## Status

Approved design direction for replacing the Jinja `/ui` workbench with a
React + TypeScript + Vite SPA served from the FastAPI container (PR #6).

## Spec inputs

- `docs/ui-ux-design-spec.md` — general design quality and accessibility standard.
- `docs/atlasdocs-ui-brand-direction.md` — product visual and interaction direction.

## Conflicts resolved

| Conflict | Resolution |
| --- | --- |
| Legacy Jinja cream/terracotta vs brand navy/cyan | Brand tokens win; cream/terracotta removed. |
| Brand allows Inter; prefer avoiding Inter | IBM Plex Sans. |
| Country entity purple vs avoid purple themes | Purple only as labeled entity-type accent. |
| Dual Jinja + React production paths | React is the sole `/ui` experience; Jinja retired (no fallback). |

## Proposal template

```text
Product intent: Provenance-aware classification workspace beside Paperless.
Primary user goal: Turn an unclassified Paperless document into confirmed typed relationships.
Visual direction: Calm navy/cyan technical workspace; logo gradient for emphasis only; IBM Plex Sans.
Primary visual element: Selected document identity + next classification action (RelationshipComposer).
Immediate context: Title, date, correspondent, type, Open in Paperless; current relationships with provenance/status.
Supporting information: Classification queue (DocumentQueue); reconcile missing/inaccessible refs.
Technical/advanced detail: Entity UUIDs, sync diagnostics—collapsed by default.
Interaction model: Inbox + drill-down (desktop: queue | detail; mobile: queue → full-screen detail with sticky actions).
Responsive composition: ≥375px stack; desktop split; reconcile as secondary route.
Distinctive AtlasDocs idea: Paperless authority strip vs AtlasDocs semantics; connected-node affordance on relationship actions—not a graph canvas.
Major states: loading / empty / error / unauthorized / success for queue, detail, composer, reconcile.
Validation plan: vitest + BFF API tests + Playwright desktop/mobile smoke; Docker multi-stage build; keyboard/focus checks.
Trade-offs: Minimal deps (React/Vite/router/icons only); no Redux/Next; autocomplete over full entity browse.
```
