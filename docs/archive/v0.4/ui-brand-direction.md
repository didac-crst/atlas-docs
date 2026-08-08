> **Historical document.** This file is archived and does not describe current AtlasDocs behavior.
> Read [../../frontend.md](../../frontend.md) instead.
> Brand tokens and product character folded into docs/frontend.md.

# AtlasDocs UI Brand Direction

## Status

Product visual and interaction direction for AtlasDocs. Complements
`../v0.2/ui-ux-design-spec.md`. Applied by the v0.4 React workbench.

## Product Character

AtlasDocs should feel like a semantic engineering tool, not office software or
a generic SaaS dashboard. Its distinctive idea is documents becoming typed
relationships and reusable knowledge.

Prefer a calm technical workspace with strong hierarchy, restrained surfaces,
and visible relationships. Avoid generic sidebar-plus-card-grid layouts,
decorative dashboards, excessive borders, and gradients used as backgrounds.

## Visual Families

- Deep navy: primary text, document identity, trust, readable structure.
- Blue-to-cyan: semantic relationships, active states, connected-node actions.
- White/light gray: workspace and document surfaces.

The logo gradient is an accent, not the dominant page background.

## Design Tokens

Suggested starting tokens:

```css
:root {
  --brand-start: #0d6cb6;
  --brand-middle: #3a4ccd;
  --brand-end: #08afc6;
  --brand-900: #102644;
  --brand-800: #0d6cb6;
  --brand-700: #2369d5;
  --brand-600: #3a4ccd;
  --brand-500: #4f46e5;
  --brand-400: #08afc6;
  --brand-300: #22c7d8;
  --brand-200: #a8eaf2;
  --brand-100: #eaf8fb;
  --background: #f7f9fc;
  --surface: #ffffff;
  --surface-alt: #f1f5f9;
  --text-primary: #102644;
  --text-secondary: #4f647b;
  --text-muted: #7a8da5;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #dc2626;
  --info: #0891b2;
}
```

Dark mode may use `#0f172a`, `#162033`, and `#1f2a3a` as background/surface
values, but dark mode is a separate implementation milestone.

## Semantic Color Use

Use color to explain meaning, not to decorate every component:

```text
Document       navy
Person         blue
Organization   cyan
Country        purple
Location       indigo
Time           slate
```

Never communicate relationship meaning through color alone. Pair color with
labels, icons, or text.

## Components and Interaction

Use product concepts rather than generic widget names. Examples include:

- `DocumentQueue`
- `SemanticDocumentDetail`
- `RelationshipComposer`
- `EntityReference`
- `EvidencePreview` (future)

The graph language should appear in meaningful interactions: selecting a
document may highlight related entities; relationship controls may use a
connected-node icon; selected entities may use a restrained brand accent.
Motion must communicate selection, continuity, or state change and must respect
`prefers-reduced-motion`.

Do not build graph visualization merely to display the logo metaphor. Add it
only when it answers a real user question.

## Typography and Icons

Use a restrained sans-serif such as Inter, Geist, or IBM Plex Sans if the
repository can load it without unnecessary performance cost. Use tabular
numerals for changing metrics and monospace only for technical values.

Use thin, consistent iconography such as Lucide, Heroicons, or Tabler. Icons
must have accessible labels or visible text when their meaning is ambiguous.

## UI Rules

1. Keep the interface mostly neutral; reserve the brand gradient for emphasis.
2. Prefer fewer, stronger regions over nested cards.
3. Keep Paperless authority visually distinct from AtlasDocs semantics.
4. Show provenance/status as readable text, not color alone.
5. Preserve keyboard, touch, contrast, and reduced-motion behavior.
6. Validate mobile composition separately from desktop.
7. Do not add visual novelty that does not improve classification or knowledge use.

## AI Assistant Workflow

Before a substantial UI change, Cursor must provide:

- user goal;
- primary visual focus;
- information hierarchy;
- interaction model;
- responsive behavior;
- states and accessibility considerations;
- one meaningful product-specific design idea.

After implementation, validate real desktop/mobile sizes, loading/empty/error/
success states, keyboard behavior, long content, and browser console output.
