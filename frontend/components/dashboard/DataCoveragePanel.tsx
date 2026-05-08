import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function DataCoveragePanel({ summary }: { summary: DashboardSummary | null }) {
  const coverage = summary?.data_coverage || summary?.data_quality?.dataCoverage;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>热点数据覆盖</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">缺少题材、涨停、炸板、连板时，热点和龙头不参与今日决策</p>
        </div>
        <Badge tone={coverage?.criticalHotspotDataMissing ? "danger" : "success"}>{coverage?.themeConfidence || "-"}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          {(coverage?.items || []).map((item) => (
            <div key={item.name} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-[var(--text-primary)]">{item.name}</span>
                <Badge tone={statusTone(item.status)}>{item.status}</Badge>
              </div>
              <div className="mt-1 leading-5 text-[var(--text-tertiary)]">{item.reason}</div>
            </div>
          ))}
        </div>
        {(coverage?.warnings || []).map((warning) => (
          <div key={warning} className="rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-2 text-xs text-[var(--color-warning)]">
            {warning}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function statusTone(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "已接入") return "success";
  if (status === "降级估算") return "warning";
  if (status === "缺失") return "danger";
  return "muted";
}
