# Vendored browser assets

CodeLabX serves these browser dependencies from its own static origin so page
rendering does not depend on a third-party CDN at runtime.

- Bootstrap 5.3.8 (MIT)
- Bootstrap Icons 1.13.1 (MIT)
- Chart.js 4.5.1 (MIT)

`manifest.json` records the exact versions and SHA-256 digests. Each package
directory includes its upstream license. Update a dependency only by pinning a
new version, verifying its upstream checksum, reviewing its release notes, and
running the complete verification gate.

Upstream minified files retain optional `sourceMappingURL` comments, but source
maps are not shipped because they are not runtime dependencies. Production
static storage hashes CSS runtime URLs while intentionally ignoring those
development-only map references.
