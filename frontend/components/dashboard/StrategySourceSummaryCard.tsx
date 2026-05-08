"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary } from "@/lib/types";

export function StrategySourceSummaryCard({ summary }: { summary: DashboardSummary | null }) {
  const data = summary?.strategy_source_summary;
  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>策略来源分布</CardTitle>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">查看策略出处、改造说明、回测验证和可信度。</p>
        </div>
        <Link className="text-sm text-[var(--color-primary)] hover:underline" href="/strategies">
          策略引擎
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2 text-sm">
          <SourceMetric label="自研" value={data?.selfDevelopedCount} />
          <SourceMetric label="公开研究" value={data?.publicResearchCount} />
          <SourceMetric label="券商研报" value={data?.brokerResearchCount} />
          <SourceMetric label="待验证" value={data?.unverifiedCount} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={data?.lowConfidenceCount ? "warning" : "success"}>低可信 {data?.lowConfidenceCount ?? 0}</Badge>
          <Badge tone={data?.insufficientBacktestCount ? "warning" : "success"}>样本/数据不足 {data?.insufficientBacktestCount ?? 0}</Badge>
          <Badge tone="muted">合计 {data?.totalCount ?? 0}</Badge>
        </div>
        <p className="text-xs leading-5 text-[var(--text-tertiary)]">
          未确认公开出处的策略只标注为自研或公开思路改造，不展示机构背书。
        </p>
      </CardContent>
    </Card>
  );
}

function SourceMetric({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 text-xl font-semibold text-[var(--color-primary)]">{value ?? "-"}</div>
    </div>
  );
}
