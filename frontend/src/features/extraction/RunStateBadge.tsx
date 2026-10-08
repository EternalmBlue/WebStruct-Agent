import {
  CheckCircle,
  CircleNotch,
  Prohibit,
  WarningCircle,
} from "@phosphor-icons/react";

import type { RunState } from "../../types/webstruct";

const RUN_STATE_LABELS: Record<RunState, string> = {
  idle: "待运行",
  running: "运行中",
  done: "已完成",
  failed: "失败",
};

export function RunStateBadge({ state }: { state: RunState }) {
  const Icon =
    state === "done"
      ? CheckCircle
      : state === "failed"
        ? WarningCircle
        : state === "running"
          ? CircleNotch
          : Prohibit;

  return (
    <span className={`run-state-badge run-state-${state}`}>
      <Icon size={15} weight={state === "running" ? "regular" : "fill"} />
      {RUN_STATE_LABELS[state]}
    </span>
  );
}
