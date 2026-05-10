"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, X } from "lucide-react";

import { CandidateFreshnessCard } from "@/components/dashboard/CandidateFreshnessCard";
import { DataCoveragePanel } from "@/components/dashboard/DataCoveragePanel";
import { DailyDecisionCard } from "@/components/dashboard/DailyDecisionCard";
import { DataQualityPanel } from "@/components/dashboard/DataQualityPanel";
import { MarketRegimeCard } from "@/components/dashboard/MarketRegimeCard";
import { MarketSnapshotCard } from "@/components/dashboard/MarketSnapshotCard";
import { MarketThemeCard } from "@/components/dashboard/MarketThemeCard";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { FunnelBreakdownCard } from "@/components/dashboard/FunnelBreakdownCard";
import { OpportunityRiskPanel } from "@/components/dashboard/OpportunityRiskPanel";
import { RecentReviewPanel } from "@/components/dashboard/RecentReviewPanel";
import { RegimeDebugPanel } from "@/components/dashboard/RegimeDebugPanel";
import { RiskAlertPanel } from "@/components/dashboard/RiskAlertPanel";
import { RiskBanner } from "@/components/dashboard/RiskBanner";
import { StrategyDistributionPanel } from "@/components/dashboard/StrategyDistributionPanel";
import { StrategyHealthCard } from "@/components/dashboard/StrategyHealthCard";
import { StrategyPerformanceRadar } from "@/components/dashboard/StrategyPerformanceRadar";
import { StrategyPerformanceSummaryCard } from "@/components/dashboard/StrategyPerformanceSummaryCard";
import { StrategySourceSummaryCard } from "@/components/dashboard/StrategySourceSummaryCard";
import {
  DrawdownChart,
  IndustryDistributionChart,
  PerformanceChart,
  RiskDistributionChart
} from "@/components/dashboard/TerminalCharts";
import { WatchlistTable } from "@/components/dashboard/WatchlistTable";
import { SystemStatusCard, buildSystemReadiness } from "@/components/dashboard/SystemStatusCard";
import { FirstRunGuide } from "@/components/onboarding/FirstRunGuide";
import { api } from "@/lib/api";
import { formatPctPoint, formatPercent } from "@/lib/format";
import type { DashboardStrategyPerformance, DashboardSummary, MarketDataSyncStatus, StrategyPerformanceSummary } from "@/lib/types";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [performanceSummary, setPerformanceSummary] = useState<StrategyPerformanceSummary | null>(null);
  const [dashboardPerformance, setDashboardPerformance] = useState<DashboardStrategyPerformance | null>(null);
  const [marketSyncStatus, setMarketSyncStatus] = useState<MarketDataSyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showGuideHint, setShowGuideHint] = useState(false);
  const [startingPipeline, setStartingPipeline] = useState(false);
  const [pipelineMessage, setPipelineMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [data, performance, strategyRadar, syncStatus] = await Promise.all([
        api.dashboard(),
        api.strategyPerformanceSummary().catch(() => null),
        api.dashboardStrategyPerformance().catch(() => null),
        api.marketDataSyncStatus().catch(() => null)
      ]);
      setSummary(data);
      setPerformanceSummary(performance);
      setDashboardPerformance(strategyRadar);
      setMarketSyncStatus(syncStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    window.addEventListener("quant:data-updated", load);
    return () => window.removeEventListener("quant:data-updated", load);
  }, [load]);

  useEffect(() => {
    setShowGuideHint(window.localStorage.getItem("felix-guide-hint-dismissed") !== "1");
  }, []);

  function dismissGuideHint() {
    window.localStorage.setItem("felix-guide-hint-dismissed", "1");
    setShowGuideHint(false);
  }

  const latestBacktest = summary?.latest_backtest;
  const layers = summary?.candidate_layers;
  const mainWatchlist = layers?.mainWatchlist || summary?.watchlist || [];
  const defensiveWatchlist = layers?.defensiveWatchlist || summary?.defensive_watchlist || [];
  const hotspotWatchlist = layers?.hotspotWatchlist || summary?.hotspot_watchlist || [];
  const actionableWatchlist = [...mainWatchlist, ...hotspotWatchlist, ...defensiveWatchlist]
    .filter((signal, index, list) => list.findIndex((item) => item.id === signal.id) === index);
  const riskPool = layers?.riskPool || summary?.risk_pool || [];
  const funnel = summary?.candidate_funnel;
  const strategyDecisionStatus = summary?.strategy_decision_status;
  const highRiskCount = riskPool.length;
  const marketLabel = summary?.market_regime?.marketRegime || summary?.market_status.summary.replace("样本市场", "") || "震荡";
  const isOffenseRegime = marketLabel === "RiskOn" || marketLabel === "Recovery";
  const riskText = isOffenseRegime
    ? `市场处于 ${marketLabel} 状态，科技成长主线较明确；但策略筛选后可行动候选 ${actionableWatchlist.length} 只，说明选股闸门仍需复核或热点数据覆盖不足。${mainWatchlist.length === 0 ? "当前存在踏空风险：市场强修复但主观察清单为空，请优先检查热点数据覆盖和风控阈值。" : "建议仅小仓试探，并优先人工复核主线候选。"}`
    : `当前市场处于 ${marketLabel} 状态，${highRiskCount} 只股票进入风险观察池，建议先判断今日决策模式，再查看候选标的。`;
  const readiness = buildSystemReadiness({ summary, performance: performanceSummary, marketSync: marketSyncStatus });

  async function startPipelineFromDashboard() {
    if (startingPipeline) return;
    setStartingPipeline(true);
    setPipelineMessage(null);
    try {
      const result = await api.runScheduledJob({ jobName: "after_close_refresh_job", force: true });
      window.localStorage.setItem("felix-scheduled-job-run-id", String(result.jobRunId));
      window.dispatchEvent(new Event("quant:job-started"));
      setPipelineMessage(result.jobRun.reused ? `已接入正在运行的后台任务：任务 ${result.jobRunId}` : `收盘刷新任务已启动：任务 ${result.jobRunId}`);
    } catch (err) {
      setPipelineMessage(err instanceof Error ? err.message : "后台刷新任务启动失败，请稍后重试。");
    } finally {
      setStartingPipeline(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-wide">Dashboard</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            基于市场状态、策略信号、风险约束和回测验证的个人量化研究终端。
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs md:flex">
          <Link
            href="/guide"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] px-3 text-[var(--color-primary)] transition-colors hover:bg-[var(--bg-card-hover)]"
          >
            <BookOpen className="h-4 w-4" />
            新手教程
          </Link>
          <MarketPill label="可行动候选" value={loading ? "加载中" : `${funnel?.finalActionableCandidates ?? mainWatchlist.length} / 初筛 ${funnel?.strategyInitialCandidates ?? summary?.candidate_count ?? 0}`} />
          <MarketPill label="市场均值" value={formatPctPoint(summary?.market_status.avg_change)} />
          <MarketPill label="策略状态" value={`有效 ${strategyDecisionStatus?.activeStrategies ?? 0} / 复盘 ${strategyDecisionStatus?.reviewOnlyStrategies ?? 0} / 暂停 ${strategyDecisionStatus?.pausedStrategies ?? 0}`} />
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">
          {error}
        </div>
      )}

      {showGuideHint && (
        <div className="flex flex-col gap-3 rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-sm text-[var(--text-secondary)] md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-2">
            <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-primary)]" />
            <div>
              <div className="font-semibold">第一次使用 Felix量化？建议先阅读 5 分钟快速上手教程。</div>
              <div className="mt-1 text-xs text-[var(--text-tertiary)]">教程覆盖数据同步、策略运行、候选池、一键诊股、回测、策略收益和风险复盘。</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/guide" className="rounded-md border border-[var(--border-strong)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--color-primary)] hover:bg-[var(--bg-card-hover)]">
              打开教程
            </Link>
            <button type="button" className="rounded-md p-2 text-[var(--text-tertiary)] hover:bg-[var(--bg-card-hover)]" onClick={dismissGuideHint} aria-label="关闭教程提示">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      <SystemStatusCard
        readiness={readiness}
        onRunStrategy={startPipelineFromDashboard}
        runningStrategy={startingPipeline}
        message={pipelineMessage}
      />

      {summary?.snapshot_meta?.isHistoricalSnapshot && (
        <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-3 text-sm leading-6 text-[var(--color-warning)]">
          当前展示的是 {summary.snapshot_meta.dataDate || "历史"} 数据库快照，仅用于研究复盘。请等待后台自动任务完成，或手动刷新数据与策略。
        </div>
      )}

      <FirstRunGuide steps={readiness.steps} />

      <RiskBanner text={riskText} />

      <DailyDecisionCard summary={summary} />

      <div className="grid gap-4">
        <MarketSnapshotCard summary={summary} />
        <WatchlistTable
          signals={actionableWatchlist}
          title="可行动候选摘要"
          description="主观察、热点观察和防御观察的合并摘要；所有标的仍需人工确认"
          emptyText="当前无可行动候选。若行情已同步，请先运行策略；若策略已运行，请检查筛选条件、热点数据覆盖和风控阈值。"
          badgeLabel={`${actionableWatchlist.length} 只`}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard title="今日更新时间" value={summary?.last_run_time || summary?.last_data_date || "尚未运行策略"} hint={summary?.last_data_date || "先同步行情并运行策略"} />
        <MetricCard title="主观察清单" value={loading ? "加载中" : String(mainWatchlist.length)} hint={mainWatchlist.length ? "可观察候选" : "未生成主观察候选"} tone="risk" />
        <MetricCard title="策略初筛漏斗" value={`${funnel?.strategyInitialCandidates ?? summary?.candidate_count ?? 0} -> ${funnel?.finalActionableCandidates ?? mainWatchlist.length}`} hint={`风险池 ${funnel?.riskPool ?? riskPool.length} / 防御 ${funnel?.defensiveWatchlist ?? defensiveWatchlist.length}`} tone="risk" />
        <MetricCard title="最近回测收益率" value={latestBacktest ? formatPercent(latestBacktest.total_return) : "尚未回测"} hint={latestBacktest?.strategy_name || "去回测页执行长期回测"} tone="up" />
      </div>

      <WatchlistTable
        signals={mainWatchlist}
        title="主观察清单"
        description="仅展示可观察、风险可控、策略硬条件满足且市场状态允许的候选"
        emptyText="主观察清单为空：当前市场或策略质量不足，今日以等待、防御观察和复盘为主。"
        badgeLabel={`${mainWatchlist.length} 只`}
      />

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
        <WatchlistTable
          signals={defensiveWatchlist}
          title="防御观察清单"
          description="RiskOff / Choppy 下优先查看低波防御、质量动量和低回撤候选"
          emptyText="暂无防御观察候选。"
          badgeLabel={`${defensiveWatchlist.length} 只`}
        />
        <WatchlistTable
          signals={hotspotWatchlist}
          title="热点观察清单"
          description="RiskOn / Recovery 下的主线强势或降级热点候选，中风险可观察但必须人工确认"
          emptyText="暂无热点观察候选，说明主线到个股映射失败或热点数据不足。"
          badgeLabel={`${hotspotWatchlist.length} 只`}
        />
      </div>

      <details className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
        <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">展开策略收益、来源和候选新鲜度</summary>
        <div className="mt-4 space-y-4">
          <StrategyPerformanceRadar data={dashboardPerformance} />
          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <StrategyDistributionPanel summary={summary} />
            <StrategySourceSummaryCard summary={summary} />
          </div>
          <StrategyPerformanceSummaryCard summary={performanceSummary} />
          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <CandidateFreshnessCard summary={summary} />
            <StrategyHealthCard summary={summary} />
          </div>
        </div>
      </details>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
        <WatchlistTable
          signals={riskPool}
          title="风险观察池摘要"
          description="高风险或暂不参与标的，仅用于风险跟踪和复盘，不作为今日行动依据"
          emptyText="暂无高风险或暂不参与标的。"
          badgeLabel={`${riskPool.length} 只`}
        />
        <RiskAlertPanel alerts={summary?.risk_alerts || []} />
      </div>

      <details className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
        <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">高级数据质量与行情状态调试</summary>
        <div className="mt-4 space-y-4">
          <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <DataQualityPanel summary={summary} />
            <DataCoveragePanel summary={summary} />
          </div>
          <RegimeDebugPanel summary={summary} />
        </div>
      </details>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <MarketRegimeCard summary={summary} />
        <MarketThemeCard summary={summary} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <OpportunityRiskPanel summary={summary} />
        <FunnelBreakdownCard summary={summary} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <PerformanceChart />
        <DrawdownChart />
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.8fr_0.8fr_1fr]">
        <RiskDistributionChart signals={mainWatchlist} />
        <IndustryDistributionChart signals={mainWatchlist} />
        <RecentReviewPanel summary={summary} />
      </div>
    </div>
  );
}

function MarketPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="finance-number ml-2 font-semibold text-[var(--color-primary)]">{value}</span>
    </div>
  );
}
