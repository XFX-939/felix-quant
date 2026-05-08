import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPctPoint } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function MarketThemeCard({ summary }: { summary: DashboardSummary | null }) {
  const theme = summary?.market_theme;
  const rows = theme?.themes || [];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>今日主线识别</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">基于板块涨幅、强势股数量、涨停扩散和成交额变化</p>
        </div>
        <Badge tone={theme?.confidence === "高" ? "success" : theme?.confidence === "中" ? "warning" : "danger"}>{theme?.confidence || "-"}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
          <div className="text-xs text-[var(--text-tertiary)]">{theme?.confidence === "低" ? "行业估算线索" : "主线判断"}</div>
          <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{theme?.displayText || "等待数据"}</div>
          {theme?.confidence === "低" && (
            <div className="mt-2 flex gap-2 text-xs leading-5 text-[var(--color-warning)]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{theme?.message || "题材数据不足，暂不输出强判断"}</span>
            </div>
          )}
        </div>
        <div className="space-y-2">
          {rows.slice(0, 3).map((item) => (
            <div key={item.name} className="grid grid-cols-[1fr_68px_76px] items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-xs">
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                  <div className="truncate font-medium text-[var(--text-primary)]">{item.name}</div>
                  {item.level && <Badge tone="muted">{item.level}</Badge>}
                </div>
                <div className="mt-1 text-[var(--text-tertiary)]">
                  可信度 {item.confidence || theme?.confidence || "-"} / 排名 {item.sectorRank} / 强势 {item.sectorStrongStockCount} 只 / 涨停 {item.sectorLimitUpCount} 只
                </div>
                {item.evidence?.[0] && <div className="mt-1 truncate text-[var(--text-secondary)]">{item.evidence[0]}</div>}
              </div>
              <div className="finance-number text-right text-[var(--color-primary)]">{item.themeScore.toFixed(1)}</div>
              <div className="finance-number text-right market-up">{formatPctPoint(item.sectorPctChg)}</div>
            </div>
          ))}
          {!rows.length && <div className="py-4 text-center text-xs text-[var(--text-tertiary)]">题材数据不足，当前仅保留行业和风格估算线索</div>}
        </div>
      </CardContent>
    </Card>
  );
}
