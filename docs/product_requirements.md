# Product Requirements

## Purpose

WebStruct-Agent is a local research-oriented workbench for schema-first web information extraction. It supports the thesis topic `基于多 Agent 协同的网页信息结构化抽取系统`.

## Scope

The current implementation provides a runnable local thesis demo foundation. The
system includes URL-first schema creation, schema management and version
persistence, a React extraction workbench, CloakBrowser-first page collection,
multi-view page representation, LangGraph agent workflow, ProgramSpec generation
and execution, human-AI Spec collaboration, evidence-aware extraction,
verification, bounded fallback repair, PostgreSQL persistence, real
OpenAI-compatible LLM fallback configuration, and an explicit-input benchmark workflow.

The repository also includes thesis support artifacts: demo screenshot,
offline/live experiment tables, and success/failure case analysis. Larger
external benchmark datasets remain future work beyond the local prototype.

## Non-Goals

- User login
- Paid SaaS features
- Distributed crawling
- Anti-bot bypass
- Captcha handling
- Generic chatbot workflows unrelated to extraction

## Acceptance Direction

The prototype should remain easy to demonstrate locally and should map directly to thesis chapters and experiments.

## Implemented Demo Flow

1. User chooses Create ProgramSpec for a new URL or Run ProgramSpec for a
   verified reusable version.
2. In create mode, the user supplies a URL and optional HTML. No runtime domain
   schema is selected unless the user explicitly supplies a schema override.
3. Backend runs the LangGraph extraction workflow.
4. Page collection captures rendered HTML, normalized text, and text blocks.
5. SchemaAgent infers a page-specific `SchemaSpec` when no explicit schema is
   supplied.
6. ProgrammerAgent generates a safe page-specific `ProgramSpec`, or uses an
   explicit assistant-provided ProgramSpec during rerun.
7. ProgramSpec executes deterministic extraction first.
8. Verifier flags missing, invalid, weak-evidence, low-confidence, or confused fields.
9. FallbackDecider sends only the flagged fields to real LLM fallback.
10. Missing credentials or provider errors are explicit fallback failures, not fake data.
11. Frontend displays structured fields, evidence, confidence, verification report, and agent trace.
12. User can open the Spec assistant, describe field/evidence changes in natural
    language, preview a draft revised `SchemaSpec` and `ProgramSpec`, apply it
    to the current task, or rerun extraction with the draft as an explicit
    override.
13. User can review/edit extracted field values and save review notes.
14. User can mark the current ProgramSpec as verified so matching schemas reuse it later.
