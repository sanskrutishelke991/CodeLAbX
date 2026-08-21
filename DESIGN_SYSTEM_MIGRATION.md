# CodeLabX design-system migration

Last reviewed: 2026-08-08

## Goal

Move the existing interface toward a maintainable static design system without a
visual rewrite, broken workflows, or weaker CSP. This is an incremental
migration plan, not a claim that all templates are already consolidated.

## Current baseline

- Shared application shell: `templates/base.html`
- Shared shell styles: `static/css/base.css`
- Shared shell behavior: `static/js/base.js`
- Public landing styles/behavior: `static/css/landing.css` and
  `static/js/landing.js`
- Legacy shared CSS: `static/css/style.css`
- Self-hosted browser packages: `static/vendor/`
- Page-specific templates: `templates/<app>/`
- Extracted page styles: `static/css/pages/` (37 files; no template style blocks)
- Extracted page behavior: `static/js/pages/` (20 files; no executable inline scripts)
- Theme variables: dark/light custom properties in the shared CSS

Bootstrap, Bootstrap Icons, and Chart.js are versioned and checksum-tracked.
Google Fonts and runtime JS/CSS CDNs are not required.

## Constraints

- Keep Django template rendering and the modular monolith.
- Do not introduce a Node build pipeline only for CSS organization.
- Preserve current URLs, form names, IDs consumed by JavaScript, and CSRF flows.
- Keep server data escaped through template output, data attributes, or
  `json_script`.
- Do not remove CSP allowances before all affected templates are migrated and
  browser-tested.

## Target static layout

```text
static/
  css/
    tokens.css
    base.css
    components.css
    pages/
      accounts.css
      ai-tools.css
      assessments.css
      challenges.css
      content.css
      dashboard.css
      learning.css
      notes.css
      practice.css
      progress.css
  js/
    base.js
    components/
    pages/
  vendor/
```

Files should be introduced only when they replace actual inline code. Avoid empty
layers or duplicate selectors.

## Migration order

### 1. Inventory and tests

For each template, record inline style blocks, inline scripts, event attributes,
and required server values. Add a route/template smoke test before moving code.

### 2. Low-risk static pages

Move legal, password-reset, badge-detail, leaderboard, and simple list-page CSS
first. These pages have little JavaScript and establish naming conventions.

### 3. Form and list components

Consolidate auth boxes, cards, filters, pagination, empty states, destructive
confirmation panels, and status badges. Keep app-prefixed class names where
styles are not genuinely shared.

### 4. Interactive feature pages

Move chat, image upload, roadmap creation, assessment timer, code review, video
progress, analytics, and challenge scripts one workflow at a time. Replace inline
handlers with `addEventListener` and pass URLs/configuration through data
attributes.

### 5. CSP tightening

Deploy a report-only policy in staging without `script-src 'unsafe-inline'`.
Resolve all violations, test normal/error paths, then enforce. Repeat for
`style-src`. Do not use hashes for large changing inline blocks as a substitute
for extraction.

## Naming rules

- Tokens use `--color-*`, `--space-*`, `--radius-*`, and `--shadow-*`.
- Reusable components use clear nouns such as `.card`, `.status-badge`, and
  `.empty-state` only when their contract is shared.
- Feature-specific classes retain an app prefix to avoid accidental coupling.
- JavaScript hooks use `data-*` attributes rather than presentation classes.
- IDs are reserved for unique controls, accessibility relationships, and
  server-provided JSON blocks.

## Validation for each migrated page

- Django route renders for authenticated/anonymous states as applicable
- keyboard activation and focus order still work
- mobile and desktop layout smoke check
- no new external runtime origins
- no `innerHTML` use for untrusted plain text
- no empty fragment links or inline event attributes
- CSP report has no new violation
- focused tests and `python scripts/verify.py` pass

## Remaining debt

No template `<style>` blocks, executable inline scripts, or inline event
attributes remain. Twenty page JavaScript files consume escaped data attributes or
`json_script` data. CSP now blocks inline scripts and handlers. The remaining debt
is 201 template style attributes plus styles created by a few interactive scripts;
these require `style-src-attr 'unsafe-inline'` until the final class-based style
migration and browser testing are complete.
