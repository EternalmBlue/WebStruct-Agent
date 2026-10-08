import type {
  BenchmarkResponse,
  BenchmarkDataset,
  ExtractionResponse,
  HealthStatus,
  ManualReviewResponse,
  ProgramSpecSummary,
  ReviewField,
  SchemaSpec,
  SchemaValidationResponse,
  SpecAssistantResponse,
  VerifiedProgramSpecSummary,
  RunSnapshot,
  RunMetricsResponse,
  RunEvent,
  RSIIterationRequest,
  RSIIterationResponse,
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

export async function loadMonitoringConfiguration() {
  const response = await fetch("/api/config");
  if (!response.ok) throw new Error(`configuration HTTP ${response.status}`);
  return readJsonResponse<{ poll_interval_ms: number; health_interval_ms: number }>(response);
}

export async function loadHealthStatus(): Promise<HealthStatus> {
  const response = await fetch("/api/health");
  if (!response.ok) {
    throw new Error(`health HTTP ${response.status}`);
  }
  return readJsonResponse<HealthStatus>(response);
}

export async function loadRunMetrics(taskId: string): Promise<RunMetricsResponse> {
  const response = await fetch(`/api/runs/${taskId}/metrics`);
  if (!response.ok) {
    throw new Error(`run metrics HTTP ${response.status}`);
  }
  return readJsonResponse<RunMetricsResponse>(response);
}

export async function loadRunEvents(taskId: string, cursor = 0) {
  const response = await fetch(`/api/runs/${encodeURIComponent(taskId)}/events?after_cursor=${cursor}`);
  if (!response.ok) throw new Error(`run events HTTP ${response.status}`);
  return readJsonResponse<{ events: RunEvent[]; next_cursor: number }>(response);
}

async function loadRunSnapshot(taskId: string): Promise<RunSnapshot> {
  const response = await fetch(`/api/runs/${encodeURIComponent(taskId)}`);
  if (!response.ok) throw new Error(`run HTTP ${response.status}`);
  return readJsonResponse<RunSnapshot>(response);
}

async function readRSIResponse(response: Response) {
  const data = await readJsonResponse<RSIIterationResponse & { detail?: string }>(response);
  if (!response.ok) throw new Error(data.detail || `RSI HTTP ${response.status}`);
  return data;
}

export async function evaluateRSIIteration(request: RSIIterationRequest) {
  return readRSIResponse(await fetch("/api/rsi/iterations", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  }));
}

export async function loadRSIIteration(iterationId: string) {
  return readRSIResponse(await fetch(`/api/rsi/iterations/${encodeURIComponent(iterationId)}`));
}

export async function rollbackRSIIteration(iterationId: string, reason: string) {
  return readRSIResponse(await fetch(`/api/rsi/iterations/${encodeURIComponent(iterationId)}/rollback`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  }));
}

export async function loadSchemas(): Promise<SchemaSpec[]> {
  const response = await fetch("/api/schemas");
  if (!response.ok) {
    throw new Error(`schemas HTTP ${response.status}`);
  }
  return readJsonResponse<SchemaSpec[]>(response);
}

export const loadBuiltinSchemas = loadSchemas;

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
  request: CreateExtractionRequest | RunVerifiedExtractionRequest,
  onProgress?: (snapshot: RunSnapshot) => void,
): Promise<ExtractionResponse> {
  const schema = request.mode === "run_verified" ? request.schema : request.schema ?? null;
  const useSchema = Boolean(schema);
  if (useSchema && schema) {
    const validation = await validateSchema(schema);
    if (!validation.valid) {
      throw new Error(validation.errors.join("；"));
    }
  }

  const body: Record<string, unknown> = {
    target_url: request.targetUrl,
    html: request.htmlInput,
    program_spec: request.mode === "create" ? request.programSpec ?? null : null,
    program_spec_mode: request.mode === "run_verified" ? "run_verified" : "create",
    persist_result: true,
    reuse_verified_program: request.mode === "run_verified",
  };
  if (schema) {
    body.schema_name = schema.name;
    body.schema_spec = schema;
  }
  const response = await fetch("/api/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await readJsonResponse<(ExtractionResponse & { detail?: string }) | RunSnapshot>(
    response
  );
  if (!response.ok) {
    const detail = "detail" in data ? data.detail : undefined;
    const errors = "errors" in data ? data.errors : [];
    throw new Error(detail || errors?.join("；") || `HTTP ${response.status}`);
  }
  if (!("schema_spec" in data)) {
    return pollExtractionRun(data.task_id, onProgress);
  }
  return data;
}

export async function pollExtractionRun(
  taskId: string,
  onProgress?: (snapshot: RunSnapshot) => void,
): Promise<ExtractionResponse> {
  const configuration = await loadMonitoringConfiguration();
  let cursor = 0;
  const observations: RunEvent[] = [];
  for (;;) {
    const snapshot = await loadRunSnapshot(taskId);
    while (cursor < snapshot.event_cursor) {
      const page = await loadRunEvents(taskId, cursor);
      if (page.next_cursor <= cursor) break;
      observations.push(...page.events.filter((event) =>
        ["browser_probe", "collection_attempt", "model_call", "field_repair"].includes(event.event_type)));
      cursor = page.next_cursor;
    }
    snapshot.observations = observations.slice();
    onProgress?.(snapshot);
    const response = await fetch(`/api/extract/${taskId}`);
    if (!response.ok) throw new Error(`extract HTTP ${response.status}`);
    const data = await readJsonResponse<ExtractionResponse | RunSnapshot>(response);
    if ("agent_traces" in data && data.status !== "queued" && data.status !== "running") {
      return data;
    }
    await new Promise((resolve) => setTimeout(resolve, configuration.poll_interval_ms));
  }
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
  dataset: BenchmarkDataset,
  onProgress?: (snapshot: RunSnapshot) => void,
): Promise<BenchmarkResponse> {
  const response = await fetch("/api/benchmark/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset }),
  });
  const data = await readJsonResponse<BenchmarkResponse | RunSnapshot>(response);
  if (!response.ok) {
    throw new Error(data.errors?.join("；") || `HTTP ${response.status}`);
  }
  if (!("benchmark_report" in data)) {
    if (!data.task_id) {
      throw new Error("benchmark response did not include task_id");
    }
    return pollBenchmarkRun(data.task_id, onProgress);
  }
  return data;
}

export async function pollBenchmarkRun(
  taskId: string,
  onProgress?: (snapshot: RunSnapshot) => void,
): Promise<BenchmarkResponse> {
  const configuration = await loadMonitoringConfiguration();
  for (;;) {
    const snapshot = await loadRunSnapshot(taskId);
    onProgress?.(snapshot);
    const response = await fetch(`/api/benchmark/reports/${taskId}`);
    if (!response.ok) throw new Error(`benchmark HTTP ${response.status}`);
    const data = await readJsonResponse<BenchmarkResponse | RunSnapshot>(response);
    if ("benchmark_report" in data && data.status !== "queued" && data.status !== "running") {
      return data;
    }
    await new Promise((resolve) => setTimeout(resolve, configuration.poll_interval_ms));
  }
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
