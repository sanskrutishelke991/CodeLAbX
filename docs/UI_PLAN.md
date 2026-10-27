# CodeLabX UI implementation plan

Last reviewed: 2026-08-08

## Current interface system

CodeLabX uses Django templates, self-hosted Bootstrap 5.3.8, self-hosted Bootstrap
Icons 1.13.1, and vanilla JavaScript. Application and feature-page CSS/JS are
served as static files. CSP blocks inline scripts and event handlers; only bounded
legacy style attributes remain temporarily allowed.

## Design principles

- Show recorded data, not random/demo metrics.
- Label illustrative previews and AI-generated feedback.
- Keep primary tasks reachable by keyboard and on narrow screens.
- Use semantic buttons for actions and links for navigation.
- Preserve visible focus and reduced-motion preferences.
- Avoid runtime third-party CSS/JS/font dependencies.
- Keep destructive actions explicit, POST-only, and confirmed.

## Navigation

### Public

- Landing page
- Sign in and registration
- Privacy and terms
- Real GitHub repository/issue links only

### Signed in

- Sticky header with profile and theme control
- Bottom primary navigation for dashboard, roadmaps, challenges, and videos
- Accessible expanded feature dial
- AI Study Buddy widget when signed in
- Skip link targeting `#main-content`

## Main screens

### Dashboard

Displays real roadmaps, next incomplete day, 365-day activity, recorded XP
transactions, earned badges, tests, watched videos, and available daily
challenges. No random recommendations or fabricated activity.

### Roadmaps and lessons

Paginated/filterable roadmap list, explicit create form, owner-scoped detail,
lifecycle controls, ordered days, optional generated lesson, and idempotent
completion.

### Assessments and challenges

Assessment creation is connected to the generation API. The browser never
receives answer keys while taking a test. Deadlines come from the server. Theory
challenges show deterministic results; coding challenges show attempt credit and
optional AI feedback without a correctness claim.

### AI tools

Chat, image analysis, practice generation, and code review use bounded inputs and
generic failure states. Stored assistant HTML is sanitized again on output.
Category filters are functional buttons, not placeholder links.

### Progress, notes, and content

Analytics charts consume `json_script` data and offer a private CSV export.
Notes, bookmarks, video library/history, image history, chat history, roadmaps,
and assessments are paginated where growth is expected.

## Accessibility baseline

Implemented:

- skip links and focus targets
- visible `:focus-visible` treatment
- reduced-motion media query
- keyboard-operable landing FAQ
- labels and button semantics on core controls
- `aria-expanded` on expandable navigation/chat controls
- POST form for logout and destructive actions

Still required before public launch:

- browser/assistive-technology walkthrough of every workflow
- complete heading/landmark audit
- color-contrast measurement in both themes
- focus trapping/restoration for custom overlays
- automated browser tests at mobile and desktop breakpoints

## CSP/static migration status

Completed in the first page-extraction tranche:

- all 41 template `<style>` blocks moved to 37 versioned page stylesheets
- 10 non-dynamic inline scripts moved to page JavaScript files
- shared `data-confirm` form behavior replaced four inline submit handlers
- roadmap, assessment-list, note, image-history, and code-review controls moved
  from inline event attributes to listeners

The second tranche moved all 10 dynamic scripts to static files, passed server
configuration through escaped data attributes/`json_script`, and removed all 34
remaining event attributes. Template regression tests now require zero style
blocks, zero inline scripts, and zero inline handlers.

Remaining work:

1. Replace the remaining 201 template `style=` attributes and runtime-generated
   style attributes.
2. Add CSP violation reporting in staging.
3. Remove the temporary `style-src-attr 'unsafe-inline'` allowance.
4. Run browser smoke tests before enforcing the final style policy.

## UI acceptance checklist

- No empty `href="#"` links
- No unsupported learner/pricing/availability claims
- No answer keys or secrets in page source
- Owner-scoped list/detail requests
- Keyboard and reduced-motion behavior preserved
- Empty, loading, success, validation, rate-limit, provider-failure, and retry
  states are understandable
- Pagination retains active filters
- Gate A and focused template/route tests pass
