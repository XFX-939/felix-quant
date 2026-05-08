"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { BarChart3, Download, Eye, Info, Loader2, Play, RotateCcw } from "lucide-react";

import { BacktestChart } from "@/components/charts/BacktestChart";
import { RiskBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { BacktestDefaults, BacktestResult, BacktestValidity, BatchBacktestDetail, Strategy, StrategyPerformanceSummary, TaskRun } from "@/lib/types";

type PeriodKey = "1M" | "3M" | "6M" | "1Y" | "2Y" | "CUSTOM";
type BacktestMode = "single" | "batch";

type BacktestForm = {
  strategy_id: string;
  stock_pool: string;
  start_date: string;
  end_date: string;
  initial_cash: string;
  fee_rate: string;
  slippage: string;
  stop_loss_pct: string;
  take_profit_pct: string;
  position_cap_pct: string;
  max_positions: string;
  max_holding_days: string;
};

const PERIOD_OPTIONS: Array<{ key: PeriodKey; label: string; hint: string }> = [
  { key: "1M", label: "近一月", hint: "约 20 个交易日" },
  { key: "3M", label: "近三月", hint: "约 60 个交易日" },
  { key: "6M", label: "近半年", hint: "约 120 个交易日" },
  { key: "1Y", label: "近一年", hint: "约 250 个交易日" },
  { key: "2Y", label: "近两年", hint: "约 500 个交易日" },
  { key: "CUSTOM", label: "自定义", hint: "手动选择区间" }
];

const STOCK_POOL_OPTIONS = [
  { value: "all_market", label: "全市场股票", hint: "用于策略有效性验证，耗时较长" },
  { value: "today_candidates", label: "当前候选池", hint: "用今日策略信号股票池验证" },
  { value: "main_watchlist", label: "主观察清单", hint: "只验证主观察标的" },
  { value: "hotspot_watchlist", label: "热点观察清单", hint: "适合 RiskOn / Recovery 复盘" },
  { value: "manual_watchlist", label: "手工关注股票", hint: "待接入自选池" },
  { value: "sample", label: "示例股票池", hint: "仅用于功能验证" }
];

const DEFAULT_FORM: BacktestForm = {
  strategy_id: "",
  stock_pool: "today_candidates",
  start_date: "",
  end_date: "",
  initial_cash: "100000",
  fee_rate: "0.0003",
  slippage: "0.001",
  stop_loss_pct: "8",
  take_profit_pct: "12",
  position_cap_pct: "20",
  max_positions: "3",
  max_holding_days: "5"
};

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [defaults, setDefaults] = useState<BacktestDefaults | null>(null);
  const [current, setCurrent] = useState<BacktestResult | null>(null);
  const [batchDetail, setBatchDetail] = useState<BatchBacktestDetail | null>(null);
  const [activeTask, setActiveTask] = useState<TaskRun | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<PeriodKey>("1Y");
  const [mode, setMode] = useState<BacktestMode>(() => {
    if (typeof window === "undefined") return "single";
    return new URLSearchParams(window.location.search).get("mode") === "batch" ? "batch" : "single";
  });
  const [form, setForm] = useState<BacktestForm>(DEFAULT_FORM);
  const [selectedStrategyIds, setSelectedStrategyIds] = useState<number[]>([]);
  const [strategySearch, setStrategySearch] = useState("");
  const [performanceSummary, setPerformanceSummary] = useState<StrategyPerformanceSummary | null>(null);
  const [batchTasks, setBatchTasks] = useState<TaskRun[]>([]);
  const [tradeFilter, setTradeFilter] = useState({ keyword: "", action: "all", risk: "all" });

  const load = useCallback(async () => {
    const [strategyData, resultData, defaultData, taskData, latestData, performanceData] = await Promise.all([
      api.strategies(),
      api.backtestHistory(),
      api.backtestDefaults(),
      api.tasks({ limit: 20 }),
      api.backtestLatest().catch(() => null),
      api.strategyPerformanceSummary().catch(() => null)
    ]);
    const runningTask = taskData.find((task) => (task.task_type.startsWith("run_backtest") || task.task_type === "batch_backtest") && ["pending", "running"].includes(task.status));
    const preferredStrategy = strategyData.find((strategy) => strategy.name === "均线趋势策略") || strategyData[0];
    const defaultBatchIds = strategyData.filter((strategy) => strategy.enabled).map((strategy) => strategy.id);
    setStrategies(strategyData);
    setResults(resultData);
    setDefaults(defaultData);
    setPerformanceSummary(performanceData);
    setBatchTasks(taskData.filter((task) => task.task_type === "batch_backtest"));
    setActiveTask((currentTask) => currentTask || runningTask || null);
    setCurrent((currentValue) => currentValue || latestData || null);
    setSelectedStrategyIds((currentValue) => (currentValue.length ? currentValue : defaultBatchIds));
    setForm((currentValue) => ({
      ...currentValue,
      strategy_id: currentValue.strategy_id || String(preferredStrategy?.id || ""),
      stock_pool: currentValue.stock_pool || defaultData.defaultStockPool || "sample",
      start_date: currentValue.start_date || defaultData.periods["1Y"],
      end_date: currentValue.end_date || defaultData.latestTradeDate
    }));
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "回测数据加载失败"));
  }, [load]);

  useEffect(() => {
    if (!activeTask || !["pending", "running"].includes(activeTask.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.task(activeTask.id);
        setActiveTask(next);
        if (next.task_type === "batch_backtest") {
          api.backtestBatch(next.id).then(setBatchDetail).catch(() => undefined);
        }
        if (!["pending", "running"].includes(next.status)) {
          setRunning(false);
          const [refreshed, latest, performanceData, refreshedTasks] = await Promise.all([
            api.backtestHistory(),
            api.backtestLatest().catch(() => null),
            api.strategyPerformanceSummary().catch(() => null),
            api.tasks({ limit: 20 })
          ]);
          setResults(refreshed);
          setCurrent(latest || null);
          setPerformanceSummary(performanceData);
          setBatchTasks(refreshedTasks.filter((task) => task.task_type === "batch_backtest"));
          if (next.task_type === "batch_backtest") {
            const detail = await api.backtestBatch(next.id).catch(() => null);
            setBatchDetail(detail);
          }
        }
      } catch (err) {
        setRunning(false);
        setError(err instanceof Error ? err.message : "回测任务状态刷新失败");
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [activeTask]);

  const selectedStrategy = strategies.find((strategy) => String(strategy.id) === form.strategy_id);
  const selectedStockPool = STOCK_POOL_OPTIONS.find((item) => item.value === form.stock_pool);
  const taskRunning = Boolean(activeTask && ["pending", "running"].includes(activeTask.status));
  const dateError = Boolean(form.start_date && form.end_date && form.start_date > form.end_date);
  const isExamplePool = form.stock_pool === "sample";
  const selectedStrategies = useMemo(() => strategies.filter((strategy) => selectedStrategyIds.includes(strategy.id)), [selectedStrategyIds, strategies]);
  const strategyPerformanceByName = useMemo(() => {
    return new Map((performanceSummary?.strategies || []).map((row) => [row.strategyName, row]));
  }, [performanceSummary]);
  const filteredStrategies = useMemo(() => {
    const keyword = strategySearch.trim().toLowerCase();
    return strategies.filter((strategy) => !keyword || strategy.name.toLowerCase().includes(keyword) || strategy.type.toLowerCase().includes(keyword));
  }, [strategies, strategySearch]);
  const selectedHasReviewOnly = selectedStrategies.some((strategy) => {
    const row = strategyPerformanceByName.get(strategy.name);
    return !strategy.enabled || row?.suggestedStrategyAction === "仅复盘" || row?.suggestedStrategyAction === "暂停" || row?.latestBacktestValidity === "样本不足";
  });
  const filteredTrades = useMemo(() => filterTrades(current, tradeFilter), [current, tradeFilter]);

  function applyPeriod(nextPeriod: PeriodKey) {
    setPeriod(nextPeriod);
    if (nextPeriod === "CUSTOM" || !defaults) return;
    setForm((currentValue) => ({
      ...currentValue,
      start_date: defaults.periods[nextPeriod],
      end_date: defaults.latestTradeDate
    }));
  }

  function updateForm<K extends keyof BacktestForm>(key: K, value: BacktestForm[K]) {
    setForm((currentValue) => ({ ...currentValue, [key]: value }));
  }

  function updateDate(key: "start_date" | "end_date", value: string) {
    setPeriod("CUSTOM");
    updateForm(key, value);
  }

  async function runBacktest() {
    if (dateError || taskRunning || running) return;
    if (mode === "batch") {
      await runBatchBacktest();
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const result = await api.runBacktestTask({
        strategy_id: Number(form.strategy_id),
        stock_pool: form.stock_pool,
        start_date: form.start_date || undefined,
        end_date: form.end_date || undefined,
        initial_cash: Number(form.initial_cash),
        fee_rate: Number(form.fee_rate),
        slippage: Number(form.slippage),
        stop_loss: Number(form.stop_loss_pct) / 100,
        take_profit: Number(form.take_profit_pct) / 100,
        position_cap: Number(form.position_cap_pct) / 100,
        max_positions: Number(form.max_positions),
        max_holding_days: Number(form.max_holding_days)
      });
      setActiveTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "回测执行失败");
    } finally {
      setRunning(false);
    }
  }

  async function runBatchBacktest() {
    if (dateError || taskRunning || running) return;
    if (!selectedStrategies.length) {
      setError("请至少选择一个策略。");
      return;
    }
    setRunning(true);
    setError(null);
    setBatchDetail(null);
    try {
      const result = await api.runBatchBacktestTask({
        strategyNames: selectedStrategies.map((strategy) => strategy.name),
        stockPool: form.stock_pool,
        startDate: form.start_date || undefined,
        endDate: form.end_date || undefined,
        initialCapital: Number(form.initial_cash),
        transactionCost: Number(form.fee_rate),
        slippage: Number(form.slippage),
        stopLoss: Number(form.stop_loss_pct) / 100,
        takeProfit: Number(form.take_profit_pct) / 100,
        maxPositionPerStock: Number(form.position_cap_pct) / 100,
        maxHoldingCount: Number(form.max_positions),
        maxHoldingDays: Number(form.max_holding_days),
        force: false
      });
      setActiveTask(result.task);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量回测执行失败");
    } finally {
      setRunning(false);
    }
  }

  function toggleBatchStrategy(strategyId: number) {
    setSelectedStrategyIds((currentValue) => (currentValue.includes(strategyId) ? currentValue.filter((id) => id !== strategyId) : [...currentValue, strategyId]));
  }

  function selectAllStrategies() {
    setSelectedStrategyIds(strategies.map((strategy) => strategy.id));
  }

  function selectEnabledStrategies() {
    setSelectedStrategyIds(strategies.filter((strategy) => strategy.enabled).map((strategy) => strategy.id));
  }

  function selectEffectiveStrategies() {
    setSelectedStrategyIds(
      strategies
        .filter((strategy) => {
          const row = strategyPerformanceByName.get(strategy.name);
          return strategy.enabled && row?.suggestedStrategyAction !== "仅复盘" && row?.suggestedStrategyAction !== "暂停" && row?.latestBacktestValidity !== "样本不足";
        })
        .map((strategy) => strategy.id)
    );
  }

  function excludeReviewPausedStrategies() {
    setSelectedStrategyIds((currentValue) =>
      currentValue.filter((id) => {
        const strategy = strategies.find((item) => item.id === id);
        const row = strategy ? strategyPerformanceByName.get(strategy.name) : null;
        return Boolean(strategy?.enabled && row?.suggestedStrategyAction !== "仅复盘" && row?.suggestedStrategyAction !== "暂停");
      })
    );
  }

  function reuseBacktest(result: BacktestResult) {
    setCurrent(result);
    setPeriod("CUSTOM");
    setForm({
      strategy_id: String(result.strategy_id),
      stock_pool: normalizeStockPool(result.result_json.stock_pool),
      start_date: result.start_date,
      end_date: result.end_date,
      initial_cash: String(result.result_json.initial_cash || 100000),
      fee_rate: String(result.result_json.fee_rate || 0.0003),
      slippage: String(result.result_json.slippage || 0.001),
      stop_loss_pct: String(Math.round((result.result_json.stop_loss || 0.08) * 10000) / 100),
      take_profit_pct: String(Math.round((result.result_json.take_profit || 0.12) * 10000) / 100),
      position_cap_pct: String(Math.round((result.result_json.position_cap || 0.2) * 10000) / 100),
      max_positions: String(result.result_json.max_positions || 3),
      max_holding_days: String(result.result_json.max_holding_days || 5)
    });
  }

  async function viewBacktest(result: BacktestResult) {
    setError(null);
    try {
      setCurrent(await api.backtestDetail(result.id));
    } catch (err) {
      setCurrent(result);
      setError(err instanceof Error ? err.message : "回测详情加载失败");
    }
  }

  async function deleteHistory(result: BacktestResult) {
    const confirmed = window.confirm("确认删除这条历史回测记录？删除后不会影响策略配置。");
    if (!confirmed) return;
    setError(null);
    try {
      await api.deleteBacktest(result.id);
      const [refreshed, latest] = await Promise.all([api.backtestHistory(), api.backtestLatest().catch(() => null)]);
      setResults(refreshed);
      if (current?.id === result.id) {
        setCurrent(latest);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "历史回测删除失败");
    }
  }

  async function viewBatchTask(taskId: number) {
    setError(null);
    try {
      setMode("batch");
      setBatchDetail(await api.backtestBatch(taskId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量回测详情加载失败");
    }
  }

  function exportTrades() {
    if (!current) return;
    const rows = [
      ["日期", "股票", "动作", "评分", "收益", "权重", "风险等级", "持仓天数", "退出原因", "理由"],
      ...filteredTrades.map((trade) => [
        trade.date,
        trade.stock_code,
        trade.action,
        String(trade.score ?? ""),
        String(trade.return ?? ""),
        String(trade.weight ?? ""),
        trade.risk_level,
        String(trade.holding_days ?? ""),
        trade.exit_reason || "",
        trade.reason || ""
      ])
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, "\"\"")}"`).join(",")).join("\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `backtest-trades-${current.id}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="text-sm font-medium text-[var(--text-tertiary)]">Backtest Validation</div>
        <h1 className="text-2xl font-semibold">回测验证</h1>
        <p className="mt-1 text-sm text-muted-foreground">验证策略在不同时间区间、市场状态和风控参数下的历史表现。回测结果仅用于研究和复盘，不构成投资建议。</p>
      </div>

      <div className="inline-flex rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-1">
        {[
          { key: "single", label: "单策略回测" },
          { key: "batch", label: "多策略批量回测" }
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            className={`h-8 rounded px-3 text-sm transition-colors ${mode === item.key ? "bg-[var(--color-primary)] text-white" : "text-[var(--text-secondary)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]"}`}
            onClick={() => setMode(item.key as BacktestMode)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}
      {isExamplePool && (
        <div className="rounded-md border border-[rgba(245,166,35,0.5)] bg-[var(--color-warning-soft)] p-3 text-sm text-[var(--color-warning)]">
          当前使用示例股票池，仅用于功能验证，不作为策略有效性依据。
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>回测参数</CardTitle>
          <p className="text-xs text-[var(--text-tertiary)]">桌面端分组填写，移动端自动单列。百分比参数在界面以百分数展示，提交给后端时转换为小数。</p>
        </CardHeader>
        <CardContent className="space-y-5">
          <section className="space-y-3">
            <SectionTitle title="基础设置" />
            <div className="flex flex-wrap gap-2">
              {PERIOD_OPTIONS.map((item) => (
                <button
                  key={item.key}
                  className={`h-8 rounded-md border px-3 text-xs transition-colors ${period === item.key ? "border-[var(--color-primary)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]"}`}
                  title={item.hint}
                  type="button"
                  onClick={() => applyPeriod(item.key)}
                >
                  {item.label}
                </button>
              ))}
              {!defaults?.usesTradingCalendar && <span className="text-xs text-[var(--text-tertiary)]">暂未接入完整交易日历，快捷周期使用本地行情日期估算。</span>}
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {mode === "single" ? (
                <Field label="回测策略" help="选择要验证的策略规则">
                  <Select value={form.strategy_id} onChange={(event) => updateForm("strategy_id", event.target.value)}>
                    {strategies.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ) : (
                <div className="md:col-span-2 xl:col-span-4">
                  <StrategyMultiSelect
                    strategies={filteredStrategies}
                    selectedIds={selectedStrategyIds}
                    performanceSummary={performanceSummary}
                    search={strategySearch}
                    onSearch={setStrategySearch}
                    onToggle={toggleBatchStrategy}
                    onAll={selectAllStrategies}
                    onEnabled={selectEnabledStrategies}
                    onEffective={selectEffectiveStrategies}
                    onExcludeReviewPaused={excludeReviewPausedStrategies}
                  />
                </div>
              )}
              <Field label="回测股票池" help={selectedStockPool?.hint}>
                <Select value={form.stock_pool} onChange={(event) => updateForm("stock_pool", event.target.value)}>
                  {STOCK_POOL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="开始日期" help="由快捷周期自动设置，也可手动改为自定义">
                <Input type="date" value={form.start_date} onChange={(event) => updateDate("start_date", event.target.value)} />
              </Field>
              <Field label="结束日期" help="默认取最新交易日">
                <Input type="date" value={form.end_date} onChange={(event) => updateDate("end_date", event.target.value)} />
              </Field>
            </div>
            {dateError && <div className="text-xs text-[var(--color-danger)]">开始日期不能晚于结束日期。</div>}
            {mode === "batch" && selectedHasReviewOnly && (
              <div className="rounded-md border border-[rgba(245,166,35,0.45)] bg-[var(--color-warning-soft)] p-2 text-xs text-[var(--color-warning)]">
                已选择的部分策略当前为样本不足、仅复盘或暂停状态，仍可用于验证，但不适合作为主回测对象。
              </div>
            )}
          </section>

          <section className="space-y-3">
            <SectionTitle title="资金与交易成本" />
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="初始资金" unit="元" help="模拟组合初始资金">
                <Input inputMode="decimal" value={form.initial_cash} onChange={(event) => updateForm("initial_cash", event.target.value)} />
              </Field>
              <Field label="手续费率" help="单边交易手续费率">
                <Input inputMode="decimal" value={form.fee_rate} onChange={(event) => updateForm("fee_rate", event.target.value)} />
              </Field>
              <Field label="滑点率" help="模拟成交价格偏差">
                <Input inputMode="decimal" value={form.slippage} onChange={(event) => updateForm("slippage", event.target.value)} />
              </Field>
            </div>
          </section>

          <section className="space-y-3">
            <SectionTitle title="风控参数" />
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
              <Field label="止损比例" unit="%" help="单次模拟观察的风险控制线">
                <Input inputMode="decimal" value={form.stop_loss_pct} onChange={(event) => updateForm("stop_loss_pct", event.target.value)} />
              </Field>
              <Field label="止盈比例" unit="%" help="阶段收益观察目标">
                <Input inputMode="decimal" value={form.take_profit_pct} onChange={(event) => updateForm("take_profit_pct", event.target.value)} />
              </Field>
              <Field label="单票最大仓位" unit="%" help="单只股票在组合中的最大权重">
                <Input inputMode="decimal" value={form.position_cap_pct} onChange={(event) => updateForm("position_cap_pct", event.target.value)} />
              </Field>
              <Field label="最大持仓数量" help="每个调仓日最多纳入的标的数">
                <Input inputMode="numeric" value={form.max_positions} onChange={(event) => updateForm("max_positions", event.target.value)} />
              </Field>
              <Field label="最大持仓天数" help="短线策略模拟观察周期">
                <Input inputMode="numeric" value={form.max_holding_days} onChange={(event) => updateForm("max_holding_days", event.target.value)} />
              </Field>
            </div>
          </section>

          {selectedStrategy?.name.includes("短线龙头候选") && (
            <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
              DragonLeaderStrategy 独立回测：次日开盘价观察，最大 5 个交易日，-6% 风险控制线，+12% 阶段收益观察目标，单票仓位不超过 10%，高风险标的只记录观察结果。
            </div>
          )}

          <Button className="w-full" onClick={runBacktest} disabled={running || taskRunning || dateError || (mode === "single" ? !form.strategy_id : selectedStrategyIds.length === 0)}>
            {running || taskRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {running || taskRunning ? "回测运行中" : mode === "batch" ? `一键执行批量回测（${selectedStrategyIds.length} 个策略）` : "异步执行回测"}
          </Button>
        </CardContent>
      </Card>

      {activeTask && <TaskProgressCard task={activeTask} />}
      {batchDetail && <BatchBacktestPanel detail={batchDetail} onViewResult={async (id) => setCurrent(await api.backtestDetail(id))} />}

      {current && (
        <>
          <BacktestValidityCard result={current} />
          <ResultMetrics result={current} />

          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <Card>
              <CardHeader>
                <CardTitle>走势图</CardTitle>
                <p className="text-xs text-[var(--text-tertiary)]">包含策略净值曲线、回撤曲线与每日收益柱状图。图表为空时请先执行回测。</p>
              </CardHeader>
              <CardContent>
                <BacktestChart result={current} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>回测摘要</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <SummaryLine label="策略" value={current.strategy_name} />
                <SummaryLine label="股票池" value={stockPoolLabel(current.result_json.stock_pool)} />
                <SummaryLine label="区间" value={`${current.start_date} 至 ${current.end_date}`} />
                <SummaryLine label="初始资金" value={formatCurrency(current.result_json.initial_cash)} />
                <SummaryLine label="股票数量" value={`${current.result_json.stock_count}`} />
                <SummaryLine label="手续费率" value={formatPercent(current.result_json.fee_rate, 2)} />
                <SummaryLine label="滑点率" value={formatPercent(current.result_json.slippage || 0, 2)} />
                <SummaryLine label="止损比例" value={formatPercent(current.result_json.stop_loss)} />
                {current.result_json.take_profit !== undefined && <SummaryLine label="止盈比例" value={formatPercent(current.result_json.take_profit)} />}
                <SummaryLine label="单票最大仓位" value={formatPercent(current.result_json.position_cap)} />
                {current.result_json.max_positions !== undefined && <SummaryLine label="最大持仓数量" value={`${current.result_json.max_positions}`} />}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>交易明细</CardTitle>
                <p className="mt-1 text-xs text-[var(--text-tertiary)]">表格只显示前 80 个字，完整理由可悬停查看。</p>
              </div>
              <Button variant="outline" onClick={exportTrades} disabled={!filteredTrades.length}>
                <Download className="h-4 w-4" />
                导出 CSV
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-3 md:grid-cols-3">
                <Input placeholder="按股票、理由搜索" value={tradeFilter.keyword} onChange={(event) => setTradeFilter((value) => ({ ...value, keyword: event.target.value }))} />
                <Select value={tradeFilter.action} onChange={(event) => setTradeFilter((value) => ({ ...value, action: event.target.value }))}>
                  <option value="all">全部动作</option>
                  {uniqueActions(current).map((action) => (
                    <option key={action} value={action}>
                      {action}
                    </option>
                  ))}
                </Select>
                <Select value={tradeFilter.risk} onChange={(event) => setTradeFilter((value) => ({ ...value, risk: event.target.value }))}>
                  <option value="all">全部风险等级</option>
                  <option value="low">低风险</option>
                  <option value="medium">中风险</option>
                  <option value="high">高风险</option>
                </Select>
              </div>
              <div className="max-h-[420px] overflow-auto scrollbar-thin">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>股票</TableHead>
                      <TableHead>动作</TableHead>
                      <TableHead>评分</TableHead>
                      <TableHead>收益</TableHead>
                      <TableHead>权重</TableHead>
                      <TableHead>风险</TableHead>
                      <TableHead>持仓天数</TableHead>
                      <TableHead>退出原因</TableHead>
                      <TableHead>理由</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredTrades.slice(0, 500).map((trade, index) => (
                      <TableRow key={`${trade.date}-${trade.stock_code}-${index}`}>
                        <TableCell>{trade.date}</TableCell>
                        <TableCell className="font-mono">{trade.stock_code}</TableCell>
                        <TableCell>{trade.action}</TableCell>
                        <TableCell>{typeof trade.score === "number" ? trade.score.toFixed(1) : "-"}</TableCell>
                        <TableCell className={`finance-number ${trade.return >= 0 ? "market-up" : "market-down"}`}>{formatPercent(trade.return, 2)}</TableCell>
                        <TableCell>{formatPercent(trade.weight)}</TableCell>
                        <TableCell>
                          <RiskBadge level={trade.risk_level} />
                        </TableCell>
                        <TableCell>{trade.holding_days ?? "-"}</TableCell>
                        <TableCell className="text-[var(--text-secondary)]">{trade.exit_reason || "-"}</TableCell>
                        <TableCell className="max-w-[320px] text-[var(--text-secondary)]" title={trade.reason}>
                          {truncateText(trade.reason, 80)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>历史回测</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>执行时间</TableHead>
                  <TableHead>策略</TableHead>
                  <TableHead>股票池</TableHead>
                  <TableHead>回测区间</TableHead>
                  <TableHead>总收益</TableHead>
                  <TableHead>最大回撤</TableHead>
                  <TableHead>胜率</TableHead>
                  <TableHead>交易次数</TableHead>
                  <TableHead>可信度</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((result) => (
                  <TableRow key={result.id}>
                    <TableCell>{result.created_at}</TableCell>
                    <TableCell>{result.strategy_name}</TableCell>
                    <TableCell>{stockPoolLabel(result.result_json.stock_pool)}</TableCell>
                    <TableCell>{`${result.start_date} 至 ${result.end_date}`}</TableCell>
                    <TableCell className={result.total_return >= 0 ? "market-up" : "market-down"}>{formatPercent(result.total_return)}</TableCell>
                    <TableCell className="text-[var(--color-danger)]">{formatPercent(result.max_drawdown)}</TableCell>
                    <TableCell>{result.trade_count < 30 ? <span className="text-[var(--text-tertiary)]">样本不足</span> : formatPercent(result.win_rate)}</TableCell>
                    <TableCell>{result.trade_count}</TableCell>
                    <TableCell>
                      <BacktestValidityBadge validity={result.validity} tradeCount={result.trade_count} />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => viewBacktest(result)}>
                          <Eye className="h-3.5 w-3.5" />
                          查看详情
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => reuseBacktest(result)}>
                          <RotateCcw className="h-3.5 w-3.5" />
                          复用参数
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => deleteHistory(result)}>
                          删除记录
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>历史批量回测</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">批量记录来自 task_runs，可查看整体结果并复用到策略收益看板。</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>执行时间</TableHead>
                  <TableHead>任务类型</TableHead>
                  <TableHead>策略数量</TableHead>
                  <TableHead>回测区间</TableHead>
                  <TableHead>股票池</TableHead>
                  <TableHead>成功</TableHead>
                  <TableHead>失败</TableHead>
                  <TableHead>总体可信度</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batchTasks.map((task) => {
                  const summary = task.summary_json as BatchBacktestDetail["summary"];
                  return (
                    <TableRow key={task.id}>
                      <TableCell>{task.created_at}</TableCell>
                      <TableCell>批量</TableCell>
                      <TableCell>{summary.strategyCount ?? task.child_task_count ?? "-"}</TableCell>
                      <TableCell>{summary.startDate && summary.endDate ? `${summary.startDate} 至 ${summary.endDate}` : task.trade_date || "-"}</TableCell>
                      <TableCell>{stockPoolLabel(summary.stockPool)}</TableCell>
                      <TableCell>{summary.successCount ?? task.success_count}</TableCell>
                      <TableCell>{summary.failedCount ?? task.failed_count}</TableCell>
                      <TableCell><Badge tone={validityTone(summary.validity?.validityLevel || "")}>{summary.validity?.validityLevel || "-"}</Badge></TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" onClick={() => viewBatchTask(task.id)}>
                          查看详情
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
                {!batchTasks.length && (
                  <TableRow>
                    <TableCell colSpan={9} className="py-8 text-center text-[var(--text-tertiary)]">暂无批量回测记录。</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <div className="text-sm font-semibold text-[var(--text-primary)]">{title}</div>;
}

function StrategyMultiSelect({
  strategies,
  selectedIds,
  performanceSummary,
  search,
  onSearch,
  onToggle,
  onAll,
  onEnabled,
  onEffective,
  onExcludeReviewPaused
}: {
  strategies: Strategy[];
  selectedIds: number[];
  performanceSummary: StrategyPerformanceSummary | null;
  search: string;
  onSearch: (value: string) => void;
  onToggle: (strategyId: number) => void;
  onAll: () => void;
  onEnabled: () => void;
  onEffective: () => void;
  onExcludeReviewPaused: () => void;
}) {
  const rows = performanceSummary?.strategies || [];
  const byName = new Map(rows.map((row) => [row.strategyName, row]));
  return (
    <div className="space-y-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-xs font-medium text-[var(--text-secondary)]">策略选择</div>
          <div className="mt-1 text-[11px] text-[var(--text-tertiary)]">已选择 {selectedIds.length} 个策略，参数会统一应用到每个策略。</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={onAll}>全选</Button>
          <Button type="button" size="sm" variant="outline" onClick={onEnabled}>只选启用策略</Button>
          <Button type="button" size="sm" variant="outline" onClick={onEffective}>只选有效策略</Button>
          <Button type="button" size="sm" variant="secondary" onClick={onExcludeReviewPaused}>排除仅复盘/暂停</Button>
        </div>
      </div>
      <Input placeholder="搜索策略名称或类型" value={search} onChange={(event) => onSearch(event.target.value)} />
      <div className="max-h-72 overflow-auto rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)]">
        {strategies.map((strategy) => {
          const perf = byName.get(strategy.name);
          const p1 = perf?.periods["1M"];
          const p3 = perf?.periods["3M"];
          const weak = !strategy.enabled || perf?.suggestedStrategyAction === "仅复盘" || perf?.suggestedStrategyAction === "暂停" || perf?.latestBacktestValidity === "样本不足";
          return (
            <label key={strategy.id} className="grid cursor-pointer gap-2 border-b border-[var(--border-subtle)] p-3 text-sm last:border-b-0 md:grid-cols-[auto_1.2fr_0.8fr_0.8fr_0.8fr_0.8fr] md:items-center">
              <input type="checkbox" checked={selectedIds.includes(strategy.id)} onChange={() => onToggle(strategy.id)} />
              <span>
                <span className="font-semibold">{strategy.name}</span>
                <span className="ml-2 text-xs text-[var(--text-tertiary)]">{strategy.type}</span>
              </span>
              <Badge tone={strategy.enabled ? "success" : "muted"}>{strategy.enabled ? perf?.suggestedStrategyAction || "有效" : "暂停"}</Badge>
              <span className={returnClass(p1?.returnRate)}>{p1?.returnRate == null ? "--" : formatPercent(p1.returnRate)}</span>
              <span className={returnClass(p3?.returnRate)}>{p3?.returnRate == null ? "--" : formatPercent(p3.returnRate)}</span>
              <span className="text-xs text-[var(--text-tertiary)]">{weak ? "需谨慎" : perf?.latestBacktestValidity || "待验证"}</span>
            </label>
          );
        })}
        {!strategies.length && <div className="p-4 text-sm text-[var(--text-tertiary)]">未找到策略。</div>}
      </div>
    </div>
  );
}

function BatchBacktestPanel({ detail, onViewResult }: { detail: BatchBacktestDetail; onViewResult: (id: number) => void | Promise<void> }) {
  const rows = [...(detail.resultTable || [])].sort((a, b) => {
    const validityRank = validitySortRank(b.validityLevel) - validitySortRank(a.validityLevel);
    if (validityRank !== 0) return validityRank;
    const tradeRank = Number((b.tradeCount || 0) >= 30) - Number((a.tradeCount || 0) >= 30);
    if (tradeRank !== 0) return tradeRank;
    return Number(b.totalReturn || -Infinity) - Number(a.totalReturn || -Infinity);
  });
  return (
    <Card>
      <CardHeader className="flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>批量回测结果汇总</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">批量回测用于横向比较策略表现，不代表未来收益。</p>
        </div>
        {detail.validity && <Badge tone={validityTone(detail.validity.validityLevel)}>{detail.validity.validityLevel}</Badge>}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Fact label="总策略数" value={`${detail.summary.strategyCount ?? detail.task.child_task_count ?? rows.length}`} />
          <Fact label="成功策略" value={`${detail.summary.successCount ?? detail.task.success_count}`} tone="success" />
          <Fact label="失败策略" value={`${detail.summary.failedCount ?? detail.task.failed_count}`} tone={detail.task.failed_count ? "warning" : "success"} />
          <Fact label="总体可信度" value={detail.validity?.validityLevel || "-"} />
        </div>
        {detail.validity?.warnings?.map((warning) => (
          <div key={warning} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 text-xs text-[var(--text-secondary)]">{warning}</div>
        ))}
        <BatchNavMiniChart rows={rows} />
        <div className="overflow-x-auto scrollbar-thin">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>策略名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>总收益</TableHead>
                <TableHead>年化收益</TableHead>
                <TableHead>最大回撤</TableHead>
                <TableHead>夏普</TableHead>
                <TableHead>胜率</TableHead>
                <TableHead>交易次数</TableHead>
                <TableHead>可信度</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${row.strategyName}-${row.backtestResultId || row.status}`}>
                  <TableCell className="font-semibold">{row.strategyName}</TableCell>
                  <TableCell><Badge tone={row.status === "success" ? "success" : "danger"}>{row.status === "success" ? "成功" : "失败"}</Badge></TableCell>
                  <TableCell className={returnClass(row.totalReturn)}>{row.totalReturn == null ? "--" : formatPercent(row.totalReturn)}</TableCell>
                  <TableCell className={returnClass(row.annualReturn)}>{row.annualReturn == null ? "--" : formatPercent(row.annualReturn)}</TableCell>
                  <TableCell className="text-[var(--color-danger)]">{row.maxDrawdown == null ? "--" : formatPercent(row.maxDrawdown)}</TableCell>
                  <TableCell>{row.sharpe == null ? "--" : row.sharpe.toFixed(2)}</TableCell>
                  <TableCell>{row.tradeCount && row.tradeCount >= 30 && row.winRate != null ? formatPercent(row.winRate) : "样本不足"}</TableCell>
                  <TableCell>{row.tradeCount ?? "-"}</TableCell>
                  <TableCell><Badge tone={validityTone(row.validityLevel || "")}>{row.validityLevel || row.error || "-"}</Badge></TableCell>
                  <TableCell>
                    <Button size="sm" variant="outline" disabled={!row.backtestResultId} onClick={() => row.backtestResultId && onViewResult(row.backtestResultId)}>
                      查看详情
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function BatchNavMiniChart({ rows }: { rows: BatchBacktestDetail["resultTable"] }) {
  const usable = rows.filter((row) => row.status === "success" && (row.equityCurve?.length || 0) > 1).slice(0, 5);
  if (!usable.length) {
    return (
      <div className="flex h-56 items-center justify-center rounded-md border border-dashed border-[var(--border-subtle)] text-sm text-[var(--text-tertiary)]">
        暂无可绘制的批量净值曲线。
      </div>
    );
  }
  const width = 720;
  const height = 220;
  const colors = ["#ff6a00", "#e64545", "#2f80ed", "#16a34a", "#8b5cf6"];
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <BarChart3 className="h-4 w-4 text-[var(--color-primary)]" />
        多策略净值对比
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-56 w-full">
        <line x1="40" y1="20" x2="40" y2="190" stroke="var(--border-subtle)" />
        <line x1="40" y1="190" x2="700" y2="190" stroke="var(--border-subtle)" />
        {usable.map((row, index) => {
          const points = (row.equityCurve || []).map((point) => Number(point.value || 0));
          const min = Math.min(...points);
          const max = Math.max(...points);
          const span = max - min || 1;
          const path = points
            .map((value, pointIndex) => {
              const x = 40 + (pointIndex / Math.max(1, points.length - 1)) * 660;
              const y = 190 - ((value - min) / span) * 160;
              return `${pointIndex === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
            })
            .join(" ");
          return <path key={row.strategyName} d={path} fill="none" stroke={colors[index % colors.length]} strokeWidth="2" />;
        })}
      </svg>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-[var(--text-tertiary)]">
        {usable.map((row, index) => (
          <span key={row.strategyName} className="inline-flex items-center gap-1">
            <span className="h-2 w-4 rounded-full" style={{ backgroundColor: colors[index % colors.length] }} />
            {row.strategyName}
          </span>
        ))}
      </div>
    </div>
  );
}

function Field({ label, help, unit, children }: { label: string; help?: string; unit?: string; children: ReactNode }) {
  return (
    <label className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-xs font-medium text-[var(--text-secondary)]">
        <span>{label}</span>
        {unit && <span className="text-[var(--text-tertiary)]">{unit}</span>}
      </div>
      {children}
      {help && <div className="text-[11px] leading-4 text-[var(--text-tertiary)]">{help}</div>}
    </label>
  );
}

function TaskProgressCard({ task }: { task: TaskRun }) {
  const running = ["pending", "running"].includes(task.status);
  const summary = task.summary_json as {
    stockCount?: number;
    tradingDays?: number;
    signalCount?: number;
    tradeCount?: number;
    strategyCount?: number;
    successCount?: number;
    failedCount?: number;
  };
  const isBatch = task.task_type === "batch_backtest";
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{isBatch ? "批量回测任务进度" : "回测任务进度"}</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{task.current_stage || "等待任务启动"}</p>
        </div>
        <Badge tone={task.status === "success" ? "success" : task.status === "failed" ? "danger" : "warning"}>{taskStatusLabel(task.status)}</Badge>
      </CardHeader>
      <CardContent>
        <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-card)]">
          <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${Math.max(0, Math.min(100, task.progress_percent || 0))}%` }} />
        </div>
        <div className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] md:grid-cols-4">
          <span>{isBatch ? "策略进度" : "阶段"}：{isBatch ? `${task.completed_child_count ?? task.processed_count}/${task.child_task_count ?? task.total_count}` : `${task.processed_count}/${task.total_count}`}</span>
          <span>{isBatch ? "策略数" : "股票数"}：{isBatch ? summary.strategyCount ?? task.child_task_count ?? "-" : summary.stockCount ?? "-"}</span>
          <span>{isBatch ? "成功策略" : "交易日"}：{isBatch ? summary.successCount ?? task.success_count : summary.tradingDays ?? "-"}</span>
          <span>{isBatch ? "失败策略" : "信号/交易"}：{isBatch ? summary.failedCount ?? task.failed_count : `${summary.signalCount ?? task.success_count}/${summary.tradeCount ?? "-"}`}</span>
          <span>成功：{task.success_count}</span>
          <span>失败：{task.failed_count}</span>
          <span>已耗时：{task.duration_ms ? `${(task.duration_ms / 1000).toFixed(1)}s` : running ? "运行中" : "-"}</span>
          <span>预计剩余：{running ? "按阶段推进" : "已结束"}</span>
        </div>
        {task.status === "success" && <div className="mt-3 text-sm text-[var(--color-success)]">回测完成，历史回测列表已刷新。</div>}
        {task.error_message && <div className="mt-3 rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-2 text-sm text-[var(--color-danger)]">{task.error_message}</div>}
      </CardContent>
    </Card>
  );
}

function BacktestValidityCard({ result }: { result: BacktestResult }) {
  const validity = result.validity;
  const level = validity?.validityLevel || "需谨慎";
  return (
    <Card className={validity?.usableForDecision ? "" : "border-[var(--border-strong)]"}>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>回测可信度</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{validity?.conclusion || "等待回测结果"}</p>
        </div>
        <Badge tone={validityTone(level)}>{level}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          <Fact label="交易次数" value={`${result.trade_count}`} />
          <Fact label="回测交易日数量" value={`${validity?.backtestDays ?? "-"}`} />
          <Fact label="股票池数量" value={`${validity?.stockPoolSize ?? result.result_json.stock_count ?? "-"}`} />
          <Fact label="数据覆盖率" value={formatPercent(validity?.dataCoverageRatio ?? result.result_json.data_coverage_ratio ?? 1)} />
          <Fact label="手续费" value={validity?.feeIncluded ? "已计入" : "未计入"} tone={validity?.feeIncluded ? "success" : "warning"} />
          <Fact label="滑点" value={validity?.slippageIncluded ? "已计入" : "未计入"} tone={validity?.slippageIncluded ? "success" : "warning"} />
          <Fact label="ST/停牌/退市" value={validity?.stSuspensionDelistHandled ? "已处理" : "需谨慎"} tone={validity?.stSuspensionDelistHandled ? "success" : "warning"} />
          <Fact label="幸存者偏差风险" value={validity?.survivorBiasRisk ? "存在" : "较低"} tone={validity?.survivorBiasRisk ? "warning" : "success"} />
          <Fact label="前视偏差风险" value={validity?.forwardBiasRisk ? "存在" : "较低"} tone={validity?.forwardBiasRisk ? "warning" : "success"} />
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="text-sm font-semibold">原因</div>
            {(validity?.validityWarnings || ["暂无额外风险提示。"]).map((warning) => (
              <div key={warning} className="rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-2 text-sm text-[var(--color-warning)]">
                {warning}
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <div className="text-sm font-semibold">如何修复</div>
            {(validity?.repairSuggestions?.length ? validity.repairSuggestions : ["扩大样本、补齐数据并重新运行回测。"]).map((suggestion) => (
              <div key={suggestion} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 text-sm text-[var(--text-secondary)]">
                {suggestion}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultMetrics({ result }: { result: BacktestResult }) {
  const validity = result.validity;
  const sampleInsufficient = result.trade_count < 30;
  const muted = Boolean(validity?.metricsMuted);
  const totalComment = result.trade_count >= 30
    ? `本次回测交易次数为 ${result.trade_count} 次，样本具备一定参考价值；但仍需结合真实股票池、成本和数据偏差验证。`
    : `本次回测交易次数为 ${result.trade_count} 次，样本不足，胜率、夏普和盈亏比不作为策略有效性依据。`;
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-8">
        <Metric label="总收益率" value={formatPercent(result.total_return)} tooltip="回测区间结束权益相对初始资金的累计收益。" tone={result.total_return >= 0 ? "up" : "down"} muted={muted} />
        <Metric label="年化收益率" value={formatPercent(result.annual_return)} tooltip="按回测区间收益外推到年化，短区间会被放大。" muted={muted} note={(validity?.backtestDays || 0) < 250 ? "短区间外推，谨慎参考" : undefined} />
        <Metric label="最大回撤" value={formatPercent(result.max_drawdown)} tooltip="净值从阶段高点回落的最大幅度。" tone="risk" />
        <Metric label="夏普比率" value={sampleInsufficient ? "样本不足" : result.sharpe.toFixed(2)} tooltip="单位波动对应的超额收益估计。" muted={muted || sampleInsufficient} />
        <Metric label="胜率" value={sampleInsufficient ? "样本不足" : formatPercent(result.win_rate)} tooltip="盈利交易数量占总交易数量的比例。" muted={muted || sampleInsufficient} />
        <Metric label="盈亏比" value={sampleInsufficient ? "样本不足" : result.result_json.profit_loss_ratio.toFixed(2)} tooltip="平均盈利交易收益与平均亏损交易损失的比值。" muted={muted || sampleInsufficient} />
        <Metric label="交易次数" value={String(result.trade_count)} tooltip="回测中生成的模拟交易记录数量。" />
        <Metric label="平均持仓" value={result.result_json.avg_holding_days !== undefined ? `${result.result_json.avg_holding_days.toFixed(2)} 天` : "-"} tooltip="完成交易的平均持有天数。" />
      </div>
      <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--text-secondary)]">{totalComment}</div>
    </div>
  );
}

function Metric({ label, value, tooltip, muted = false, tone, note }: { label: string; value: string; tooltip: string; muted?: boolean; tone?: "up" | "down" | "risk"; note?: string }) {
  const color = muted
    ? "text-[var(--text-tertiary)]"
    : tone === "up"
      ? "market-up"
      : tone === "down"
        ? "market-down"
        : tone === "risk"
          ? "text-[var(--color-danger)]"
          : "text-[var(--color-primary)]";
  return (
    <Card title={tooltip}>
      <CardContent className="pt-4">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          {label}
          <Info className="h-3 w-3" />
        </div>
        <div className={`finance-number mt-3 text-lg font-semibold ${color}`}>{value}</div>
        {muted && <div className="mt-1 text-[10px] text-[var(--color-warning)]">可信度不足，不高亮</div>}
        {note && <div className="mt-1 text-[10px] text-[var(--text-tertiary)]">{note}</div>}
      </CardContent>
    </Card>
  );
}

function BacktestValidityBadge({ validity, tradeCount }: { validity?: BacktestValidity; tradeCount: number }) {
  const usable = Boolean(validity?.usableForDecision);
  const label = validity?.validityLevel || (tradeCount < 30 ? "样本不足" : "需谨慎");
  return (
    <div className="flex items-center gap-2">
      <Badge tone={usable ? "success" : validityTone(label)}>{label}</Badge>
      {!usable && <span className="text-[10px] text-[var(--text-tertiary)]">不参与有效性排序</span>}
    </div>
  );
}

function Fact({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "warning" }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className={`mt-2 text-sm font-semibold ${tone === "success" ? "text-[var(--color-success)]" : tone === "warning" ? "text-[var(--color-warning)]" : "text-[var(--text-primary)]"}`}>{value}</div>
    </div>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function filterTrades(result: BacktestResult | null, filter: { keyword: string; action: string; risk: string }) {
  if (!result) return [];
  const keyword = filter.keyword.trim().toLowerCase();
  return result.result_json.trades.filter((trade) => {
    const keywordMatched = !keyword || `${trade.stock_code} ${trade.reason} ${trade.action}`.toLowerCase().includes(keyword);
    const actionMatched = filter.action === "all" || trade.action === filter.action;
    const riskMatched = filter.risk === "all" || trade.risk_level === filter.risk;
    return keywordMatched && actionMatched && riskMatched;
  });
}

function uniqueActions(result: BacktestResult | null) {
  if (!result) return [];
  return Array.from(new Set(result.result_json.trades.map((trade) => trade.action))).filter(Boolean);
}

function truncateText(value: string, maxLength: number) {
  if (!value) return "-";
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function stockPoolLabel(value?: string) {
  const normalized = normalizeStockPool(value || "");
  return STOCK_POOL_OPTIONS.find((option) => option.value === normalized)?.label || value || "-";
}

function normalizeStockPool(value: string) {
  if (value === "all") return "all_market";
  if (value === "current_candidates") return "today_candidates";
  if (value === "today_candidates_only") return "today_candidates";
  return value || "sample";
}

function validityTone(level: string): "success" | "warning" | "danger" | "muted" {
  if (level === "可信") return "success";
  if (level === "需谨慎" || level === "区间不足") return "warning";
  if (level === "样本不足" || level === "数据不足" || level === "仅功能验证") return "danger";
  return "muted";
}

function validitySortRank(level?: string) {
  if (level === "可信") return 5;
  if (level === "需谨慎") return 4;
  if (level === "样本不足") return 3;
  if (level === "数据不足") return 2;
  if (level === "仅功能验证") return 1;
  return 0;
}

function returnClass(value?: number | null) {
  if (value == null) return "text-[var(--text-tertiary)]";
  return value >= 0 ? "market-up" : "market-down";
}

function taskStatusLabel(status: TaskRun["status"]) {
  if (status === "running") return "运行中";
  if (status === "pending") return "排队中";
  if (status === "success") return "成功";
  if (status === "partial_success") return "部分成功";
  if (status === "failed") return "失败";
  return "已取消";
}
