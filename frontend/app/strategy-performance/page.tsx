"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { BarChart3, Play, RefreshCw } from "lucide-react";

import {
  StrategyDrawdownChart,
  StrategyNavLineChart,
  StrategyPerformanceHeatmap,
  StrategyReturnBarChart
} from "@/components/charts/StrategyPerformanceCharts";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  PerformancePeriod,
  StrategyNavResponse,
  StrategyPerformanceDetail,
  StrategyPerformanceRow,
  StrategyPerformanceSummary,
  StrategyPeriodPerformance,
  TaskRun
} from "@/lib/types";

const PERIODS: PerformancePeriod[] = ["1M", "3M", "6M", "1Y"];
const PERIOD_LABELS: Record<PerformancePeriod, string> = {
  "1M": "近1月",
  "3M": "近3月",
  "6M": "近半年",
  "1Y": "近1年",
  "ALL": "全部"
};

type SortKey = "return1M" | "return3M" | "return6M" | "return1Y" | "maxDrawdown" | "sharpeRatio" | "winRate" | "tradeCount";

export default function StrategyPerformancePage() {
  const [summary, setSummary] = useState<StrategyPerformanceSummary | null>(null);
  const [nav, setNav] = useState<StrategyNavResponse | null>(null);
  const [detail, setDetail] = useState<StrategyPerformanceDetail | null>(null);
  const [period, setPeriod] = useState<PerformancePeriod>("1Y");
  const [status, setStatus] = useState("all");
  const [strategyType, setStrategyType] = useState("all");
  const [benchmark, setBenchmark] = useState("LOCAL_EQUAL_WEIGHT");
  const [sortKey, setSortKey] = useState<SortKey>("return1M");
  const [onlyEnabled, setOnlyEnabled] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("strategy");
  });
  const [task, setTask] = useState<TaskRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setError(null);
    try {
      const data = await api.strategyPerformanceSummary({ benchmarkCode: benchmark });
      setSummary(data);
      setSelectedStrategy((current) => current || data.strategies[0]?.strategyName || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "策略收益加载失败");
    } finally {
      setLoading(false);
    }
  }, [benchmark]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const filteredRows = useMemo(() => {
    const rows = (summary?.strategies || []).filter((row) => {
      const statusValue = statusLabel(row.suggestedStrategyAction);
      const matchesStatus = status === "all" || statusValue === status;
      const matchesType = strategyType === "all" || row.strategyType.includes(strategyType) || row.strategyName.includes(strategyType);
      const matchesEnabled = !onlyEnabled || row.enabled;
      return matchesStatus && matchesType && matchesEnabled;
    });
    return [...rows].sort((a, b) => sortValue(b, sortKey) - sortValue(a, sortKey));
  }, [onlyEnabled, sortKey, status, strategyType, summary?.strategies]);

  const chartStrategies = useMemo(() => filteredRows.slice(0, 5).map((row) => row.strategyName), [filteredRows]);

  useEffect(() => {
    if (!chartStrategies.length) {
      setNav(null);
      return;
    }
    api
      .strategyPerformanceNav({ strategyNames: chartStrategies.join(","), period, benchmarkCode: benchmark })
      .then(setNav)
      .catch((err) => setError(err instanceof Error ? err.message : "净值曲线加载失败"));
  }, [benchmark, chartStrategies, period]);

  useEffect(() => {
    if (!selectedStrategy) {
      setDetail(null);
      return;
    }
    api
      .strategyPerformanceDetail(selectedStrategy, { period })
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [period, selectedStrategy]);

  useEffect(() => {
    if (!task || !["pending", "running"].includes(task.status)) return;
    const timer = window.setInterval(async () => {
      const next = await api.task(task.id);
      setTask(next);
      if (!["pending", "running"].includes(next.status)) {
        window.clearInterval(timer);
        await loadSummary();
      }
    }, 1400);
    return () => window.clearInterval(timer);
  }, [loadSummary, task]);

  async function refreshPerformance() {
    setError(null);
    try {
      const result = await api.refreshStrategyPerformance({ force: true });
      setTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新策略收益失败");
    }
  }

  async function runEnabledBatchBacktest() {
    setError(null);
    try {
      const defaults = await api.backtestDefaults();
      const strategyNames = (summary?.strategies || []).filter((row) => row.enabled).map((row) => row.strategyName);
      if (!strategyNames.length) {
        setError("当前没有启用策略可回测。");
        return;
      }
      const result = await api.runBatchBacktestTask({
        strategyNames,
        stockPool: defaults.defaultStockPool || "today_candidates",
        startDate: defaults.periods["1Y"],
        endDate: defaults.latestTradeDate,
        initialCapital: 100000,
        transactionCost: 0.0003,
        slippage: 0.001,
        stopLoss: 0.08,
        takeProfit: 0.12,
        maxPositionPerStock: 0.2,
        maxHoldingCount: 3,
        maxHoldingDays: 5
      });
      setTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量回测启动失败");
    }
  }

  async function generateNav() {
    setError(null);
    try {
      const result = await api.generateStrategyNav({ force: false });
      setTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成策略净值失败");
    }
  }

  async function refreshSummaryOnly() {
    setError(null);
    try {
      const result = await api.refreshStrategySummary({ force: true });
      setTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新收益汇总失败");
    }
  }

  const overview = summary?.overview;
  const validation = summary?.validation;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm text-[var(--text-tertiary)]">Strategy Performance</div>
          <h1 className="mt-1 text-xl font-semibold">策略收益看板</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">跟踪各策略在不同周期下的收益、回撤、胜率与净值变化。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-tertiary)]">
            更新时间：{summary?.updatedAt || "--"}
          </div>
          <Button onClick={refreshPerformance} disabled={task ? ["pending", "running"].includes(task.status) : false}>
            <RefreshCw className={cn("h-4 w-4", task && ["pending", "running"].includes(task.status) && "animate-spin")} />
            更新策略收益
          </Button>
          <Button variant="outline" onClick={runEnabledBatchBacktest} disabled={task ? ["pending", "running"].includes(task.status) : false}>
            <Play className="h-4 w-4" />
            刷新并回测全部启用策略
          </Button>
        </div>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}
      {task && ["pending", "running"].includes(task.status) && <TaskProgress task={task} />}

      <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
        策略收益来自后端 `strategy_nav_daily` 与 `strategy_performance_summary`，由回测结果或策略净值预聚合生成。样本不足和数据不足不作为策略有效性结论。
      </div>

      <PerformanceDataStatus summary={summary} />

      <DataRepairCard
        validation={validation}
        disabled={task ? ["pending", "running"].includes(task.status) : false}
        onGenerateNav={generateNav}
        onRefreshSummary={refreshSummaryOnly}
      />

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <OverviewCard title="近1月最佳策略" value={overview?.best1M?.strategyName || "尚未生成"} hint={overview?.best1M ? formatOptionalPercent(overview.best1M.returnRate) : "先生成策略净值"} />
        <OverviewCard title="近3月最佳策略" value={overview?.best3M?.strategyName || "尚未生成"} hint={overview?.best3M ? formatOptionalPercent(overview.best3M.returnRate) : "先执行长期回测"} />
        <OverviewCard title="近半年最佳策略" value={overview?.best6M?.strategyName || "尚未生成"} hint={overview?.best6M ? formatOptionalPercent(overview.best6M.returnRate) : "等待收益汇总"} />
        <OverviewCard title="近1年最佳策略" value={overview?.best1Y?.strategyName || "尚未生成"} hint={overview?.best1Y ? formatOptionalPercent(overview.best1Y.returnRate) : "等待收益汇总"} />
        <OverviewCard title="启用策略数量" value={summary ? String(overview?.enabledStrategyCount ?? 0) : "加载中"} hint="当前配置启用" />
        <OverviewCard title="有效回测策略" value={summary ? String(overview?.validBacktestStrategyCount ?? 0) : "加载中"} hint="回测可信度为可信" />
        <OverviewCard title="样本不足策略" value={summary ? String(overview?.insufficientSampleCount ?? 0) : "加载中"} hint="交易次数或覆盖率不足" />
        <OverviewCard title="最大回撤最高" value={overview?.maxDrawdownStrategy?.strategyName || "尚未生成"} hint={overview?.maxDrawdownStrategy ? formatOptionalPercent(overview.maxDrawdownStrategy.maxDrawdown) : "无可比样本"} tone="risk" />
      </section>

      <Card>
        <CardContent className="grid gap-3 pt-4 md:grid-cols-2 xl:grid-cols-6">
          <Select value={period} onChange={(event) => setPeriod(event.target.value as PerformancePeriod)}>
            <option value="1M">1M 近1月</option>
            <option value="3M">3M 近3月</option>
            <option value="6M">6M 近半年</option>
            <option value="1Y">1Y 近1年</option>
            <option value="ALL">ALL 全部</option>
          </Select>
          <Select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">全部状态</option>
            <option value="有效">有效</option>
            <option value="降权">降权</option>
            <option value="仅复盘">仅复盘</option>
            <option value="暂停">暂停</option>
          </Select>
          <Select value={strategyType} onChange={(event) => setStrategyType(event.target.value)}>
            <option value="all">全部类型</option>
            <option value="趋势">趋势</option>
            <option value="热点">热点</option>
            <option value="低波">低波</option>
            <option value="质量">质量</option>
            <option value="价值">价值</option>
            <option value="短线">短线</option>
            <option value="Alpha">Alpha</option>
          </Select>
          <Select value={benchmark} onChange={(event) => setBenchmark(event.target.value)}>
            <option value="LOCAL_EQUAL_WEIGHT">本地等权基准</option>
            <option value="000300.SH">沪深300</option>
            <option value="000905.SH">中证500</option>
            <option value="000852.SH">中证1000</option>
            <option value="399006.SZ">创业板指</option>
            <option value="NONE">无基准</option>
          </Select>
          <Select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="return1M">近1月收益</option>
            <option value="return3M">近3月收益</option>
            <option value="return6M">近半年收益</option>
            <option value="return1Y">近1年收益</option>
            <option value="maxDrawdown">最大回撤</option>
            <option value="sharpeRatio">夏普比率</option>
            <option value="winRate">胜率</option>
            <option value="tradeCount">交易次数</option>
          </Select>
          <label className="flex h-9 items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-secondary)]">
            <input type="checkbox" checked={onlyEnabled} onChange={(event) => setOnlyEnabled(event.target.checked)} />
            只看启用策略
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>策略收益表格</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">样本不足或数据不足时，收益不作为策略有效性依据。</p>
          </div>
          <Badge tone="default">{filteredRows.length} 个策略</Badge>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full min-w-[1180px] text-sm">
              <thead className="border-b border-[var(--border-subtle)] bg-[var(--color-primary-soft)] text-xs text-[var(--text-secondary)]">
                <tr>
                  <Th>策略名称</Th>
                  <Th>今日状态</Th>
                  <Th>近1月</Th>
                  <Th>近3月</Th>
                  <Th>近半年</Th>
                  <Th>近1年</Th>
                  <Th>1年回撤</Th>
                  <Th>胜率</Th>
                  <Th>交易</Th>
                  <Th>夏普</Th>
                  <Th>可信度</Th>
                  <Th align="right">操作</Th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row) => (
                  <tr key={row.strategyName} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-elevated)]">
                    <Td>
                      <button className="text-left font-semibold text-[var(--text-primary)] hover:text-[var(--color-primary)]" onClick={() => setSelectedStrategy(row.strategyName)} type="button">
                        {row.strategyName}
                      </button>
                      <div className="mt-1 text-xs text-[var(--text-tertiary)]">{row.strategyType}</div>
                    </Td>
                    <Td><StatusBadge row={row} /></Td>
                    <Td><ReturnCell performance={row.periods["1M"]} /></Td>
                    <Td><ReturnCell performance={row.periods["3M"]} /></Td>
                    <Td><ReturnCell performance={row.periods["6M"]} /></Td>
                    <Td><ReturnCell performance={row.periods["1Y"]} /></Td>
                    <Td><PeriodMetric performance={row.periods["1Y"]} value={row.periods["1Y"]?.maxDrawdown} formatter={formatOptionalPercent} tone="drawdown" /></Td>
                    <Td><PeriodMetric performance={row.periods["1Y"]} value={row.periods["1Y"]?.winRate} formatter={formatOptionalPercent} /></Td>
                    <Td>{row.periods["1Y"]?.tradeCount ?? "--"}</Td>
                    <Td><PeriodMetric performance={row.periods["1Y"]} value={row.periods["1Y"]?.sharpeRatio} formatter={formatOptionalNumber} /></Td>
                    <Td><ValidityBadge level={row.periods["1Y"]?.validityLevel || row.latestBacktestValidity} /></Td>
                    <Td align="right">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => setSelectedStrategy(row.strategyName)}>
                          查看走势
                        </Button>
                        <Link href="/backtest" className="inline-flex h-8 items-center rounded-md border border-[var(--border-subtle)] px-2 text-xs text-[var(--text-secondary)] hover:text-[var(--color-primary)]">
                          重新回测
                        </Link>
                      </div>
                    </Td>
                  </tr>
                ))}
                {!filteredRows.length && (
                  <tr>
                    <Td colSpan={12} className="py-4">
                      <EmptyState
                        variant={loading ? "loading" : error ? "error" : "backtest-missing"}
                        title={loading ? "正在加载策略收益" : "暂无可用策略收益"}
                        description={loading ? "正在读取 strategy_performance_summary 和策略净值缓存。" : "当前缺少 strategy_nav_daily 或 strategy_performance_summary，因此不能用 0.0% 伪装收益。"}
                        reason={error || "请先生成策略净值、执行长期回测，或刷新收益汇总。样本不足策略不会参与有效性排序。"}
                        primaryAction={{ label: "生成策略净值", onClick: generateNav, disabled: Boolean(task && ["pending", "running"].includes(task.status)) }}
                        secondaryAction={{ label: "执行长期回测", href: "/backtest" }}
                      />
                    </Td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>多策略净值曲线</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyNavLineChart data={nav} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>策略收益热力图</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyPerformanceHeatmap rows={filteredRows.slice(0, 12)} periods={PERIODS} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>单策略详情走势</CardTitle>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">{selectedStrategy || "请选择策略"}</p>
            </div>
            {detail && <Badge tone="muted">{detail.diagnosis.performanceStatus}</Badge>}
          </CardHeader>
          <CardContent>
            <StrategyNavLineChart data={detail ? { period, benchmarkCode: benchmark, series: [{ strategyName: detail.strategyName, points: detail.nav }] } : null} height={260} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>回撤曲线</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyDrawdownChart points={detail?.nav || []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>每日收益柱状图</CardTitle>
          </CardHeader>
          <CardContent>
            <StrategyReturnBarChart points={detail?.nav || []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>策略表现诊断</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-[var(--text-secondary)]">
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              {detail?.diagnosis.diagnosisText || "暂无诊断，请先选择策略并更新策略收益。"}
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <MiniMetric label="建议动作" value={detail?.diagnosis.suggestedStrategyAction || "--"} />
              <MiniMetric label="交易记录" value={`${detail?.trades.length ?? 0} 条`} />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function OverviewCard({ title, value, hint, tone }: { title: string; value: string; hint: string; tone?: "risk" }) {
  return (
    <Card>
      <CardContent className="p-3.5">
        <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
        <div className={cn("mt-2 truncate text-lg font-semibold", tone === "risk" ? "text-[var(--color-success)]" : "text-[var(--color-primary)]")}>{value}</div>
        <div className="mt-1 truncate text-xs text-[var(--text-tertiary)]">{hint || "--"}</div>
      </CardContent>
    </Card>
  );
}

function PerformanceDataStatus({ summary }: { summary: StrategyPerformanceSummary | null }) {
  const validation = summary?.validation;
  const navReady = Boolean(validation && validation.missingNavStrategies.length === 0);
  const summaryReady = Boolean(validation && validation.missingSummaryStrategies.length === 0);
  const latest = validation?.latestTradeDate || summary?.updatedAt || "尚未生成";
  const validCount = summary?.overview.validBacktestStrategyCount ?? 0;
  const insufficient = summary?.overview.insufficientSampleCount ?? validation?.insufficientSampleItems.length ?? 0;
  const oneYearDiagnostics = validation?.periodCoverageDiagnostics?.filter((item) => item.period === "1Y") || [];
  const weakestOneYear = [...oneYearDiagnostics].sort((a, b) => a.coverageRatio - b.coverageRatio)[0];
  const oneYearCoverageText = weakestOneYear
    ? `${weakestOneYear.availableRows}/${weakestOneYear.requiredRows} 点`
    : "待生成";
  const reason = validation?.warnings.slice(0, 2).join("；") || "收益数据链路正常时，表格和走势图会从后端预聚合表读取。";
  return (
    <Card>
      <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>收益数据链路状态</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">判断收益图表为何为空，以及下一步应该生成哪类数据。</p>
        </div>
        <Badge tone={validation?.isHealthy ? "success" : "warning"}>{validation?.isHealthy ? "链路可用" : "需要补齐"}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          <RepairMetric label="strategy_nav_daily" value={navReady ? "已覆盖" : `缺 ${validation?.missingNavStrategies.length ?? 0} 个`} />
          <RepairMetric label="performance_summary" value={summaryReady ? "已生成" : `缺 ${validation?.missingSummaryStrategies.length ?? 0} 个`} />
          <RepairMetric label="最近生成时间" value={latest} />
          <RepairMetric label="有效策略数量" value={`${validCount} 个`} />
          <RepairMetric label="样本不足策略" value={`${insufficient} 个`} />
          <RepairMetric label="近1年最低覆盖" value={oneYearCoverageText} />
        </div>
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
          {reason}
        </div>
      </CardContent>
    </Card>
  );
}

function TaskProgress({ task }: { task: TaskRun }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-3.5">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span>{task.current_stage || "策略收益任务运行中"}</span>
          <span className="finance-number text-[var(--color-primary)]">{task.progress_percent.toFixed(0)}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
          <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${task.progress_percent}%` }} />
        </div>
        <div className="flex flex-wrap gap-3 text-xs text-[var(--text-tertiary)]">
          <span>已处理 {task.processed_count}/{task.total_count}</span>
          <span>成功 {task.success_count}</span>
          <span>失败 {task.failed_count}</span>
          <span>耗时 {Math.round((task.duration_ms || 0) / 1000)}s</span>
        </div>
      </CardContent>
    </Card>
  );
}

function ReturnCell({ performance }: { performance?: StrategyPeriodPerformance }) {
  if (!performance || performance.returnRate === null || performance.returnRate === undefined) {
    return <span className="text-[var(--text-tertiary)]">--</span>;
  }
  if (performance.validityLevel === "数据不足") {
    return (
      <span className="text-[var(--color-danger)]" title={performance.warnings.join("；") || "数据覆盖不足"}>
        数据不足 <span className="text-xs text-[var(--text-tertiary)]">{Math.round(performance.dataCoverageRatio * 100)}%</span>
      </span>
    );
  }
  if (performance.validityLevel === "样本不足") {
    return <span className="text-[var(--color-warning)]" title={`交易次数 ${performance.tradeCount}，统计意义较弱`}>样本不足</span>;
  }
  return <span className={returnTone(performance.returnRate)}>{formatPercent(performance.returnRate)}</span>;
}

function PeriodMetric({
  performance,
  value,
  formatter,
  tone
}: {
  performance?: StrategyPeriodPerformance;
  value?: number | null;
  formatter: (value?: number | null) => string;
  tone?: "drawdown";
}) {
  if (!performance || value === null || value === undefined) {
    return <span className="text-[var(--text-tertiary)]">--</span>;
  }
  if (performance.validityLevel === "数据不足") {
    return (
      <span className="text-[var(--color-danger)]" title={performance.warnings.join("；") || "数据覆盖不足"}>
        数据不足 <span className="text-xs text-[var(--text-tertiary)]">{Math.round(performance.dataCoverageRatio * 100)}%</span>
      </span>
    );
  }
  if (performance.validityLevel === "样本不足") {
    return <span className="text-[var(--color-warning)]" title={`交易次数 ${performance.tradeCount}，统计意义较弱`}>样本不足</span>;
  }
  return <span className={tone === "drawdown" ? "text-[var(--color-success)]" : undefined}>{formatter(value)}</span>;
}

function DataRepairCard({
  validation,
  disabled,
  onGenerateNav,
  onRefreshSummary
}: {
  validation?: StrategyPerformanceSummary["validation"];
  disabled: boolean;
  onGenerateNav: () => void;
  onRefreshSummary: () => void;
}) {
  const missingNav = validation?.missingNavStrategies.length || 0;
  const missingSummary = validation?.missingSummaryStrategies.length || 0;
  const insufficientSample = validation?.insufficientSampleItems.length || 0;
  const lowCoverage = validation?.lowCoverageItems.length || 0;
  const invalidZero = validation?.invalidZeroReturnItems.length || 0;
  const oneYearDiagnostics = validation?.periodCoverageDiagnostics?.filter((item) => item.period === "1Y") || [];
  const worstCoverage = [...oneYearDiagnostics].sort((a, b) => a.coverageRatio - b.coverageRatio)[0];
  const coverageHint = worstCoverage
    ? `近1年最低覆盖 ${worstCoverage.availableRows}/${worstCoverage.requiredRows} 个净值点，仍缺 ${worstCoverage.missingRows} 个。`
    : "尚未检测到近1年净值覆盖诊断。";
  if (validation?.isHealthy && !insufficientSample && !lowCoverage) {
    return (
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-3.5">
          <div>
            <div className="text-sm font-semibold">策略收益数据链路正常</div>
            <div className="mt-1 text-xs text-[var(--text-tertiary)]">已检测到每日净值和周期汇总，仍需结合回测可信度和样本量复核。</div>
          </div>
          <Badge tone="success">数据可绘图</Badge>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>数据修复建议</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">系统会区分缺少净值、缺少汇总、样本不足和覆盖不足，不用零收益伪装有效表现。</p>
        </div>
        <Badge tone={invalidZero ? "danger" : missingNav || missingSummary ? "warning" : "muted"}>{invalidZero ? "数据异常" : "需要修复"}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <RepairMetric label="缺少每日净值" value={`${missingNav} 个策略`} />
          <RepairMetric label="缺少收益汇总" value={`${missingSummary} 个策略`} />
          <RepairMetric label="样本不足" value={`${insufficientSample} 项`} />
          <RepairMetric label="覆盖不足" value={`${lowCoverage} 项`} />
        </div>
        {!!validation?.warnings.length && (
          <ul className="space-y-1 text-xs leading-5 text-[var(--text-secondary)]">
            {validation.warnings.slice(0, 4).map((warning) => (
              <li key={warning}>- {warning}</li>
            ))}
          </ul>
        )}
        {lowCoverage > 0 && (
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
            {coverageHint} 这通常表示历史行情或策略净值窗口不足，需要先补齐历史数据，再重新生成策略净值和收益汇总。
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          <Button onClick={onGenerateNav} disabled={disabled}>
            生成策略净值
          </Button>
          <Button variant="outline" onClick={onRefreshSummary} disabled={disabled}>
            刷新收益汇总
          </Button>
          <Link href="/backtest" className="inline-flex h-9 items-center rounded-md border border-[var(--border-subtle)] px-3 text-sm text-[var(--text-secondary)] hover:text-[var(--color-primary)]">
            执行长期回测
          </Link>
          <Link href="/data-center" className="inline-flex h-9 items-center rounded-md border border-[var(--border-subtle)] px-3 text-sm text-[var(--text-secondary)] hover:text-[var(--color-primary)]">
            补齐历史数据
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

function RepairMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function ValidityBadge({ level }: { level?: string }) {
  const tone = level === "可信" ? "success" : level === "数据不足" ? "danger" : "warning";
  return <Badge tone={tone}>{level || "数据不足"}</Badge>;
}

function StatusBadge({ row }: { row: StrategyPerformanceRow }) {
  const label = statusLabel(row.suggestedStrategyAction);
  const tone = label === "有效" ? "success" : label === "暂停" ? "danger" : label === "仅复盘" ? "muted" : "warning";
  return <Badge tone={tone}>{label}</Badge>;
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <div className="text-[var(--text-tertiary)]">{label}</div>
      <div className="mt-1 font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function Th({ children, align = "left" }: { children: ReactNode; align?: "left" | "right" }) {
  return <th className={cn("px-3 py-2 font-medium", align === "right" && "text-right")}>{children}</th>;
}

function Td({ children, align = "left", colSpan, className = "" }: { children: ReactNode; align?: "left" | "right"; colSpan?: number; className?: string }) {
  return <td colSpan={colSpan} className={cn("px-3 py-3 align-middle", align === "right" && "text-right", className)}>{children}</td>;
}

function statusLabel(action: string) {
  if (action === "保持启用") return "有效";
  if (action === "降权观察") return "降权";
  if (action === "仅复盘") return "仅复盘";
  if (action === "暂停") return "暂停";
  return action || "仅复盘";
}

function sortValue(row: StrategyPerformanceRow, key: SortKey) {
  if (key === "return1M") return row.periods["1M"]?.returnRate ?? -999;
  if (key === "return3M") return row.periods["3M"]?.returnRate ?? -999;
  if (key === "return6M") return row.periods["6M"]?.returnRate ?? -999;
  if (key === "return1Y") return row.periods["1Y"]?.returnRate ?? -999;
  if (key === "maxDrawdown") return -(row.periods["1Y"]?.maxDrawdown ?? 999);
  if (key === "sharpeRatio") return row.periods["1Y"]?.sharpeRatio ?? -999;
  if (key === "winRate") return row.periods["1Y"]?.winRate ?? -999;
  return row.periods["1Y"]?.tradeCount ?? 0;
}

function returnTone(value?: number | null) {
  if (value === undefined || value === null) return "text-[var(--text-tertiary)]";
  if (value > 0) return "text-[var(--color-danger)]";
  if (value < 0) return "text-[var(--color-success)]";
  return "text-[var(--text-secondary)]";
}

function formatOptionalPercent(value?: number | null) {
  if (value === undefined || value === null) return "--";
  return formatPercent(value);
}

function formatOptionalNumber(value?: number | null) {
  if (value === undefined || value === null || Number.isNaN(value)) return "--";
  return value.toFixed(2);
}
