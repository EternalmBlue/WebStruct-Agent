import { useEffect, useMemo, useState } from "react";
import {
  BracketsCurly,
  CheckCircle,
  FileHtml,
  GitBranch,
  Play,
  Plus,
  Wrench,
} from "@phosphor-icons/react";

import {
  loadSchemas,
  loadHealthStatus,
  loadVerifiedProgramSpecs,
  pollExtractionRun,
  reviseSpecWithAssistant,
  runBenchmarkRequest,
  runExtractionRequest,
  submitManualReviewRequest,
} from "../api/webstructApi";
import { AgentTracePanel } from "../features/extraction/AgentTracePanel";
import { BenchmarkPanel } from "../features/evaluation/BenchmarkPanel";
import { EvidencePanel } from "../features/verification/EvidencePanel";
import { ExtractionResultsPanel } from "../features/extraction/ExtractionResultsPanel";
import { FieldEditor } from "../features/schema/FieldEditor";
import { ManualReviewPanel } from "../features/review/ManualReviewPanel";
import { ProgramSpecPreviewPanel } from "../features/program/ProgramSpecPreviewPanel";
import { RunStateBadge } from "../features/extraction/RunStateBadge";
import { VerificationReportPanel } from "../features/verification/VerificationReportPanel";
import { WorkflowRail } from "../features/extraction/WorkflowRail";
import { sampleHtml } from "../lib/sampleHtml";
import {
  appendEmptyField,
  cloneSchema,
  removeField,
  updateField,
} from "../lib/schemaDraft";
import { toReviewFields } from "../lib/reviewFields";
import type {
  BenchmarkDataset,
  BenchmarkResponse,
  ConnectionState,
  ExtractionResponse,
  FieldSpec,
  HealthStatus,
  ReviewField,
  RunState,
  SchemaSpec,
  SpecAssistantResponse,
  VerifiedProgramSpecSummary,
} from "../types/webstruct";

type WorkMode = "create" | "run";

export function Dashboard() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("checking");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [schemas, setSchemas] = useState<SchemaSpec[]>([]);
  const [selectedSchemaName, setSelectedSchemaName] = useState("");
  const [verifiedProgramSpecs, setVerifiedProgramSpecs] = useState<
    VerifiedProgramSpecSummary[]
  >([]);
  const [selectedVerifiedProgramSignature, setSelectedVerifiedProgramSignature] =
    useState("");
  const [schemaDraft, setSchemaDraft] = useState<SchemaSpec | null>(null);
  const [useCustomSchema, setUseCustomSchema] = useState(false);
  const [targetUrl, setTargetUrl] = useState("");
  const [htmlInput, setHtmlInput] = useState("");
  const [runState, setRunState] = useState<RunState>("idle");
  const [benchmarkState, setBenchmarkState] = useState<RunState>("idle");
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null);
  const [reviewFields, setReviewFields] = useState<ReviewField[]>([]);
  const [ruleName, setRuleName] = useState("");
  const [markProgramVerified, setMarkProgramVerified] = useState(false);
  const [reviewState, setReviewState] = useState<RunState>("idle");
  const [reviewMessage, setReviewMessage] = useState("");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantState, setAssistantState] = useState<RunState>("idle");
  const [assistantMessage, setAssistantMessage] = useState("");
  const [assistantError, setAssistantError] = useState("");
  const [assistantDraft, setAssistantDraft] =
    useState<SpecAssistantResponse | null>(null);
  const [error, setError] = useState("");
  const [htmlDrawerOpen, setHtmlDrawerOpen] = useState(false);
  const [schemaDrawerOpen, setSchemaDrawerOpen] = useState(false);
  const [reuseVerifiedProgram, setReuseVerifiedProgram] = useState(false);
  const [workMode, setWorkMode] = useState<WorkMode>("create");

  async function refreshVerifiedProgramSpecs() {
    const verifiedProgramData = await loadVerifiedProgramSpecs();
    setVerifiedProgramSpecs(verifiedProgramData);
    setSelectedVerifiedProgramSignature((currentSignature) => {
      if (
        currentSignature &&
        verifiedProgramData.some(
          (programSpec) => programSpec.schema_signature === currentSignature
        )
      ) {
        return currentSignature;
      }
      return verifiedProgramData[0]?.schema_signature ?? "";
    });
  }

  useEffect(() => {
    if (workMode === "run") {
      setUseCustomSchema(true);
      setReuseVerifiedProgram(true);
      setAssistantDraft(null);
      setAssistantError("");
      setAssistantOpen(false);
      setReviewMessage("");
      setRuleName("");
      setMarkProgramVerified(false);
    } else {
      setUseCustomSchema(false);
      setReuseVerifiedProgram(false);
    }
    setSchemaDrawerOpen(false);
  }, [workMode]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [healthData, schemaData] = await Promise.all([
          loadHealthStatus(),
          loadSchemas(),
        ]);
        if (!cancelled) {
          setHealth(healthData);
          setSchemas(schemaData);
          setConnectionState("online");
          setError("");
          if (schemaData[0]) {
            setSelectedSchemaName(schemaData[0].name);
          }
          try {
            await refreshVerifiedProgramSpecs();
          } catch {
            setVerifiedProgramSpecs([]);
            setSelectedVerifiedProgramSignature("");
          }
        }
      } catch (currentError) {
        if (!cancelled) {
          setConnectionState("offline");
          setHealth(null);
          setError("");
        }
      }
    }

    loadInitialData();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const rawTask = window.localStorage.getItem("webstruct.activeTask");
    const legacyTaskId = window.localStorage.getItem("webstruct.activeTaskId");
    let activeTask: { kind?: string; task_id?: string } | null = null;
    if (rawTask) {
      try {
        activeTask = JSON.parse(rawTask) as { kind?: string; task_id?: string };
      } catch {
        window.localStorage.removeItem("webstruct.activeTask");
      }
    }
    if (!activeTask && legacyTaskId) {
      activeTask = { kind: "extraction", task_id: legacyTaskId };
    }
    if (!activeTask?.task_id || activeTask.kind !== "extraction" || extraction || runState === "running") {
      return;
    }
    setRunState("running");
    pollExtractionRun(activeTask.task_id, (snapshot) => {
      setRunState(snapshot.status === "failed" ? "failed" : "running");
    })
      .then((data) => {
        setExtraction(data);
        setReviewFields(toReviewFields(data));
        setRuleName(defaultRuleName(data));
        setRunState(data.status === "failed" ? "failed" : "done");
        window.localStorage.removeItem("webstruct.activeTask");
        window.localStorage.removeItem("webstruct.activeTaskId");
      })
      .catch(() => {
        setError("状态暂未更新，已保留上次任务数据。");
      });
  }, []);

  useEffect(() => {
    if (workMode === "run") {
      if (!verifiedProgramSpecs.length) {
        setSchemaDraft(null);
        return;
      }
      const selectedVerifiedProgram =
        verifiedProgramSpecs.find(
          (programSpec) =>
            programSpec.schema_signature === selectedVerifiedProgramSignature
        ) ?? verifiedProgramSpecs[0];
      if (
        selectedVerifiedProgram &&
        selectedVerifiedProgram.schema_signature !==
          selectedVerifiedProgramSignature
      ) {
        setSelectedVerifiedProgramSignature(
          selectedVerifiedProgram.schema_signature
        );
      }
      setSchemaDraft(cloneSchema(selectedVerifiedProgram.schema_spec));
      return;
    }

    if (!schemas.length) {
      setSchemaDraft(
        useCustomSchema
          ? {
              name: "自定义 Schema",
              description: "",
              domain: "",
              fields: [],
            }
          : null,
      );
      return;
    }
    const selectedSchema =
      schemas.find((schema) => schema.name === selectedSchemaName) ?? schemas[0];
    if (selectedSchema.name !== selectedSchemaName) {
      setSelectedSchemaName(selectedSchema.name);
    }
    setSchemaDraft(cloneSchema(selectedSchema));
  }, [
    schemas,
    selectedSchemaName,
    selectedVerifiedProgramSignature,
    verifiedProgramSpecs,
    useCustomSchema,
    workMode,
  ]);

  const activeSchema =
    assistantDraft?.schema_spec ??
    extraction?.schema_spec ??
    (useCustomSchema ? schemaDraft : null);
  const fieldsByName = useMemo(() => indexFieldsByName(activeSchema), [activeSchema]);
  const hasInput = Boolean(targetUrl.trim() || htmlInput.trim());
  const requiresSchemaForRun = workMode === "run" && !schemaDraft;
  const canRun = Boolean(hasInput && !requiresSchemaForRun && runState !== "running");
  const canEditSchema = workMode === "create" && useCustomSchema;
  const hasRunStarted = runState !== "idle" || Boolean(extraction);
  const inputMode = htmlInput.trim()
    ? "使用粘贴 HTML"
    : targetUrl.trim()
      ? "从目标 URL 采集"
      : "等待目标 URL";
  const programSpecMode = programSpecModeText(
    extraction?.program_generation_mode,
    extraction?.program_reused,
    reuseVerifiedProgram
  );
  const schemaMode = schemaModeText(
    extraction?.schema_generation_mode,
    useCustomSchema
  );
  const modeCopy = modeContent[workMode];
  const isCreateMode = workMode === "create";
  const isRunMode = workMode === "run";
  const selectedVerifiedProgram = verifiedProgramSpecs.find(
    (programSpec) =>
      programSpec.schema_signature === selectedVerifiedProgramSignature
  );

  async function runExtraction() {
    if (!hasInput) {
      return;
    }
    if (workMode === "run" && !schemaDraft) {
      setError(
        verifiedProgramSpecs.length
          ? "运行 ProgramSpec 需要先选择一个已验证版本。"
          : "还没有已验证 ProgramSpec，请先在复核中标记可复用版本。"
      );
      return;
    }
    const createUsesManualSchema = workMode === "create" && useCustomSchema;
    if ((workMode === "run" || createUsesManualSchema) && !schemaDraft) {
      setError("固定字段契约尚未加载，请关闭固定契约或连接后端。");
      return;
    }
    setRunState("running");
    setError("");
    setExtraction(null);
    setHtmlDrawerOpen(false);
    setSchemaDrawerOpen(false);
    try {
      const data =
        workMode === "run"
          ? await runExtractionRequest({
              mode: "run_verified",
              targetUrl,
              htmlInput,
              schema: schemaDraft!,
            }, (snapshot) => {
              window.localStorage.setItem("webstruct.activeTaskId", snapshot.task_id);
              setRunState(snapshot.status === "failed" ? "failed" : "running");
            })
          : await runExtractionRequest({
              mode: "create",
              targetUrl,
              htmlInput,
              schema: createUsesManualSchema ? schemaDraft : null,
              programSpec: null,
            }, (snapshot) => {
              window.localStorage.setItem("webstruct.activeTaskId", snapshot.task_id);
              setRunState(snapshot.status === "failed" ? "failed" : "running");
            });
      setExtraction(data);
      setReviewFields(toReviewFields(data));
      setRuleName(defaultRuleName(data));
      setMarkProgramVerified(false);
      setReviewMessage("");
      setAssistantDraft(null);
      setAssistantError("");
      setRunState(data.errors.length ? "failed" : "done");
    } catch (currentError) {
      setRunState("failed");
      setError(currentError instanceof Error ? currentError.message : "抽取失败");
    }
  }

  async function runBenchmark() {
    if (!activeSchema) {
      setError("请先在创建模式中打开“手动字段范围”，提供 Schema 后再运行评测。");
      return;
    }
    setBenchmarkState("running");
    setBenchmark(null);
    setError("");
    try {
      const dataset: BenchmarkDataset = {
        name: "工作台显式样例评测",
        items: [{
          item_id: "workbench-sample",
          url: targetUrl,
          html: htmlInput.trim() || sampleHtml,
          schema_spec: activeSchema,
          gold_record: {},
        }],
      };
      const data = await runBenchmarkRequest(dataset, (snapshot) => {
        window.localStorage.setItem(
          "webstruct.activeTask",
          JSON.stringify({ kind: "benchmark", task_id: snapshot.task_id }),
        );
      });
      setBenchmark(data);
      setBenchmarkState(data.errors.length ? "failed" : "done");
      window.localStorage.removeItem("webstruct.activeTask");
    } catch (currentError) {
      setBenchmarkState("failed");
      setError(
        currentError instanceof Error ? currentError.message : "Benchmark 失败"
      );
    }
  }

  async function submitReview() {
    if (workMode !== "create") {
      return;
    }
    if (!extraction?.program_spec) {
      return;
    }
    setReviewState("running");
    setReviewMessage("");
    setError("");
    try {
      const data = await submitManualReviewRequest({
        extraction,
        reviewFields,
        markProgramVerified,
        ruleName,
      });
      if (data.program_verified) {
        try {
          await refreshVerifiedProgramSpecs();
        } catch {
          // Keep the successful save visible even if the refresh fails.
        }
      }
      setReviewState("done");
      setReviewMessage(
        data.program_verified
          ? `已保存 ${data.field_count} 个复核字段，并将“${ruleName.trim() || extraction.schema_spec.name}”标记为可复用规则。`
          : `已保存 ${data.field_count} 个复核字段。`
      );
    } catch (currentError) {
      setReviewState("failed");
      setError(
        currentError instanceof Error ? currentError.message : "复核提交失败"
      );
    }
  }

  async function sendAssistantMessage() {
    if (workMode !== "create") {
      return;
    }
    if (!extraction || !assistantMessage.trim()) {
      return;
    }
    setAssistantState("running");
    setAssistantError("");
    try {
      const data = await reviseSpecWithAssistant({
        extraction,
        message: assistantMessage,
      });
      setAssistantDraft(data);
      setAssistantState("done");
    } catch (currentError) {
      setAssistantState("failed");
      setAssistantError(
        currentError instanceof Error ? currentError.message : "Spec 协作失败"
      );
    }
  }

  function applyAssistantDraft() {
    if (workMode !== "create") {
      return;
    }
    if (!assistantDraft || !extraction) {
      return;
    }
    setExtraction({
      ...extraction,
      schema_spec: assistantDraft.schema_spec,
      program_spec: assistantDraft.program_spec,
      schema_generation_mode: "assistant_draft",
      program_generation_mode: "assistant_draft",
    });
    setReviewFields(toReviewFields({
      ...extraction,
      schema_spec: assistantDraft.schema_spec,
      program_spec: assistantDraft.program_spec,
    }));
    setRuleName(defaultRuleName({
      ...extraction,
      schema_spec: assistantDraft.schema_spec,
    }));
    setMarkProgramVerified(false);
    setReviewMessage("");
  }

  async function rerunWithAssistantDraft() {
    if (workMode !== "create") {
      return;
    }
    if (!assistantDraft || !extraction) {
      return;
    }
    const preservedHtml = htmlInput.trim()
      ? htmlInput
      : extraction.view_bundle?.raw_html ?? "";
    setRunState("running");
    setError("");
    try {
      const data = await runExtractionRequest({
        mode: "create",
        targetUrl: extraction.view_bundle?.url ?? targetUrl,
        htmlInput: preservedHtml,
        schema: assistantDraft.schema_spec,
        programSpec: assistantDraft.program_spec,
      });
      setExtraction(data);
      setReviewFields(toReviewFields(data));
      setRuleName(defaultRuleName(data));
      setMarkProgramVerified(false);
      setReviewMessage("");
      setRunState(data.errors.length ? "failed" : "done");
    } catch (currentError) {
      setRunState("failed");
      setError(currentError instanceof Error ? currentError.message : "重新抽取失败");
    }
  }

  function switchToCreateModeForRevision() {
    setWorkMode("create");
    setAssistantDraft(null);
    setAssistantError("");
    setAssistantOpen(false);
    setReviewMessage("");
  }

  return (
    <main className="app-shell">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">WebStruct-Agent</p>
          <h1>ProgramSpec 工作台</h1>
          <p className="header-summary">
            创建页负责生成、修订和保存规则；运行页只复用已验证规则。
          </p>
        </div>
        {runState !== "idle" ? (
          <div className="header-actions">
            <RunStateBadge state={runState} />
          </div>
        ) : null}
      </section>

      <section className="flow-layout">
        <div className="flow-main">
          <section className="mode-switcher" aria-label="ProgramSpec 工作模式">
            <button
              className={`mode-card${workMode === "create" ? " mode-card-active" : ""}`}
              type="button"
              onClick={() => setWorkMode("create")}
              aria-pressed={workMode === "create"}
            >
              <span className="mode-card-icon">
                <Wrench size={22} weight="duotone" />
              </span>
              <span>
                <strong>创建规则</strong>
                <small>从 URL 生成字段和 ProgramSpec</small>
              </span>
              {workMode === "create" ? <CheckCircle size={18} weight="fill" /> : null}
            </button>
            <button
              className={`mode-card${workMode === "run" ? " mode-card-active" : ""}`}
              type="button"
              onClick={() => setWorkMode("run")}
              aria-pressed={workMode === "run"}
            >
              <span className="mode-card-icon">
                <GitBranch size={22} weight="duotone" />
              </span>
              <span>
                <strong>运行规则</strong>
                <small>复用人工验证版本</small>
              </span>
              {workMode === "run" ? <CheckCircle size={18} weight="fill" /> : null}
            </button>
          </section>

          <article className="flow-node flow-node-primary">
            <div className="node-index">1</div>
            <div className="node-body">
              <div className="node-heading">
                <div>
                  <p className="panel-kicker">{modeCopy.kicker}</p>
                  <h2>{modeCopy.title}</h2>
                </div>
                <span className="schema-chip">
                  {modeCopy.chip(useCustomSchema, schemaDraft, selectedVerifiedProgram)}
                </span>
              </div>

              <div className="url-run-row">
                <label className="url-field">
                  <span>目标 URL</span>
                  <input
                    inputMode="url"
                    value={targetUrl}
                    onChange={(event) => setTargetUrl(event.target.value)}
                    placeholder="https://example.edu/notice/001"
                  />
                </label>
                <button
                  className="primary-button run-button"
                  type="button"
                  onClick={runExtraction}
                  disabled={!canRun}
                >
                  {runState === "running" ? (
                    isCreateMode ? "生成与抽取中" : "规则运行中"
                  ) : (
                    <>
                      <Play size={16} weight="fill" />
                      {modeCopy.action}
                    </>
                  )}
                </button>
              </div>

              {workMode === "run" ? (
                <label className="quick-schema-select">
                  <span>已验证 ProgramSpec</span>
                  <select
                    value={selectedVerifiedProgramSignature}
                    onChange={(event) =>
                      setSelectedVerifiedProgramSignature(event.target.value)
                    }
                    disabled={!verifiedProgramSpecs.length}
                  >
                    {verifiedProgramSpecs.length ? (
                      verifiedProgramSpecs.map((programSpec) => (
                        <option
                          key={programSpec.schema_signature}
                          value={programSpec.schema_signature}
                        >
                          {programSpec.rule_name || programSpec.schema_name}
                          {" · "}
                          {programSpec.program_count} 条规则
                        </option>
                      ))
                    ) : (
                      <option value="">暂无已验证 ProgramSpec</option>
                    )}
                  </select>
                  <p className="input-note">
                    {verifiedProgramSpecs.length
                      ? `已保存 ${verifiedProgramSpecs.length} 个可复用版本`
                      : "先在人工复核中标记可复用版本，再到这里运行。"}
                  </p>
                </label>
              ) : null}

              <p className="input-note">
                {requiresSchemaForRun
                  ? "需要先加载字段契约，才能查找已验证 ProgramSpec。"
                  : modeCopy.note}
              </p>

              <div className="mode-path" aria-label={modeCopy.pathLabel}>
                {modeCopy.steps.map((step, index) => (
                  <span key={step}>
                    <strong>{index + 1}</strong>
                    {step}
                  </span>
                ))}
              </div>

              <details
                className="advanced-drawer"
                open={htmlDrawerOpen}
                onToggle={(event) =>
                  setHtmlDrawerOpen(event.currentTarget.open)
                }
              >
                <summary>
                  <FileHtml size={16} weight="duotone" />
                  粘贴 HTML（可选）
                  {htmlInput.trim() ? <span>已填写，优先使用</span> : null}
                </summary>
                <textarea
                  value={htmlInput}
                  onChange={(event) => setHtmlInput(event.target.value)}
                  rows={8}
                  placeholder="可选：URL 无法访问或本地调试时粘贴 HTML，系统会优先使用这段页面内容。"
                />
                <div className="inline-actions">
                  <button
                    className="button-secondary"
                    type="button"
                    onClick={() => setHtmlInput(sampleHtml)}
                  >
                    载入样例 HTML
                  </button>
                  <button
                    className="button-secondary"
                    type="button"
                    onClick={() => setHtmlInput("")}
                    disabled={!htmlInput}
                  >
                    清空 HTML
                  </button>
                </div>
              </details>

              <details
                className="advanced-drawer"
                open={schemaDrawerOpen}
                onToggle={(event) =>
                  setSchemaDrawerOpen(event.currentTarget.open)
                }
              >
                <summary>
                  <BracketsCurly size={16} weight="duotone" />
                  {workMode === "create" ? "字段范围（可选）" : "运行设置"}
                  <span>
                    {workMode === "run"
                      ? "只复用验证版"
                      : useCustomSchema
                        ? `${schemaDraft?.fields.length ?? 0} 个手动字段`
                        : "URL-first 自动"}
                  </span>
                </summary>
                {workMode === "create" ? (
                  <>
                    <div className="program-policy">
                      <strong>手动指定字段</strong>
                      <p>
                        默认关闭。关闭时 AI 会先读取当前 URL，再自行生成字段契约和新的 ProgramSpec；只有已明确字段范围或做对照实验时才打开。
                      </p>
                      <label className="checkbox-control">
                        <input
                          type="checkbox"
                          checked={useCustomSchema}
                          onChange={(event) => setUseCustomSchema(event.target.checked)}
                        />
                        启用手动字段范围
                      </label>
                    </div>
                    <div className="program-policy">
                      <strong>规则生成方式</strong>
                      <p>
                        创建模式会生成当前页面专属的新 ProgramSpec，不复用旧规则。需要复用已验证版本时，请切换到“运行规则”。
                      </p>
                    </div>
                  </>
                ) : (
                  <div className="program-policy">
                    <strong>只读运行</strong>
                    <p>
                      运行模式只查找人工验证过的 ProgramSpec。没有匹配版本时会明确失败，不会自动创建或保存新规则。
                    </p>
                  </div>
                )}
                {canEditSchema ? (
                  <>
                    <label className="field-control">
                      <span>字段契约来源</span>
                      <select
                        value={selectedSchemaName}
                        onChange={(event) => setSelectedSchemaName(event.target.value)}
                      >
                        {schemas.map((schema) => (
                          <option key={schema.name} value={schema.name}>
                            {schema.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    {schemaDraft ? (
                      <>
                        <div className="field-editor-grid schema-meta-grid">
                          <label className="field-control">
                            <span>Schema 名称</span>
                            <input
                              value={schemaDraft.name}
                              onChange={(event) =>
                                setSchemaDraft((current) =>
                                  current
                                    ? { ...current, name: event.target.value }
                                    : current,
                                )
                              }
                              placeholder="例如：课程公告字段"
                            />
                          </label>
                          <label className="field-control">
                            <span>领域标识</span>
                            <input
                              value={schemaDraft.domain}
                              onChange={(event) =>
                                setSchemaDraft((current) =>
                                  current
                                    ? { ...current, domain: event.target.value }
                                    : current,
                                )
                              }
                              placeholder="例如：course_notice"
                            />
                          </label>
                        </div>
                        <div className="schema-summary">
                          <span>{schemaDraft.description || schemaDraft.domain}</span>
                          <strong>{schemaDraft.fields.length} fields</strong>
                        </div>
                        <div className="schema-toolbar">
                          <button
                            className="button-secondary"
                            type="button"
                            onClick={() =>
                              setSchemaDraft((current) => appendEmptyField(current))
                            }
                          >
                            <Plus size={15} weight="bold" />
                            添加字段
                          </button>
                        </div>
                        <div className="schema-fields">
                          {schemaDraft.fields.map((field, index) => (
                            <FieldEditor
                              key={`${field.name}-${index}`}
                              field={field}
                              index={index}
                              onChange={(nextField) =>
                                setSchemaDraft((current) =>
                                  updateField(current, index, nextField)
                                )
                              }
                              onRemove={() =>
                                setSchemaDraft((current) => removeField(current, index))
                              }
                            />
                          ))}
                        </div>
                      </>
                    ) : null}
                  </>
                ) : null}
                {workMode === "run" && schemaDraft ? (
                  <div className="schema-summary">
                    <span>{schemaDraft.description || schemaDraft.domain}</span>
                    <strong>{schemaDraft.fields.length} fields</strong>
                  </div>
                ) : null}
              </details>
            </div>
          </article>

          {error ? <p className="error-banner">{error}</p> : null}

          {!hasRunStarted ? (
            <section className="start-guide">
              <GitBranch size={22} weight="duotone" />
              <div>
                <strong>{isCreateMode ? "从 URL 创建规则" : "复用已验证规则"}</strong>
                <p>{modeCopy.emptyHint}</p>
              </div>
            </section>
          ) : null}

          {extraction ? (
            <section className="spec-summary-strip" aria-label="Spec 草稿摘要">
              <div>
                <span>字段契约</span>
                <strong>
                  {extraction.schema_spec.name} · {extraction.schema_spec.fields.length} 个字段
                </strong>
                <small>{schemaMode}</small>
              </div>
              <div>
                <span>ProgramSpec</span>
                <strong>
                  {extraction.program_spec?.field_programs.length ?? 0} 条规则
                </strong>
                <small>{programSpecMode}</small>
              </div>
              <div>
                <span>质量检查</span>
                <strong>
                  {extraction.verification_report
                    ? extraction.verification_report.passed
                      ? "可进入复核"
                      : "需要修订"
                    : "等待校验"}
                </strong>
                <small>
                  {extraction.verification_report
                    ? `${extraction.verification_report.issues.length} 个问题`
                    : "校验节点尚未输出"}
                </small>
              </div>
              {isCreateMode ? (
                <div>
                  <span>下一步</span>
                  <strong>
                    {extraction.verification_report?.passed
                      ? "复核并保存规则"
                      : "修订后重新运行"}
                  </strong>
                  <small>草稿不会自动变成可复用版本</small>
                </div>
              ) : null}
            </section>
          ) : null}

          {runState === "running" || extraction ? (
            <details className="workflow-drawer">
              <summary>
                <GitBranch size={16} weight="duotone" />
                运行进度
                <span>{runState === "running" ? "运行中" : "查看步骤"}</span>
              </summary>
              <WorkflowRail extraction={extraction} runState={runState} />
            </details>
          ) : null}

          {runState === "running" || extraction ? (
            <section className="results-grid" aria-label="抽取输出">
              <ExtractionResultsPanel
                extraction={extraction}
                fieldsByName={fieldsByName}
                isRunning={runState === "running"}
                allowSpecCollaboration={isCreateMode}
                title={isCreateMode ? "抽取结果" : "规则执行结果"}
                readOnlyNotice={
                  isRunMode
                    ? "运行模式只复用已验证 ProgramSpec。这里只能查看执行结果、证据和校验问题，不会修改或保存 Spec。"
                    : undefined
                }
                assistantDraft={assistantDraft}
                assistantMessage={assistantMessage}
                setAssistantMessage={setAssistantMessage}
                assistantState={assistantState}
                assistantError={assistantError}
                assistantOpen={assistantOpen}
                setAssistantOpen={setAssistantOpen}
                onSendAssistantMessage={sendAssistantMessage}
                onApplyAssistantDraft={applyAssistantDraft}
                onRerunWithAssistantDraft={rerunWithAssistantDraft}
              />
              {isRunMode ? (
                <section className="panel run-readonly-panel">
                  <div className="panel-heading">
                    <div>
                      <p className="panel-kicker">READ ONLY</p>
                      <h2>需要修订规则？</h2>
                    </div>
                    <button
                      className="button-secondary"
                      type="button"
                      onClick={switchToCreateModeForRevision}
                    >
                      回到创建模式修订
                    </button>
                  </div>
                  <p>
                    运行模式不会协作制定、人工复核或保存 ProgramSpec。若当前已验证版本不适合这个页面，请回到创建模式生成新版草稿。
                  </p>
                </section>
              ) : null}
              <VerificationReportPanel
                extraction={extraction}
                isRunning={runState === "running"}
                onOpenSpecAssistant={
                  isCreateMode ? () => setAssistantOpen(true) : undefined
                }
              />
              {isCreateMode ? (
                <ManualReviewPanel
                  extraction={extraction}
                  reviewFields={reviewFields}
                  setReviewFields={setReviewFields}
                  ruleName={ruleName}
                  setRuleName={setRuleName}
                  markProgramVerified={markProgramVerified}
                  setMarkProgramVerified={setMarkProgramVerified}
                  reviewState={reviewState}
                  reviewMessage={reviewMessage}
                  onSubmitReview={submitReview}
                />
              ) : null}
              <ProgramSpecPreviewPanel
                programSpec={extraction?.program_spec}
                schemaSpec={extraction?.schema_spec}
              />
            </section>
          ) : null}

          {hasRunStarted || benchmarkState !== "idle" || benchmark ? (
            <details className="diagnostics-drawer">
              <summary>
                <GitBranch size={16} weight="duotone" />
                证据与诊断
                <span>证据、Trace、运行参数、论文评测</span>
              </summary>
              <section className="diagnostics-grid" aria-label="证据与诊断信息">
                <EvidencePanel
                  extraction={extraction}
                  isRunning={runState === "running"}
                />
                <AgentTracePanel extraction={extraction} />
                <details className="context-panel compact-details">
                  <summary>本次运行参数</summary>
                  <dl className="context-list">
                    <div>
                      <dt>模式</dt>
                      <dd>{workMode === "create" ? "创建规则" : "运行规则"}</dd>
                    </div>
                    <div>
                      <dt>输入</dt>
                      <dd>{inputMode}</dd>
                    </div>
                    <div>
                      <dt>Schema</dt>
                      <dd>{schemaMode}</dd>
                    </div>
                    <div>
                      <dt>ProgramSpec</dt>
                      <dd>{programSpecMode}</dd>
                    </div>
                    {extraction ? (
                      <>
                        <div>
                          <dt>字段契约</dt>
                          <dd>{extraction.schema_spec.name}</dd>
                        </div>
                        <div>
                          <dt>任务</dt>
                          <dd>{extraction.task_id}</dd>
                        </div>
                      </>
                    ) : null}
                    {extraction?.schema_generation_error ? (
                      <div>
                        <dt>Schema 降级</dt>
                        <dd>{extraction.schema_generation_error}</dd>
                      </div>
                    ) : null}
                    {extraction?.program_generation_error ? (
                      <div>
                        <dt>生成降级</dt>
                        <dd>{extraction.program_generation_error}</dd>
                      </div>
                    ) : null}
                  </dl>
                </details>

                <details
                  className="context-panel compact-details"
                  open={
                    connectionState === "offline" ||
                    runState === "failed" ||
                    health?.llm_configured === false
                  }
                >
                  <summary>系统状态</summary>
                  <dl className="context-list">
                    <div>
                      <dt>连接</dt>
                      <dd>{statusTextFor(connectionState)}</dd>
                    </div>
                    <div>
                      <dt>模型</dt>
                      <dd>{health?.llm_model ?? "等待后端"}</dd>
                    </div>
                    <div>
                      <dt>LLM</dt>
                      <dd>{health ? (health.llm_configured ? "已配置" : "未配置") : "等待后端"}</dd>
                    </div>
                    <div>
                      <dt>数据库</dt>
                      <dd>{health?.database_driver ?? "等待后端"}</dd>
                    </div>
                  </dl>
                </details>

                <details className="context-panel compact-details">
                  <summary>论文评测（可选）</summary>
                  <BenchmarkPanel
                    benchmark={benchmark}
                    benchmarkState={benchmarkState}
                    onRunBenchmark={runBenchmark}
                  />
                </details>
              </section>
            </details>
          ) : null}
        </div>
      </section>
    </main>
  );
}

const modeContent: Record<
  WorkMode,
  {
    kicker: string;
    title: string;
    action: string;
    note: string;
    emptyHint: string;
    pathLabel: string;
    steps: string[];
    chip: (
      useCustomSchema: boolean,
      schemaDraft: SchemaSpec | null,
      selectedProgram?: VerifiedProgramSpecSummary
    ) => string;
  }
> = {
  create: {
    kicker: "CREATE",
    title: "创建抽取规则（ProgramSpec）",
    action: "AI 创建规则并抽取",
    note: "输入 URL 后，系统会先读取页面，再生成字段契约和 ProgramSpec。",
    emptyHint: "填入目标 URL 后，AI 会基于当前页面生成字段契约和 ProgramSpec，并马上跑一次抽取与质量检查。",
    pathLabel: "创建规则流程",
    steps: ["读取页面", "设计字段", "生成规则", "抽取校验"],
    chip: (useCustomSchema, schemaDraft) =>
      useCustomSchema ? schemaDraft?.name ?? "Schema 加载中" : "URL-first 自动",
  },
  run: {
    kicker: "RUN",
    title: "运行已验证规则",
    action: "运行规则",
    note: "选择人工验证过的 ProgramSpec，只执行抽取，不修订或保存规则。",
    emptyHint: "先选择一个已验证 ProgramSpec，再输入同类页面 URL。运行页只展示执行结果，不提供修订或保存入口。",
    pathLabel: "运行规则流程",
    steps: ["选择规则", "输入 URL", "执行抽取", "查看结果"],
    chip: (_useCustomSchema, schemaDraft, selectedProgram) =>
      selectedProgram?.rule_name ||
      selectedProgram?.schema_name ||
      schemaDraft?.name ||
      "请选择已验证规则",
  },
};

function statusTextFor(connectionState: ConnectionState): string {
  return {
    checking: "检测中",
    online: "已连接",
    offline: "未连接",
  }[connectionState];
}

function schemaModeText(
  mode: string | undefined,
  useCustomSchema: boolean
): string {
  if (mode === "llm") {
    return "AI 根据当前 URL 生成";
  }
  if (mode === "provided") {
    return "使用固定字段契约";
  }
  return useCustomSchema ? "运行时使用固定字段契约" : "运行时 AI 生成";
}

function programSpecModeText(
  mode: string | undefined,
  reused: boolean | undefined,
  reuseRequested: boolean
): string {
  if (reused || mode === "reused") {
    return "已复用人工验证版本";
  }
  if (mode === "llm") {
    return "AI 根据当前 URL 生成";
  }
  if (mode === "deterministic_fallback") {
    return "AI 不可用，确定性兜底";
  }
  return reuseRequested ? "只运行已验证 ProgramSpec，未匹配则失败" : "运行时 AI 生成";
}

function indexFieldsByName(schema: SchemaSpec | null): Map<string, FieldSpec> {
  const fieldsByName = new Map<string, FieldSpec>();
  schema?.fields.forEach((field) => fieldsByName.set(field.name, field));
  return fieldsByName;
}

function defaultRuleName(extraction: Pick<ExtractionResponse, "schema_spec" | "view_bundle">): string {
  const pageTitle = extraction.view_bundle?.title?.trim();
  if (pageTitle) {
    return `${pageTitle.slice(0, 28)} 抽取规则`;
  }
  return `${extraction.schema_spec.name} 抽取规则`;
}
