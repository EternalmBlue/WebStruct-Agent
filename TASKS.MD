# WebStruct-Agent Tasks

This task list is aligned with the proposal and task book for the thesis project
`基于多 Agent 协同的网页信息结构化抽取系统设计与实现`.

## Current Milestone

The project has passed the opening-report stage and now has a runnable local
demo foundation: backend workflow, frontend extraction workbench, Playwright
collection, real fallback decision flow, benchmark comparison, persistence
read-back APIs, manual review, PostgreSQL persistence with automatic migration,
schema version persistence, user-verified ProgramSpec reuse, Docker packaging,
screenshots, experiment tables, and case analysis. Larger
external datasets remain future work beyond the thesis prototype.

## P0 - Must Finish For A Credible Demo

- [x] Replace demo page collection with Playwright-based rendered collection.
  - Captures rendered HTML for HTTP(S) pages with urllib fallback.
  - Captures visible text through normalization.
  - Captures DOM/text blocks with selector/xpath hints.
  - Stores page metadata in `PageObservation` and `ViewBundle`.

- [x] Build the real frontend extraction workbench.
  - Schema selector for built-in schemas.
  - URL input and sample HTML input.
  - Run extraction button.
  - Extraction result table.
  - Field evidence panel.
  - Verification report panel.
  - Agent trace display.
  - Clear loading, success, and error states.

- [x] Implement schema editing in the UI.
  - Start from built-in templates.
  - Add, edit, and remove fields.
  - Configure type, required flag, description, and aliases.
  - Validate through the backend schema validation endpoint before extraction.

- [x] Implement real fallback decision flow.
  - Add a DecisionRouter or FallbackDecider.
  - Trigger fallback only for missing, low-confidence, confused, or weak-evidence
    fields.
  - Keep DeepSeek/OpenAI-compatible LLM credentials environment-only.
  - Keep missing LLM credentials as an explicit fallback error, not fake data.
  - Re-run verification after fallback merges results.

- [x] Strengthen verifier checks.
  - Required field missing.
  - Field type mismatch.
  - Date normalization failure.
  - Evidence text supports value.
  - Publish date versus deadline confusion.
  - Empty or low-quality evidence.
  - Confidence score calculation.

- [x] Expand benchmark datasets beyond the original single-sample demo fixtures.
  - Include at least three Chinese domains:
    - `高校通知`
    - `招聘公告`
    - `政务公开 / 政策法规`
  - Added 9 checked-in samples across three domains for visible comparison tables.
  - Keep gold labels in a consistent format.

- [x] Produce benchmark comparison output for the current demo dataset.
  - Direct LLM.
  - LLM + Schema.
  - Program Only.
  - Hybrid without Verifier.
  - Ours Full.
  - Metrics: field accuracy, required-field missing rate, schema adherence,
    evidence precision, average confidence, estimated token cost, runtime,
    ProgramSpec reuse rate, selective accuracy, and optional repair success rate.
  - Thesis tables and case analysis are available in docs/experiment_results_live.md and docs/experiment_results.md.

## P1 - Needed For Thesis Quality

- [x] Add persistence coverage beyond extraction payloads.
  - [x] Schema versions.
  - [x] User-verified ProgramSpec records.
  - [x] Verification reports inside extraction run payloads.
  - [x] Benchmark reports.
  - [x] Agent traces inside persisted payloads.
  - [x] PostgreSQL runtime persistence.
  - [x] Automatic table migration on backend startup.

- [x] Add API endpoints required by the frontend.
  - `GET /api/schemas`
  - schema validation endpoint
  - extraction run endpoint
  - extraction run detail endpoint
  - benchmark run endpoint
  - benchmark report detail endpoint

- [x] Improve ProgramSpec reuse.
  - Store user-verified ProgramSpec.
  - Reuse ProgramSpec for matching schema signatures.
  - Track ProgramSpec reuse rate in benchmark reports.
  - Final thesis experiments should make reuse-rate calculation
    dataset-instance aware.

- [x] Improve repair behavior.
  - Uses verifier issues and `FallbackDecider` to repair missing, confused,
    invalid, low-confidence, and weak-evidence fields.
  - Records provider/key failures as explicit field-level fallback failures.
  - Re-runs verification after repair.
  - Keeps repair attempts bounded.

- [x] Add frontend benchmark screen.
  - Select dataset/schema.
  - Run benchmark.
  - Show comparison table.
  - Show metric explanations and representative cases remain P2 polish.

- [x] Add frontend manual review flow.
  - Let users confirm or edit field values.
  - Save field review notes.
  - Mark ProgramSpec as user verified when appropriate.
  - Rewriting persisted extraction results from review edits remains optional
    polish.

- [x] Add more tests around edge cases.
  - Missing fields.
  - Multiple date candidates.
  - Deadline versus publish date confusion.
  - Unsupported ProgramSpec strategy.
  - Failed page collection.
  - Benchmark no-persistence behavior.
  - Current coverage includes missing required fallback failure, failed page
    collection, API detail read-back, graph compile, and benchmark methods.

- [x] Package the project with Docker.
  - PostgreSQL service with health check and persistent volume.
  - FastAPI backend image with Playwright browser dependencies.
  - Nginx frontend image proxying `/api` to backend.
  - `docker compose up --build` as the deployable local startup path.

## P2 - Polish And Paper Support

- [x] Update `docs/product_requirements.md` after frontend behavior is real.
- [x] Update `docs/system_architecture.md` after Playwright and fallback routing
  are implemented.
- [x] Update `docs/langgraph_workflow.md` with final graph routing, including
  fallback and repair paths.
- [x] Update `docs/schema_spec.md` with final schema-editing examples.
- [x] Update `docs/program_spec.md` with final DSL examples and safety rules.
- [x] Update `docs/evidence_spec.md` with final evidence and confidence scoring.
- [x] Update `docs/benchmark_design.md` with final dataset, methods, and metrics.
- [x] Update `docs/thesis_mapping.md` so each thesis chapter maps to actual
  modules, screenshots, tests, and experiment outputs.
- [x] Add screenshots for the final demo flow.
- [x] Prepare thesis experiment tables from benchmark output.
- [x] Write success-case and failure-case analysis for the paper.

## Validation Checklist

Run this after backend changes:

```powershell
cd F:\WebStruct-Agent\backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -c "from app.main import app; from app.extraction.workflow import build_extraction_graph; from app.benchmark.workflow import build_benchmark_graph; build_extraction_graph(); build_benchmark_graph(); print('ok')"
```

Run this after frontend changes:

```powershell
cd F:\WebStruct-Agent\frontend
npm run build
```

Run this before claiming demo readiness:

```powershell
cd F:\WebStruct-Agent\backend
.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.domain import ExtractionRequest, BenchmarkRequest; from app.extraction.workflow import run_extraction_workflow; from app.benchmark.workflow import run_benchmark_workflow; html=Path(r'F:\WebStruct-Agent\data\samples\university_notice_001.html').read_text(encoding='utf-8'); s=run_extraction_workflow(ExtractionRequest(target_url='file://F:/WebStruct-Agent/data/samples/university_notice_001.html', html=html, schema_name='高校通知', persist_result=False)); b=run_benchmark_workflow(BenchmarkRequest(schema_name='高校通知')); print(s.get('status'), len(s.get('agent_traces', []))); print(b.get('status'), len(b.get('agent_traces', [])))"
```

## Suggested Delivery Order

1. Playwright collector.
2. Extraction workbench frontend.
3. Schema editor and validation.
4. Verifier/fallback/router completion.
5. Benchmark dataset expansion.
6. Benchmark UI and final experiment output.
7. Documentation and thesis chapter mapping update.
