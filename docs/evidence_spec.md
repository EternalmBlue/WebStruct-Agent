# Evidence Spec

## Purpose

Evidence records should explain why each extracted field value is trusted.

## Planned Objects

- `FieldEvidence`
- `EvidenceBundle`
- `VerificationReport`

## Verification Direction

The verifier should check required fields, type mismatches, date normalization, evidence quality, confidence, and common confusion such as publish date versus deadline.

## Implemented Status

The backend now returns field-level evidence and verification reports from `POST /api/extract`.

Implemented checks include:

- required field missing
- field type mismatch
- date normalization failure
- evidence text supports value
- publish date versus deadline confusion
- empty or low-quality evidence
- confidence score floor by extraction strategy

Each field result includes `value`, `normalized_value`, `confidence`, `strategy`, `status`, and evidence snippets.

Fallback-specific behavior:

- Deterministic extraction can complete without an LLM key.
- Fields selected for fallback by `FallbackDecider` call the configured real
  provider only after verification.
- Missing credentials or provider errors set field status to `fallback_failed`
  and add `llm_fallback_failed` to the verification report.
- The verifier is re-run after fallback/repair so the final report matches the
  returned field values and errors.

Manual review records let users confirm or edit returned field values and attach
notes. When the user marks the ProgramSpec as verified, later matching schemas can
reuse the same ProgramSpec.
