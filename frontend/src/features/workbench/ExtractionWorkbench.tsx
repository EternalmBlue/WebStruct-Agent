import { useMemo, useState } from "react";
import {
  ArrowClockwise,
  Check,
  Eye,
  FloppyDisk,
  Plus,
  Sparkle,
  Trash,
  ArrowUUpLeft,
} from "@phosphor-icons/react";

import { runFieldValueAssist } from "../../api/webstructApi";
import { appendEmptyField, updateField } from "../../lib/schemaDraft";
import { formatValue } from "../../lib/formatters";
import type {
  ExtractionResponse,
  FieldExtractionResult,
  FieldSpec,
  ProgramSpecSummary,
  SchemaSpec,
  RunState,
  SpecAssistantResponse,
} from "../../types/webstruct";

type FieldValueState = {
  guidance: string;
  state: RunState;
  message: string;
};

export function ExtractionWorkbench({
  extraction,
  schema,
  onSchemaChange,
  onSchemaAssist,
  schemaAssistState,
  schemaAssistMessage,
  onFieldResult,
  onFieldProgram,
  onCheck,
  onGuidanceChange,
}: {
  extraction: ExtractionResponse;
  schema: SchemaSpec;
  onSchemaChange: (schema: SchemaSpec) => void;
  onSchemaAssist: (message: string) => void;
  schemaAssistState: RunState;
  schemaAssistMessage: string;
  onFieldResult: (result: FieldExtractionResult) => void;
  onFieldProgram: (fieldName: string, program: ProgramSpecSummary["field_programs"]) => void;
  onCheck: () => void;
  onGuidanceChange: (fieldName: string, guidance: string) => void;
}) {
  const [activeFieldName, setActiveFieldName] = useState(
    schema.fields[0]?.name ?? "",
  );
  const [archivedFields, setArchivedFields] = useState<FieldSpec[]>([]);
  const [schemaMessage, setSchemaMessage] = useState("");
  const [valueStates, setValueStates] = useState<Record<string, FieldValueState>>(
    {},
  );

  const resultsByName = useMemo(
    () =>
      new Map(
        (extraction.extraction_result?.fields ?? []).map((result) => [
          result.field_name,
          result,
        ]),
      ),
    [extraction.extraction_result?.fields],
  );
  const activeField = schema.fields.find(
    (field) => field.name === activeFieldName,
  ) ?? schema.fields[0];
  const activeResult = activeField ? resultsByName.get(activeField.name) : undefined;
  const activeEvidence = activeResult?.evidence[0];
  const snapshotText =
    extraction.view_bundle?.text ||
    extraction.view_bundle?.lines?.join("\n") ||
    "当前任务没有可展示的页面文本快照。";
  const visibleFields = schema.fields.filter(
    (field) =>
      !archivedFields.some((archivedField) => archivedField.name === field.name),
  );
  const archived = archivedFields;

  function updateSchema(nextSchema: SchemaSpec) {
    onSchemaChange(nextSchema);
    if (!nextSchema.fields.some((field) => field.name === activeFieldName)) {
      setActiveFieldName(nextSchema.fields[0]?.name ?? "");
    }
  }

  function addField() {
    const nextSchema = appendEmptyField(schema);
    if (!nextSchema) return;
    const nextField = nextSchema.fields[nextSchema.fields.length - 1];
    setArchivedFields((current) =>
      current.filter((field) => field.name !== nextField.name),
    );
    setActiveFieldName(nextField.name);
    updateSchema(nextSchema);
  }

  function archiveField(field: FieldSpec) {
    if (visibleFields.length <= 1) {
      return;
    }
    setArchivedFields((current) => [
      ...current.filter((candidate) => candidate.name !== field.name),
      field,
    ]);
    onSchemaChange({
      ...schema,
      fields: schema.fields.filter((candidate) => candidate.name !== field.name),
    });
    const next = schema.fields.find((candidate) => candidate.name !== field.name);
    if (next) setActiveFieldName(next.name);
  }

  function restoreField(field: FieldSpec) {
    setArchivedFields((current) =>
      current.filter((candidate) => candidate.name !== field.name),
    );
    onSchemaChange({
      ...schema,
      fields: [...schema.fields, field],
    });
    setActiveFieldName(field.name);
  }

  function setFieldGuidance(fieldName: string, guidance: string) {
    setValueStates((current) => ({
      ...current,
      [fieldName]: {
        guidance,
        state: current[fieldName]?.state ?? "idle",
        message: current[fieldName]?.message ?? "",
      },
    }));
    onGuidanceChange(fieldName, guidance);
  }

  async function retryField(field: FieldSpec) {
    if (!extraction.task_id) return;
    const guidance = valueStates[field.name]?.guidance ?? "";
    setValueStates((current) => ({
      ...current,
      [field.name]: { guidance, state: "running", message: "" },
    }));
    try {
      const response = await runFieldValueAssist({
        taskId: extraction.task_id,
        field,
        guidanceValue: guidance,
      });
      onFieldResult(response.result);
      onFieldProgram(field.name, response.program_spec.field_programs);
      setValueStates((current) => ({
        ...current,
        [field.name]: { guidance, state: "done", message: response.assistant_message },
      }));
    } catch (error) {
      setValueStates((current) => ({
        ...current,
        [field.name]: {
          guidance,
          state: "failed",
          message: error instanceof Error ? error.message : "字段协作失败",
        },
      }));
    }
  }

  return (
    <section className="extraction-workbench" aria-label="字段抽取协作工作台">
      <div className="workbench-heading">
        <div>
          <p className="panel-kicker">COLLABORATIVE EXTRACTION</p>
          <h2>页面证据与字段协作</h2>
          <p>
            当前页面只读取一次。字段方案和字段值分别协作，修改字段不会重新截图；
            只有重新读取 URL 才会生成新的页面快照。
          </p>
        </div>
        <span className="snapshot-pill">
          <Eye size={15} weight="duotone" />
          快照已锁定
        </span>
      </div>

      <div className="workbench-grid">
        <section className="snapshot-panel">
          <div className="panel-heading compact-heading">
            <div>
              <p className="panel-kicker">CLOAKBROWSER SNAPSHOT</p>
              <h3>{extraction.view_bundle?.title || "当前页面"}</h3>
            </div>
            <span className="snapshot-url">
              {extraction.view_bundle?.url || "HTML 输入"}
            </span>
          </div>
          {extraction.view_bundle?.raw_html ? (
            <iframe
              className="snapshot-frame"
              title="CloakBrowser 页面快照"
              sandbox=""
              srcDoc={extraction.view_bundle.raw_html}
            />
          ) : (
            <div className="snapshot-frame snapshot-frame-empty">
              页面没有返回可渲染 HTML，使用下方文本证据视图。
            </div>
          )}
          <div className="evidence-focus">
            <div className="evidence-focus-heading">
              <strong>引用出处高亮</strong>
              <span>{activeField?.name || "未选择字段"}</span>
            </div>
            <p className="highlighted-text">
              {renderHighlightedText(snapshotText, activeEvidence)}
            </p>
            {activeEvidence ? (
              <small>
                {activeEvidence.source} · 证据置信度{" "}
                {Math.round(activeEvidence.score * 100)}%
              </small>
            ) : (
              <small>点击右侧字段查看其证据；尚未命中时会保留整页文本。</small>
            )}
          </div>
        </section>

        <section className="field-collaboration-panel">
          <div className="collaboration-block schema-collaboration">
            <div className="collaboration-heading">
              <div>
                <p className="panel-kicker">FIELD SCHEMA AGENT</p>
                <h3>抽取哪些字段</h3>
              </div>
              <button className="button-secondary icon-button" type="button" onClick={addField}>
                <Plus size={15} weight="bold" />
                添加字段
              </button>
            </div>
            <p className="collaboration-note">
              你只需要描述想要的字段，规则逻辑仍由 AI 维护。
            </p>
            <div className="assistant-inline">
              <textarea
                value={schemaMessage}
                onChange={(event) => setSchemaMessage(event.target.value)}
                placeholder="例如：增加版权类型、插件中文名称和插件英文名称；删除不重要的作者字段。"
                rows={2}
              />
              <button
                className="primary-button"
                type="button"
                disabled={!schemaMessage.trim() || schemaAssistState === "running"}
                onClick={() => {
                  onSchemaAssist(schemaMessage);
                  setSchemaMessage("");
                }}
              >
                <Sparkle size={15} weight="fill" />
                {schemaAssistState === "running" ? "协作中" : "让 AI 调整字段"}
              </button>
            </div>
            {schemaAssistMessage ? (
              <p className="assistant-inline-message">{schemaAssistMessage}</p>
            ) : null}
            <div className="field-card-list">
              {visibleFields.map((field) => {
                const result = resultsByName.get(field.name);
                const isActive = activeField?.name === field.name;
                return (
                  <article className={`field-card${isActive ? " field-card-active" : ""}`} key={field.name}>
                    <button
                      className="field-card-select"
                      type="button"
                      onClick={() => setActiveFieldName(field.name)}
                    >
                      <span className="field-card-title">
                        <strong>{field.name}</strong>
                        <small>{field.type}{field.required ? " · 必填" : ""}</small>
                      </span>
                      <span className={`field-card-status field-card-status-${result?.status ?? "missing"}`}>
                        {fieldValueStatus(result?.status)}
                      </span>
                    </button>
                    <div className="field-card-edit">
                      <label>
                        <span>字段说明</span>
                        <input
                          value={field.description}
                          onChange={(event) =>
                            updateSchema(
                              updateField(
                                schema,
                                schema.fields.findIndex((item) => item.name === field.name),
                                { ...field, description: event.target.value },
                              ) ?? schema,
                            )
                          }
                        />
                      </label>
                      <button
                        className="icon-button danger-button"
                        type="button"
                        onClick={() => archiveField(field)}
                        title="暂时移出字段方案"
                      >
                        <Trash size={14} />
                        暂停
                      </button>
                    </div>
                    <div className="field-value-collaboration">
                      <label>
                        <span>当前抽取值</span>
                        <input
                          readOnly
                          value={formatValue(result?.normalized_value ?? result?.value ?? "")}
                          placeholder="未命中"
                        />
                      </label>
                      <label>
                        <span>引导值（参照当前页面）</span>
                        <input
                          value={
                            valueStates[field.name]?.guidance ??
                            String(result?.normalized_value ?? result?.value ?? "")
                          }
                          onFocus={() =>
                            setFieldGuidance(
                              field.name,
                              valueStates[field.name]?.guidance ??
                                String(result?.normalized_value ?? result?.value ?? ""),
                            )
                          }
                          onChange={(event) =>
                            setFieldGuidance(field.name, event.target.value)
                          }
                          placeholder="例如：页面中的插件中文名称"
                        />
                      </label>
                      <button
                        className="button-secondary field-retry-button"
                        type="button"
                        disabled={valueStates[field.name]?.state === "running"}
                        onClick={() => retryField(field)}
                      >
                        <ArrowClockwise size={14} />
                        {valueStates[field.name]?.state === "running" ? "重试中" : "协作此字段"}
                      </button>
                    </div>
                    {valueStates[field.name]?.message ? (
                      <small className={`field-task-message field-task-message-${valueStates[field.name].state}`}>
                        {valueStates[field.name].message}
                      </small>
                    ) : null}
                  </article>
                );
              })}
            </div>
            {archived.length ? (
              <div className="archived-fields">
                <strong>已暂停字段</strong>
                {archived.map((field) => (
                  <button
                    className="archived-field"
                    type="button"
                    key={field.name}
                    onClick={() => restoreField(field)}
                  >
                    <ArrowUUpLeft size={13} />
                    {field.name}
                    <span>恢复</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <div className="collaboration-footer">
            <span>
              <Check size={15} weight="bold" />
              字段调整会立即更新规则预览，值协作只影响当前字段。
            </span>
            <button className="primary-button" type="button" onClick={onCheck}>
              <FloppyDisk size={15} weight="fill" />
              下一步：质量检查
            </button>
          </div>
        </section>
      </div>
    </section>
  );
}

function renderHighlightedText(
  text: string,
  evidence?: { text: string; start_char?: number | null; end_char?: number | null },
) {
  if (!evidence) return text;
  const start =
    evidence.start_char != null
      ? evidence.start_char
      : Math.max(0, text.indexOf(evidence.text));
  const end =
    evidence.end_char != null
      ? evidence.end_char
      : start + evidence.text.length;
  if (start < 0 || end <= start || start >= text.length) return text;
  return (
    <>
      {text.slice(0, start)}
      <mark>{text.slice(start, Math.min(end, text.length))}</mark>
      {text.slice(Math.min(end, text.length))}
    </>
  );
}

function fieldValueStatus(status?: string): string {
  return (
    {
      extracted: "已命中",
      repaired: "已修复",
      missing: "未命中",
      fallback_failed: "需协作",
    }[status ?? "missing"] ?? "待处理"
  );
}
