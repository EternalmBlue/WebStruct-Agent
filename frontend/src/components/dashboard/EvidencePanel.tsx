import type { ExtractionResponse } from "../../types/webstruct";
import { formatPercent } from "../../lib/formatters";
import { SkeletonRows } from "./Skeleton";

export function EvidencePanel({
  extraction,
  isRunning,
}: {
  extraction: ExtractionResponse | null;
  isRunning: boolean;
}) {
  const hasEvidence = extraction?.extraction_result?.fields.some(
    (field) => field.evidence.length
  );

  return (
    <section className="panel evidence-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="panel-kicker">EVIDENCE</p>
          <h2>证据片段</h2>
        </div>
      </div>
      {isRunning ? (
        <SkeletonRows count={4} />
      ) : hasEvidence ? (
        <div className="evidence-list">
          {extraction?.extraction_result?.fields.flatMap((field) =>
            field.evidence.map((evidence, index) => (
              <article
                className="evidence-item"
                key={`${field.field_name}-${index}`}
              >
                <div>
                  <strong>{field.field_name}</strong>
                  <span>
                    {evidence.source} · {formatPercent(evidence.score)}
                  </span>
                </div>
                <p>{evidence.text}</p>
              </article>
            ))
          )}
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂未形成证据</strong>
          <p>字段抽取完成后，这里会展示支持该值的页面片段。</p>
        </div>
      )}
    </section>
  );
}
