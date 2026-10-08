import type { ExtractionResponse, ProgramSpecSummary, SchemaSpec } from "../../types/webstruct";

export function ProgramSpecPreviewPanel({
  programSpec,
  schemaSpec,
  validationIssues = [],
}: {
  programSpec: ProgramSpecSummary | null | undefined;
  schemaSpec: SchemaSpec | null | undefined;
  validationIssues?: NonNullable<ExtractionResponse["program_validation_issues"]>;
}) {
  if (!programSpec) {
    return (
      <section className="panel program-preview-panel">
        <div className="panel-heading compact-heading">
          <div>
            <p className="panel-kicker">RULES</p>
            <h2>规则预览</h2>
          </div>
        </div>
        <div className="empty-state">
          <strong>暂无 ProgramSpec</strong>
          <p>生成规则后，这里会用可读方式展示每个字段的抽取规则。</p>
        </div>
      </section>
    );
  }

  const fieldsByName = new Map(schemaSpec?.fields.map((field) => [field.name, field]));

  return (
    <section className="panel program-preview-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="panel-kicker">RULES</p>
          <h2>规则预览</h2>
        </div>
        <span className="version-pill">
          {programSpec.field_programs.length} 条规则
        </span>
      </div>
      <div className="program-rule-list">
        {programSpec.field_programs.map((fieldProgram, index) => {
          const field = fieldsByName.get(fieldProgram.field_name);
          return (
            <article className="program-rule-item" key={`${fieldProgram.field_name}-${index}`}>
              <div>
                <strong>{field?.description || fieldProgram.field_name}</strong>
                <span>{fieldProgram.field_name}</span>
              </div>
              <p>{ruleSummary(fieldProgram)}</p>
            </article>
          );
        })}
      </div>
      {validationIssues.length ? (
        <div className="program-validation-issues" role="status">
          <strong>已拒绝的规则</strong>
          {validationIssues.map((issue, index) => (
            <p key={`${issue.field || "rule"}-${index}`}>
              {issue.field || "未知字段"} · {issue.reason}
              {issue.selector ? ` · ${issue.selector}` : ""}
              {issue.match_count !== undefined && issue.match_count !== null
                ? ` · 匹配 ${issue.match_count}`
                : ""}
            </p>
          ))}
        </div>
      ) : null}
      <details className="program-json-drawer">
        <summary>查看 ProgramSpec JSON</summary>
        <pre>{JSON.stringify(programSpec, null, 2)}</pre>
      </details>
    </section>
  );
}

function ruleSummary(fieldProgram: ProgramSpecSummary["field_programs"][number]): string {
  if (fieldProgram.strategy === "css") {
    return `从 CSS 选择器 ${fieldProgram.selector || "未指定"}${fieldProgram.attribute ? ` 的 ${fieldProgram.attribute} 属性` : ""}抽取`;
  }
  if (fieldProgram.strategy === "xpath") {
    return `从 XPath ${fieldProgram.selector || "未指定"}${fieldProgram.attribute ? ` 的 ${fieldProgram.attribute} 属性` : ""}抽取`;
  }
  if (fieldProgram.strategy === "regex_on_text") {
    return `在页面文本中用正则 ${fieldProgram.pattern || "未指定"} 匹配`;
  }
  if (fieldProgram.strategy === "text_near_label") {
    const labels = fieldProgram.labels?.length
      ? fieldProgram.labels.join("、")
      : fieldProgram.label || "字段标签";
    return `抽取靠近“${labels}”的文本`;
  }
  if (fieldProgram.strategy === "llm_fallback") {
    return "当结构化规则未命中时，允许 LLM 按页面上下文兜底";
  }
  return `使用 ${fieldProgram.strategy} 策略抽取`;
}
