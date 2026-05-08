import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary } from "@/lib/types";

const modeLabels: Record<string, string> = {
  WAIT: "等待",
  DEFENSIVE_OBSERVE: "防御观察",
  WATCH: "谨慎观察",
  PROBE: "小仓试探",
  RISK_OFF: "风险关闭",
};

export function DailyDecisionCard({ summary }: { summary: DashboardSummary | null }) {
  const decision = summary?.daily_decision;
  const modeLabel = modeLabels[decision?.decisionMode || ""] || "等待数据";
  return (
    <Card className="border-[var(--border-strong)]">
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>今日决策结论</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">先判断今日是否适合行动，再看候选标的</p>
        </div>
        <Badge tone={decision?.decisionMode === "PROBE" ? "warning" : decision?.decisionMode === "WAIT" || decision?.decisionMode === "RISK_OFF" ? "danger" : "default"}>
          {modeLabels[decision?.decisionMode || ""] || "-"}
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <div>
            <div className="text-2xl font-semibold text-[var(--color-primary)]">{modeLabel}</div>
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              {decision?.decisionText || "请先更新数据并运行策略，系统会生成今日决策结论。"}
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <Mini label="市场状态" value={decision?.marketRegime || summary?.market_regime?.marketRegime || "-"} />
              <Mini
                label="建议总仓位"
                value={
                  decision
                    ? `${formatPercent(decision.suggestedTotalPositionMin, 0)} ~ ${formatPercent(decision.suggestedTotalPositionMax, 0)}`
                    : "-"
                }
              />
              <Mini label="下一次复查" value={decision?.nextCheck || "-"} />
            </div>
          </div>
          <div className="grid gap-3">
            <ActionList title="允许动作" items={decision?.allowedActions || []} tone="success" />
            <ActionList title="禁止动作" items={decision?.forbiddenActions || []} tone="danger" />
          </div>
        </div>
        <div className="mt-4 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
          <div className="text-xs font-semibold text-[var(--text-tertiary)]">核心原因</div>
          <ul className="mt-2 space-y-1.5 text-sm text-[var(--text-secondary)]">
            {(decision?.keyReasons.length ? decision.keyReasons : ["暂无策略运行结论"]).map((item) => (
              <li key={item}>- {item}</li>
            ))}
          </ul>
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          <Checklist title={`当前为什么是${modeLabel}`} items={decision?.whyCurrentMode || []} fallback="当前模式由市场状态、候选质量和风险比例共同决定。" />
          <Checklist title={decision?.decisionMode === "WAIT" ? "等待什么信号" : "还在等待什么信号"} items={decision?.waitingSignals || []} fallback="等待市场状态和策略质量改善。" />
          <Checklist title="切换到防御观察" items={decision?.switchConditions?.toDefensiveObserve || []} fallback="等待低风险防御候选出现。" />
          <Checklist title="切换到谨慎观察 / 小仓试探" items={[...(decision?.switchConditions?.toWatch || []), ...(decision?.switchConditions?.toProbe || [])]} fallback="等待主观察清单和有效策略恢复。" />
        </div>
      </CardContent>
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function ActionList({ title, items, tone }: { title: string; items: string[]; tone: "success" | "danger" }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.length ? items.map((item) => <Badge key={item} tone={tone}>{item}</Badge>) : <Badge tone="muted">无</Badge>}
      </div>
    </div>
  );
}

function Checklist({ title, items, fallback }: { title: string; items: string[]; fallback: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="text-xs font-semibold text-[var(--text-tertiary)]">{title}</div>
      <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--text-secondary)]">
        {(items.length ? items : [fallback]).slice(0, 5).map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}
