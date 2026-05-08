import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

export function CandidateFreshnessCard({ summary }: { summary: DashboardSummary | null }) {
  const freshness = summary?.candidate_diversity;
  return (
    <Card>
      <CardHeader>
        <CardTitle>候选池新鲜度</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <Mini label="今日新进入" value={`${freshness?.newCandidateCount ?? 0} 只`} />
          <Mini label="近5日重复率" value={formatPercent(freshness?.repeatRate5d, 0)} />
          <Mini label="最大行业集中度" value={formatPercent(freshness?.industryConcentration, 0)} />
          <Mini label="大市值蓝筹占比" value={formatPercent(freshness?.largeCapRatio, 0)} />
        </div>
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-secondary)]">
          重复最高标的：
          {(freshness?.topRepeatedCandidates || []).slice(0, 3).map((item) => item.name).join(" / ") || "-"}
        </div>
        {(freshness?.warnings || []).map((warning) => (
          <div key={warning} className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-2 text-xs text-[var(--text-secondary)]">
            {warning}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 font-semibold text-[var(--color-primary)]">{value}</div>
    </div>
  );
}
