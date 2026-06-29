# Thesis Mapping

## Thesis Topic

`基于多 Agent 协同的网页信息结构化抽取系统`

## Project Mapping

- Product requirements map to research problem definition.
- System architecture maps to design and implementation chapters.
- LangGraph workflow maps to the multi-agent collaboration method.
- SchemaSpec and ProgramSpec map to structured extraction methodology.
- Evidence and verification map to extraction quality control.
- Benchmark design maps to experiment setup and result analysis.

## Implemented Status

The current repository can support a local thesis prototype demonstration:

- Multi-agent collaboration is represented by LangGraph nodes and `AgentRunTrace`.
- Schema-first extraction is represented by `SchemaSpec` and built-in Chinese domain schemas.
- Page acquisition and multi-view representation are represented by Playwright
  collection, normalized text, headings, lines, and text blocks with selector/xpath hints.
- Programmatic extraction is represented by the safe `ProgramSpec` DSL.
- Hybrid extraction is represented by deterministic ProgramSpec execution plus
  `FallbackDecider` and real DeepSeek/OpenAI-compatible fallback.
- Quality control is represented by evidence bundles, confidence, fallback
  failure status, and verification reports.
- Experiments are represented by the benchmark graph, persisted benchmark
  reports, and comparison method metrics.
- The frontend workbench provides demo screenshots for schema editing,
  extraction results, evidence, verification report, agent trace, manual review,
  and benchmark.
- User feedback is represented by manual review records and user-verified
  ProgramSpec reuse.

The implementation is prototype-oriented but now includes local demo screenshots,
experiment result tables, and success/failure case analysis artifacts for thesis writing.


## Deliverable Artifacts

- Demo screenshot: `docs/demo-workbench.png`
- Live benchmark table: `docs/experiment_results_live.md`
- Reproducible benchmark table: `docs/experiment_results.md`
