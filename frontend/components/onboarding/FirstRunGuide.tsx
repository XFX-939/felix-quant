import Link from "next/link";
import { CheckCircle2, CircleDashed, Clock3, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ReadinessStep } from "@/components/dashboard/SystemStatusCard";

export function FirstRunGuide({ steps }: { steps: ReadinessStep[] }) {
  const shouldShow = steps.some((step) => step.status !== "已完成");
  if (!shouldShow) return null;
  return (
    <Card className="border-[rgba(245,166,35,0.45)]">
      <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>首次使用向导</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            从数据同步到回测复盘的最短路径。按顺序完成后，Dashboard、候选池和策略收益会更可信。
          </p>
        </div>
        <Badge tone="warning">建议先完成</Badge>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
          {steps.map((step, index) => (
            <div key={step.id} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-[var(--text-tertiary)]">Step {index + 1}</span>
                <StatusIcon status={step.status} />
              </div>
              <div className="mt-2 text-sm font-semibold">{step.title}</div>
              <p className="mt-2 min-h-12 text-xs leading-5 text-[var(--text-secondary)]">{step.description}</p>
              {step.reason && <div className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--color-warning)]">{step.reason}</div>}
              {step.href ? (
                <Link href={step.href} className="mt-3 inline-flex h-8 items-center rounded-md border border-[var(--border-strong)] px-2 text-xs text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
                  {step.actionLabel}
                </Link>
              ) : (
                <div className="mt-3 text-xs text-[var(--text-tertiary)]">可在上方状态卡片执行</div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function StatusIcon({ status }: { status: ReadinessStep["status"] }) {
  if (status === "已完成") return <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />;
  if (status === "进行中") return <Clock3 className="h-4 w-4 text-[var(--color-primary)]" />;
  if (status === "失败") return <XCircle className="h-4 w-4 text-[var(--color-danger)]" />;
  return <CircleDashed className="h-4 w-4 text-[var(--color-warning)]" />;
}
