# WebStruct-Agent

WebStruct-Agent is a local research prototype for the undergraduate thesis project:

`基于多 Agent 协同的网页信息结构化抽取系统`

The project is an information extraction workbench, not a commercial SaaS product. The MVP focuses on a runnable local demo, a clear LangGraph-based workflow foundation, schema-first extraction, evidence-aware results, and benchmark support.

This repository follows a **spec-first + BDD** discipline: behavior is defined in
`specs/features/*.feature` first, then automated with `pytest-bdd`, and only then implemented
inside a feature center. See [`specs/README.md`](./specs/README.md).

## Tech Stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite (default local database) or PostgreSQL (Docker Compose)
- LangGraph
- CloakBrowser SDK (rendered collection adapter; HTTP fallback is explicit)
- pytest + pytest-bdd

Frontend:

- React
- Vite
- TypeScript

LLM:

- DeepSeek is the default OpenAI-compatible provider.
- Runtime settings and sensitive credentials are loaded only from the local `config.toml`.

## Project Structure

```text
webstruct-agent/
  README.md
  AGENTS.md
  specs/                 spec-first 唯一事实来源：功能中心行为契约
    feature-centers.md   功能中心 ↔ 实现 ↔ 测试 的索引
    features/*.feature   Gherkin 场景（pytest-bdd 直接执行这些文件）
  backend/
  frontend/
  data/
  docs/
```

Backend package layout — organized into **feature centers** plus a shared **platform**:

```text
backend/app/
  contracts/    类型化契约对象：SchemaSpec / ProgramSpec / EvidenceBundle /
                VerificationReport / AgentRunTrace / GraphRunState
  features/     功能中心，每个中心自带 router / service / workflow / repository
    ops_center/           健康检查与运行保障
    schema_center/        用户/模型 Schema、校验与版本留存
    page_center/          页面采集与多视图归一化
    program_center/       ProgramSpec 确定性生成、安全净化、已验证程序复用
    extraction_center/    LangGraph 九节点主链路 + 证据/校验/修复
    evaluation_center/    五种方法对比评测与指标报告
    review_center/        人工复核回写与程序登记
    spec_assistant_center/对话式 Schema/ProgramSpec 修订
  platform/     跨中心复用的技术能力
    config.py           运行时配置与模型凭据
    persistence/        引擎、自动迁移、ORM 模型、通用 JSON 载荷读写
    llm/                ModelAdapter 协议及其实现（未配置时显式失败）
    tracing/            统一的图节点追踪执行器
    text_processing.py  文本归一化与证据片段处理
```

Each feature center maps 1:1 to a `.feature` spec and a BDD test module.
The full mapping lives in [`specs/feature-centers.md`](./specs/feature-centers.md).

Frontend source layout:

```text
frontend/src/
  api/          typed backend API clients
  components/   reusable workbench presentation panels
  features/     feature-aligned panels (extraction / schema / program / verification /
                review / evaluation)
  lib/          formatting, sample HTML, schema draft, and review helpers
  pages/        route-level page composition
  types/        shared WebStruct TypeScript contracts
```

## Snapshot Rule Builder

Create mode moves from URL-first extraction into a two-column snapshot workspace.
`FieldSchemaAgent` proposes only the active field set, while `FieldValueAgent`
works on one field at a time and returns value, page evidence, and a safe
field-local ProgramSpec. Field edits never re-collect the page. The quality
check replays the candidate against the saved snapshot and can optionally
validate a different same-origin page with the same structure before a rule is
marked verified.

The collaboration endpoints are:

```text
POST /api/spec-assistant/fields/schema
POST /api/spec-assistant/fields/value
POST /api/spec-assistant/fields/check
```

Test layout:

```text
backend/tests/
  conftest.py   共享夹具（默认断开真实 LLM 调用；db 标记按数据库可达性跳测）
  bdd/          行为测试：每个模块绑定一个 specs/features/*.feature
  unit/         按功能中心分组的细粒度单元测试
  support/      测试数据基元
```

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy the configuration template and edit it locally:

```powershell
Copy-Item config.example.toml config.toml
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

> `config.toml` is resolved from the project root and relative paths are anchored to
> that file, so the service can be started from either the project root or `backend/`.

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

The Vite dev server proxies `/api` requests using `[frontend].api_target`
from the project-root `config.toml`. Change that TOML value and restart Vite
when the backend runs on another local port.

## LLM Configuration

LLM fallback uses an OpenAI-compatible chat-completions API. DeepSeek is the default provider.
Set the model key, optional browser license, and `browser.auto_download` directly in `config.toml`.
The file is ignored by Git and is mounted read-only in Docker. Environment variables
and `.env` are not loaded or used as overrides.
When `browser.auto_download = true`, a missing pinned CloakBrowser binary is provisioned
on the first URL collection into `browser.cache_path`; health checks report the pending
browser state until that collection occurs.

## Database Configuration

The `[database].url` item in `config.toml` decides the storage backend:

```text
sqlite:///./webstruct_agent.db                                      # 本地默认，开箱即用
postgresql+psycopg://webstruct:webstruct@127.0.0.1:5432/webstruct_agent  # Docker Compose
```

Tables are created/updated automatically on backend startup (SQLAlchemy metadata plus
idempotent column additions).

## Docker Setup

Docker Compose packages PostgreSQL, FastAPI, and the Nginx-hosted frontend:

```powershell
docker compose up --build
```

Then open:

```text
http://127.0.0.1:5173
```

The compose stack starts, with dependency gating by healthcheck:

- `postgres`: PostgreSQL 16 with persistent volume `postgres_data`
- `backend`: FastAPI service on `http://127.0.0.1:8000` (waits for healthy postgres)
- `frontend`: Nginx static frontend on `http://127.0.0.1:5173` (waits for healthy backend),
  proxying `/api` to backend

Both images ship a
`.dockerignore` so local `.venv`, `node_modules`, caches, logs, and tests never enter the
build context.

For Docker, mount the same local `config.toml` read-only and set the desired database
and model values there.

## Core APIs

The backend exposes a runnable LangGraph extraction workflow:

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

Submit an extraction (the response is a 202 queued receipt):

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/extract `
  -Body '{"target_url":"https://example.edu/notice/001","html":"<html><body><h1>课程公告</h1></body></html>","schema_spec":{"name":"课程公告","domain":"course_notice","description":"课程公告字段","fields":[{"name":"title","description":"公告标题","type":"text","required":true,"aliases":["标题"],"examples":[]}]}}'
```

Use `GET /api/runs/{task_id}` and `GET /api/runs/{task_id}/events?after_cursor=...`
for progress, then `GET /api/extract/{task_id}` for the terminal result.

Revise the current task's SchemaSpec and ProgramSpec with the spec assistant:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/spec-assistant/revise `
  -Body '{"task_id":"extract_xxx","message":"把作者字段对应到发布单位，发布日期取正文上方日期","schema_spec":{"name":"当前Schema","domain":"notice","fields":[{"name":"title","description":"标题","type":"text","required":true,"aliases":["标题"],"examples":[]}]},"program_spec":null}'
```

The assistant endpoint reads the saved task's page `ViewBundle`, returns a
draft revised `SchemaSpec` and a **sanitized** `ProgramSpec` (unsupported strategies are
dropped and reported in `validation_issues`), and does not mark the draft as user verified.

Run a benchmark only when every item supplies an explicit SchemaSpec:

```powershell
Invoke-RestMethod `
  -Method Post `
  -ContentType "application/json" `
  -Uri http://127.0.0.1:8000/api/benchmark/run `
  -Body '{"dataset":{"name":"my-dataset","items":[{"item_id":"sample-1","html":"<html>...</html>","schema_spec":{"name":"课程公告","domain":"course_notice","description":"课程公告字段","fields":[{"name":"title","description":"公告标题","type":"text","required":true,"aliases":["标题"],"examples":[]}]}, "gold_record":{"title":"课程公告"}}]}}'
```

Persisted results can be read back with:

```text
GET /api/extract/{task_id}
GET /api/benchmark/reports/{task_id}
GET /api/schemas/versions
GET /api/program-specs/verified
```

## Tests

Run all backend tests (BDD scenarios + unit tests):

```powershell
cd backend
pytest
```

Run only one feature center's behavior suite:

```powershell
cd backend
pytest tests/bdd/test_extraction_center.py
pytest -k "评测"           # 中文场景名可直接用于 -k 过滤
```

Notes:

- Tests never call real LLM providers: a conftest fixture disables credentials by default,
  so failures are deterministic and offline-safe.
- Cases requiring a real database are marked `@pytest.mark.db` and skipped only when the
  configured database is unreachable. With the default SQLite URL, the full suite runs locally.

Lint/fix imports before committing:

```powershell
cd backend
python -m ruff check app tests
```

Build the frontend:

```powershell
cd frontend
npm run build
```

## Current Stage

Stage 4 is a thesis-ready local demo foundation:

- typed contract objects for SchemaSpec, ProgramSpec, evidence, verification, graph state, and benchmark reports
  - no runtime built-in domain schemas; user/model-generated Schema versions remain persisted
- LangGraph extraction workflow with the required named nodes and status-guarded edges
- URL-first create mode where page collection and view normalization happen
  before SchemaAgent inference unless the user explicitly supplies a schema
  - CloakBrowser-first rendered page collection with explicitly recorded HTTP fallback
- normalized page text plus DOM/text blocks with selector and xpath hints
- safe ProgramSpec DSL execution without `eval` or `exec`
- DeepSeek/OpenAI-compatible LLM fallback through `ModelAdapter`, failing explicitly without credentials
- fallback decision routing for missing, low-confidence, weak-evidence, confused, or type-invalid fields
- field-level evidence, confidence, verification, and one repair pass
- persistence for extraction run payloads, schema versions, benchmark reports, user-verified programs, and manual reviews
- failed runs keep the `failed` status instead of being masked as completed
- automatic table migration on backend startup
- Docker Compose packaging with healthcheck-gated startup
- benchmark workflow with the required benchmark nodes and five comparison methods
- React extraction workbench with schema selection/editing, schema validation, URL/HTML input, results, evidence, verification report, agent trace, and benchmark table
- manual review API and frontend panel for confirming/editing field values
- SpecCollaborationAgent API and frontend panel for human-AI draft revision of
  SchemaSpec and ProgramSpec from the current task's page context
- user-verified ProgramSpec storage and reuse for matching schema signatures
- spec-first BDD suite wired to `specs/features/*.feature` for all eight feature centers

Thesis support artifacts are available under `docs/`: demo screenshot, live and offline benchmark tables, plus success/failure case analysis.
