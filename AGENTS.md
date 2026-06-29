# AGENTS.md

## Project

This repository is for the undergraduate thesis project:

《基于多 Agent 协同的网页信息结构化抽取系统》

Product name: WebStruct-Agent.

The system is a research-oriented web information extraction workbench, not a commercial SaaS product.

## Product Positioning

Build a local web application that supports:

1. Schema-first web information extraction
2. LangGraph-based multi-agent workflow
3. Multi-view web page representation
4. ProgramSpec DSL generation and execution
5. Hybrid extraction with programmatic extraction and LLM fallback
6. Field-level evidence, confidence, and verification
7. Built-in benchmark and comparison experiments

The implementation should prioritize a working thesis prototype and product demonstration.

## Mandatory Agent Orchestration Choice

Use LangGraph as the core agent orchestration runtime.

Do not implement the core workflow as a plain sequential Python script unless it is only a fallback for tests.

The core extraction workflow must be represented as a LangGraph StateGraph with typed state and named nodes.

Required graph nodes:

- schema_agent_node
- page_collector_node
- view_normalizer_node
- planner_agent_node
- programmer_agent_node
- extractor_agent_node
- verifier_agent_node
- repair_agent_node
- result_persist_node

Required benchmark graph nodes:

- dataset_loader_node
- baseline_runner_node
- ours_runner_node
- metric_agent_node
- report_agent_node

## DeepAgents Policy

DeepAgents may be introduced only as an optional enhancement layer.

Do not make DeepAgents a hard dependency of the MVP.

Acceptable use cases for DeepAgents:

1. Advanced schema assistant
2. Complex multi-step research assistant
3. Long-context benchmark analysis assistant
4. Optional subagent experimentation

The main extraction workflow must remain understandable and runnable with LangGraph directly.

If DeepAgents is added, wrap it behind an optional service interface:

- DeepAgentSchemaAssistant
- DeepAgentBenchmarkAnalyst

The system must still work when deepagents is not installed.

## Engineering Priorities

Prioritize:

1. A working local demo
2. Clear LangGraph workflow
3. Traceable agent state
4. Schema-first extraction
5. ProgramSpec DSL
6. Evidence and verifier
7. Benchmark runner
8. Simple, understandable UI

Do not implement:

- user login
- paid SaaS features
- distributed crawling
- anti-bot bypass
- captcha handling
- arbitrary code execution
- large knowledge-base QA
- complex unrelated dashboards
- generic chatbot UI unrelated to extraction

## Tech Stack

Backend:

- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite
- LangGraph
- Playwright Python
- pytest

Frontend:

- React
- Vite
- TypeScript
- simple CSS or Tailwind

LLM:

- Use a ModelAdapter abstraction
- DeepSeek is the default OpenAI-compatible provider
- Model credentials must be read from environment variables only
- ProgramSpec deterministic extraction may run without an API key
- LLM fallback must fail explicitly when provider credentials are missing

## Required Typed Objects

Implement typed models for:

- SchemaSpec
- FieldSpec
- PageObservation
- ViewBundle
- ExtractionPlan
- FieldExtractionPlan
- ProgramSpec
- FieldProgramSpec
- ExtractionResult
- FieldExtractionResult
- FieldEvidence
- EvidenceBundle
- VerificationReport
- AgentRunTrace
- GraphRunState
- BenchmarkDataset
- BenchmarkReport

## LangGraph State Requirements

Create a central typed graph state, for example:

- task_id
- schema_spec
- target_url
- seed_urls
- page_observation
- view_bundle
- extraction_plan
- program_spec
- extraction_result
- evidence_bundle
- verification_report
- repair_attempts
- benchmark_config
- benchmark_report
- agent_traces
- errors
- status

Each graph node must:

1. Read only the fields it needs from state
2. Return partial state updates
3. Record an AgentRunTrace
4. Never silently swallow errors
5. Avoid arbitrary code execution
6. Be testable as a normal Python function

## Agent Rules

Agents must not be implemented as free-form chat only.

Each agent node must have:

- name
- role
- structured input
- structured output
- status
- error message
- runtime_ms
- trace record

Required agents:

- SchemaAgent
- PageCollectorAgent
- ViewNormalizerAgent
- PlannerAgent
- ProgrammerAgent
- ExtractorAgent
- VerifierAgent
- RepairAgent
- EvaluatorAgent

## ProgramSpec Safety

ProgramSpec DSL is not arbitrary code.

Allowed strategies:

- css
- xpath
- regex_on_text
- text_near_label
- llm_fallback

Allowed postprocess functions:

- strip
- normalize_whitespace
- normalize_date

Never use eval or exec to run generated programs.

## Verification Requirements

The verifier must check at least:

1. Required field missing
2. Field type mismatch
3. Date normalization failure
4. Evidence text supports value
5. publish_date vs deadline confusion
6. Empty or low-quality evidence
7. Confidence score calculation

## Built-in Schemas

Provide at least three Chinese domain schemas:

1. 高校通知
2. 招聘公告
3. 政务公开 / 政策法规

## Benchmark Requirements

Evaluation Mode must compare:

- Direct LLM
- LLM + Schema
- Program Only
- Hybrid without Verifier
- Ours Full

Metrics:

- Field Accuracy
- Required Field Missing Rate
- Schema Adherence
- Evidence Precision
- Average Confidence
- Estimated Token Cost
- Runtime
- Program Reuse Rate
- Selective Accuracy
- Repair Success Rate, optional or placeholder

## Documentation Requirements

Maintain these docs:

- docs/product_requirements.md
- docs/system_architecture.md
- docs/langgraph_workflow.md
- docs/schema_spec.md
- docs/program_spec.md
- docs/evidence_spec.md
- docs/benchmark_design.md
- docs/thesis_mapping.md

These documents should support thesis writing directly.

## Validation Requirements

After backend changes:

- run pytest if possible
- ensure FastAPI app imports successfully
- ensure LangGraph workflow can compile

After frontend changes:

- run npm build or TypeScript check if possible

Always update README when startup commands or public behavior changes.
