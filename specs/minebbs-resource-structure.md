# MineBBS Category 70 Structure Notes

Observed 2026-10-08 with the pinned CloakBrowser adapter and the manually selected
resource URLs from `https://www.minebbs.com/resources/categories/70/`.

## Stable regions

- Resource title: usually `h1.p-title-value`; the version is often a nested
  `span.u-muted`, so the whole H1 is not a clean version field.
- Resource body: usually `.resourceBody-main .bbWrapper`; `.resourceBody-main`
  also contains structured metadata and must not be used as the description field.
- Resource metadata: `.p-description` and resource field lists contain author,
  creation date, tags, platform, dependencies, and supported versions.
- OpenGraph title: `meta[property="og:title"]` is a useful title candidate but
  may omit the version and category badges.
- Related resources: `.resourceSidebarList` contains unrelated resource titles
  and must be excluded from the current resource body.

## Variable regions

Resource bodies differ in length, Markdown-like formatting, image/attachment
blocks, tables, code blocks, and optional purchase/review/update sections. A
generic schema should therefore separate `title`, `version`, `author`,
`created_at`, `tags`, `supported_platforms`, `dependencies`, and `body`, and
should not treat the complete document text as one field.

The ten fixed URLs used in the 2026-10-08 validation smoke make that variance
observable: body text ranged from 122 to 16,659 characters (median 2,022),
embedded images from 0 to 39 (median 2), tables from 0 to 7, and code blocks
from 0 to 3. All ten pages reached final HTTP 200 after the configured
navigation delay. This is an observed sample, not a population claim.

The next structural increment should therefore add optional metadata fields
and per-field candidate selectors, while keeping `body` as a scoped fallback.
It should compare field-level match counts and evidence quality across new
pages rather than optimizing for one body-length pattern.

## Rule guidance

Generated rules should prefer one-match selectors scoped to the current resource:

```text
title: h1.p-title-value
version: h1.p-title-value .u-muted or a resource version field
body: .resourceBody-main .bbWrapper
metadata: .p-description or explicit resource field rows
```

These are guidance, not runtime built-in domain schemas. User-provided and
human-verified ProgramSpec rules remain authoritative.

All such rules still pass the typed ProgramSpec contract. A selector is not
accepted merely because it is syntactically present in a JSON payload: the
strategy must provide the matching parameter shape before page-level selector
validation runs.
