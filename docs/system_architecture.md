# System Architecture

## Overview

The system is a monorepo with a FastAPI backend, a React/Vite frontend,
PostgreSQL persistence, Docker Compose packaging, and data folders for samples
and benchmark gold records.

## Backend

- FastAPI exposes HTTP APIs.
- Pydantic defines typed request and response models.
- SQLAlchemy manages PostgreSQL persistence.
- LangGraph orchestrates extraction and benchmark workflows through typed `StateGraph` definitions.

Backend packages are organized by responsibility:

- `app/api/`: HTTP transport and response assembly
- `app/domain/`: typed objects, API models, and graph state
- `app/extraction/`: schema catalog, Playwright collection, normalization, planning, fallback decisions, ProgramSpec execution, verification, repair, agent nodes, and extraction workflow
- `app/benchmark/`: checked-in evaluation fixtures, method runners, metrics, benchmark nodes, and benchmark workflow
- `app/storage/`: database engine, ORM models, automatic table migration, startup initialization, and domain-specific repositories
- `app/workflows/`: shared traceable node helpers

Implemented API groups:

- `GET /api/health`
- `GET /api/schemas`
- `POST /api/schemas/validate`
- `GET /api/schemas/versions`
- `POST /api/extract`
- `GET /api/extract/{task_id}`
- `POST /api/spec-assistant/revise`
- `POST /api/benchmark/run`
- `GET /api/benchmark/reports/{task_id}`
- `POST /api/reviews/manual`

The extraction workflow stores completed run payloads in PostgreSQL for local traceability.
Validated or extraction-used schema versions are persisted by stable schema
signature, and the extraction response includes the schema version used for the
run. Benchmark reports are also persisted and can be read back by task id.
Manual reviews and user-verified ProgramSpec records are stored for local
traceability and schema-signature-based reuse.

Spec collaboration is exposed through `POST /api/spec-assistant/revise`. The
endpoint reads the persisted extraction task's `ViewBundle`, sends the page
HTML/text plus the current `SchemaSpec` and `ProgramSpec` to
`SpecCollaborationAgent`, and returns a draft revised `SchemaSpec` plus safe
`ProgramSpec`. The draft is not automatically marked as user verified.

Backend startup runs automatic migration with SQLAlchemy metadata: missing
tables are created and missing columns are added idempotently. Docker Compose
starts PostgreSQL, backend, and frontend containers for a deployable local
prototype.

## Extraction Pipeline

1. `page_collector_node` uses supplied HTML when present; otherwise it tries
   Playwright rendered collection for HTTP(S) pages and falls back to `urllib`.
2. `view_normalizer_node` creates normalized text, lines, headings, and text
   blocks with selector/xpath hints.
3. `schema_agent_node` resolves an explicit user-supplied `SchemaSpec` or asks
   the LLM to infer a page-specific schema from the current `ViewBundle`.
   Built-in schemas are used only as explicit overrides or fallback when schema
   inference cannot run. Persisted runs also record the schema version/signature
   used by the task.
4. `planner_agent_node` builds an extraction plan.
5. `programmer_agent_node` uses an explicit provided ProgramSpec when supplied
   by the spec assistant rerun path, reuses a user-verified ProgramSpec only in
   run mode, otherwise it builds a safe page-specific ProgramSpec DSL.
6. `extractor_agent_node` runs deterministic ProgramSpec strategies first.
7. `verifier_agent_node` checks required fields, types, date normalization,
   evidence support, confidence, and publish/deadline confusion.
8. `repair_agent_node` uses `FallbackDecider` to call the real LLM provider only
   for fields that need fallback. Missing keys or provider errors are recorded as
   explicit field-level fallback failures.
9. `result_persist_node` persists the final state when requested.

## Frontend

- React renders the local workbench UI.
- Vite handles development and build tooling.
- The frontend calls backend APIs through the `/api` proxy.
- Source files are split into typed API clients (`src/api`), workbench panels
  (`src/components/dashboard`), reusable helpers (`src/lib`), page composition
  (`src/pages`), and shared contracts (`src/types`).
- The workbench supports URL-first schema creation, optional schema
  selection/editing, schema validation, URL/HTML input, extraction results,
  field evidence, verification report, agent trace, human-AI spec
  collaboration, manual review, user-verified ProgramSpec marking, and
  benchmark comparison.

## Data

- `data/samples/` stores sample pages or input fixtures.
- `data/gold/` stores benchmark gold records.
