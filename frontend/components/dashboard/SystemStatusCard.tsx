"use client";

import Link from "next/link";
import { AlertTriangle, BarChart3, CheckCircle2, Database, PlayCircle, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSummary, MarketDataSyncStatus, StrategyPerformanceSummary } from "@/lib/types";

export type ReadinessStep = {
  id: string;
  title: string;
  description: string;
  status: "未完成" | "进行中" | "已完成" | "失败";
  reason?: string;
  actionLabel: string;
  href?: string;
};

export type SystemReadiness = {
  stockPoolCount: number;
  marketDataReady: boolean;
  strategyRanToday: boolean;
  strategyPerformanceReady: boolean;
  backtestReady: boolean;
  latestUpdatedAt?: string | null;
  nextAction: ReadinessStep;
  steps: ReadinessStep[];
};

export function buildSystemReadiness({
  summary,
  performance,
  marketSync
}: {
  summary: DashboardSummary | null;
  performance: StrategyPerformanceSummary | null;
  marketSync: MarketDataSyncStatus | null;
}): SystemReadiness {
  const candidatePoolCount = summary?.candidate_funnel?.rawStockPool || 0;
  const syncedPoolCount = Math.max(marketSync?.successCount || 0, marketSync?.totalCount || 0);
  const stockPoolCount = candidatePoolCount || syncedPoolCount || summary?.market_status.total_count || 0;
  const marketDataReady = Boolean(
    summary?.snapshot_meta?.fromDatabaseSnapshot ||
      summary?.last_data_date ||
      (marketSync?.status === "success" &&
        (marketSync.successCount > 0 || marketSync.usingCacheDate || marketSync.latestTradeDate))
  );
  const strategyRanToday = Boolean(summary?.last_run_time || (summary?.strategy_status || []).some((item) => item.today_signal_count > 0));
  const hasAnyReturn = Boolean(
    (performance?.strategies || []).some((row) =>
      Object.values(row.periods || {}).some((period) => period?.returnRate !== null && period?.returnRate !== undefined)
    )
  );
  const strategyPerformanceReady = Boolean(performance?.validation?.isHealthy || hasAnyReturn);
  const backtestReady = Boolean(summary?.latest_backtest || (summary?.recent_backtests || []).length > 0);
  const candidateReviewReady = strategyRanToday && ((summary?.watchlist || []).length > 0 || (summary?.candidate_layers?.mainWatchlist || []).length > 0 || (summary?.candidate_layers?.hotspotWatchlist || []).length > 0);
  const reviewReady = Boolean((summary?.recent_reviews || []).length > 0);
  const latestUpdatedAt = marketSync?.latestUpdatedAt || summary?.last_run_time || summary?.last_data_date;

  const steps: ReadinessStep[] = [
    {
      id: "stock-pool",
      title: "同步全市场股票池",
      description: `当前股票池 ${stockPoolCount} 只；低于 500 只时，候选池容易反复集中在少数样本股。`,
      status: stockPoolCount >= 500 ? "已完成" : stockPoolCount > 0 ? "未完成" : "未完成",
      reason: stockPoolCount < 500 ? "股票池规模不足，先去数据中心扩充样本。" : undefined,
      actionLabel: stockPoolCount >= 500 ? "查看数据中心" : "扩充全市场股票池",
      href: "/data-center"
    },
    {
      id: "market-data",
      title: "同步每日行情",
      description: "Dashboard、候选池、连板统计和策略运行都会优先读取本地行情缓存。",
      status: marketSync?.isRunning ? "进行中" : marketSync?.status === "failed" ? "失败" : marketDataReady ? "已完成" : "未完成",
      reason: marketSync?.status === "failed" ? marketSync.errorMessage || "行情同步失败，请在数据中心重试。" : undefined,
      actionLabel: marketDataReady ? "查看行情状态" : "同步每日行情",
      href: "/data-center"
    },
    {
      id: "run-strategy",
      title: "确认后台策略快照",
      description: "后台任务会生成市场状态、候选分层、风险约束和今日决策结论；手动刷新仅作为兜底。",
      status: strategyRanToday ? "已完成" : "未完成",
      reason: strategyRanToday ? undefined : "今日策略尚未运行，页面结论可能只是上一次缓存或等待状态。",
      actionLabel: strategyRanToday ? "查看候选池" : "手动刷新数据与策略",
      href: strategyRanToday ? "/candidates" : undefined
    },
    {
      id: "inspect",
      title: "查看候选与一键诊股",
      description: "先看主观察、热点观察和防御观察，再对重点股票生成研报式诊断。",
      status: candidateReviewReady ? "已完成" : strategyRanToday ? "未完成" : "未完成",
      reason: strategyRanToday ? "策略已运行，但还没有形成可复核候选；可检查候选池筛选或一键诊股样本覆盖。" : "策略未运行前，候选池和诊股结论可能缺少今日信号。",
      actionLabel: "查看候选池",
      href: "/candidates"
    },
    {
      id: "performance",
      title: "生成策略净值",
      description: "策略收益看板需要 strategy_nav_daily 和 strategy_performance_summary。",
      status: strategyPerformanceReady ? "已完成" : "未完成",
      reason: strategyPerformanceReady ? undefined : "尚未生成策略净值，收益图表和有效性判断会显示数据不足。",
      actionLabel: strategyPerformanceReady ? "查看策略收益" : "生成策略净值",
      href: "/strategy-performance"
    },
    {
      id: "backtest",
      title: "执行回测验证",
      description: "回测用于验证策略样本量、回撤、胜率和净值曲线，不作为投资建议。",
      status: backtestReady ? "已完成" : "未完成",
      reason: backtestReady ? undefined : "暂无回测记录，策略有效性结论还不充分。",
      actionLabel: backtestReady ? "查看回测记录" : "执行长期回测",
      href: "/backtest"
    },
    {
      id: "review",
      title: "写入复盘记录",
      description: "记录今日市场状态、策略信号、人工判断和明日跟踪点。",
      status: reviewReady ? "已完成" : "未完成",
      reason: reviewReady ? undefined : "暂无复盘记录；建议在策略运行和诊股后沉淀人工结论。",
      actionLabel: reviewReady ? "查看复盘" : "写复盘",
      href: "/reviews"
    }
  ];

  const nextAction =
    steps.find((step) => step.status === "失败") ||
    steps.find((step) => step.status === "进行中") ||
    steps.find((step) => step.status === "未完成") ||
    {
      id: "ready",
      title: "查看今日候选池",
      description: "基础数据、策略运行、回测和策略收益链路已具备可用条件。",
      status: "已完成" as const,
      actionLabel: "查看今日候选池",
      href: "/candidates"
    };

  return { stockPoolCount, marketDataReady, strategyRanToday, strategyPerformanceReady, backtestReady, latestUpdatedAt, nextAction, steps };
}

export function SystemStatusCard({
  readiness,
  onRunStrategy,
  runningStrategy,
  message
}: {
  readiness: SystemReadiness;
  onRunStrategy: () => void;
  runningStrategy: boolean;
  message?: string | null;
}) {
  const allReady = readiness.steps.every((step) => step.status === "已完成");
  return (
    <Card className="border-[var(--border-strong)]">
      <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[var(--color-primary)]" />
            <CardTitle>系统状态与下一步操作</CardTitle>
          </div>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            先确认数据底座和策略链路是否完整，再解读候选、评级和回测结论。
          </p>
        </div>
        <Badge tone={allReady ? "success" : readiness.nextAction.status === "失败" ? "danger" : "warning"}>
          {allReady ? "系统可用" : "需要初始化"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <StatusMetric label="行情数据" value={readiness.marketDataReady ? "已同步" : "待同步"} good={readiness.marketDataReady} />
          <StatusMetric label="股票池规模" value={`${readiness.stockPoolCount} 只`} good={readiness.stockPoolCount >= 500} />
          <StatusMetric label="今日策略" value={readiness.strategyRanToday ? "已运行" : "未运行"} good={readiness.strategyRanToday} />
          <StatusMetric label="策略收益" value={readiness.strategyPerformanceReady ? "可查看" : "缺净值"} good={readiness.strategyPerformanceReady} />
          <StatusMetric label="回测记录" value={readiness.backtestReady ? "已有" : "待验证"} good={readiness.backtestReady} />
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <div className="flex items-start gap-2">
              {readiness.nextAction.status === "失败" ? (
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-danger)]" />
              ) : readiness.nextAction.id === "ready" ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-success)]" />
              ) : (
                <PlayCircle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />
              )}
              <div>
                <div className="text-sm font-semibold">建议下一步：{readiness.nextAction.title}</div>
                <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{readiness.nextAction.description}</div>
                {readiness.nextAction.reason && <div className="mt-2 text-xs leading-5 text-[var(--color-warning)]">{readiness.nextAction.reason}</div>}
                {message && <div className="mt-2 text-xs text-[var(--color-primary)]">{message}</div>}
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {readiness.nextAction.id === "run-strategy" && !readiness.nextAction.href ? (
                <Button onClick={onRunStrategy} disabled={runningStrategy}>
                  <PlayCircle className="h-4 w-4" />
                  {runningStrategy ? "正在启动后台任务" : readiness.nextAction.actionLabel}
                </Button>
              ) : readiness.nextAction.href ? (
                <Link className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[var(--color-primary)] bg-[var(--color-primary)] px-3 text-sm font-medium text-white hover:brightness-110" href={readiness.nextAction.href}>
                  {readiness.nextAction.id === "performance" ? <BarChart3 className="h-4 w-4" /> : <Database className="h-4 w-4" />}
                  {readiness.nextAction.actionLabel}
                </Link>
              ) : null}
              <Link className="inline-flex h-9 items-center justify-center rounded-md border border-[var(--border-strong)] px-3 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]" href="/guide">
                查看使用教程
              </Link>
            </div>
          </div>

          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
            <div className="font-semibold text-[var(--text-primary)]">可用性口径</div>
            <div className="mt-2">最近更新时间：{readiness.latestUpdatedAt || "尚未记录更新时间"}</div>
            <div>策略收益与回测不足时，页面会显示“数据不足/样本不足”，不再用 0 或空图表伪装有效结论。</div>
            <div className="mt-2 text-[var(--text-tertiary)]">本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusMetric({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className={good ? "mt-1 font-semibold text-[var(--color-success)]" : "mt-1 font-semibold text-[var(--color-warning)]"}>{value}</div>
    </div>
  );
}
