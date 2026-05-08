import { Filter } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function FunnelBreakdownCard({ summary }: { summary: DashboardSummary | null }) {
  const rows = summary?.candidate_funnel?.filterBreakdown || [];

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
          <Filter className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
        </span>
        <div>
          <CardTitle>策略筛选漏斗</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">拆解初筛到可行动候选，过滤过严时自动标红</p>
        </div>
      </CardHeader>
      <CardContent className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
        {rows.map((row) => (
          <div key={row.name} className={`rounded-md border p-3 ${row.warning ? "border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)]" : "border-[var(--border-subtle)] bg-[var(--bg-elevated)]"}`}>
            <div className="text-xs text-[var(--text-tertiary)]">{row.name}</div>
            <div className={`finance-number mt-2 text-lg font-semibold ${row.warning ? "text-[var(--color-danger)]" : "text-[var(--color-primary)]"}`}>
              {row.count}
            </div>
            <div className="mt-1 text-[11px] text-[var(--text-tertiary)]">{formatPercent(row.ratio, 0)}</div>
            {row.warning && <div className="mt-2 text-[10px] leading-4 text-[var(--color-danger)]">过滤过严，需复核阈值</div>}
          </div>
        ))}
        {!rows.length && <div className="py-4 text-sm text-[var(--text-tertiary)]">等待策略运行漏斗数据</div>}
      </CardContent>
    </Card>
  );
}
