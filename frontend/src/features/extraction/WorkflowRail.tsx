import {
  BracketsCurly,
  CheckCircle,
  Database,
  FileMagnifyingGlass,
  Funnel,
  GitBranch,
  ShieldCheck,
} from "@phosphor-icons/react";

import type { ExtractionResponse, RunSnapshot, RunState } from "../../types/webstruct";

const WORKFLOW_STEPS = [
  { traceName: "page_collector_node", label: "页面采集", Icon: FileMagnifyingGlass },
  { traceName: "view_normalizer_node", label: "页面整理", Icon: Funnel },
  { traceName: "schema_agent_node", label: "字段设计", Icon: BracketsCurly },
  { traceName: "planner_agent_node", label: "抽取规划", Icon: GitBranch },
  { traceName: "programmer_agent_node", label: "规则生成", Icon: GitBranch },
  { traceName: "extractor_agent_node", label: "字段抽取", Icon: FileMagnifyingGlass },
  { traceName: "verifier_agent_node", label: "质量检查", Icon: ShieldCheck },
  { traceName: "repair_agent_node", label: "修复", Icon: ShieldCheck },
  { traceName: "result_persist_node", label: "保存结果", Icon: Database },
];

export function WorkflowRail({
  extraction,
  runState,
  snapshot,
}: {
  extraction: ExtractionResponse | null;
  runState: RunState;
  snapshot?: RunSnapshot | null;
}) {
  const completedTraceNames = new Set(
    extraction?.agent_traces
      .filter((trace) => trace.status === "success")
      .map((trace) => trace.name) ?? []
  );

  return (
    <section className="workflow-rail" aria-label="抽取节点流">
      {WORKFLOW_STEPS.map(({ traceName, label, Icon }, index) => {
        const nodeStatus = snapshot?.nodes?.[traceName]?.status;
        const completed = nodeStatus === "success" || completedTraceNames.has(traceName);
        const pending = nodeStatus === "running" || (!snapshot && runState === "running" && index === 0);
        return (
          <div
            className={`workflow-step${completed ? " workflow-step-complete" : ""}${
              pending ? " workflow-step-pending" : ""
            }`}
            key={traceName}
          >
            <span className="workflow-step-index">{index + 1}</span>
            <Icon size={18} weight={completed ? "fill" : "regular"} />
            <span>{label}</span>
            {nodeStatus === "failed" ? <span className="field-status">失败</span> : null}
            {nodeStatus === "skipped" ? <span className="field-status">跳过</span> : null}
            {completed ? <CheckCircle size={15} weight="fill" /> : null}
          </div>
        );
      })}
    </section>
  );
}
