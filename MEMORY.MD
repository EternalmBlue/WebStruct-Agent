# WebStruct-Agent Memory

This file records project facts that future contributors and agents should preserve.
It is not a replacement for source code, tests, or the thesis documents. When facts
drift, update this file after verifying the repository.

## Project Identity

- Repository path: `F:\WebStruct-Agent`
- Product name: `WebStruct-Agent`
- Thesis title: `基于多 Agent 协同的网页信息结构化抽取系统设计与实现`
- Project type: undergraduate thesis prototype and local research workbench
- Product boundary: not a commercial SaaS product
- Primary scenario: Chinese weakly structured web information extraction
- Core thesis line: schema-first extraction, LangGraph multi-agent workflow,
  ProgramSpec DSL, LLM fallback, field-level evidence, confidence, verification,
  and benchmark comparison

## Current Verified Status

Last verified on 2026-06-26.

- Current stage: Stage 4 thesis-ready local demo foundation.
- Overall thesis-delivery estimate: about 90 percent complete for the local
  undergraduate prototype; larger external benchmark scale remains future work.
- Backend tests without a reachable PostgreSQL service: `10 passed, 5 skipped,
  1 warning`; start PostgreSQL to run the skipped persistence/API integration tests.
- Backend smoke passes:
  - extraction workflow status: `completed`
  - extraction traces: 9 nodes
  - sample text blocks: 5
  - benchmark workflow status: `completed`
  - benchmark traces: 5 nodes
- Frontend build passes with `npm run build`.
- Docker Compose packaging exists for PostgreSQL, backend, and frontend; Docker
  daemon must be running before `docker compose up --build`.
- Thesis artifacts exist: `docs/demo-workbench.png`, `docs/experiment_results_live.md`, `docs/experiment_results_live.csv`, `docs/experiment_results.md`, and `docs/experiment_results.csv`.
- Residual scan is clean for legacy mock adapter names, sample-memory URLs,
  deprecated model flags, and hard-coded key fragments.

## Verified Commands

Use these as a quick health check when resuming work.

```powershell
cd F:\WebStruct-Agent\backend
.\.venv\Scripts\python.exe -m pytest
```

```powershell
cd F:\WebStruct-Agent\backend
.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.domain import ExtractionRequest, BenchmarkRequest; from app.extraction.workflow import run_extraction_workflow; from app.benchmark.workflow import run_benchmark_workflow; html=Path(r'F:\WebStruct-Agent\data\samples\university_notice_001.html').read_text(encoding='utf-8'); s=run_extraction_workflow(ExtractionRequest(target_url='file://F:/WebStruct-Agent/data/samples/university_notice_001.html', html=html, schema_name='高校通知', persist_result=False)); b=run_benchmark_workflow(BenchmarkRequest(schema_name='高校通知')); print(s.get('status')); print([t.name for t in s.get('agent_traces', [])]); print(b.get('status')); print([t.name for t in b.get('agent_traces', [])])"
```

```powershell
cd F:\WebStruct-Agent\frontend
npm run build
```

## Architecture Facts

- Backend framework: FastAPI, Pydantic, SQLAlchemy, PostgreSQL.
- Workflow runtime: LangGraph `StateGraph`.
- Frontend stack: React, Vite, TypeScript.
- LLM integration must stay behind `ModelAdapter`.
- DeepSeek is the default OpenAI-compatible LLM provider.
- LLM credentials must come from environment variables only.
- ProgramSpec deterministic extraction can run without an API key, but fields
  that require `llm_fallback` fail explicitly when no provider key is configured.

Backend package layout:

```text
backend/app/
  api/          FastAPI routers only
  benchmark/    benchmark dataset, metrics, benchmark_nodes, and LangGraph workflow
  core/         settings and runtime configuration
  domain/       Pydantic models, API models, and typed graph state
  extraction/   schema catalog, Playwright collection, normalization, planning,
                fallback decisions, ProgramSpec execution, verification,
                repair, agent_nodes, and workflow
  storage/      SQLAlchemy engine, ORM models, automatic migrations, and
                domain-specific repositories
  workflows/    shared traceable LangGraph node helpers
frontend/src/
  api/          typed backend API clients
  components/   dashboard presentation panels
  lib/          formatters, sample HTML, schema draft, and review helpers
  pages/        route-level page composition
  types/        shared TypeScript contracts
```

## Implemented Core

- Typed domain models exist for schema, page/view, extraction plan, ProgramSpec,
  extraction result, evidence, verification, traces, graph state, and benchmark.
- Built-in Chinese schemas exist for:
  - `高校通知`
  - `招聘公告`
  - `政务公开 / 政策法规`
- Required extraction graph nodes exist:
  - `schema_agent_node`
  - `page_collector_node`
  - `view_normalizer_node`
  - `planner_agent_node`
  - `programmer_agent_node`
  - `extractor_agent_node`
  - `verifier_agent_node`
  - `repair_agent_node`
  - `result_persist_node`
- Required benchmark graph nodes exist:
  - `dataset_loader_node`
  - `baseline_runner_node`
  - `ours_runner_node`
  - `metric_agent_node`
  - `report_agent_node`
- `ProgramSpec` is a controlled DSL and must not use `eval` or `exec`.
- Page collection tries Playwright for HTTP(S), falls back to `urllib`, and records
  text blocks with selector/xpath hints in page/view metadata.
- The frontend is a usable extraction workbench: schema selection/editing,
  backend schema validation, URL/HTML input, extraction results, field evidence,
  verification report, agent trace, and benchmark comparison table.
- `FallbackDecider` triggers real LLM fallback/repair only for missing,
  low-confidence, weak-evidence, confused, or invalid fields. Missing LLM
  credentials produce explicit `fallback_failed` field status and verifier issues.
- Extraction failures route to persistence/end instead of cascading into later
  missing-state errors.
- Storage initialization is guarded and runs automatic table migration.
- PostgreSQL persists extraction run payloads, schema versions, and benchmark report
  payloads; detail endpoints read them back.
- Schema versions are recorded by stable schema signature and can be read through
  `GET /api/schemas/versions`.
- Manual reviews can be submitted through `POST /api/reviews/manual`.
- User-verified ProgramSpec records are stored by schema signature and reused by
  `programmer_agent_node`; smoke currently reports `program_reused=True` after
  a verified schema has been stored.
- Docker Compose packages PostgreSQL, backend, and frontend for deployable local
  startup.
- Nested benchmark workflow calls should use `persist_result=False` to avoid
  redundant PostgreSQL writes.

## Known Gaps

- Benchmark currently uses 9 checked-in HTML fixtures across three Chinese domains.
  It is suitable for prototype thesis demonstration; larger external datasets remain future work.
- ProgramSpec reuse is surfaced in benchmark reports. Current demo fixtures are
  deterministic enough for prototype comparison; strict reuse-rate experiments
  should reset or control local PostgreSQL state.
- Manual review records currently save reviewed field values and notes, but do
  not yet rewrite persisted extraction results.

## Thesis Requirements To Preserve

The project should stay focused on:

- Schema-first task expression.
- Multi-agent collaboration represented by LangGraph typed nodes.
- Multi-view page representation.
- ProgramSpec generation and execution.
- Hybrid extraction with programmatic extraction and LLM fallback.
- Field-level evidence, confidence, and verification.
- Built-in benchmark and comparison experiments.

Do not spend thesis time on:

- user login
- paid SaaS features
- distributed crawling
- anti-bot bypass
- captcha handling
- arbitrary code execution
- unrelated dashboards
- generic chatbot UI unrelated to extraction

## Documentation Map

Maintain these thesis-support documents:

- `docs/product_requirements.md`
- `docs/system_architecture.md`
- `docs/langgraph_workflow.md`
- `docs/schema_spec.md`
- `docs/program_spec.md`
- `docs/evidence_spec.md`
- `docs/benchmark_design.md`
- `docs/thesis_mapping.md`

Update README only when startup commands, public behavior, API shape, or current
stage descriptions change.
