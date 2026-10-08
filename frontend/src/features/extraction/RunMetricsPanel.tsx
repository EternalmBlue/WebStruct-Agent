import { useEffect, useState } from "react";

import type {
  ExtractionResponse,
  MetricEnvelope,
  RunSnapshot,
} from "../../types/webstruct";

const metricLabels: Record<string, string> = {
  workflow_runtime_ms: "工作流耗时",
  collection_attempt_count: "采集尝试",
  browser_launch_success_rate: "浏览器启动成功率",
  collection_success_rate: "采集成功率",
  access_limited_count: "访问限制次数",
  evidence_coverage: "证据覆盖率",
  average_confidence: "平均置信度",
  required_field_missing_rate: "必填字段缺失率",
  verification_score: "校验得分",
  repair_supported_rate: "修复成功率",
  model_call_count: "模型调用次数",
  actual_input_tokens: "实际输入 Token",
  actual_output_tokens: "实际输出 Token",
  estimated_input_tokens: "估算输入 Token",
  estimated_output_tokens: "估算输出 Token",
  queue_wait_ms: "队列等待",
  fallback_attempt_count: "HTTP 降级尝试",
  schema_field_count: "契约字段数",
  extracted_field_count: "非空字段数",
  verification_passed: "校验通过",
  verification_issue_count: "校验问题数",
  repair_attempt_count: "字段修复次数",
  program_reuse: "规则复用",
  field_completion_rate: "字段完成率",
  optional_field_missing_rate: "可选字段缺失率",
  selector_ambiguity_count: "选择器歧义",
  selector_error_count: "选择器错误",
  program_rule_rejection_count: "规则拒绝",
  browser_wait_ms: "浏览器等待",
  selector_attempt_count: "选择器执行次数",
  schema_failure_count: "Schema 失败次数",
  token_usage_missing_calls: "缺少用量的调用数",
  partial_actual_input_tokens: "已知部分输入 Token",
  partial_actual_output_tokens: "已知部分输出 Token",
};

export function RunMetricsPanel({
  extraction,
  snapshot,
}: {
  extraction: ExtractionResponse | null;
  snapshot: RunSnapshot | null;
}) {
  const metrics = extraction?.metrics ?? snapshot?.metrics ?? {};
  const entries = Object.entries(metrics).filter(([, item]) => item);
  const mainMetrics = entries.filter(([name]) => [
    "workflow_runtime_ms", "queue_wait_ms", "collection_attempt_count",
    "access_limited_count", "evidence_coverage", "average_confidence",
    "required_field_missing_rate", "field_completion_rate", "verification_score",
    "model_call_count", "selector_ambiguity_count", "selector_error_count",
  ].includes(name));
  const detailMetrics = entries.filter((entry) => !mainMetrics.includes(entry));
  const activeNode = snapshot?.current_node;
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (snapshot?.status !== "running") return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [snapshot?.status]);
  const elapsed = snapshot?.runtime_ms ?? (snapshot?.start_time
    ? Math.max(0, now - Date.parse(snapshot.start_time)) : null);
  const collection = [...(snapshot?.observations ?? [])].reverse().find(
    (event) => event.event_type === "collection_attempt",
  );
  const probe = [...(snapshot?.observations ?? [])].reverse().find(
    (event) => event.event_type === "browser_probe",
  );
  const nodeEntries = Object.values(snapshot?.nodes ?? {}).filter(
    (node) => node.status !== "pending",
  );

  return (
    <section className="panel run-metrics-panel">
      <div className="panel-heading compact-heading">
        <div>
          <h2>运行指标</h2>
        </div>
        <span className="schema-chip">
          {snapshot?.status === "running" ? "实时" : extraction ? "终态" : "等待"}
        </span>
      </div>
      {snapshot ? (
        <div className="metric-strip">
          <div>
            <span>当前节点</span>
            <strong>{activeNode ?? (snapshot.status === "queued" ? "等待调度" : snapshot.status === "running" ? "处理中" : snapshot.status === "failed" ? "运行失败" : "已完成")}</strong>
          </div>
          <div>
            <span>进度</span>
            <strong>{snapshot.progress.toFixed(0)}%</strong>
          </div>
          <div>
            <span>运行时长</span>
            <strong>{formatMetricValue(elapsed, "ms")}</strong>
          </div>
        </div>
      ) : null}
      {collection ? (
        <dl className="context-list">
          <div><dt>采集分类</dt><dd>{String(collection.classification)} · HTTP {String(collection.http_status ?? "不可用")}</dd></div>
          <div><dt>采集器 / 降级</dt><dd>{String(collection.collector)} / {collection.fallback_attempted ? "已尝试" : "未尝试"}</dd></div>
          <div><dt>分类信号</dt><dd>{Array.isArray(collection.classification_signals) ? collection.classification_signals.join(", ") || "无" : "不可用"}</dd></div>
        </dl>
      ) : null}
      {probe ? (
        <dl className="context-list">
          <div><dt>浏览器启动 / 导航 / 关闭</dt><dd>{probe.launch_verified ? "已验证" : "失败"} / {probe.navigation_verified ? "已验证" : "未验证"} / {probe.close_verified === true ? "已释放" : probe.close_verified === false ? "失败" : "不适用"}</dd></div>
          <div><dt>启动 / 导航耗时</dt><dd>{formatMetricValue(probe.launch_latency_ms as number | null, "ms")} / {formatMetricValue(probe.navigation_latency_ms as number | null, "ms")}</dd></div>
          <div><dt>导航后等待</dt><dd>{formatMetricValue(probe.post_navigation_wait_ms as number | null, "ms")} / 配置 {formatMetricValue(probe.post_navigation_wait_configured_ms as number | null, "ms")} · {String(probe.post_navigation_wait_outcome ?? "不可用")}</dd></div>
          <div><dt>初始 / 最终 HTTP</dt><dd>{String(probe.initial_http_status ?? "不可用")} / {String(probe.final_http_status ?? "不可用")}</dd></div>
        </dl>
      ) : null}
      {entries.length ? (
        <div className="metric-list">
          {mainMetrics.map(([name, item]) => (
            <MetricRow key={name} name={name} metric={item} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>指标尚未产生</strong>
        </div>
      )}
      {detailMetrics.length ? <details className="node-timing-details">
        <summary>全部指标与 Token 用量</summary>
        <div className="metric-list">
          {detailMetrics.map(([name, item]) => <MetricRow key={name} name={name} metric={item} />)}
        </div>
      </details> : null}
      {nodeEntries.length ? (
        <details className="node-timing-details">
          <summary>节点耗时</summary>
          <div className="node-timing-list">
            {nodeEntries.map((node) => (
              <div key={node.name}>
                <span>{node.name}</span>
                <strong>{formatMetricValue(node.runtime_ms, "ms")}</strong>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function MetricRow({ name, metric }: { name: string; metric: MetricEnvelope }) {
  return (
    <div className="metric-row">
      <span>{metricLabels[name] ?? name}</span>
      <strong>{formatMetricValue(metric.value, metric.unit)}</strong>
      <small className={`metric-source metric-source-${metric.source}`}>
        {metric.source} · n={metric.sample_count ?? 0}
      </small>
      {metric.reason ? <em>{metric.reason}</em> : null}
    </div>
  );
}

function formatMetricValue(value: number | null | undefined, unit?: string) {
  if (value === null || value === undefined) {
    return "不可用";
  }
  if (unit === "ratio") {
    return `${(value * 100).toFixed(1)}%`;
  }
  if (unit === "ms") {
    return `${Math.round(value)} ms`;
  }
  return `${value}`;
}
