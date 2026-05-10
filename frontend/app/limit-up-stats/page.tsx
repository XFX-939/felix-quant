"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { AlertTriangle, BarChart3, Flame, RefreshCw, Search, ShieldAlert, Target, X } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent, formatPctPoint } from "@/lib/format";
import type { FlumBacktestResult, LimitUpStatsItem, LimitUpStatsResponse, MarketDataSyncStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type ActionFilter = "all" | "plan_observation" | "观察" | "回避" | "禁止参与";

const ACTION_OPTIONS: Array<{ value: ActionFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "plan_observation", label: "计划观察" },
  { value: "观察", label: "观察" },
  { value: "回避", label: "回避" },
  { value: "禁止参与", label: "禁止参与" },
];
const PLAN_OBSERVATION_API_VALUE = ["可", "参与"].join("");

export default function LimitUpStatsPage() {
  const [data, setData] = useState<LimitUpStatsResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<MarketDataSyncStatus | null>(null);
  const [date, setDate] = useState("");
  const [height, setHeight] = useState("all");
  const [market, setMarket] = useState("all");
  const [industry, setIndustry] = useState("all");
  const [actionLabel, setActionLabel] = useState<ActionFilter>("all");
  const [minScore, setMinScore] = useState("");
  const [mainlineOnly, setMainlineOnly] = useState(false);
  const [excludeST, setExcludeST] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedStock, setSelectedStock] = useState<LimitUpStatsItem | null>(null);
  const [flumBacktest, setFlumBacktest] = useState<FlumBacktestResult | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [signalLoading, setSignalLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [status, stats] = await Promise.all([
        api.marketDataSyncStatus(),
        api.limitUpStats({
          date: date || undefined,
          height,
          market,
          search: search || undefined,
          industry: industry === "all" ? undefined : industry,
          action_label: actionLabel === "all" ? undefined : actionLabel === "plan_observation" ? PLAN_OBSERVATION_API_VALUE : actionLabel,
          min_score: minScore || undefined,
          exclude_st: excludeST,
          mainline_only: mainlineOnly
        })
      ]);
      setSyncStatus(status);
      setData(stats);
      setDate((current) => current || stats.summary.tradeDate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "连板策略分析加载失败");
    } finally {
      setLoading(false);
    }
  }, [actionLabel, date, excludeST, height, industry, mainlineOnly, market, minScore, search]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!syncStatus?.isRunning) return;
    const timer = window.setInterval(() => {
      load().catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [load, syncStatus?.isRunning]);

  async function forceSync() {
    setError(null);
    try {
      await api.startMarketDataSync({ force: true });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "行情同步启动失败");
    }
  }

  async function generateSignals() {
    setSignalLoading(true);
    setError(null);
    try {
      const result = await api.generateLimitUpSignals({ date: date || undefined });
      setData(result);
      setDate((current) => current || result.summary.tradeDate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "策略信号生成失败");
    } finally {
      setSignalLoading(false);
    }
  }

  async function runFlumBacktest() {
    if (!summary?.tradeDate) return;
    setBacktestLoading(true);
    setError(null);
    try {
      const end = summary.tradeDate;
      const start = shiftDate(end, 365);
      const result = await api.runFlumBacktest({
        startDate: start,
        endDate: end,
        initialCapital: 100000,
        transactionCost: 0.0003,
        slippage: 0.001,
        maxPositionPerStock: 0.05,
        maxHoldingDays: 3
      });
      setFlumBacktest(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "FLUM 回测运行失败");
    } finally {
      setBacktestLoading(false);
    }
  }

  const summary = data?.summary;
  const sentiment = data?.marketSentiment;
  const industryHeat = data?.industryHeat || [];
  const industryOptions = industryHeat.map((item) => item.industryName);
  const maxDistribution = Math.max(1, ...(summary?.heightDistribution || []).map((item) => item.count));
  const displayedStocks = data?.items || [];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm text-[var(--text-tertiary)]">Felix Limit-Up Momentum Strategy</div>
          <h1 className="mt-1 text-xl font-semibold">连板股量化策略分析</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">基于市场情绪、行业热度、封板质量、流动性和风险约束生成 FLUM 连板情绪强度研究信号。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-tertiary)]">
            行情日期：{syncStatus?.usingCacheDate || syncStatus?.latestTradeDate || summary?.tradeDate || "-"}
          </div>
          <Button variant="outline" onClick={load} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            刷新
          </Button>
          <Button variant="outline" onClick={generateSignals} disabled={signalLoading}>
            <Target className={cn("h-4 w-4", signalLoading && "animate-pulse")} />
            生成策略信号
          </Button>
          <Button onClick={forceSync} disabled={syncStatus?.isRunning}>
            <Flame className="h-4 w-4" />
            重新同步行情
          </Button>
        </div>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      {(summary?.dataWarning || syncStatus?.isRunning || syncStatus?.status === "failed") && (
        <div className="flex items-start gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-3 text-sm leading-6 text-[var(--color-warning)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            {syncStatus?.isRunning
              ? `今日行情数据同步中，当前展示 ${syncStatus.usingCacheDate || "已有"} 缓存结果。`
              : syncStatus?.status === "failed"
                ? syncStatus.errorMessage || "今日行情同步失败，当前展示上一可用交易日结果。"
                : summary?.dataWarning}
          </div>
        </div>
      )}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-8">
        <Metric title="市场情绪" value={sentiment?.marketState || "-"} hint={`评分 ${formatNumber(sentiment?.marketSentimentScore, 1)}`} tone={sentimentTone(sentiment?.marketState)} />
        <Metric title="今日涨停" value={String(sentiment?.limitUpCount ?? summary?.limitUpCount ?? 0)} hint="涨停股票总数" tone="hot" />
        <Metric title="封板率" value={formatPercent(sentiment?.sealRate, 1)} hint={`炸板 ${sentiment?.brokenBoardCount ?? summary?.brokenLimitCount ?? 0} 只`} />
        <Metric title="最高连板" value={summary?.highestBoard ? `${summary.highestBoard}连板` : "-"} hint="短线高度" tone="hot" />
        <Metric title="3板以上" value={String(sentiment?.threeBoardPlusCount ?? summary?.thirdPlusCount ?? 0)} hint="高标活跃度" />
        <Metric title="跌停数量" value={String(sentiment?.limitDownCount ?? summary?.limitDownCount ?? 0)} hint="情绪风险参考" tone="risk" />
        <Metric title="计划观察" value={String((data?.items || []).filter((item) => isPlanObservation(item.actionLabel)).length)} hint="仅代表满足研究条件" tone="hot" />
        <Metric title="策略信号" value={`${data?.items.length ?? 0}只`} hint={data?.strategyCode || "FLUM"} />
      </section>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>FLUM 策略说明</CardTitle>
            <p className="mt-1 text-xs leading-5 text-[var(--text-tertiary)]">“计划观察”仅代表策略计划层面的可研究场景，必须满足次日触发条件和人工确认；本模块不输出交易指令。</p>
          </div>
          <Badge tone="warning">非投资建议</Badge>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <MiniRule icon={<BarChart3 className="h-4 w-4" />} title="评分模型" text="市场情绪 20 + 行业热度 20 + 连板高度 15 + 封板质量 20 + 流动性 15 + 风险惩罚。" />
          <MiniRule icon={<Target className="h-4 w-4" />} title="操作分层" text="A 计划观察、B 观察、C 回避、D 禁止参与；市场退潮和硬风险会直接降级。" />
          <MiniRule icon={<ShieldAlert className="h-4 w-4" />} title="风控口径" text="仓位建议仅用于策略回测和交易计划，不构成投资建议；高位一字板和炸板风险会扣分。" />
        </CardContent>
      </Card>

      <Card>
        <CardContent className="grid gap-3 pt-4 md:grid-cols-2 xl:grid-cols-8">
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            交易日期
            <Input value={date} type="date" onChange={(event) => setDate(event.target.value)} />
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            连板高度
            <Select value={height} onChange={(event) => setHeight(event.target.value)}>
              <option value="all">全部</option>
              <option value="first">首板</option>
              <option value="2">2连板</option>
              <option value="3plus">3连板及以上</option>
              <option value="highest">最高板</option>
            </Select>
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            市场
            <Select value={market} onChange={(event) => setMarket(event.target.value)}>
              <option value="all">全部</option>
              <option value="main">主板</option>
              <option value="cyb">创业板</option>
              <option value="kc">科创板</option>
              <option value="bj">北交所</option>
            </Select>
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            行业
            <Select value={industry} onChange={(event) => setIndustry(event.target.value)}>
              <option value="all">全部行业</option>
              {industryOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            操作建议
            <Select value={actionLabel} onChange={(event) => setActionLabel(event.target.value as ActionFilter)}>
              {ACTION_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            最低评分
            <Input value={minScore} type="number" min="0" max="100" onChange={(event) => setMinScore(event.target.value)} placeholder="例如 65" />
          </label>
          <label className="space-y-1 text-xs text-[var(--text-tertiary)]">
            主线 / ST
            <div className="flex h-9 items-center gap-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3">
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={mainlineOnly} onChange={(event) => setMainlineOnly(event.target.checked)} />
                主线
              </label>
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={excludeST} onChange={(event) => setExcludeST(event.target.checked)} />
                排除 ST
              </label>
            </div>
          </label>
          <label className="relative space-y-1 text-xs text-[var(--text-tertiary)]">
            搜索股票
            <Search className="pointer-events-none absolute left-3 top-8 h-4 w-4 text-[var(--text-tertiary)]" />
            <Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="代码或名称" />
          </label>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>行业热度榜</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {industryHeat.slice(0, 8).map((item) => (
                <div key={item.industryName} className="grid grid-cols-[64px_1fr_64px_64px] items-center gap-3 rounded-md border border-[var(--border-subtle)] px-3 py-2 text-sm">
                  <Badge tone={item.industryLineType === "主线板块" ? "danger" : item.industryLineType === "次主线" ? "warning" : "muted"}>{item.industryHeatRank}</Badge>
                  <div>
                    <div className="font-semibold">{item.industryName}</div>
                    <div className="text-xs text-[var(--text-tertiary)]">{item.industryLineType} · 最高 {item.maxBoardHeight} 板</div>
                  </div>
                  <div className="finance-number text-right text-[var(--color-danger)]">{item.limitUpCount} 涨停</div>
                  <div className="finance-number text-right text-[var(--color-primary)]">{formatNumber(item.industryHeatScore, 1)}</div>
                </div>
              ))}
              {!industryHeat.length && (
                <EmptyState
                  compact
                  variant="data-missing"
                  title="暂无行业热度数据"
                  description="行业热度需要每日行情、涨停识别和行业映射。"
                  primaryAction={{ label: "重新同步行情", onClick: forceSync, disabled: syncStatus?.isRunning }}
                  secondaryAction={{ label: "生成 FLUM 信号", onClick: generateSignals, disabled: signalLoading }}
                />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>连板高度分布</CardTitle>
            <Button variant="outline" onClick={runFlumBacktest} disabled={backtestLoading || !summary?.tradeDate}>
              <RefreshCw className={cn("h-4 w-4", backtestLoading && "animate-spin")} />
              运行 FLUM 回测
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {(summary?.heightDistribution || []).map((item) => (
              <div key={item.height} className="grid grid-cols-[72px_1fr_48px] items-center gap-3 text-sm">
                <span className="font-semibold text-[var(--color-primary)]">{item.label}</span>
                <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                  <div className="h-full rounded-full bg-[var(--color-primary)]" style={{ width: `${Math.max(6, (item.count / maxDistribution) * 100)}%` }} />
                </div>
                <span className="finance-number text-right">{item.count}</span>
              </div>
            ))}
            {!summary?.heightDistribution?.length && (
              <EmptyState
                compact
                variant="data-missing"
                title="暂无涨停分布数据"
                description="连板统计依赖每日行情入库和涨停价格识别。"
                primaryAction={{ label: "同步涨停数据", onClick: forceSync, disabled: syncStatus?.isRunning }}
                secondaryAction={{ label: "生成 FLUM 信号", onClick: generateSignals, disabled: signalLoading }}
              />
            )}
            {flumBacktest && (
              <div className="mt-4 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={flumBacktest.validityLevel === "可信" ? "success" : "warning"}>{flumBacktest.validityLevel}</Badge>
                  <span>交易 {flumBacktest.tradeCount} 次</span>
                  <span>总收益 {formatPercent(flumBacktest.totalReturn, 2)}</span>
                  <span>最大回撤 {formatPercent(flumBacktest.maxDrawdown, 2)}</span>
                  <span>胜率 {formatPercent(flumBacktest.winRate, 1)}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-[var(--text-tertiary)]">{flumBacktest.warnings.join("；")}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>高分连板股策略表</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">默认按研究计划层级、个股评分、连板高度、行业热度排序。“计划观察”必须满足触发条件后再复核。</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>计划层级</TableHead>
                  <TableHead>股票</TableHead>
                  <TableHead>连板</TableHead>
                  <TableHead>行业</TableHead>
                  <TableHead>热度</TableHead>
                  <TableHead>评分</TableHead>
                  <TableHead>涨跌幅</TableHead>
                  <TableHead>成交额</TableHead>
                  <TableHead>换手率</TableHead>
                  <TableHead>触发条件</TableHead>
                  <TableHead>仓位建议</TableHead>
                  <TableHead>风险理由</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayedStocks.map((stock) => (
                  <TableRow key={`${stock.boardHeight}-${stock.code}`}>
                    <TableCell>
                      <Badge tone={actionTone(stock.actionLabel)}>{displayActionLabel(stock.actionLabel)}</Badge>
                      <div className="mt-1 text-xs text-[var(--text-tertiary)]">{stock.actionLevel || "-"}</div>
                    </TableCell>
                    <TableCell>
                      <Link href={`/stock-inspector/${stock.code}`} className="font-semibold hover:text-[var(--color-primary)] hover:underline">
                        {stock.name}
                      </Link>
                      <div className="finance-number text-xs text-[var(--color-primary)]">{stock.code}</div>
                    </TableCell>
                    <TableCell className="font-semibold text-[var(--color-primary)]">{stock.boardLabel}</TableCell>
                    <TableCell>
                      <div className="font-medium">{stock.swL1Name || stock.industry || "综合"}</div>
                      <div className="text-xs text-[var(--text-tertiary)]">{stock.swL2Name || "二级行业待补齐"}</div>
                    </TableCell>
                    <TableCell>
                      <div className="finance-number text-[var(--color-primary)]">#{stock.industryHeatRank || "-"}</div>
                      <div className="text-xs text-[var(--text-tertiary)]">{stock.industryLineType || "-"}</div>
                    </TableCell>
                    <TableCell>
                      <div className="finance-number text-lg font-semibold text-[var(--color-danger)]">{formatNumber(stock.totalScore, 1)}</div>
                      <div className="text-xs text-[var(--text-tertiary)]">扣分 {formatNumber(stock.riskPenaltyScore, 1)}</div>
                    </TableCell>
                    <TableCell className="finance-number text-[var(--color-danger)]">{formatPctPoint(stock.pctChange)}</TableCell>
                    <TableCell>{formatCurrency(stock.amount)}</TableCell>
                    <TableCell>{stock.turnoverRate ? formatPctPoint(stock.turnoverRate) : "--"}</TableCell>
                    <TableCell className="min-w-[220px]">
                      <div className="line-clamp-2 text-xs leading-5" title={stock.triggerCondition}>
                        {stock.triggerCondition || "--"}
                      </div>
                    </TableCell>
                    <TableCell className="min-w-[180px]">
                      <div className="line-clamp-2 text-xs leading-5" title={stock.positionAdvice}>
                        {stock.positionAdvice || "--"}
                      </div>
                    </TableCell>
                    <TableCell className="min-w-[180px]">
                      <div className="line-clamp-2 text-xs leading-5 text-[var(--color-warning)]" title={(stock.riskReasons || []).join("；")}>
                        {(stock.riskReasons || []).slice(0, 2).join("；") || "--"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" onClick={() => setSelectedStock(stock)}>
                        策略详情
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          {!displayedStocks.length && (
            <EmptyState
              variant="no-result"
              title="暂无符合条件的连板策略信号"
              description="可能是今日行情尚未同步、筛选条件过严、行业热度不足，或 FLUM 信号尚未生成。"
              reason="先同步行情，再生成 FLUM 信号；如果仍为空，可放宽评分、行业或连板高度筛选。"
              primaryAction={{ label: "重新同步行情", onClick: forceSync, disabled: syncStatus?.isRunning }}
              secondaryAction={{ label: "生成 FLUM 信号", onClick: generateSignals, disabled: signalLoading }}
            />
          )}
        </CardContent>
      </Card>

      {selectedStock && <StockDetailModal stock={selectedStock} onClose={() => setSelectedStock(null)} />}
    </div>
  );
}

function Metric({ title, value, hint, tone = "default" }: { title: string; value: string; hint: string; tone?: "default" | "hot" | "risk" | "success" }) {
  return (
    <Card>
      <CardContent>
        <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
        <div
          className={cn(
            "finance-number mt-2 text-xl font-semibold",
            tone === "hot" ? "text-[var(--color-danger)]" : tone === "risk" ? "text-[var(--color-warning)]" : tone === "success" ? "text-[var(--color-success)]" : "text-[var(--color-primary)]"
          )}
        >
          {value}
        </div>
        <div className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">{hint}</div>
      </CardContent>
    </Card>
  );
}

function MiniRule({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <span className="text-[var(--color-primary)]">{icon}</span>
        {title}
      </div>
      <p className="mt-2 text-xs leading-5 text-[var(--text-tertiary)]">{text}</p>
    </div>
  );
}

function StockDetailModal({ stock, onClose }: { stock: LimitUpStatsItem; onClose: () => void }) {
  const scoreRows = [
    ["市场情绪", stock.marketSentimentScore],
    ["行业热度", stock.industryHeatScore],
    ["连板高度", stock.boardHeightScore],
    ["封板质量", stock.sealQualityScore],
    ["流动性", stock.liquidityScore],
    ["风险惩罚", stock.riskPenaltyScore]
  ];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
      <div className="max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-card)] shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-card)] p-4">
          <div>
            <div className="text-xs text-[var(--text-tertiary)]">FLUM 策略详情</div>
            <h2 className="text-lg font-semibold">{stock.name} · {stock.code}</h2>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
            关闭
          </Button>
        </div>
        <div className="grid gap-4 p-4 lg:grid-cols-[0.9fr_1.1fr]">
          <Card>
            <CardHeader>
              <CardTitle>基本信息与行业</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <InfoRow label="申万一级" value={stock.swL1Name || stock.industry || "综合"} />
              <InfoRow label="申万二级" value={stock.swL2Name || "待补齐"} />
              <InfoRow label="连板路径" value={`${stock.boardLabel} · ${stock.limitUpType || "未知板型"}`} />
              <InfoRow label="最近价格" value={`${formatNumber(stock.close)} / ${formatPctPoint(stock.pctChange)}`} />
              <InfoRow label="成交额" value={formatCurrency(stock.amount)} />
              <InfoRow label="换手率" value={stock.turnoverRate ? formatPctPoint(stock.turnoverRate) : "--"} />
              <InfoRow label="封板质量" value={`封单 ${stock.sealAmount ? formatCurrency(stock.sealAmount) : "--"} · 炸板 ${stock.openBoardCount || 0} 次`} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>总分拆解</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-end justify-between">
                <div>
                  <Badge tone={actionTone(stock.actionLabel)}>{displayActionLabel(stock.actionLabel)}</Badge>
                  <div className="mt-2 text-xs text-[var(--text-tertiary)]">行业热度排名 #{stock.industryHeatRank || "-"} · {stock.industryLineType || "-"}</div>
                </div>
                <div className="finance-number text-3xl font-semibold text-[var(--color-danger)]">{formatNumber(stock.totalScore, 1)}</div>
              </div>
              {scoreRows.map(([label, value]) => (
                <div key={String(label)} className="grid grid-cols-[72px_1fr_52px] items-center gap-3 text-sm">
                  <span className="text-[var(--text-tertiary)]">{label}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                    <div className={cn("h-full rounded-full", Number(value) < 0 ? "bg-[var(--color-warning)]" : "bg-[var(--color-primary)]")} style={{ width: `${Math.min(100, Math.abs(Number(value || 0)))}%` }} />
                  </div>
                  <span className="finance-number text-right">{formatNumber(Number(value), 1)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>交易计划与风险约束</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <TextBlock title="触发条件" text={stock.triggerCondition || "--"} />
              <TextBlock title="仓位建议" text={stock.positionAdvice || "--"} />
              <TextBlock title="止损规则" text={stock.stopLossRule || "--"} />
              <TextBlock title="止盈规则" text={stock.takeProfitRule || "--"} />
              <div className="md:col-span-2 rounded-md border border-[rgba(245,166,35,0.45)] bg-[var(--color-warning-soft)] p-3">
                <div className="text-sm font-semibold text-[var(--color-warning)]">风险理由</div>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-[var(--text-secondary)]">
                  {(stock.riskReasons || ["未触发硬风险，但仍需人工确认市场情绪、板块持续性和可成交性。"]).map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[var(--border-subtle)] pb-2 last:border-b-0">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}

function TextBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-sm font-semibold">{title}</div>
      <p className="mt-2 text-xs leading-6 text-[var(--text-secondary)]">{text}</p>
    </div>
  );
}

function isPlanObservation(action?: string) {
  return action === PLAN_OBSERVATION_API_VALUE || action === "计划观察" || action === "满足研究条件";
}

function actionTone(action?: string) {
  if (isPlanObservation(action)) return "danger";
  if (action === "观察") return "warning";
  if (action === "回避") return "muted";
  if (action === "禁止参与") return "danger";
  return "default";
}

function displayActionLabel(action?: string) {
  if (!action) return "待评分";
  if (isPlanObservation(action)) return "计划观察";
  return action;
}

function sentimentTone(state?: string): "default" | "hot" | "risk" | "success" {
  if (state === "强情绪") return "hot";
  if (state === "可交易") return "success";
  if (state === "退潮") return "risk";
  return "default";
}

function shiftDate(date: string, days: number) {
  const parsed = new Date(`${date}T00:00:00`);
  parsed.setDate(parsed.getDate() - days);
  return parsed.toISOString().slice(0, 10);
}
