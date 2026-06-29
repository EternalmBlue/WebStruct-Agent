import type { ExtractionResponse, ReviewField } from "../types/webstruct";
import { formatValue } from "./formatters";

export function toReviewFields(extraction: ExtractionResponse): ReviewField[] {
  return (
    extraction.extraction_result?.fields.map((field) => ({
      field_name: field.field_name,
      value: formatValue(field.normalized_value ?? field.value),
      accepted: field.status === "extracted" || field.status === "repaired",
      note: field.error_message || "",
    })) ?? []
  );
}

export function updateReviewField(
  fields: ReviewField[],
  index: number,
  field: ReviewField
): ReviewField[] {
  const next = [...fields];
  next[index] = field;
  return next;
}
