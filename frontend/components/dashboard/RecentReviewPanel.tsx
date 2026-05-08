import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function RecentReviewPanel({ summary }: { summary: DashboardSummary | null }) {
  const backtest = summary?.latest_backtest;
  return (
    <Card>
      <CardHeader>
        <CardTitle>运行记录 / 复盘记录</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <RecordLine label="最近一次回测" value={backtest ? `${backtest.strategy_name} ${formatPercent(backtest.total_return)}` : "暂无回测"} />
        <RecordLine label="最近一次运行" value={summary?.last_run_time || "-"} mono />
        <RecordLine label="人工复盘结论" value={summary?.recent_reviews?.[0]?.summary || "待填写"} />
        <div className="flex items-center justify-between rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
          <div>
            <div className="text-xs text-[var(--text-tertiary)]">人工确认状态</div>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone="warning">待确认</Badge>
              <span className="text-xs text-[var(--text-tertiary)]">策略结果需人工复盘后执行</span>
            </div>
          </div>
          <Link href="/reviews" className="rounded-md border border-[var(--border-strong)] px-3 py-1.5 text-xs text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
            去确认
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

function RecordLine({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className={`${mono ? "finance-number" : ""} text-right font-medium text-[var(--text-primary)]`}>{value}</span>
    </div>
  );
}

