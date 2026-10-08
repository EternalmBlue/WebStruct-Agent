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
