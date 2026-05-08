import Link from "next/link";
import type { ReactNode } from "react";
import { BarChart3, FilePenLine, Search } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Signal } from "@/lib/types";

export function WatchlistTable({
  signals,
  title = "今日观察清单",
  description = "候选标的、策略触发、风险理由与人工确认入口",
  emptyText = "暂无候选信号",
  badgeLabel,
}: {
  signals: Signal[];
  title?: string;
  description?: string;
  emptyText?: string;
  badgeLabel?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          {badgeLabel && <Badge tone="muted">{badgeLabel}</Badge>}
          <Link href="/candidates" className="text-xs text-[var(--color-primary)] hover:underline">
            查看全部
          </Link>
        </div>
      </CardHeader>
      <CardContent className="px-3 pb-3">
        <div className="hidden overflow-x-auto scrollbar-thin md:block">
          <Table className="min-w-[1160px] table-fixed">
            <colgroup>
              <col className="w-[90px]" />
              <col className="w-[80px]" />
              <col className="w-[118px]" />
              <col className="w-[76px]" />
              <col className="w-[86px]" />
              <col className="w-[88px]" />
              <col className="w-[88px]" />
              <col className="w-[82px]" />
              <col />
              <col className="w-[218px]" />
            </colgroup>
            <TableHeader>
              <TableRow>
                <TableHead className="whitespace-nowrap">代码</TableHead>
                <TableHead className="whitespace-nowrap">名称</TableHead>
                <TableHead className="whitespace-nowrap">策略</TableHead>
                <TableHead className="whitespace-nowrap text-right">综合评分</TableHead>
                <TableHead className="whitespace-nowrap">市场状态</TableHead>
                <TableHead className="whitespace-nowrap">风险等级</TableHead>
                <TableHead className="whitespace-nowrap">建议动作</TableHead>
                <TableHead className="whitespace-nowrap text-right">建议仓位</TableHead>
                <TableHead>风险理由</TableHead>
                <TableHead className="whitespace-nowrap text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {signals.map((signal) => (
                <TableRow key={signal.id} className="h-[68px]">
                  <TableCell className="finance-number whitespace-nowrap font-semibold text-[var(--color-primary)]">
                    <Link href={`/stocks/${signal.stock_code}`}>{signal.stock_code}</Link>
                  </TableCell>
                  <TableCell className="whitespace-nowrap font-medium">{signal.stock_name}</TableCell>
                  <TableCell className="whitespace-nowrap text-[var(--text-secondary)]">
                    <div>{signal.dragon ? "短线龙头候选策略" : signal.strategy_name}</div>
                    {signal.candidateLevel && <div className="mt-1 text-[11px] text-[var(--color-primary)]">{signal.candidateLevel}</div>}
                  </TableCell>
                  <TableCell className="finance-number whitespace-nowrap text-right font-semibold">{signal.score.toFixed(1)}</TableCell>
                  <TableCell className="finance-number whitespace-nowrap text-[var(--color-primary)]">{signal.marketRegime || "-"}</TableCell>
                  <TableCell>
                    <RiskBadge level={signal.risk_level} />
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    <ActionLabel level={signal.risk_level} action={signal.suggestedAction} />
                  </TableCell>
                  <TableCell className="finance-number whitespace-nowrap text-right">{formatWeight(signal.suggestedWeight)}</TableCell>
                  <TableCell className="text-[var(--text-secondary)]">
                    <ReasonSummary signal={signal} />
                  </TableCell>
                  <TableCell>
                    <div className="flex min-w-0 justify-end gap-1.5">
                      <SmallAction href={`/stocks/${signal.stock_code}`} icon={<Search className="h-3.5 w-3.5" />} label="详情" />
                      <SmallAction href="/backtest" icon={<BarChart3 className="h-3.5 w-3.5" />} label="回测" />
                      <SmallAction href={`/reviews?stock=${signal.stock_code}`} icon={<FilePenLine className="h-3.5 w-3.5" />} label="复盘" />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {!signals.length && (
                <TableRow>
                  <TableCell colSpan={10} className="py-8 text-center text-[var(--text-tertiary)]">
                    {emptyText}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        <div className="grid gap-3 md:hidden">
          {signals.map((signal) => (
            <WatchlistMobileCard key={signal.id} signal={signal} />
          ))}
          {!signals.length && <div className="py-8 text-center text-sm text-[var(--text-tertiary)]">{emptyText}</div>}
        </div>
      </CardContent>
    </Card>
  );
}

function formatWeight(value?: number) {
  if (value === undefined || value === null) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function WatchlistMobileCard({ signal }: { signal: Signal }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/stocks/${signal.stock_code}`} className="finance-number text-base font-semibold text-[var(--color-primary)]">
            {signal.stock_code}
          </Link>
          <div className="mt-1 text-sm">{signal.stock_name}</div>
        </div>
        <RiskBadge level={signal.risk_level} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded border border-[var(--border-subtle)] p-2">
          <div className="text-[var(--text-tertiary)]">策略</div>
          <div className="mt-1 text-[var(--text-primary)]">{signal.dragon ? "短线龙头候选策略" : signal.strategy_name}</div>
        </div>
        <div className="rounded border border-[var(--border-subtle)] p-2">
          <div className="text-[var(--text-tertiary)]">综合评分</div>
          <div className="finance-number mt-1 text-[var(--color-primary)]">{signal.score.toFixed(1)}</div>
        </div>
      </div>
      {signal.candidateLevel && <div className="mt-3 text-xs text-[var(--color-primary)]">{signal.candidateLevel} / {signal.suggestedAction}</div>}
      <div className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
        <ReasonSummary signal={signal} />
      </div>
    </div>
  );
}

function ActionLabel({ level, action }: { level: string; action?: string }) {
  const label = action || (level === "high" ? "谨慎观察" : level === "medium" ? "观察" : "观察");
  const className =
    label === "暂不参与"
      ? "text-[var(--text-tertiary)]"
      : label === "谨慎观察"
      ? "text-[var(--color-warning)]"
      : level === "medium"
        ? "text-[var(--color-primary)]"
        : "text-[var(--color-success)]";
  return <span className={`whitespace-nowrap text-xs font-semibold ${className}`}>{label}</span>;
}

function SmallAction({ href, icon, label }: { href: string; icon: ReactNode; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex h-7 min-w-[58px] shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-md border border-[var(--border-strong)] px-2 text-xs text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
    >
      {icon}
      {label}
    </Link>
  );
}

function ReasonSummary({ signal }: { signal: Signal }) {
  if (!signal.dragon && !signal.strategyCandidate) {
    return <span className="block leading-5">{signal.risk_reason}</span>;
  }
  const trigger = (signal.triggerReasons || []).slice(0, 2).join("；");
  const risk = (signal.riskReasons || []).slice(0, 2).join("；");
  const exit = (signal.exitRules || [])[0];
  return (
    <div className="space-y-1 leading-5">
      <div><span className="text-[var(--color-primary)]">触发：</span>{trigger || signal.reason}</div>
      <div><span className="text-[var(--color-warning)]">风险：</span>{risk || signal.risk_reason}</div>
      <div><span className="text-[var(--text-tertiary)]">退出：</span>{exit}</div>
    </div>
  );
}
