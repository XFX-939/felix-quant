import { ShieldAlert, TrendingUp } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function DecisionSummaryCard({ summary }: { summary: DashboardSummary | null }) {
  const highRiskCount = summary?.watchlist.filter((signal) => signal.risk_level === "high").length ?? 0;
  const candidateCount = summary?.candidate_count ?? 0;
  const riskLevel = summary?.current_risk_level || "medium";
  const positionCap = summary?.market_regime?.suggestedTotalPosition;
  const position = positionCap !== undefined ? `≤ ${(positionCap * 100).toFixed(0)}%` : riskLevel === "high" ? "≤ 30%" : riskLevel === "medium" ? "≤ 50%" : "≤ 70%";
  const regime = summary?.market_regime?.marketRegime;
  const decision = regime === "Panic" || riskLevel === "high" || candidateCount < 6 ? "谨慎观察" : "观察为主";
  const market = regime || summary?.market_status.summary || "样本市场震荡";

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
            <TrendingUp className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
          </span>
          <div>
            <CardTitle>今日决策摘要</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">策略触发、风险条件与人工确认前的研究结论</p>
          </div>
        </div>
        <RiskBadge level={riskLevel} />
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-4">
          <div className="text-xs text-[var(--text-tertiary)]">今日建议</div>
          <div className="mt-3 text-3xl font-semibold tracking-tight text-[var(--color-primary)]">{decision}</div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <SummaryStat label="建议仓位" value={position} />
            <SummaryStat label="候选标的" value={`${candidateCount}`} />
            <SummaryStat label="市场状态" value={market.replace("样本市场", "")} />
            <SummaryStat label="高风险" value={`${highRiskCount}`} />
          </div>
        </div>
        <div className="flex flex-col justify-between gap-4">
          <p className="text-sm leading-7 text-[var(--text-secondary)]">
            {summary?.market_regime?.explanation || "市场状态仍需更多数据确认"}。候选标的需结合触发原因、风险理由和回测依据做人工确认，当前系统不输出投资建议。
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            {["市场量能不足", "行业轮动较快", "策略信号偏谨慎"].map((item) => (
              <div key={item} className="flex items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 text-xs text-[var(--text-secondary)]">
                <ShieldAlert className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden />
                {item}
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="warning">人工确认</Badge>
            <Badge tone="muted">不构成投资建议</Badge>
            <Badge tone="default">回测依据优先</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 text-lg font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}
