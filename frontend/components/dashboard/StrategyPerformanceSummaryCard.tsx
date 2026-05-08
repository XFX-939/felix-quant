"use client";

import Link from "next/link";
import { ArrowUpRight, BarChart3 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { StrategyPerformanceSummary } from "@/lib/types";

export function StrategyPerformanceSummaryCard({ summary }: { summary: StrategyPerformanceSummary | null }) {
  const overview = summary?.overview;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-[var(--color-primary)]" />
            策略表现摘要
          </CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">收益、回撤和样本可信度来自后端策略净值预聚合。</p>
        </div>
        <Link
          href="/strategy-performance"
          className="inline-flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--color-primary)]"
        >
          查看看板
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 md:grid-cols-2">
          <PerformanceMetric title="近1月最佳" name={overview?.best1M?.strategyName} value={overview?.best1M?.returnRate} />
          <PerformanceMetric title="近3月最佳" name={overview?.best3M?.strategyName} value={overview?.best3M?.returnRate} />
          <PerformanceMetric title="近1年最佳" name={overview?.best1Y?.strategyName} value={overview?.best1Y?.returnRate} />
          <PerformanceMetric title="回撤最高策略" name={overview?.maxDrawdownStrategy?.strategyName} value={overview?.maxDrawdownStrategy?.maxDrawdown} isDrawdown />
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge tone="default">启用 {overview?.enabledStrategyCount ?? "--"}</Badge>
          <Badge tone="success">有效回测 {overview?.validBacktestStrategyCount ?? "--"}</Badge>
          <Badge tone="warning">样本不足 {overview?.insufficientSampleCount ?? "--"}</Badge>
          <Badge tone="danger">建议暂停 {overview?.suggestedPauseCount ?? "--"}</Badge>
        </div>
        <div className="text-xs leading-5 text-[var(--text-tertiary)]">
          样本不足和数据不足的收益率不会作为策略有效性结论，需结合交易次数、覆盖率和回测可信度复核。
        </div>
      </CardContent>
    </Card>
  );
}

function PerformanceMetric({ title, name, value, isDrawdown = false }: { title: string; name?: string | null; value?: number | null; isDrawdown?: boolean }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
      <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
      <div className="mt-1 truncate text-sm font-semibold text-[var(--text-primary)]">{name || "--"}</div>
      <div className={cn("mt-1 finance-number text-xs", isDrawdown ? "text-[var(--color-success)]" : returnTone(value))}>
        {value === undefined || value === null ? "--" : formatPercent(value)}
      </div>
    </div>
  );
}

function returnTone(value?: number | null) {
  if (value === undefined || value === null) return "text-[var(--text-tertiary)]";
  if (value > 0) return "text-[var(--color-danger)]";
  if (value < 0) return "text-[var(--color-success)]";
  return "text-[var(--text-secondary)]";
}
