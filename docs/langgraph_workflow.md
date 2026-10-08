# LangGraph Workflow

## Requirement

LangGraph is the mandatory orchestration runtime for the core extraction workflow.

## Required Extraction Nodes

- `schema_agent_node`
- `page_collector_node`
- `view_normalizer_node`
- `planner_agent_node`
- `programmer_agent_node`
- `extractor_agent_node`
- `verifier_agent_node`
- `repair_agent_node`
- `result_persist_node`

## Required Benchmark Nodes

- `dataset_loader_node`
- `baseline_runner_node`
- `ours_runner_node`
- `metric_agent_node`
- `report_agent_node`

## Implemented Extraction Workflow

The backend implements the core extraction workflow in `app/extraction/workflow.py` as a LangGraph `StateGraph` with typed `GraphRunState`.

Node order:

1. `page_collector_node`
2. `view_normalizer_node`
3. `schema_agent_node`
4. `planner_agent_node`
5. `programmer_agent_node`
6. `extractor_agent_node`
7. `verifier_agent_node`
8. `repair_agent_node`
9. `result_persist_node`

Each node returns partial state updates and appends an `AgentRunTrace`. Nodes are also normal Python functions, so tests can call them through the compiled graph or directly in later unit tests.

URL-only extraction is page-first: `schema_spec` is treated as an explicit
override. When no schema is supplied, `schema_agent_node` infers a page-specific
`SchemaSpec` from the normalized `ViewBundle`, then `programmer_agent_node`
generates or accepts a safe page-specific `ProgramSpec`.

The graph uses guarded conditional edges after each extraction node. If a node
marks the state as failed, the graph routes directly to `result_persist_node` so
partial traces and errors remain visible instead of cascading into missing-state
exceptions.

Fallback routing is implemented inside `repair_agent_node`:

1. `verifier_agent_node` produces a `VerificationReport`.
2. `FallbackDecider` selects fields with missing required values, type mismatch,
   date normalization failure, unsupported evidence, low-quality evidence,
   low confidence, or publish/deadline confusion.
3. `repair_agent_node` calls the configured DeepSeek/OpenAI-compatible adapter
   only for those fields.
4. Successful fallback results are merged and re-verified.
5. Missing credentials or provider errors produce `fallback_failed` field status
   and `llm_fallback_failed` verification issues.

## Implemented Benchmark Workflow

The benchmark workflow in `app/benchmark/workflow.py` is also a LangGraph `StateGraph`.

Node order:

1. `dataset_loader_node`
2. `baseline_runner_node`
3. `ours_runner_node`
4. `metric_agent_node`
5. `report_agent_node`

The benchmark workflow may use checked-in Chinese HTML fixtures for thesis interface and metric demonstration. Each fixture supplies its Schema explicitly; no runtime domain-template catalog is consulted. It compares Direct LLM, LLM + Schema, Program Only, Hybrid without Verifier, and Ours Full.

`report_agent_node` persists the benchmark report payload so experiment results
can be read back through `GET /api/benchmark/reports/{task_id}`.
