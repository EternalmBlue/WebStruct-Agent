import type { ExtractionResponse } from "../../types/webstruct";
import { formatPercent } from "../../lib/formatters";
import { SkeletonRows } from "./Skeleton";

export function VerificationReportPanel({
  extraction,
  isRunning,
  onOpenSpecAssistant,
}: {
  extraction: ExtractionResponse | null;
  isRunning: boolean;
  onOpenSpecAssistant?: () => void;
}) {
  return (
    <section className="panel report-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="panel-kicker">QUALITY</p>
          <h2>质量检查</h2>
        </div>
      </div>
      {isRunning ? (
        <SkeletonRows count={3} />
      ) : extraction?.verification_report ? (
        <div className="report-block">
          <div className="score-line">
            <span>
              {extraction.verification_report.passed ? "通过" : "需要复核"}
            </span>
            <strong>{formatPercent(extraction.verification_report.score)}</strong>
          </div>
          {extraction.verification_report.issues.length ? (
            <>
              <div className="quality-action">
                <strong>建议先修订规则，再重新运行。</strong>
                <p>
                  这些问题来自当前字段契约、抽取值和证据之间的匹配检查。
                </p>
                {onOpenSpecAssistant ? (
                  <button
                    className="button-secondary"
                    type="button"
                    onClick={onOpenSpecAssistant}
                  >
                    让 AI 修订规则
                  </button>
                ) : null}
              </div>
              <ul className="issue-list">
                {extraction.verification_report.issues.map((issue, index) => (
                  <li key={`${issue.field_name}-${issue.code}-${index}`}>
                    <strong>{issue.field_name}</strong>
                    <span>{severityText(issue.severity)}</span>
                    {issue.message}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="empty-state positive-state">
              <strong>未发现明显问题</strong>
              <p>字段完整性、类型、日期格式和证据支持通过当前检查，可进入人工复核。</p>
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state">
          <strong>校验节点还没有输出</strong>
          <p>抽取完成后，这里会显示字段缺失、类型错误、证据不足等问题。</p>
        </div>
      )}
    </section>
  );
}

function severityText(severity: string): string {
  return (
    {
      error: "错误",
      warning: "提醒",
      info: "信息",
    }[severity] ?? severity
  );
}
