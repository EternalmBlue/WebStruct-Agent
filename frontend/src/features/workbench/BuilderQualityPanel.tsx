import { ArrowRight, CheckCircle, Globe, Warning } from "@phosphor-icons/react";
import type { ExtractionResponse, RunState } from "../../types/webstruct";

export function BuilderQualityPanel({
  extraction,
  secondUrl,
  setSecondUrl,
  state,
  message,
  onCheck,
  onPreview,
  canPreview,
}: {
  extraction: ExtractionResponse;
  secondUrl: string;
  setSecondUrl: (value: string) => void;
  state: RunState;
  message: string;
  onCheck: () => void;
  onPreview: () => void;
  canPreview: boolean;
}) {
  const report = extraction.verification_report;
  return (
    <section className="panel builder-quality-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">QUALITY CHECK</p>
          <h2>质量检查</h2>
        </div>
        {report?.passed ? (
          <span className="quality-state quality-state-pass">
            <CheckCircle size={15} weight="fill" /> 已通过
          </span>
        ) : (
          <span className="quality-state quality-state-warn">
            <Warning size={15} weight="fill" /> 需要修订
          </span>
        )}
      </div>
      <p className="quality-lead">
        检查会在原页面快照上重新执行当前规则，不会重新读取第一页。可选填同域同结构的另一篇页面做泛化验证。
      </p>
      <label className="quality-url-field">
        <span><Globe size={14} /> 同结构第二 URL（可选）</span>
        <input
          value={secondUrl}
          onChange={(event) => setSecondUrl(event.target.value)}
          placeholder="https://同一论坛/分区/另一篇帖子"
        />
      </label>
      {message ? <p className="assistant-inline-message">{message}</p> : null}
      {report ? (
        <div className="quality-score">
          <strong>{Math.round(report.score * 100)}%</strong>
          <span>{report.issues.length ? `${report.issues.length} 个问题` : "证据、类型与置信度检查通过"}</span>
        </div>
      ) : null}
      {report?.issues.length ? (
        <ul className="quality-issues">
          {report.issues.map((issue, index) => (
            <li key={`${issue.field_name}-${issue.code}-${index}`}>
              <strong>{issue.field_name || "整体"}</strong>
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="quality-actions">
        <button className="primary-button" type="button" onClick={onCheck} disabled={state === "running"}>
          {state === "running" ? "检查中" : "重新检查当前规则"}
        </button>
        <button className="button-secondary" type="button" onClick={onPreview} disabled={!canPreview}>
          查看规则预览 <ArrowRight size={15} />
        </button>
      </div>
    </section>
  );
}
