# Benchmark Design

## Purpose

The benchmark module will compare extraction methods and support thesis experiments.

## Planned Baselines

- Direct LLM
- LLM + Schema
- Program Only
- Hybrid without Verifier
- Ours Full

## Planned Metrics

- Field Accuracy
- Required Field Missing Rate
- Schema Adherence
- Evidence Precision
- Average Confidence
- Estimated Token Cost
- Runtime
- Program Reuse Rate
- Selective Accuracy
- Repair Success Rate

## Implemented Status

`POST /api/benchmark/run` runs a LangGraph benchmark workflow over checked-in Chinese HTML fixtures.

Implemented comparison methods:

- Direct LLM
- LLM + Schema
- Program Only
- Hybrid without Verifier
- Ours Full

The current benchmark uses 9 checked-in fixtures across three Chinese domains. Metrics are suitable for thesis prototype demonstration and comparative analysis; larger external datasets remain future work.

Benchmark reports are persisted and can be read back through:

```text
GET /api/benchmark/reports/{task_id}
```

The frontend workbench can run the benchmark and display the method comparison
table. The current fixture scale is sufficient for prototype demonstration and
paper-ready case analysis; expanding each domain beyond the checked-in samples
is future work for larger empirical studies.

## Thesis Artifacts

- Live benchmark table: `docs/experiment_results_live.md` and `docs/experiment_results_live.csv`
- Offline reproducible table: `docs/experiment_results.md` and `docs/experiment_results.csv`
- Demo screenshot: `docs/demo-workbench.png`
