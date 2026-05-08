export function formatPercent(value?: number | null, digits = 1) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatPctPoint(value?: number | null, digits = 2) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return `${value.toFixed(digits)}%`;
}

export function formatNumber(value?: number | null, digits = 2) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

export function formatCurrency(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  return value.toLocaleString("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 0
  });
}

export function riskLabel(level?: string | null) {
  if (level === "high") return "高";
  if (level === "medium") return "中";
  if (level === "low") return "低";
  return "-";
}

