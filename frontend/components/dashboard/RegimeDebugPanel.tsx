import { Bug, CheckCircle2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPctPoint, formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function RegimeDebugPanel({ summary }: { summary: DashboardSummary | null }) {
  const regime = summary?.market_regime;
  const raw = regime?.rawMarketRegime || regime?.marketRegime || "-";
  const finalRegime = regime?.marketRegime || "-";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
            <Bug className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
          </span>
          <div>
            <CardTitle>行情状态调试</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">解释 MarketRegimeModel 为什么输出当前状态</p>
          </div>
        </div>
        <Badge tone={regime?.intradayRecoveryOverride ? "warning" : "muted"}>{raw === finalRegime ? "未覆盖" : "已覆盖"}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <DebugMetric label="20日收益" value={formatPctPoint(regime?.indexReturn20d)} />
          <DebugMetric label="今日创业板" value={formatPctPoint(regime?.cybIndexPctChg)} />
          <DebugMetric label="今日科创50" value={formatPctPoint(regime?.kc50PctChg)} />
          <DebugMetric label="成交额变化" value={formatPercent(regime?.totalAmountChange)} />
          <DebugMetric label="上涨占比" value={formatPercent(regime?.snapshotUpStockRatio ?? regime?.upStockRatio)} />
          <DebugMetric label="涨停数量" value={String(regime?.snapshotLimitUpCount ?? regime?.limitUpCount ?? "-")} />
          <DebugMetric label="强势方向数" value={String(regime?.strongSectorCount ?? "-")} />
          <DebugMetric label="板块最高涨幅" value={formatPctPoint(regime?.topSectorAvgPct)} />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <SignalFlag label="strongRecoverySignal" active={Boolean(regime?.strongRecoverySignal)} />
          <SignalFlag label="superRiskOnSignal" active={Boolean(regime?.superRiskOnSignal)} />
        </div>
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
          <div className="font-semibold text-[var(--text-primary)]">原始模型：{raw}；最终状态：{finalRegime}</div>
          <div className="mt-1">{regime?.overrideReason || "原始模型与覆盖模型一致。"}</div>
          <ul className="mt-2 space-y-1">
            {(regime?.regimeReasons?.length ? regime.regimeReasons : [regime?.explanation || "暂无解释"]).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function DebugMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <div className="text-[11px] text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 text-sm font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function SignalFlag({ label, active }: { label: string; active: boolean }) {
  const Icon = active ? CheckCircle2 : XCircle;
  return (
    <div className="flex items-center justify-between rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className={active ? "text-[var(--color-success)]" : "text-[var(--text-tertiary)]"}>
        <Icon className="inline h-3.5 w-3.5" aria-hidden /> {active ? "触发" : "未触发"}
      </span>
    </div>
  );
}
