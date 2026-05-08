import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function DataQualityPanel({ summary }: { summary: DashboardSummary | null }) {
  const quality = summary?.data_quality;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>数据质量和回测可信度</CardTitle>
        <Badge tone={quality?.integrityLevel === "可信" ? "success" : quality?.integrityLevel === "不可信" ? "danger" : "warning"}>
          {quality?.integrityLevel || "-"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Status label="行情数据" ok={Boolean(quality?.priceDataUpdated)} />
          <Status label="涨停/炸板" ok={Boolean(quality?.limitUpDataReady && quality?.brokenLimitDataReady)} />
          <Status label="概念题材" ok={Boolean(quality?.conceptDataReady)} />
          <Status label="手续费/滑点" ok={Boolean(quality?.feeIncluded && quality?.slippageIncluded)} />
        </div>
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
          <div className="finance-number text-lg font-semibold text-[var(--color-primary)]">{quality?.integrityScore ?? 0}</div>
          <div className="text-xs text-[var(--text-tertiary)]">可信度评分 / 数据版本 {quality?.dataVersion || "-"}</div>
        </div>
        <ul className="space-y-1.5 text-xs leading-5 text-[var(--text-secondary)]">
          {(quality?.integrityWarnings || []).slice(0, 5).map((item) => (
            <li key={item}>- {item}</li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function Status({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <Badge tone={ok ? "success" : "warning"}>{ok ? "已接入" : "不完整"}</Badge>
    </div>
  );
}
