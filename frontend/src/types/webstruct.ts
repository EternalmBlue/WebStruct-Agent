export type HealthStatus = {
  status: string;
  app_name: string;
  model_mode: string;
  llm_configured: boolean;
  llm_model: string;
  database_driver: string;
  config_source?: string;
  config_loaded?: boolean;
  browser?: {
    available: boolean; provider: string; version?: string; binary_version?: string;
    sdk_installed?: boolean; binary_ready?: boolean; launch_verified?: boolean;
    navigation_verified?: boolean; last_probe_at?: string | null; reason?: string | null;
  };
  observability?: { available: boolean; summary: string };
};

export type RunSnapshot = {
  task_id: string;
  correlation_id: string;
  status: "queued" | "running" | "completed" | "failed";
  current_node: string | null;
  completed_node_count: number;
  total_node_count: number;
  progress: number;
  updated_at: string;
  event_cursor: number;
  runtime_ms?: number | null;
  start_time?: string | null;
  queue_wait_ms?: number | null;
  observations?: RunEvent[];
  errors: string[];
  original_task_id?: string | null;
  nodes?: Record<
    string,
    {
      name: string;
      role?: string;
      status: string;
      runtime_ms?: number | null;
      output_summary?: string;
      error_message?: string | null;
    }
  >;
  metrics_version?: string;
  metrics?: Record<string, MetricEnvelope>;
  fingerprint?: Record<string, unknown>;
};

export type MetricEnvelope = {
  value: number | null;
  source: "measured" | "estimated" | "unavailable" | string;
  unit?: string;
  sample_count?: number;
  reason?: string | null;
};

export type FieldType = "string" | "text" | "number" | "date" | "url" | "list";

export type FieldSpec = {
  name: string;
  description: string;
  type: FieldType;
  required: boolean;
  aliases: string[];
  examples: string[];
};

export type SchemaSpec = {
  name: string;
  description: string;
  domain: string;
  fields: FieldSpec[];
};

export type ViewBundle = {
  url: string;
  raw_html?: string;
  text?: string;
  lines?: string[];
  title?: string;
  headings?: string[];
  metadata?: Record<string, unknown>;
};

export type FieldEvidence = {
  field_name: string;
  source: string;
  text: string;
  start_char?: number | null;
  end_char?: number | null;
  score: number;
};

export type FieldExtractionResult = {
  field_name: string;
  value: unknown;
  normalized_value: unknown;
  confidence: number;
  evidence: FieldEvidence[];
  strategy: string;
  status: string;
  error_message?: string | null;
};

export type ProgramSpecSummary = {
  version: string;
  safety_mode: string;
  field_programs: Array<{
    field_name: string;
    strategy: string;
    enabled?: boolean;
    selector?: string | null;
    attribute?: string | null;
    pattern?: string | null;
    label?: string | null;
    labels?: string[];
    postprocess?: string[];
  }>;
};

export type ExtractionResponse = {
  task_id: string;
  correlation_id?: string;
  status: string;
  schema_spec: SchemaSpec | null;
  schema_generation_mode?: string;
  schema_generation_error?: string | null;
  view_bundle?: ViewBundle | null;
  schema_version?: {
    schema_signature: string;
    schema_name: string;
    version: number;
    source: string;
  } | null;
  program_spec?: ProgramSpecSummary | null;
  program_reused?: boolean;
  program_generation_mode?: string;
  program_generation_error?: string | null;
  program_validation_issues?: Array<{
    field?: string;
    strategy?: string;
    selector?: string;
    reason: string;
    match_count?: number | null;
  }>;
  extraction_result?: {
    schema_name: string;
    fields: FieldExtractionResult[];
    overall_confidence: number;
  } | null;
  verification_report?: {
    passed: boolean;
    score: number;
    issues: Array<{
      field_name: string;
      code: string;
      severity: string;
      message: string;
    }>;
  } | null;
  agent_traces: Array<{
    name: string;
    role: string;
    status: string;
    runtime_ms: number;
    output_summary: string;
    error_message?: string | null;
  }>;
  errors: string[];
  metrics_version?: string;
  metrics?: Record<string, MetricEnvelope>;
  fingerprint?: Record<string, unknown>;
};

export type RunMetricsResponse = {
  task_id: string;
  status: string;
  config_version?: string;
  metrics_version?: string;
  metrics: Record<string, MetricEnvelope>;
  fingerprint?: Record<string, unknown>;
};

export type RunEvent = {
  sequence: number;
  event_type: string;
  timestamp: string;
  [key: string]: unknown;
};

export type RSIIterationRequest = {
  experiment_id: string;
  baseline_run_id: string;
  candidate_run_id: string;
  hypothesis_id: string;
  hypothesis: string;
  intervention: string;
  change_set_id: string;
  parent_iteration_id?: string | null;
};

export type RSIIterationResponse = RSIIterationRequest & {
  iteration_id: string;
  status: "accepted" | "rejected" | "blocked" | "rolled_back";
  metric_deltas: Record<string, number | null>;
  baseline_metrics: Record<string, MetricEnvelope>;
  candidate_metrics: Record<string, MetricEnvelope>;
  thresholds: Record<string, number>;
  decision_reason: string;
  quality_basis: string;
  evaluation_version?: string;
  rollback_reason?: string | null;
};

export type ReviewField = {
  field_name: string;
  value: string;
  accepted: boolean;
  note: string;
};

export type BenchmarkResponse = {
  task_id?: string;
  correlation_id?: string;
  status: string;
  benchmark_report?: {
    dataset_name: string;
    summary: string;
    methods: Array<{
      method: string;
      field_accuracy: number | null;
      required_field_missing_rate: number | null;
      schema_adherence: number | null;
      evidence_precision: number | null;
      average_confidence: number | null;
      program_reuse_rate: number | null;
      selective_accuracy: number | null;
      repair_success_rate?: number | null;
      estimated_token_cost?: number | null;
      runtime_ms?: number | null;
      evidence_coverage?: number | null;
      actual_input_tokens?: number | null;
      actual_output_tokens?: number | null;
      partial_actual_input_tokens?: number;
      partial_actual_output_tokens?: number;
      model_call_count?: number;
      token_usage_missing_calls?: number;
      failure_count?: number;
      success_count?: number;
      sample_count?: number;
      sample_errors?: Record<string, string[]>;
      metric_sources?: Record<string, string>;
      unavailable_reasons?: Record<string, string>;
    }>;
  } | null;
  errors: string[];
};

export type BenchmarkItem = {
  item_id: string;
  url?: string;
  html: string;
  schema_name?: string;
  schema_spec: SchemaSpec;
  gold_record: Record<string, string>;
};

export type BenchmarkDataset = {
  name: string;
  items: BenchmarkItem[];
};

export type ConnectionState = "checking" | "online" | "offline";
export type RunState = "idle" | "running" | "done" | "failed";

export type SchemaValidationResponse = {
  valid: boolean;
  errors: string[];
};

export type ManualReviewResponse = {
  status: string;
  program_verified: boolean;
  field_count: number;
  detail?: string;
};

export type SpecAssistantResponse = {
  task_id: string;
  assistant_message: string;
  schema_spec: SchemaSpec;
  program_spec: ProgramSpecSummary;
  change_summary: string[];
  validation_issues: string[];
};

export type VerifiedProgramSpecSummary = {
  schema_signature: string;
  schema_name: string;
  rule_name?: string;
  schema_spec: SchemaSpec;
  program_count: number;
  created_at: string;
};
