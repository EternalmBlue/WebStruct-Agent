# RSI observation and evaluation protocol

Confirmed 2026-10-08. [resource-validation.md](resource-validation.md) supersedes the
challenge-driven polling policy with an unconditional configured navigation delay
and adds versioned completion/selector guardrails. This is supervised evaluation, not autonomous
code generation, deployment, anti-bot bypass, or a claim of recursive self-improvement.

## Collection

- Each attempt has collector, start/end timestamps, monotonic duration, HTTP status,
  safe final URL, classification, classification signals, SDK/binary versions, launch
  and navigation timings and outcome. Redirect count is unavailable unless measured.
- Classifications: usable_content, empty_page, access_limited, server_error,
  network_error, unknown. Final HTTP 401/403/429/468 are access-limited. The collector
  does not inspect challenge-provider markup, scripts, IDs or titles; a HTTP 200 page is
  handled by its generic visible-content result after the configured navigation wait.
- Browser collection always waits [browser].post_navigation_wait_ms (default
  10000, 0 disables waiting) after goto, allowing normal document navigation.
  Record initial_http_status and the final main-document response; only classify
  the final response and DOM. Retain configured/actual wait duration, outcome and
  document response count. No challenge-driven waiting or provider-specific recognition
  is added.
  No persistent profile, fingerprint, custom UA, retry navigation, challenge clicks,
  solver, proxy rotation or login automation is added.
- Classify before schema inference, including pasted HTML. Reject script/style-only
  pages. Classification uses only generic HTTP and visible-content signals.
- Access limits stop fallback; launch/network/empty/server failures may use configured
  HTTP fallback. Failed attempts persist as events even with business retention disabled.
- Health is passive: sdk_installed/binary_ready are readiness, launch_verified and
  navigation_verified describe the last actual attempt and include last_probe_at.
  It does not download or launch a browser. Launch success is independent of page access.

## Metrics and provenance

GET /api/runs/{task_id}/metrics returns versioned metrics and a comparison fingerprint.
Each metric has value, source (measured/estimated/unavailable), unit, sample_count and
reason for missing data. Percentiles use linear interpolation of empirical samples;
one sample is allowed but the count must be visible. No claim of population performance.
Queue time is wall-clock timestamp difference; workflow/node/call times are monotonic.
Quality score means verifier score, never annotated accuracy. Missing/repair/evidence
counts, coverage, schema/program/page signatures, model call counts, token completeness
and actual/estimated usage are persisted separately from full page payloads.
Nested values in diagnostics are redacted. URLs omit userinfo, query and fragment.

GET /api/observability/summary extends existing fields with metric envelopes for
failure rate, P50/P95/P99, queue and node times, launch/collection success, fallback,
access limits, schema failures, reuse, verification, evidence and repair outcomes.
Root tasks only; zero denominators are unavailable with reasons. Rates use actual
attempt or eligible task denominators, not all submitted tasks indiscriminately.

Model calls are instrumented at the HTTP boundary: purpose, field, result, latency,
actual input/output tokens, missing usage count, estimated input/output tokens and
estimation formula. No full prompts/response text/credentials in events. No outgoing
HTTP request means zero actual calls, not a failed provider call. Zero calls cost zero.
Field repair records pre/post values in business state for offline gold scoring, not
diagnostic logs; repaired is not synonymous with correct or verifier-supported.

Benchmark scoring uses field confidence and configured confidence threshold, includes
required fields absent from gold, type constraints and unknown keys, evidence coverage
separate from precision, and repair correctness before/after divided by attempted
fields. Non-program methods have no reuse rate. Actual token totals are unavailable
if any real call omitted usage; partial totals and missing-call counts remain visible.
Shared initial deterministic ProgramSpec and its signature are used by all program
methods; Ours Full explicitly enables verifier-directed repair. Direct LLM receives
no hidden target schema; a single generic record call replaces fixed domain fields.

## Iterations

POST /api/rsi/iterations accepts experiment_id, optional parent_iteration_id,
baseline_run_id, candidate_run_id, hypothesis_id, hypothesis, intervention, change_set_id.
GET /api/rsi/iterations/{iteration_id} retrieves immutable evaluation and measurements.
POST /api/rsi/iterations/{iteration_id}/rollback records a human rollback decision and
reason; it does not undo files, mutate rules, or change the original runs.
Errors: 404 unknown run/iteration/parent; 422 invalid fields; 409 nonterminal runs or
invalid rollback. Comparable completed extraction runs require same nonempty page hash,
schema signature, model name, and repair/reuse mode. Program signatures may differ.
Unknown/failed/incomparable or missing guardrail quality leads to blocked, regressions/no improvement to
rejected, sufficient improvement within latency guardrail to accepted. Missing runtime
blocks evaluation. Thresholds are [rsi].min_quality_delta (>0, default .01) and
[rsi].max_latency_regression_ratio (>=0, default .2) in config.toml and saved per iteration.
Evaluation policy version 2 uses proxy quality =
0.5 * verification_score + 0.3 * field_completion_rate + 0.2 * evidence_coverage.
Each component and required_field_missing_rate must be measured and versioned;
any verifier, completion or evidence decrease, or required-missing increase, rejects
the candidate. The weighted gain must meet min_quality_delta. Iteration output
explicitly states no gold accuracy and records the evaluation policy version.
Rollback is idempotent and remains queryable. Metrics failures never overwrite source
tasks; report an unavailable/blocked evaluation and safe error reason.

Persistence: runtime_tasks/runtime_events retain metrics in their existing JSON;
rsi_iterations has iteration_id, experiment_id, status, payload_json and created_at.
No secrets/full input snapshots are copied to RSI records. Hypothesis and intervention
are redacted. No new workflow replaces required LangGraph extraction/benchmark nodes.

## Acceptance

New feature steps must have exact bindings with meaningful assertions, not generic
no-op fallbacks. Tests cover HTTP 200 challenge, ordinary WAF article, no fallback on
468, launch timeout, redirect final URL, cleanup, nested redaction, retained metrics
without business HTML, partial token usage, wrong-to-right repair and incomparability.
Live MineBBS is a bounded opt-in smoke, never an offline test dependency. Stop on access
limits and do not solve challenges. Use local controlled pages for reproducible success.
