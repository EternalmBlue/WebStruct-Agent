import { useEffect, useState } from "react";
import { ArrowCounterClockwise, GitBranch } from "@phosphor-icons/react";

import {
  evaluateRSIIteration,
  loadRSIIteration,
  rollbackRSIIteration,
} from "../../api/webstructApi";
import type { RSIIterationResponse, RunState } from "../../types/webstruct";

const qualityLabels: Record<string, string> = {
  quality_proxy: "质量代理",
  verification_score: "校验得分",
  field_completion_rate: "字段完成率",
  evidence_coverage: "证据覆盖率",
  required_field_missing_rate: "必填缺失率",
  optional_field_missing_rate: "可选缺失率",
  selector_ambiguity_count: "选择器歧义",
  selector_error_count: "选择器错误",
  program_rule_rejection_count: "规则拒绝",
  workflow_runtime_ms: "工作流耗时",
  model_call_count: "模型调用",
};

export function RSIIterationPanel({ candidateRunId }: { candidateRunId?: string }) {
  const [baselineRunId, setBaselineRunId] = useState("");
  const [experimentId, setExperimentId] = useState("workbench");
  const [hypothesis, setHypothesis] = useState("");
  const [hypothesisId, setHypothesisId] = useState("");
  const [intervention, setIntervention] = useState("");
  const [changeSetId, setChangeSetId] = useState("");
  const [iterationId, setIterationId] = useState("");
  const [rollbackReason, setRollbackReason] = useState("");
  const [result, setResult] = useState<RSIIterationResponse | null>(null);
  const [state, setState] = useState<RunState>("idle");
  const [error, setError] = useState("");
  useEffect(() => {
    setResult(null);
    setError("");
  }, [candidateRunId]);
  const canEvaluate = Boolean(candidateRunId && [baselineRunId, experimentId, hypothesis,
    hypothesisId, intervention, changeSetId].every((value) => value.trim()));

  async function evaluate() {
    if (!canEvaluate || !candidateRunId) return;
    setState("running");
    setError("");
    try {
      const response = await evaluateRSIIteration({
        experiment_id: experimentId.trim() || "workbench",
        baseline_run_id: baselineRunId.trim(),
        candidate_run_id: candidateRunId,
        hypothesis_id: hypothesisId.trim(),
        hypothesis: hypothesis.trim(),
        intervention: intervention.trim(),
        change_set_id: changeSetId.trim(),
      });
      setResult(response);
      setState("done");
    } catch (currentError) {
      setState("failed");
      setError(currentError instanceof Error ? currentError.message : "RSI 评估失败");
    }
  }

  async function rollback() {
    if (!result || !rollbackReason.trim()) return;
    setState("running");
    setError("");
    try {
      const response = await rollbackRSIIteration(result.iteration_id, rollbackReason.trim());
      setResult(response);
      setState("done");
    } catch (currentError) {
      setState("failed");
      setError(currentError instanceof Error ? currentError.message : "RSI 回滚失败");
    }
  }

  async function retrieve() {
    setState("running");
    setError("");
    try {
      setResult(await loadRSIIteration(iterationId.trim()));
      setState("done");
    } catch (currentError) {
      setState("failed");
      setError(currentError instanceof Error ? currentError.message : "RSI 查询失败");
    }
  }

  return (
    <section className="panel rsi-panel">
      <div className="panel-heading compact-heading">
        <div>
          <p className="panel-kicker">RSI</p>
          <h2>监督迭代比较</h2>
        </div>
        <GitBranch size={19} weight="duotone" />
      </div>
      <p className="panel-help">候选任务：{candidateRunId ?? "尚未运行"} · 质量依据：校验、字段完成与证据覆盖，非标注准确率</p>
      <div className="rsi-form">
        <label>
          <span>实验标识</span>
          <input value={experimentId} onChange={(event) => setExperimentId(event.target.value)} />
        </label>
        <label>
          <span>基线任务 ID</span>
          <input value={baselineRunId} onChange={(event) => setBaselineRunId(event.target.value)} placeholder="extract-..." />
        </label>
        <label>
          <span>假设标识</span>
          <input value={hypothesisId} onChange={(event) => setHypothesisId(event.target.value)} />
        </label>
        <label>
          <span>假设</span>
          <input value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} placeholder="更具体的规则应提高证据覆盖率" />
        </label>
        <label>
          <span>干预措施</span>
          <input value={intervention} onChange={(event) => setIntervention(event.target.value)} />
        </label>
        <label>
          <span>变更集标识</span>
          <input value={changeSetId} onChange={(event) => setChangeSetId(event.target.value)} />
        </label>
        <button className="button-secondary" type="button" onClick={evaluate} disabled={state === "running" || !canEvaluate}>
          {state === "running" ? "评估中" : "比较当前运行"}
        </button>
      </div>
      <div className="rsi-query">
        <label><span>历史迭代 ID</span><input value={iterationId} onChange={(event) => setIterationId(event.target.value)} placeholder="rsi-..." /></label>
        <button className="button-secondary" type="button" disabled={!iterationId.trim() || state === "running"} onClick={retrieve}>查询迭代</button>
      </div>
      {error ? <p className="inline-error">{error}</p> : null}
      {result ? (
        <div className="rsi-result">
          <div className="rsi-result-heading">
            <strong>{statusText(result.status)}</strong>
            <span>{result.decision_reason}</span>
          </div>
          <p className="panel-help">{result.iteration_id} · v{result.evaluation_version ?? "1"} · {result.hypothesis}</p>
          {(result.status === "accepted" || result.status === "rejected") ? (
            <div className="rsi-query">
              <label><span>回滚原因</span><input value={rollbackReason} onChange={(event) => setRollbackReason(event.target.value)} /></label>
              <button className="button-secondary" type="button" title="仅记录人工回滚，不还原代码或规则" disabled={!rollbackReason.trim() || state === "running"} onClick={rollback}>
                <ArrowCounterClockwise size={16} />记录回滚
              </button>
            </div>
          ) : result.rollback_reason ? <p>{result.rollback_reason}</p> : null}
          <dl className="context-list">
            {Object.entries(qualityLabels).map(([name, label]) => (
              <div key={name}>
                <dt>{label}变化</dt>
                <dd>{result.metric_deltas[name] == null ? "不可用" : result.metric_deltas[name]!.toFixed(4)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </section>
  );
}

function statusText(status: RSIIterationResponse["status"]) {
  return { accepted: "已接受", rejected: "已拒绝", blocked: "已阻断", rolled_back: "已回滚" }[status];
}
