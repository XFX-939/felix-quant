import { Activity, Gauge } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPctPoint, formatPercent } from "@/lib/format";
import type { DashboardSummary, MarketRegime } from "@/lib/types";

const regimeTone: Record<MarketRegime, string> = {
  RiskOn: "text-[var(--color-danger)]",
  Choppy: "text-[var(--color-warning)]",
  RiskOff: "text-[var(--color-success)]",
  Panic: "text-[var(--color-danger)]",
  Recovery: "text-[var(--color-primary)]"
};

export function MarketRegimeCard({ summary }: { summary: DashboardSummary | null }) {
  const regime = summary?.market_regime;
  const marketRegime = regime?.marketRegime || "Choppy";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
            <Activity className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
          </span>
          <div>
            <CardTitle>市场状态识别</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">MarketRegimeModel 规则识别与策略启用状态</p>
          </div>
        </div>
        <span className={`finance-number text-lg font-semibold ${regimeTone[marketRegime]}`}>{marketRegime}</span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm leading-6 text-[var(--text-secondary)]">
          {regime?.explanation || "正在等待市场状态数据"}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <RegimeMetric label="20日收益" value={formatPctPoint(regime?.indexReturn20d)} />
          <RegimeMetric label="上涨占比" value={formatPercent(regime?.snapshotUpStockRatio ?? regime?.upStockRatio)} />
          <RegimeMetric label="涨停数量" value={String(regime?.snapshotLimitUpCount ?? regime?.limitUpCount ?? "-")} />
          <RegimeMetric label="建议总仓位" value={formatPercent(regime?.suggestedTotalPosition)} strong />
        </div>
        {regime?.overrideReason && (
          <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-xs leading-5 text-[var(--color-primary)]">
            {regime.overrideReason}
          </div>
        )}
        <StrategyBadges title="启用策略" items={regime?.enabledStrategies || []} tone="default" />
        <StrategyBadges title="降权策略" items={regime?.reducedStrategies || []} tone="warning" />
      </CardContent>
    </Card>
  );
}

function RegimeMetric({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] p-2">
      <div className="text-[var(--text-tertiary)]">{label}</div>
      <div className={`finance-number mt-1 font-semibold ${strong ? "text-[var(--color-primary)]" : "text-[var(--text-primary)]"}`}>
        {value}
      </div>
    </div>
  );
}

function StrategyBadges({ title, items, tone }: { title: string; items: string[]; tone: "default" | "warning" }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <div className="flex items-center gap-1 text-[var(--text-tertiary)]">
        <Gauge className="h-3.5 w-3.5" aria-hidden />
        {title}
      </div>
      {items.length ? items.map((item) => <Badge key={item} tone={tone}>{item}</Badge>) : <Badge tone="muted">无</Badge>}
    </div>
  );
}
