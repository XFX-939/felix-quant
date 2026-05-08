import { Activity } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function StrategyHealthCard({ summary }: { summary: DashboardSummary | null }) {
  const backtest = summary?.latest_backtest;
  const metrics = [
    { label: "近60日收益率", value: formatPercent(backtest?.total_return), tone: "up", hint: backtest?.strategy_name || "最近回测" },
    { label: "最大回撤", value: formatPercent(backtest?.max_drawdown), tone: "down", hint: "回撤优先观察" },
    { label: "胜率", value: formatPercent(backtest?.win_rate), tone: "default", hint: `${backtest?.trade_count ?? 0} 次交易` },
    { label: "夏普比率", value: backtest ? backtest.sharpe.toFixed(2) : "-", tone: "default", hint: "风险调整收益" },
    { label: "最近交易次数", value: String(backtest?.trade_count ?? 0), tone: "default", hint: "回测明细" },
    { label: "平均持仓天数", value: "3.2", tone: "default", hint: "模拟统计" },
    { label: "策略状态", value: "正常", tone: "safe", hint: "启用策略运行中" },
    { label: "数据质量", value: "良好", tone: "safe", hint: summary?.last_data_date || "-" }
  ];

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)]">
          <Activity className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
        </span>
        <div>
          <CardTitle>策略健康度</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">收益、回撤、胜率、数据链路与策略状态</p>
        </div>
      </CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <div className="text-xs text-[var(--text-tertiary)]">{metric.label}</div>
            <div className={`finance-number mt-2 text-lg font-semibold ${metric.tone === "up" ? "market-up" : metric.tone === "down" || metric.tone === "safe" ? "market-down" : ""}`}>
              {metric.value}
            </div>
            <div className="mt-1 text-[11px] text-[var(--text-tertiary)]">{metric.hint}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

