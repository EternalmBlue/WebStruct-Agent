# Experiment Results

## Dataset

The checked-in benchmark dataset contains 9 Chinese HTML fixtures: 3 university notices, 3 job postings, and 3 government-policy pages.
Each item carries its Schema explicitly; these fixtures are not runtime built-in Schema templates.
This exported table was generated in offline mode with LLM credentials disabled, so LLM-only methods fail explicitly instead of producing synthetic values.

## Benchmark Summary

| Schema | Method | Field Accuracy | Missing Rate | Schema Adherence | Evidence Precision | Avg Confidence | Token Estimate | Runtime ms | Program Reuse | Selective Accuracy | Repair Success |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 高校通知 | Direct LLM | 0.00 | 1.00 | 0.70 | 0.00 | 0.00 | 283 | 0 | 0.00 | 0.00 |  |
| 高校通知 | LLM + Schema | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 283 | 1 | 0.00 | 0.00 |  |
| 高校通知 | Program Only | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 266 | 4 | 1.00 | 1.00 |  |
| 高校通知 | Hybrid without Verifier | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 352 | 0 | 1.00 | 1.00 |  |
| 高校通知 | Ours Full | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 388 | 40 | 1.00 | 1.00 | 0.00 |
| 招聘公告 | Direct LLM | 0.00 | 1.00 | 0.70 | 0.00 | 0.00 | 283 | 1 | 0.00 | 0.00 |  |
| 招聘公告 | LLM + Schema | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 283 | 0 | 0.00 | 0.00 |  |
| 招聘公告 | Program Only | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 266 | 0 | 1.00 | 1.00 |  |
| 招聘公告 | Hybrid without Verifier | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 352 | 0 | 1.00 | 1.00 |  |
| 招聘公告 | Ours Full | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 388 | 16 | 1.00 | 1.00 | 0.00 |
| 政务公开 / 政策法规 | Direct LLM | 0.00 | 1.00 | 0.70 | 0.00 | 0.00 | 283 | 0 | 0.00 | 0.00 |  |
| 政务公开 / 政策法规 | LLM + Schema | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 283 | 0 | 0.00 | 0.00 |  |
| 政务公开 / 政策法规 | Program Only | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 266 | 1 | 1.00 | 1.00 |  |
| 政务公开 / 政策法规 | Hybrid without Verifier | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 352 | 0 | 1.00 | 1.00 |  |
| 政务公开 / 政策法规 | Ours Full | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 388 | 16 | 1.00 | 1.00 | 0.00 |

## Success Case

University notice sample `university_notice_002` completed with verification status `passed=True`.

| Field | Value | Strategy | Confidence | Evidence Count |
| --- | --- | --- | ---: | ---: |
| title | 关于组织2026年暑期社会实践的通知 | css | 0.81 | 1 |
| publish_date | 2026-06-18 | text_near_label | 0.85 | 1 |
| department | 学生工作处 | text_near_label | 0.85 | 1 |
| deadline | 2026-07-10 | text_near_label | 0.85 | 1 |
| contact | 李老师，联系电话：010-87654321 | text_near_label | 0.85 | 1 |

## Failure / Limitation Case

Synthetic required-field sample demonstrates the explicit fallback-failure path when provider credentials are disabled.

| Field | Value | Status | Strategy | Evidence Count | Error |
| --- | --- | --- | --- | ---: | --- |
| title | 测试通知 | extracted | css | 1 |  |
| approval_code |  | fallback_failed | none | 0 | LLM fallback requires model.api_key in config.toml |

## Analysis Notes

- Program Only and Ours Full perform well on label-rich pages because `text_near_label` and date normalization match the fixture structure.
- LLM-only methods depend on provider availability. In offline mode they are recorded as explicit missing/failure results rather than fabricated predictions.
- Current fixtures are thesis-demo scale rather than statistically large-scale. The conclusion should be framed as prototype verification and comparative demonstration.
- Manual review can mark ProgramSpec as user verified; final experiments should reset or control local PostgreSQL state when measuring reuse rate.
