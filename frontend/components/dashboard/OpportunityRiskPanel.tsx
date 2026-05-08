import { AlertTriangle, Radar } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function OpportunityRiskPanel({ summary }: { summary: DashboardSummary | null }) {
  const missed = summary?.missed_opportunity_risk;
  const riskPoolCount = summary?.candidate_funnel?.riskPool ?? summary?.risk_pool?.length ?? 0;
  const regime = summary?.market_regime?.marketRegime || "-";
  const chaseLevel = riskPoolCount > 20 ? "高" : riskPoolCount > 8 ? "中" : "低";

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
          <Radar className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
        </span>
        <div>
          <CardTitle>机会与风险平衡</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">同时显示追高风险和踏空风险，避免只按防御口径判断</p>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 xl:grid-cols-2">
        <RiskBlock
          title="追高风险"
          level={chaseLevel}
          icon="warning"
          items={[
            `${riskPoolCount} 只标的进入风险观察池`,
            regime === "RiskOn" ? "RiskOn 下仍需规避高位放量滞涨和炸板未修复标的" : "当前市场状态下优先控制回撤和波动",
          ]}
        />
        <RiskBlock
          title="踏空风险"
          level={missed?.level || "低"}
          icon="radar"
          items={missed?.reasons || ["暂无明显踏空风险"]}
          fixes={missed?.suggestedFixes || []}
        />
      </CardContent>
    </Card>
  );
}

function RiskBlock({
  title,
  level,
  items,
  fixes = [],
  icon,
}: {
  title: string;
  level: "低" | "中" | "高";
  items: string[];
  fixes?: string[];
  icon: "warning" | "radar";
}) {
  const Icon = icon === "warning" ? AlertTriangle : Radar;
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Icon className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
          {title}
        </div>
        <Badge tone={level === "高" ? "danger" : level === "中" ? "warning" : "success"}>{level}</Badge>
      </div>
      <ul className="mt-3 space-y-1.5 text-xs leading-5 text-[var(--text-secondary)]">
        {items.slice(0, 3).map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
      {fixes.length > 0 && (
        <div className="mt-3 rounded-sm border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-xs leading-5 text-[var(--text-tertiary)]">
          {fixes[0]}
        </div>
      )}
    </div>
  );
}
