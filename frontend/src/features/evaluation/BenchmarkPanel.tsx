import { ChartBar, Play } from "@phosphor-icons/react";

import type { BenchmarkResponse, RunState } from "../../types/webstruct";
import { formatPercent } from "../../lib/formatters";
import { SkeletonRows } from "../common/Skeleton";

export function BenchmarkPanel({
  benchmark,
  benchmarkState,
  onRunBenchmark,
}: {
  benchmark: BenchmarkResponse | null;
  benchmarkState: RunState;
  onRunBenchmark: () => void;
}) {
  return (
    <section className="panel benchmark-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">EVALUATION</p>
          <h2>评测对比</h2>
        </div>
        <button
          className="button-secondary"
          type="button"
          onClick={onRunBenchmark}
          disabled={benchmarkState === "running"}
        >
          {benchmarkState === "running" ? (
            "评测中"
          ) : (
            <>
              <Play size={15} weight="fill" />
              运行评测
            </>
          )}
        </button>
      </div>
      {benchmarkState === "running" ? (
        <SkeletonRows count={5} />
      ) : benchmark?.benchmark_report ? (
        <>
        <table className="data-table">
          <thead>
            <tr>
              <th>方法</th>
              <th>字段准确率</th>
              <th>缺失率</th>
              <th>Schema</th>
              <th>证据精度</th>
              <th>选择性准确率</th>
            </tr>
          </thead>
          <tbody>
            {benchmark.benchmark_report.methods.map((method) => (
              <tr key={method.method}>
                <td>{method.method}</td>
                <td>{formatPercent(method.field_accuracy)}</td>
                <td>{formatPercent(method.required_field_missing_rate)}</td>
                <td>{formatPercent(method.schema_adherence)}</td>
                <td>{formatPercent(method.evidence_precision)}</td>
                <td>{formatPercent(method.selective_accuracy)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <details className="node-timing-details">
          <summary>耗时、调用与指标来源</summary>
          {benchmark.benchmark_report.methods.map((method) => (
            <div className="benchmark-method-diagnostics" key={method.method}>
              <strong>{method.method}</strong>
              <dl className="context-list">
                <div><dt>成功 / 失败 / 样本</dt><dd>{method.success_count ?? 0} / {method.failure_count ?? 0} / {method.sample_count ?? 0}</dd></div>
                <div><dt>耗时 / 调用</dt><dd>{method.runtime_ms ?? "不可用"} ms / {method.model_call_count ?? 0}</dd></div>
                <div><dt>Token 输入 / 输出</dt><dd>{method.actual_input_tokens ?? "不可用"} / {method.actual_output_tokens ?? "不可用"}</dd></div>
                <div><dt>已知部分 Token / 缺用量调用</dt><dd>{method.partial_actual_input_tokens ?? 0} + {method.partial_actual_output_tokens ?? 0} / {method.token_usage_missing_calls ?? 0}</dd></div>
                <div><dt>证据覆盖 / 修复正确率</dt><dd>{formatPercent(method.evidence_coverage)} / {formatPercent(method.repair_success_rate)}</dd></div>
              </dl>
              {Object.entries(method.metric_sources ?? {}).map(([name, source]) =>
                <p key={name} className="panel-help">{name} · {source}{method.unavailable_reasons?.[name] ? ` · ${method.unavailable_reasons[name]}` : ""}</p>,
              )}
              {Object.entries(method.sample_errors ?? {}).map(([name, errors]) =>
                <p className="inline-error" key={name}>{name}: {errors.join("; ")}</p>,
              )}
            </div>
          ))}
        </details>
        </>
      ) : (
        <div className="empty-state benchmark-empty">
          <ChartBar size={24} weight="duotone" />
          <strong>可选评测节点</strong>
          <p>需要先提供显式 Schema 与页面样例；报告会区分 measured、estimated 和 unavailable。</p>
        </div>
      )}
    </section>
  );
}
