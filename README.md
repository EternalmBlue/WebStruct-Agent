# WebStruct-Agent

WebStruct-Agent is a local research prototype for the undergraduate thesis project:

`基于多 Agent 协同的网页信息结构化抽取系统`

The project is an information extraction workbench, not a commercial SaaS product. The MVP focuses on a runnable local demo, a clear LangGraph-based workflow foundation, schema-first extraction, evidence-aware results, and benchmark support.

## Tech Stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- LangGraph
- Playwright Python
- pytest

Frontend:

- React
- Vite
- TypeScript

LLM:

- DeepSeek is the default OpenAI-compatible provider.
- Model credentials are read from environment variables only.

## Project Structure

```text
webstruct-agent/
  README.md
  AGENTS.md
  .env.example
  backend/
  frontend/
  data/
  docs/
```

Backend package layout:

```text
backend/app/
  api/          FastAPI routers only
  benchmark/    benchmark dataset, metrics, benchmark_nodes, and LangGraph workflow
  core/         settings and runtime configuration
  domain/       Pydantic models, API contracts, and typed graph state
  extraction/   schema catalog, Playwright collection, page/view normalization,
                fallback routing, ProgramSpec execution, verifier, repair,
                agent_nodes, and LangGraph workflow
  storage/      SQLAlchemy engine, ORM models, automatic migrations, and
                domain-specific repositories
  workflows/    shared traceable LangGraph node helpers
```

Frontend source layout:

```text
frontend/src/
  api/          typed backend API clients
  components/   reusable workbench presentation panels
  lib/          formatting, sample HTML, schema draft, and review helpers
  pages/        route-level page composition
  types/        shared WebStruct TypeScript contracts
```

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install Playwright browser binaries:

```powershell
cd backend
python -m playwright install
```

Start the backend:

```powershell
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/api` requests to the FastAPI backend at `http://127.0.0.1:8000`.
If the backend is running on another local port, start Vite with `VITE_API_TARGET`:

```powershell
cd frontend
$env:VITE_API_TARGET="http://127.0.0.1:8010"
npm run dev
```

## LLM Configuration

LLM fallback uses an OpenAI-compatible chat-completions API. DeepSeek is the default provider.
Set credentials in the environment or local `.env` file. Do not hard-code API keys in source code.

Copy `.env.example` to `.env` when local overrides are needed:

```powershell
Copy-Item .env.example .env
```

## Docker Setup

The recommended deployable local setup uses Docker Compose with PostgreSQL,
FastAPI, and Nginx-hosted frontend containers:

```powershell
docker compose up --build
```

Then open:

```text
http://127.0.0.1:5173
```

The compose stack starts:

- `postgres`: PostgreSQL 16 with persistent volume `postgres_data`
- `backend`: FastAPI service on `http://127.0.0.1:8000`
- `frontend`: Nginx static frontend on `http://127.0.0.1:5173`, proxying `/api` to backend

Backend startup runs automatic table migration through SQLAlchemy metadata:
missing tables are created and missing columns are added idempotently.

For LLM fallback inside Docker, copy `backend.env.example` to `backend.env` and
fill provider settings locally. `backend.env` is ignored by Git.

## Core APIs

The backend now exposes a runnable LangGraph extraction workflow:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/schemas
```

Validate a custom schema before extraction:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/schemas/validate `
  -Body '{"name":"高校通知","domain":"university_notice","fields":[{"name":"title","description":"通知标题","type":"text","required":true,"aliases":["标题"],"examples":[]}]}'
```

Run the built-in demo extraction:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/extract `
  -Body '{"target_url":"https://example.edu/notice/001","html":"<html><body><h1>关于开展2026年大学生创新训练项目申报的通知</h1><p>发布单位：教务处</p><p>发布日期：2026年06月12日</p><p>申报截止：2026年06月30日</p></body></html>","schema_name":"高校通知"}'
```

Revise the current task's SchemaSpec and ProgramSpec with the spec assistant:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/spec-assistant/revise `
  -Body '{"task_id":"extract_xxx","message":"把作者字段对应到发布单位，发布日期取正文上方日期","schema_spec":{"name":"当前Schema","domain":"notice","fields":[{"name":"title","description":"标题","type":"text","required":true,"aliases":["标题"],"examples":[]}]},"program_spec":null}'
```

The assistant endpoint reads the saved task's page `ViewBundle`, returns a
draft revised `SchemaSpec` and safe `ProgramSpec`, and does not mark the draft
as user verified.

Run the built-in benchmark demo:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/benchmark/run `
  -Body '{"schema_name":"高校通知"}'
```

Persisted results can be read back with:

```text
GET /api/extract/{task_id}
GET /api/benchmark/reports/{task_id}
```

## Tests

Run backend tests:

```powershell
cd backend
pytest
```

Persistence/API integration tests require a reachable PostgreSQL database from
`DATABASE_URL`. Start `docker compose up -d postgres` first to run the full
backend suite locally.

Build the frontend:

```powershell
cd frontend
npm run build
```

## Current Stage

Stage 4 is a thesis-ready local demo foundation:

- typed domain models for SchemaSpec, ProgramSpec, evidence, verification, graph state, and benchmark reports
- built-in schemas for 高校通知, 招聘公告, and 政务公开 / 政策法规
- LangGraph extraction workflow with the required named nodes
- URL-first create mode where page collection and view normalization happen
  before SchemaAgent inference unless the user explicitly supplies a schema
- Playwright-first rendered page collection with urllib fallback
- normalized page text plus DOM/text blocks with selector and xpath hints
- safe ProgramSpec DSL execution without `eval` or `exec`
- DeepSeek/OpenAI-compatible LLM fallback through `ModelAdapter`
- fallback decision routing for missing, low-confidence, weak-evidence, confused, or type-invalid fields
- field-level evidence, confidence, verification, and one repair pass
- PostgreSQL persistence for extraction run payloads, schema versions, and benchmark reports
- automatic table migration on backend startup
- Docker Compose packaging for PostgreSQL, backend, and frontend
- benchmark workflow with the required benchmark nodes and five comparison methods
- React extraction workbench with schema selection/editing, schema validation, URL/HTML input, results, evidence, verification report, agent trace, and benchmark table
- manual review API and frontend panel for confirming/editing field values
- SpecCollaborationAgent API and frontend panel for human-AI draft revision of
  SchemaSpec and ProgramSpec from the current task's page context
- user-verified ProgramSpec storage and reuse for matching schema signatures
- schema version read-back through `GET /api/schemas/versions`

Thesis support artifacts are available under `docs/`: demo screenshot, live and offline benchmark tables, plus success/failure case analysis.
