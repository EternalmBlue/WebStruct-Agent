import type { ExtractionResponse } from "../../types/webstruct";

export function AgentTracePanel({
  extraction,
}: {
  extraction: ExtractionResponse | null;
}) {
  return (
    <section className="panel trace-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="panel-kicker">TRACE</p>
          <h2>节点执行链路</h2>
        </div>
      </div>
      {extraction?.agent_traces.length ? (
        <ol className="trace-list">
          {extraction.agent_traces.map((trace) => (
            <li key={`${trace.name}-${trace.runtime_ms}`}>
              <strong>{trace.name}</strong>
              <span>
                {trace.status} · {trace.runtime_ms}ms
              </span>
              <p>{trace.output_summary || trace.error_message}</p>
            </li>
          ))}
        </ol>
      ) : (
        <div className="empty-state">
          <strong>节点尚未运行</strong>
          <p>运行后会按顺序记录每个 Agent 节点的状态、耗时和摘要。</p>
        </div>
      )}
    </section>
  );
}
