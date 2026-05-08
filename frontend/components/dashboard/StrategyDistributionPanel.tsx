import { BarChart3 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function StrategyDistributionPanel({ summary }: { summary: DashboardSummary | null }) {
  const rows = summary?.strategy_distribution || [];

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
          <BarChart3 className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
        </span>
        <div>
          <CardTitle>策略结果分布</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">候选数量、主观察数量、风险比例与今日有效性</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.slice(0, 8).map((row) => (
          <div key={row.strategyName} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 text-xs">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium text-[var(--text-primary)]">{row.strategyName}</div>
                <div className="mt-1 line-clamp-1 text-[var(--text-tertiary)]">{row.reason || "等待策略运行诊断"}</div>
              </div>
              <Badge tone={statusTone(row.status)}>{row.status || "有效"}</Badge>
            </div>
            <div className="mt-2 grid grid-cols-4 gap-2">
              <Metric label="候选" value={String(row.candidateCount)} />
              <Metric label="主观察" value={String(row.mainCount ?? 0)} primary={(row.mainCount ?? 0) > 0} />
              <Metric label="高风险" value={String(row.highRiskCount)} danger={row.highRiskCount > 0} />
              <Metric label="均分" value={row.averageScore.toFixed(1)} primary />
            </div>
            {row.backtestValidity && (
              <div className="mt-2 flex items-center justify-between gap-2 border-t border-[var(--border-subtle)] pt-2">
                <span className="text-[10px] text-[var(--text-tertiary)]">近期回测</span>
                <div className="flex items-center gap-2">
                  <span className="finance-number text-[10px] text-[var(--text-tertiary)]">
                    {row.latestBacktestTradeCount ?? 0} 次交易
                  </span>
                  <Badge tone={row.backtestValidity.usableForDecision ? "success" : "warning"}>
                    {row.backtestValidity.validityLevel}
                  </Badge>
                </div>
              </div>
            )}
          </div>
        ))}
        {!rows.length && <div className="py-8 text-center text-sm text-[var(--text-tertiary)]">暂无策略运行结果</div>}
      </CardContent>
    </Card>
  );
}

function statusTone(status?: string): "success" | "warning" | "danger" | "muted" {
  if (status === "有效") return "success";
  if (status === "降权") return "warning";
  if (status === "暂停") return "danger";
  return "muted";
}

function Metric({ label, value, primary = false, danger = false }: { label: string; value: string; primary?: boolean; danger?: boolean }) {
  const color = danger ? "text-[var(--color-danger)]" : primary ? "text-[var(--color-primary)]" : "text-[var(--text-primary)]";
  return (
    <div className="text-right">
      <div className="text-[10px] text-[var(--text-tertiary)]">{label}</div>
      <div className={`finance-number font-semibold ${color}`}>{value}</div>
    </div>
  );
}
