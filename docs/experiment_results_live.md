# Experiment Results (Live Provider)

## Dataset

The built-in benchmark currently contains 9 checked-in Chinese HTML fixtures: 3 university notices, 3 job postings, and 3 government-policy pages.
This table was generated with the configured live OpenAI-compatible provider when available; LLM methods are expected to fail explicitly if credentials are absent.

## Benchmark Summary

| Schema | Method | Field Accuracy | Missing Rate | Schema Adherence | Evidence Precision | Avg Confidence | Token Estimate | Runtime ms | Program Reuse | Selective Accuracy | Repair Success |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 高校通知 | Direct LLM | 0.93 | 0.00 | 0.70 | 1.00 | 0.74 | 463 | 31410 | 0.00 | 0.93 |  |
| 高校通知 | LLM + Schema | 1.00 | 0.00 | 1.00 | 1.00 | 0.83 | 463 | 5902 | 0.00 | 1.00 |  |
| 高校通知 | Program Only | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 266 | 5 | 1.00 | 1.00 |  |
| 高校通知 | Hybrid without Verifier | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 352 | 2 | 1.00 | 1.00 |  |
| 高校通知 | Ours Full | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 388 | 40 | 1.00 | 1.00 | 0.00 |
| 招聘公告 | Direct LLM | 1.00 | 0.00 | 0.70 | 1.00 | 0.74 | 443 | 35154 | 0.00 | 1.00 |  |
| 招聘公告 | LLM + Schema | 1.00 | 0.00 | 1.00 | 1.00 | 0.83 | 443 | 6374 | 0.00 | 1.00 |  |
| 招聘公告 | Program Only | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 258 | 5 | 1.00 | 1.00 |  |
| 招聘公告 | Hybrid without Verifier | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 339 | 4 | 1.00 | 1.00 |  |
| 招聘公告 | Ours Full | 1.00 | 0.00 | 1.00 | 1.00 | 0.85 | 374 | 24 | 0.00 | 1.00 | 0.00 |
| 政务公开 / 政策法规 | Direct LLM | 0.67 | 0.20 | 0.70 | 1.00 | 0.74 | 444 | 34547 | 0.00 | 0.53 |  |
| 政务公开 / 政策法规 | LLM + Schema | 0.67 | 0.20 | 1.00 | 1.00 | 0.83 | 444 | 6412 | 0.00 | 0.53 |  |
| 政务公开 / 政策法规 | Program Only | 0.67 | 0.20 | 1.00 | 1.00 | 0.85 | 259 | 2 | 1.00 | 0.53 |  |
| 政务公开 / 政策法规 | Hybrid without Verifier | 0.67 | 0.20 | 1.00 | 1.00 | 0.85 | 340 | 1 | 1.00 | 0.53 |  |
| 政务公开 / 政策法规 | Ours Full | 0.67 | 0.20 | 1.00 | 1.00 | 0.85 | 375 | 21 | 0.00 | 0.53 | 0.00 |

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
| approval_code |  | fallback_failed | none | 0 | LLM fallback abstained: required_field_missing |

## Analysis Notes

- Program Only and Ours Full perform well on label-rich pages because `text_near_label` and date normalization match the fixture structure.
- LLM-only methods depend on provider availability. When credentials are missing, they are recorded as explicit missing/failure results rather than fabricated predictions.
- Current fixtures are thesis-demo scale rather than statistically large-scale. The conclusion should be framed as prototype verification and comparative demonstration.
- Manual review can mark ProgramSpec as user verified; final experiments should reset or control local PostgreSQL state when measuring reuse rate.
