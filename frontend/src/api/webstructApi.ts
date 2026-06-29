import type {
  BenchmarkResponse,
  ExtractionResponse,
  HealthStatus,
  ManualReviewResponse,
  ProgramSpecSummary,
  ReviewField,
  SchemaSpec,
  SchemaValidationResponse,
  SpecAssistantResponse,
  VerifiedProgramSpecSummary,
} from "../types/webstruct";

type CreateExtractionRequest = {
  mode: "create";
  targetUrl: string;
  htmlInput: string;
  schema?: SchemaSpec | null;
  programSpec?: ProgramSpecSummary | null;
};

type RunVerifiedExtractionRequest = {
  mode: "run_verified";
  targetUrl: string;
  htmlInput: string;
  schema: SchemaSpec;
};

async function readJsonResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    const message = text
      .replace(/<[^>]*>/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 180);
    throw new Error(message || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadHealthStatus(): Promise<HealthStatus> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`health HTTP ${response.status}`);
  }
  return readJsonResponse<HealthStatus>(response);
}

export async function loadBuiltinSchemas(): Promise<SchemaSpec[]> {
  const response = await fetch("/api/schemas");
  if (!response.ok) {
    throw new Error(`schemas HTTP ${response.status}`);
  }
  return readJsonResponse<SchemaSpec[]>(response);
}

export async function loadVerifiedProgramSpecs(): Promise<
  VerifiedProgramSpecSummary[]
> {
  const response = await fetch("/api/program-specs/verified");
  if (!response.ok) {
    throw new Error(`program-specs HTTP ${response.status}`);
  }
  return readJsonResponse<VerifiedProgramSpecSummary[]>(response);
}

export async function validateSchema(
  schema: SchemaSpec
): Promise<SchemaValidationResponse> {
  const response = await fetch("/api/schemas/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(schema),
  });
  return readJsonResponse<SchemaValidationResponse>(response);
}

export async function runExtractionRequest(
  request: CreateExtractionRequest | RunVerifiedExtractionRequest
): Promise<ExtractionResponse> {
  const schema = request.mode === "run_verified" ? request.schema : request.schema ?? null;
  const useSchema = Boolean(schema);
  if (useSchema && schema) {
    const validation = await validateSchema(schema);
    if (!validation.valid) {
      throw new Error(validation.errors.join("；"));
    }
  }

  const response = await fetch("/api/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_url: request.targetUrl,
      html: request.htmlInput,
      schema_name: schema ? schema.name : "",
      schema_spec: schema,
      program_spec: request.mode === "create" ? request.programSpec ?? null : null,
      program_spec_mode: request.mode === "run_verified" ? "run_verified" : "create",
      persist_result: true,
      reuse_verified_program: request.mode === "run_verified",
    }),
  });
  const data = await readJsonResponse<ExtractionResponse & { detail?: string }>(
    response
  );
  if (!response.ok) {
    throw new Error(data.detail || data.errors?.join("；") || `HTTP ${response.status}`);
  }
  return data;
}

export async function reviseSpecWithAssistant({
  extraction,
  message,
}: {
  extraction: ExtractionResponse;
  message: string;
}): Promise<SpecAssistantResponse> {
  const response = await fetch("/api/spec-assistant/revise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_id: extraction.task_id,
      message,
      schema_spec: extraction.schema_spec,
      program_spec: extraction.program_spec,
    }),
  });
  const data = await readJsonResponse<SpecAssistantResponse & { detail?: string }>(
    response
  );
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

export async function runBenchmarkRequest(
  schemaName: string
): Promise<BenchmarkResponse> {
  const response = await fetch("/api/benchmark/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ schema_name: schemaName || "高校通知" }),
  });
  const data = await readJsonResponse<BenchmarkResponse>(response);
  if (!response.ok) {
    throw new Error(data.errors?.join("；") || `HTTP ${response.status}`);
  }
  return data;
}

export async function submitManualReviewRequest({
  extraction,
  reviewFields,
  markProgramVerified,
  ruleName,
}: {
  extraction: ExtractionResponse;
  reviewFields: ReviewField[];
  markProgramVerified: boolean;
  ruleName: string;
}): Promise<ManualReviewResponse> {
  if (!extraction.program_spec) {
    throw new Error("当前抽取结果没有可复核的 ProgramSpec");
  }

  const response = await fetch("/api/reviews/manual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task_id: extraction.task_id,
      schema_spec: extraction.schema_spec,
      program_spec: extraction.program_spec,
      fields: reviewFields,
      mark_program_verified: markProgramVerified,
      rule_name: ruleName,
    }),
  });
  const data = await readJsonResponse<ManualReviewResponse>(response);
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}
