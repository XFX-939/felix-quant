import { Activity, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPctPoint, formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function MarketSnapshotCard({ summary }: { summary: DashboardSummary | null }) {
  const regime = summary?.market_regime;
  const strongest = summary?.market_theme?.themes?.[0];

  return (
    <Card className="border-[var(--border-strong)]">
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
            <TrendingUp className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
          </span>
          <div>
            <CardTitle>今日行情快照</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">用于校正市场状态、主线识别和今日决策口径</p>
          </div>
        </div>
        <Badge tone={regime?.superRiskOnSignal ? "danger" : regime?.strongRecoverySignal ? "warning" : "muted"}>
          {regime?.superRiskOnSignal ? "超级修复" : regime?.strongRecoverySignal ? "强修复" : "常规"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <SnapshotMetric label="上证指数" value={formatPctPoint(regime?.shIndexPctChg)} tone="up" />
          <SnapshotMetric label="深证成指" value={formatPctPoint(regime?.szIndexPctChg)} tone="up" />
          <SnapshotMetric label="创业板指" value={formatPctPoint(regime?.cybIndexPctChg)} tone="up" />
          <SnapshotMetric label="科创50" value={formatPctPoint(regime?.kc50PctChg)} tone="up" />
          <SnapshotMetric label="全市场成交额" value={formatLargeAmount(regime?.totalAmount)} />
          <SnapshotMetric label="上涨家数" value={`${regime?.upStockCount ?? "-"} / ${formatPercent(regime?.snapshotUpStockRatio)}`} />
          <SnapshotMetric label="涨停 / 跌停" value={`${regime?.snapshotLimitUpCount ?? regime?.limitUpCount ?? "-"} / ${regime?.snapshotLimitDownCount ?? regime?.limitDownCount ?? "-"}`} />
          <SnapshotMetric label="最强方向" value={strongest?.name || "等待数据"} />
        </div>
        <div className="flex items-start gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
          <Activity className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]" aria-hidden />
          <span>
            {regime?.marketSnapshot?.message || regime?.overrideReason || "当前使用本地行情数据估算市场快照。"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function SnapshotMetric({ label, value, tone }: { label: string; value: string; tone?: "up" }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className={`finance-number mt-1 truncate text-sm font-semibold ${tone === "up" ? "market-up" : "text-[var(--text-primary)]"}`}>
        {value}
      </div>
    </div>
  );
}

function formatLargeAmount(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return "-";
  if (value >= 1000000000000) return `${(value / 1000000000000).toFixed(2)} 万亿`;
  if (value >= 100000000) return `${(value / 100000000).toFixed(0)} 亿`;
  return value.toLocaleString("zh-CN");
}
