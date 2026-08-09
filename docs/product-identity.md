# AtlasDocs Product Identity

## Status

Product-experience amendment for the public AtlasDocs repository.

This applies to the public AtlasDocs product and should be read together with:

- the [product experience specification](product-experience-spec.md);
- the [v0.7 product experience contract](v0.7-product-experience.md) and [roadmap](roadmap.md);
- [frontend](frontend.md) / archived UI brand direction;
- this document as the product-identity source of truth for shell copy.

## 1. Product-first principle

AtlasDocs is the product.

Paperless is infrastructure used by AtlasDocs, similar in product visibility to PostgreSQL, Valkey, or another internal service.

Paperless remains the authoritative document engine, but it should not dominate the user’s conceptual experience.

The default product language should be:

```text
AtlasDocs
Where evidence becomes knowledge.
```

Paperless should appear only where it provides useful technical context or an advanced source action.

## 2. Product slogan

Use this slogan consistently across the core product shell:

```text
Where evidence becomes knowledge.
```

It may appear in:

- login;
- home;
- loading states;
- footer;
- About/product-information views.

It must remain visually secondary to the active task and must not consume excessive space in operational screens.

## 3. Login experience

The login page should be AtlasDocs-branded:

```text
[AtlasDocs logo]
AtlasDocs
Where evidence becomes knowledge.

Username
Password

[ Sign in ]

Secure authentication powered by Paperless.
```

Requirements:

- AtlasDocs logo and product name are primary.
- Paperless is acknowledged in small secondary text.
- Do not describe the page as a Paperless login.
- Preserve server-side token handling, HttpOnly sessions, CSRF, rate limits, and secure error handling.
- Never expose credentials or tokens to browser storage, HTML, JavaScript, URLs, or logs.

## 4. Home experience

Home should begin with:

```text
AtlasDocs
Where evidence becomes knowledge.

Search anything…
```

The home screen remains a product entry point, not a marketing hero and not a generic dashboard.

Below the search entry point, show practical work areas such as Explore, Needs classification, Needs review, failed ingestion, and recently changed knowledge.

The slogan must not displace the primary search and task actions.

## 5. Loading and connection states

Loading states should retain product identity:

```text
AtlasDocs
Where evidence becomes knowledge.
Connecting…
```

The implementation must not expose internal service names, Docker hostnames, raw upstream errors, credentials, or Paperless tokens.

## 6. Footer

The application shell may include:

```text
AtlasDocs
Where evidence becomes knowledge.
Powered by Paperless-ngx
```

“Powered by Paperless-ngx” should be small and visually secondary. It is an acknowledgement, not the product identity.

## 7. About/product information

Provide a concise About view when appropriate:

```text
AtlasDocs
Where evidence becomes knowledge.

AtlasDocs transforms document archives into connected knowledge.

Every document is treated as evidence. Through entities, relationships,
and context, evidence becomes knowledge that can be explored, searched,
and understood.

Built on:
  Paperless-ngx
  PostgreSQL
  Valkey
  FastAPI
  React
```

The About view should be informative and product-oriented, not a marketing landing page.

## 8. Product manifesto

AtlasDocs may expose the following manifesto in About or product documentation:

```text
Documents are static.
Knowledge is connected.

Every invoice belongs to a purchase.
Every purchase belongs to a person.
Every person belongs to a family.
Every medical report belongs to a life.

AtlasDocs transforms isolated documents into connected evidence,
so knowledge can emerge.

Where evidence becomes knowledge.
```

This statement should guide product decisions, not become repetitive copy throughout the interface.

## 9. Brand hierarchy

Use this priority order:

1. AtlasDocs product identity.
2. Current user task or knowledge context.
3. Atlas entities, relationships, and evidence.
4. Paperless source/integration details.
5. Technical infrastructure details.

Do not show Paperless as the primary navigation label, page title, or conceptual owner of AtlasDocs content.

## 10. Acceptance criteria

- Login, home, loading, footer, and About views use AtlasDocs identity.
- The slogan appears consistently but does not overwhelm operational workflows.
- Paperless is acknowledged without dominating the interface.
- The application remains usable without reading the manifesto.
- No marketing-style landing page replaces the working application.
- Authentication and authorization behavior remain unchanged.
- No credentials, tokens, internal URLs, or raw upstream errors appear in the UI.
