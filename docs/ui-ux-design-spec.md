# AtlasDocs UI/UX Design Specification

## Purpose

This specification guides AI coding assistants designing AtlasDocs interfaces. The goal is an intentional, distinctive, coherent, understandable, pleasant, product-specific interface rather than a generic dashboard or cosmetic CSS pass.

AtlasDocs is a personal document system: Paperless-ngx owns document storage, OCR, search, previews, and authorization; AtlasDocs adds classification, relationships, cases, and meaning. The UI should feel like a calm, trustworthy archival utility with an editorial sense of organization, not like an operations control room.

## Design before implementation

Before changing a frontend, write a short proposal that answers:

- What is the product in one sentence?
- Who is using this screen and what is the primary goal?
- What should be noticed first?
- What decision or action becomes easier?
- What emotional impression and product-specific idea should the screen convey?
- What is primary, contextual, supporting, and technical information?
- How does the user move through it: inbox, tabs, drill-down, contextual panel, drawer, timeline, batch mode, or another justified model?

Do not begin implementation while the visual direction and interaction model are vague. For AtlasDocs, start with the workflow and classification task, not with a default sidebar, card grid, or component library.

## AtlasDocs product direction

The primary v0.1 workflow is “turn an unclassified document into a trusted, searchable part of the personal archive.” The default focus should be the Inbox / Needs Classification queue and the document currently being classified.

Recommended hierarchy:

1. Primary: document identity and the next classification decision.
2. Context: Paperless title, date, preview, origin, and current classification.
3. Supporting: suggested metadata, related entities, batch-selection context.
4. Technical: checksums, source paths, task IDs, sync diagnostics, and raw metadata.

The distinctive idea should be a provenance-aware classification workspace: show the document, its Paperless authority, and deterministic legacy suggestions together, while clearly distinguishing suggestions from confirmed relationships. Do not make a generic graph visualization the normal interface.

## Composition and visual hierarchy

Each screen must have one dominant purpose and be understandable within seconds. Use whitespace, typography, alignment, and grouping as structure. Prefer fewer strong regions over many small containers. Do not enclose every element in a card or give every metric equal visual weight.

Do not preserve a weak layout merely because it exists. Decide whether a request needs polish, a component redesign, a hierarchy change, or a screen rebuild. Preserve behavior and data contracts where practical, not weak composition.

Avoid defaulting to:

- a generic left sidebar and top navigation;
- identical statistic cards;
- rounded white cards on grey backgrounds;
- purple-blue gradients or glassmorphism;
- excessive pills, badges, borders, and decorative charts;
- generic hero sections or icons for every label.

Use controls and containers only when they communicate interaction, grouping, selection, separation, or state.

## Interaction and states

Interactions must be direct and predictable. Prefer selecting a document to reveal contextual actions, a document drawer for focused review, batch selection for repeated classification, and a clear link to open the authoritative Paperless view.

Every interactive element needs defined default, hover, focus, pressed, selected, disabled, loading, empty, error, and success states. Important actions must be visible on touch devices and must not depend on hover.

Use progressive disclosure for advanced relationships, diagnostics, raw source data, and synchronization details. The default screen should remain understandable without exposing implementation details.

## Responsive design

Mobile is a separate composition, not a compressed desktop. Reconsider priority, navigation, panel order, document preview, sticky actions, drawers, scrolling, and batch controls at each breakpoint.

Validate at 375px, 390-393px, 430px, tablet portrait, tablet landscape, standard desktop, and wide desktop. Touch targets should generally be at least 44x44 CSS pixels. Ensure long titles, filenames, relationship names, errors, and empty states fit without overlap or layout shifts.

## Motion

Motion should communicate state change, continuity, hierarchy, progress, or a spatial relationship. Keep it subtle, fast, interruptible, and consistent. Support `prefers-reduced-motion`. Do not animate every component independently or use motion only as decoration.

## Data visualization

Only add a visualization when it answers a real question, such as what changed, which documents are unclassified, where migration is failing, or how a case is progressing. Provide units, time range, thresholds, context, accessible alternatives, and useful loading/empty states. Avoid decorative charts, unexplained gauges, arbitrary smoothing, excessive colors, and dense legends.

## Typography and color

Use a limited type scale for display, page title, section title, body, secondary text, labels, numerical values, and captions. Use restrained readable typography appropriate to a personal archive; use tabular numerals for changing counts and monospace only for diagnostics or machine data.

Centralize semantic design tokens for colors, spacing, typography, radii, shadows, durations, easing, widths, breakpoints, and z-index layers. Tokens should include background, surface, primary/secondary text, accent, success, warning, danger, border, and focus. Maintain contrast and never use color as the only state indicator.

## Components

Build components around AtlasDocs concepts rather than visual shapes. Prefer names such as `ClassificationInbox`, `DocumentContext`, `ProvenanceSuggestion`, `RelationshipEditor`, `BatchClassification`, and `SyncStatus` over `Card1`, `InfoBox`, or `WidgetContainer`.

Keep components cohesive and do not create abstractions before repeated usage is demonstrated. Generic primitives are acceptable below product-level components.

## Accessibility and performance

Use semantic HTML, keyboard navigation, visible focus, correct heading order, meaningful labels, text alternatives, appropriate ARIA, screen-reader-compatible state changes, reduced-motion support, usable zoom, and text scaling. Do not replace semantic controls with clickable divs.

Keep the interface fast on low-power or remotely served infrastructure. Avoid oversized bundles, unnecessary dependencies, uncompressed images, excessive DOM nodes, continuous high-frequency animation, blocking requests, and unnecessary re-renders. Use progressive enhancement and preserve the existing backend/data boundaries.

Do not put Paperless business logic, authorization decisions, or persistence rules into presentation components. Paperless remains the authority for document access; semantic results must be filtered before they reach the UI.

## AI assistant workflow

For a major frontend task:

1. Inspect existing screens, components, data contracts, flows, responsive behavior, tokens, and constraints.
2. Diagnose the real limitation: hierarchy, density, generic language, navigation, mobile composition, feedback, empty states, or information architecture.
3. Propose user goal, composition, hierarchy, interaction, visual direction, responsive behavior, and distinctive idea.
4. Implement the complete coherent change, including non-ideal states.
5. Validate function, responsive layouts, keyboard/touch use, accessibility, console errors, loading/error/empty/long-content states, and visual consistency.
6. Critique the result: focal point, product specificity, unnecessary competition, mobile quality, meaningful distinctiveness, and removable complexity.

For substantial work, report design rationale, structural changes, viewport/state validation, and known limitations. Do not claim polish without visual inspection.

## Anti-patterns and definition of done

Avoid preserving bad layouts, equal-weight metric grids, nested cards, hierarchy by color alone, decorative animation, generic SaaS templates, placeholder copy, ambiguous icon-only actions, hover-only actions, stacked desktop columns as mobile design, unnecessary frameworks, screenshot optimization, misleading charts, and completion claims without real viewport checks.

The work is complete only when the user goal is clearer, hierarchy is explicit, the result is specific to AtlasDocs, responsive layouts are deliberate, major states work, keyboard/touch/accessibility are considered, design tokens remain coherent, complexity is justified, and existing functionality still behaves correctly.

## Required proposal template

```text
Product intent:
Primary user goal:
Visual direction:
Primary visual element:
Immediate context:
Supporting information:
Technical/advanced detail:
Interaction model:
Responsive composition:
Distinctive AtlasDocs idea:
Major states:
Validation plan:
Trade-offs:
```
