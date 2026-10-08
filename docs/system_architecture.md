# System Architecture

## Overview

The system is a monorepo with a FastAPI backend, a React/Vite frontend,
persistence (SQLite locally, PostgreSQL in Docker Compose), Docker Compose
packaging, and data folders for samples and benchmark gold records.

Behavior is specified first: every feature center has a Gherkin contract under
`specs/features/`, executed by `backend/tests/bdd/`. See `specs/README.md` for the
spec-first workflow and `specs/feature-centers.md` for the center-to-code mapping.

## Backend

- FastAPI exposes HTTP APIs.
- Pydantic defines typed request and response models.
- SQLAlchemy manages PostgreSQL persistence.
- LangGraph orchestrates extraction and benchmark workflows through typed `StateGraph` definitions.

Backend packages are organized into **feature centers** (`app/features/`) plus a
shared technical **platform** (`app/platform/`) and typed **contracts**
(`app/contracts/`). Each feature center owns its router, service/workflow logic and
repository, and is described by exactly one `.feature` spec:

| Feature center | Owns | Spec |
| --- | --- | --- |
| `ops_center` | 健康检查、运行保障 | `ops-center.feature` |
| `schema_center` | 用户/模型 Schema、校验规则、版本留存 | `schema-center.feature` |
| `page_center` | 页面采集、多视图归一化 | `page-center.feature` |
| `program_center` | ProgramSpec 生成/净化/复用 | `program-center.feature` |
| `extraction_center` | LangGraph 九节点主链路 | `extraction-center.feature` |
| `evaluation_center` | 五种方法对比评测与指标 | `evaluation-center.feature` |
| `review_center` | 人工复核回写与程序登记 | `review-center.feature` |
| `spec_assistant_center` | 对话式规格修订 | `spec-assistant-center.feature` |

Platform modules shared across centers:

- `platform/configuration/`: TOML settings, credentials, validation, and public projection
- `platform/persistence/`: engine, automatic migration, ORM models, generic JSON payload store
- `platform/llm/`: `ModelAdapter` protocol, OpenAI-compatible adapter, unconfigured adapter, factory
- `platform/tracing/`: `run_traced_node`, producing `AgentRunTrace` for every graph node
- `platform/text_processing.py`: text normalization and evidence snippet handling

Routers are mounted centrally by `features.register_feature_routers(app)`, driven by
the `FEATURE_CENTERS` registry, so adding a center is a one-line change.

Local persistence defaults to SQLite via `[database].url` in `config.toml`;
Docker Compose reads the same mounted TOML file.

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
- `GET /api/program-specs/verified`
- `POST /api/runs/{task_id}/retry`

The extraction workflow stores completed run payloads for local traceability. Failed
runs keep `status = "failed"` instead of being masked as completed, so replaying
`GET /api/extract/{task_id}` reflects reality. Validated or extraction-used schema
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
   CloakBrowser rendered collection for HTTP(S) pages and falls back to `urllib`
   only when explicitly enabled.
2. `view_normalizer_node` creates normalized text, lines, headings, and text
   blocks with selector/xpath hints.
3. `schema_agent_node` resolves an explicit user-supplied `SchemaSpec` or asks
   the LLM to infer a page-specific schema from the current `ViewBundle`.
   No built-in domain schema is used. Persisted runs also record the schema version/signature
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
