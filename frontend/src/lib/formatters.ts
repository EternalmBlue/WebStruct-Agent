export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "未抽取";
  }
  if (Array.isArray(value)) {
    return value.join("，");
  }
  return String(value);
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
