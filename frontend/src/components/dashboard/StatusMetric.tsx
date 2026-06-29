import type { ReactNode } from "react";

export function StatusMetric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: ReactNode;
}) {
  return (
    <div className="status-metric">
      {icon ? <span className="status-metric-icon">{icon}</span> : null}
      <span>{label}</span>
      <strong title={value}>{value}</strong>
    </div>
  );
}
