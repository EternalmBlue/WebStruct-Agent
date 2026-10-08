import type { ExtractionResponse, FieldSpec } from "../../types/webstruct";
import { formatPercent, formatValue } from "../../lib/formatters";
import { SkeletonRows } from "../common/Skeleton";
import { SpecAssistantPanel } from "../schema/SpecAssistantPanel";
import type { RunState, SpecAssistantResponse } from "../../types/webstruct";

export function ExtractionResultsPanel({
  extraction,
  fieldsByName,
  isRunning,
  allowSpecCollaboration,
  title,
  readOnlyNotice,
  assistantDraft,
  assistantMessage,
  setAssistantMessage,
  assistantState,
  assistantError,
  assistantOpen,
  setAssistantOpen,
  onSendAssistantMessage,
  onApplyAssistantDraft,
  onRerunWithAssistantDraft,
}: {
  extraction: ExtractionResponse | null;
  fieldsByName: Map<string, FieldSpec>;
  isRunning: boolean;
  allowSpecCollaboration: boolean;
  title: string;
  readOnlyNotice?: string;
  assistantDraft: SpecAssistantResponse | null;
  assistantMessage: string;
  setAssistantMessage: (message: string) => void;
  assistantState: RunState;
  assistantError: string;
  assistantOpen: boolean;
  setAssistantOpen: (isOpen: boolean) => void;
  onSendAssistantMessage: () => void;
  onApplyAssistantDraft: () => void;
  onRerunWithAssistantDraft: () => void;
}) {
  return (
    <section className="panel result-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">RESULT</p>
          <h2>{title}</h2>
        </div>
        {extraction?.schema_version ? (
          <span className="version-pill">
            Schema v{extraction.schema_version.version}
          </span>
        ) : null}
        {allowSpecCollaboration && extraction?.schema_spec ? (
          <SpecAssistantPanel
            extraction={extraction}
            draft={assistantDraft}
            message={assistantMessage}
            setMessage={setAssistantMessage}
            state={assistantState}
            error={assistantError}
            isOpen={assistantOpen}
            setIsOpen={setAssistantOpen}
            onSend={onSendAssistantMessage}
            onApply={onApplyAssistantDraft}
            onRerun={onRerunWithAssistantDraft}
          />
        ) : null}
      </div>
      {!allowSpecCollaboration && readOnlyNotice ? (
        <p className="read-only-note">{readOnlyNotice}</p>
      ) : null}
      {isRunning ? (
        <SkeletonRows count={5} />
      ) : extraction?.extraction_result ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>字段</th>
              <th>抽取值</th>
              <th className="technical-column">策略</th>
              <th>置信度</th>
              <th>结果</th>
            </tr>
          </thead>
          <tbody>
            {extraction.extraction_result.fields.map((field) => (
              <tr key={field.field_name}>
                <td>
                  {fieldsByName.get(field.field_name)?.description ||
                    field.field_name}
                </td>
                <td>{formatValue(field.normalized_value ?? field.value)}</td>
                <td className="technical-column">
                  <span className="strategy-pill">{field.strategy}</span>
                </td>
                <td>
                  <span className="confidence-meter">
                    <span style={{ width: formatPercent(field.confidence) }} />
                    {formatPercent(field.confidence)}
                  </span>
                </td>
                <td>
                  <span className={`field-status field-status-${field.status}`}>
                    {fieldStatusText(field.status)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="empty-state">
          <strong>字段节点还没有输出</strong>
          <p>运行抽取后，这里会显示字段值、策略和置信度。</p>
        </div>
      )}
    </section>
  );
}

function fieldStatusText(status: string): string {
  return (
    {
      extracted: "已抽取",
      repaired: "已修复",
      missing: "缺失",
      fallback_failed: "未命中",
    }[status] ?? status
  );
}
