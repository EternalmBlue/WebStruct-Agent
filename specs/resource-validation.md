# Fixed resource validation increment

Confirmed 2026-10-08. Scope: the existing single-page extraction workbench.
No forum discovery graph, crawler, domain Schema template, CAPTCHA solver,
browser profile, fingerprint, UA override, or challenge-provider recognition.

## Browser

`[browser].post_navigation_wait_ms` defaults to 10000, accepts 0..60000.
After `goto`, wait once, unconditionally, with the browser event loop running.
Allow natural redirects. Read the DOM, current URL and last main-document
response only after waiting. No sampling/classification drives the wait.
Supplied HTML never waits. Generic final HTTP/content checks remain unchanged.
Record configured/actual wait, outcome, initial/final status and response count.
Legacy challenge_wait_ms/challenge_poll_ms remain accepted for configuration
compatibility but no longer control collection. No challenge markup is inspected.

## Verification

An absent/empty optional field is not an error and does not lower the score.
Missing fields still appear in extraction results and completeness metrics.
An optional provider/execution failure remains a warning.
Nonempty optional fields still undergo type, date, confidence and evidence checks.
Zero and False are values, not missing. Required-field failure remains an error.
Workflow `completed` remains distinct from verification `passed`.

## ProgramSpec

Use a real HTML tree, CSS engine and XPath evaluator. Preserve nested text,
handle void tags, exclude scripts/styles, and never execute generated code.
Text-block locator hints use the parsed tree's sibling-local paths, not global
tag counters, so nesting and void elements cannot corrupt selector evidence.
Optional `attribute` reads a matched element's attribute; XPath may return text
or attribute strings. Evidence offsets are null when a normalized value is
not an actual contiguous substring of the text view.

Give the model bounded, content-focused HTML and matched selector samples
instead of only the document prefix (often entirely CSS/scripts/navigation).
Generated CSS/XPath rules are checked against the current DOM: syntax errors,
zero matches, ambiguous matches, empty values, and document-title/root rules
are rejected with structured diagnostics. Prefer narrow explicit rules.
Validation examines selected nodes, not just the selector spelling: qualified
root/title selectors are also rejected. This guard applies to model-generated
and model-revised drafts, while explicit user/verified programs stay unchanged.
No automatic `//title` fallback. A unique h1 may remain a deterministic fallback.
Explicit user-provided and verified programs are not rewritten.
At execution, invalid/ambiguous DOM rules fail at field level, allowing later
rules and explicit LLM fallback; do not silently take the first of many matches.

The typed DSL enforces strategy-specific shapes at every boundary:
`css`/`xpath` require a selector, `regex_on_text` requires a compilable
pattern, `text_near_label` requires a label, and `llm_fallback` cannot carry
DOM/regex locator parameters. Unknown fields and extra object keys are rejected
instead of being silently accepted by the contract layer.

## RSI

Keep immutable runs and supervised acceptance/rollback semantics.
Metrics version 2 adds all-field completion, optional missing, selector errors,
ambiguity, rejected generated rules and measured browser wait.
Store an evaluator version in the fingerprint; incompatible evaluator/metric
versions cannot compare verifier scores. On comparable runs, reject apparent
score gains accompanied by lower completion/evidence or more required misses.
These are quality proxies, not gold accuracy.
Missing or unversioned guardrail measurements block evaluation. Candidate quality
is a weighted proxy: 0.5 * verifier score + 0.3 * field completion + 0.2 * evidence
coverage. Acceptance requires its gain to meet min_quality_delta without any
verifier/completion/evidence/required-missing regression or excessive latency.
The evaluation policy version is stored with each iteration. Optional absence
does not harm verification, but remains visible in completion and proxy quality.

Validation uses the ten manually selected resource URLs from category 70,
not an automatically discovered forum. Fetch each with CloakBrowser once,
then replay the exact collected HTML into baseline/candidate LangGraph runs
using a fixed explicit Schema. Investigate title/version/author/body nodes,
record per-page values, selector scope, independent DOM reference comparisons,
token provenance and RSI decisions. DOM references are not human gold labels.
Live collection and snapshot replay latencies are separate. No resource
download, purchase or login. Persist this opt-in experiment locally in the
existing runtime and RSI stores; offline BDD must not depend on MineBBS.
