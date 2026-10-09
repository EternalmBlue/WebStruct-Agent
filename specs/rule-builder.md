# Rule Builder

Approved scope: one page snapshot, two independent collaboration flows, four pages.
This supplements `ui-workbench.feature` and `spec-assistant-center.feature`.

## Flow

1. URL-first creation (optional supplied HTML, no implicit schema override).
2. Automatic transition to a snapshot/fields workspace after successful extraction.
3. Quality check, optional second URL of the same page structure, review and save.
4. Read-only preview grouped by rule, listing its owning field(s).

The source is CloakBrowser-collected HTML rendered in an isolated inert snapshot,
not a remote interactive browser session. External navigation, page scripts and
forms are disabled. Clicking a field highlights its evidence inside this snapshot.
Selecting text binds evidence guidance for that field. A separate text view is
available when the original styling cannot be rendered.

Only explicit re-read or a new URL creates a new page snapshot. Field/value edits
never call the collector. Snapshot identity and draft revision accompany every
collaboration; stale responses cannot overwrite a newer draft.

## Independent Collaboration

- FieldSchemaAgent reads the current snapshot, active schema and natural-language
  request, and proposes fields only. It cannot change values or rules. Accepting
  its proposal retains unchanged fields and invalidates only changed/new fields.
- FieldValueAgent works on exactly one field, with the immutable snapshot,
  optional reference value and selected evidence. It generates that field's safe
  DSL, executes it, and returns structured value/evidence/rules/verification.
- Both are typed, traced LangGraph StateGraphs behind ModelAdapter.
- Fields support add, rename, description/type/required edits, soft delete,
  restore and pause. Deleted/paused fields are excluded from check and save.
- Reference values apply to this page, not literal constants for future pages.
  They cannot become evidence unless found in the saved snapshot.
- Multiple field jobs may run concurrently with a bounded client queue; no
  unrelated field is re-extracted. Failed jobs retain draft input and can retry.

## Check And Save

Field/value edits invalidate the previous check. Quality check executes the
current safe DSL against the original snapshot, verifies evidence/type/confidence,
and checks that guided values are reproduced. Missing evidence and mismatches
remain visible; an unpassed check cannot register a verified rule.

Optional second-URL validation executes the same candidate ProgramSpec, without
generating replacements or auto-saving it. It is a same-origin, different URL
for another page with the same structure (for example another forum thread).

Refresh restores the source task, draft fields, guidance, page and check. It never
resubmits creation. Busy collaboration is restored as retryable, not as success.
Stored drafts contain no credentials. User-facing UI never edits DSL/selectors.

## Verification

Backend BDD covers the two independent agents, immutable snapshots, selective
execution, missing context, unsupported evidence, check/replay and save gating.
Frontend Playwright checks cover creation transitions, field lifecycle, evidence
highlight/selection, proposal acceptance, retry, refresh and responsive layouts.
