"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock3, Database, Loader2, Play, RefreshCw, RotateCcw, TriangleAlert } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { DataStatusOverview, FailedSyncRecord, FullMarketSyncJob, JobRun, JobsLatestStatus, MarketDataSyncStatus, Stock, TaskRun } from "@/lib/types";

export default function DataCenterPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [job, setJob] = useState<FullMarketSyncJob | null>(null);
  const [marketStatus, setMarketStatus] = useState<MarketDataSyncStatus | null>(null);
  const [jobsLatest, setJobsLatest] = useState<JobsLatestStatus | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatusOverview | null>(null);
  const [jobRuns, setJobRuns] = useState<JobRun[]>([]);
  const [tasks, setTasks] = useState<TaskRun[]>([]);
  const [failedRecords, setFailedRecords] = useState<FailedSyncRecord[]>([]);
  const [limit, setLimit] = useState("800");
  const [loadingStocks, setLoadingStocks] = useState(true);
  const [starting, setStarting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStocks = useCallback(async () => {
    setLoadingStocks(true);
    try {
      const data = await api.stocks();
      setStocks(data);
    } finally {
      setLoadingStocks(false);
    }
  }, []);

  const loadJob = useCallback(async (jobId?: string | null) => {
    const status = await api.fullMarketSyncStatus(jobId);
    setJob(status);
    return status;
  }, []);

  const loadTasks = useCallback(async () => {
    const [data, jobs, status] = await Promise.all([
      api.tasks({ limit: 10 }),
      api.jobsLatest().catch(() => null),
      api.dataStatus().catch(() => null)
    ]);
    setTasks(data);
    setJobsLatest(jobs);
    setDataStatus(status);
    if (jobs?.runningRuns?.length) {
      setJobRuns(jobs.runningRuns);
    }
    api.jobRuns({ limit: 20 })
      .then((result) => setJobRuns(result.runs))
      .catch(() => undefined);
    return data;
  }, []);

  const loadFailedRecords = useCallback(async () => {
    const data = await api.failedSyncRecords({ task_type: "sync_stock_daily", limit: 12 });
    setFailedRecords(data);
    return data;
  }, []);

  useEffect(() => {
    loadStocks().catch((err) => setError(err instanceof Error ? err.message : "股票池加载失败"));
    loadJob().catch(() => undefined);
    loadTasks().catch(() => undefined);
    api.marketDataSyncStatus().then(setMarketStatus).catch(() => undefined);
    loadFailedRecords().catch(() => undefined);
  }, [loadFailedRecords, loadJob, loadStocks, loadTasks]);

  useEffect(() => {
    if (!job?.jobId || !["pending", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await loadJob(job.jobId);
        if (next.status === "completed") {
          await loadStocks();
          window.dispatchEvent(new Event("quant:data-updated"));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "同步状态刷新失败");
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [job?.jobId, job?.status, loadJob, loadStocks]);

  useEffect(() => {
    if (!tasks.some((task) => ["pending", "running"].includes(task.status))) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await loadTasks();
        if (!next.some((task) => ["pending", "running"].includes(task.status))) {
          await Promise.all([loadFailedRecords(), loadStocks(), api.marketDataSyncStatus().then(setMarketStatus).catch(() => undefined)]);
          window.dispatchEvent(new Event("quant:data-updated"));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "任务状态刷新失败");
      }
    }, 2500);
    return () => window.clearInterval(timer);
  }, [loadFailedRecords, loadStocks, loadTasks, tasks]);

  const industryCount = useMemo(() => {
    const map = new Map<string, number>();
    stocks.forEach((stock) => map.set(stock.industry || "未分类", (map.get(stock.industry || "未分类") || 0) + 1));
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [stocks]);

  async function startSync() {
    setStarting(true);
    setError(null);
    try {
      const numericLimit = Number(limit);
      const data = await api.startFullMarketSync(Number.isFinite(numericLimit) && numericLimit > 0 ? numericLimit : undefined);
      setJob(data);
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "全市场同步启动失败");
    } finally {
      setStarting(false);
    }
  }

  async function retryFailedStocks() {
    setRetrying(true);
    setError(null);
    try {
      await api.retryFailedStocks({ taskType: "sync_stock_daily" });
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "补抓失败股票任务启动失败");
    } finally {
      setRetrying(false);
    }
  }

  async function refreshAll() {
    setError(null);
    try {
      await Promise.all([loadStocks(), loadJob(job?.jobId), loadTasks(), loadFailedRecords()]);
      await api.marketDataSyncStatus().then(setMarketStatus).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "刷新失败");
    }
  }

  async function runScheduledJob(jobName: string) {
    setStarting(true);
    setError(null);
    try {
      const result = await api.runScheduledJob({ jobName, force: true });
      window.localStorage.setItem("felix-scheduled-job-run-id", String(result.jobRunId));
      window.dispatchEvent(new Event("quant:job-started"));
      await loadTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "后台任务启动失败");
    } finally {
      setStarting(false);
    }
  }

  const running = job?.status === "pending" || job?.status === "running";
  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));
  const latestFailed = job?.result?.failed?.slice(0, 3) ?? [];
  const runningTask = tasks.find((task) => ["pending", "running"].includes(task.status));
  const retryableFailedRecords = failedRecords.filter((record) => ["pending", "retrying", "failed"].includes(record.status));

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-semibold">数据中心</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">行情数据、股票池规模、全市场同步和数据质量的集中管理入口</p>
        </div>
        <Button variant="outline" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4" />
          刷新状态
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">
          {error}
        </div>
      )}

      <Card className="border-[var(--border-strong)]">
        <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>数据健康度总览</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">数据中心是首次初始化和日常维护入口，策略运行前先看这里。</p>
          </div>
          <Badge tone={stocks.length >= 500 && marketStatus?.status === "success" ? "success" : "warning"}>
            {stocks.length >= 500 && marketStatus?.status === "success" ? "可用于策略运行" : "需要维护"}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <Metric label="股票池数量" value={loadingStocks ? "加载中" : `${stocks.length} 只`} hint={stocks.length < 500 ? "建议扩充到 500+ 后再看候选稳定性" : "股票池规模可用"} tone={stocks.length < 500 ? "warning" : "success"} />
          <Metric label="行业覆盖数量" value={`${industryCount.length} 个`} hint={industryCount.slice(0, 2).map(([name, count]) => `${name} ${count}`).join(" / ") || "待同步行业"} />
          <Metric label="最近行情日期" value={marketStatus?.usingCacheDate || marketStatus?.latestTradeDate || "未同步"} hint={marketStatus?.latestUpdatedAt || "等待每日行情入库"} tone={marketStatus?.status === "success" ? "success" : "warning"} />
          <Metric label="最近同步任务" value={jobStatusLabel(job?.status)} hint={job?.message || "无全市场股票池任务"} tone={job?.status === "failed" ? "danger" : job?.status === "completed" ? "success" : "default"} />
          <Metric label="失败股票" value={`${failedRecords.length} 条`} hint={retryableFailedRecords.length ? "可一键补抓失败股票" : "暂无待补抓记录"} tone={retryableFailedRecords.length ? "warning" : "success"} />
          <Metric label="策略可用性" value={stocks.length >= 500 && marketStatus?.status === "success" ? "可运行" : "需补齐"} hint={stocks.length >= 500 ? "等待后台自动任务，必要时手动刷新数据与策略" : "先同步股票池和行情"} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>自动任务状态</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              后台会在 09:00、11:35、15:15 自动刷新；前端默认读取最近一次成功数据库快照。
            </p>
          </div>
          <Badge tone={jobsLatest?.runningRuns?.length ? "warning" : jobsLatest?.latestSuccess ? "success" : "warning"}>
            {jobsLatest?.runningRuns?.length ? "后台运行中" : jobsLatest?.latestSuccess ? "已有成功任务" : "等待初始化"}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            {["morning_prewarm_job", "midday_refresh_job", "after_close_refresh_job"].map((jobName) => {
              const run = jobsLatest?.todayRuns?.[jobName];
              return (
                <div key={jobName} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold">{scheduledJobName(jobName)}</div>
                    <Badge tone={run?.status === "success" || run?.status === "partial_success" ? "success" : run?.status === "failed" || run?.status === "failed_timeout" ? "danger" : run?.status === "running" ? "warning" : "default"}>
                      {jobRunStatusLabel(run?.status)}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs leading-5 text-[var(--text-tertiary)]">
                    <div>数据日：{run?.data_date || jobsLatest?.dataDate || "-"}</div>
                    <div>阶段：{run?.current_stage || "等待后台调度"}</div>
                    <div>时间：{run?.finished_at || run?.started_at || "-"}</div>
                  </div>
                  <Button variant="outline" size="sm" className="mt-3" disabled={starting || Boolean(jobsLatest?.runningRuns?.length)} onClick={() => runScheduledJob(jobName)}>
                    <RefreshCw className="h-4 w-4" />
                    手动执行
                  </Button>
                </div>
              );
            })}
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Metric label="总体状态" value={dataStatusLabel(dataStatus?.overallStatus)} hint={dataStatus?.dataDate ? `数据日期 ${dataStatus.dataDate}` : "尚未生成数据库快照"} tone={dataStatus?.overallStatus === "normal" ? "success" : "warning"} />
            <Metric label="最近快照" value={dataStatus?.latestDashboardSnapshot?.generated_at || "未生成"} hint={dataStatus?.latestDashboardSnapshot?.snapshot_type || "Dashboard 将使用实时兜底"} />
            <Metric label="失败股票" value={`${dataStatus?.failedStockCount ?? failedRecords.length} 条`} hint="单只失败不会阻塞整条流水线" tone={(dataStatus?.failedStockCount ?? 0) > 0 ? "warning" : "success"} />
            <Metric label="调度时区" value={jobsLatest?.timezone || "Asia/Shanghai"} hint={jobsLatest?.schedulerEnabled ? "服务端调度已开启" : "服务端调度未开启"} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="当前股票池" value={loadingStocks ? "加载中" : `${stocks.length} 只`} hint={stocks.length < 100 ? "样本池过小，会反复出现少数蓝筹" : "可用于更广泛策略扫描"} tone={stocks.length < 100 ? "warning" : "success"} />
        <Metric label="行业覆盖" value={`${industryCount.length} 个`} hint={industryCount.slice(0, 3).map(([name, count]) => `${name} ${count}`).join(" / ") || "等待行业映射"} />
        <Metric label="同步状态" value={jobStatusLabel(job?.status)} hint={job?.message || "暂无同步任务"} tone={job?.status === "failed" ? "danger" : job?.status === "completed" ? "success" : "default"} />
        <Metric label="最近同步结果" value={job?.result?.stock_count ? `${job.result.stock_count} 只` : "尚未同步"} hint={job?.result?.price_rows ? `日线 ${job.result.price_rows.toLocaleString("zh-CN")} 行 / 重试 ${job.result.retry_count ?? 0} 次` : "等待全市场同步"} />
      </div>

      {runningTask && (
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3">
            <div>
              <CardTitle>当前异步任务</CardTitle>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">长任务不会阻塞页面，可继续浏览；任务完成后自动刷新数据。</p>
            </div>
            <Badge tone="warning">{taskStatusLabel(runningTask.status)}</Badge>
          </CardHeader>
          <CardContent>
            <TaskProgress task={runningTask} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3">
          <div>
            <CardTitle>全市场股票池同步</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">从 AKShare 东方财富 A 股列表扩充股票池，并批量同步最近日线行情</p>
          </div>
          <Badge tone={stocks.length < 100 ? "warning" : "success"}>{stocks.length < 100 ? "当前仍是小样本" : "股票池已扩展"}</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 xl:grid-cols-[1fr_1.2fr]">
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Database className="h-4 w-4 text-[var(--color-primary)]" aria-hidden />
                同步参数
              </div>
              <p className="mt-2 text-xs leading-5 text-[var(--text-tertiary)]">
                首次建议先同步 500-1000 只测试链路；确认稳定后把限制留空或提高到 5000+。全量逐只日线会比较慢，也可能被上游限流。
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Input value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="同步数量上限，例如 800" inputMode="numeric" />
                <Button onClick={startSync} disabled={starting || running}>
                  {starting || running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {running ? "同步中" : "同步全市场股票池"}
                </Button>
                <Button variant="outline" onClick={retryFailedStocks} disabled={retrying || Boolean(runningTask) || retryableFailedRecords.length === 0}>
                  {retrying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                  补抓失败股票
                </Button>
              </div>
            </div>
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold">同步进度</div>
                <Badge tone={job?.status === "failed" ? "danger" : job?.status === "completed" ? "success" : "default"}>{jobStatusLabel(job?.status)}</Badge>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--bg-card)]">
                <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${progress}%` }} />
              </div>
              <div className="mt-2 flex items-center justify-between text-xs text-[var(--text-tertiary)]">
                <span>{job?.message || "暂无同步任务"}</span>
                <span className="finance-number">{progress}%</span>
              </div>
              {running && (
                <div className="mt-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-xs leading-5 text-[var(--text-secondary)]">
                  全量同步会逐只拉取日线行情，进度会按股票推进。同步期间请暂缓手动刷新数据与策略，避免数据写入和策略运行抢占同一个本地数据库。
                </div>
              )}
            {job?.error && <div className="mt-3 rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-2 text-xs text-[var(--color-danger)]">{job.error}</div>}
              {job?.status === "failed" && (
                <div className="mt-3 rounded-md border border-[rgba(245,166,35,0.45)] bg-[var(--color-warning-soft)] p-2 text-xs leading-5 text-[var(--color-warning)]">
                  如果是 AKShare 限流、网络断开或字段变化：建议先把同步数量降到 500-1000，稍后重试；已有失败记录可点击“补抓失败股票”，日常优先使用增量同步。
                </div>
              )}
              {job?.status === "completed" && (
                <div className="mt-3 flex items-start gap-2 rounded-md border border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] p-2 text-xs leading-5 text-[var(--color-success)]">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  同步完成。后台自动任务会在下一次调度时生成候选；如需立即验证，可点击顶部“手动刷新数据与策略”。
                </div>
              )}
              {latestFailed.length > 0 && (
                <div className="mt-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-xs leading-5 text-[var(--text-tertiary)]">
                  <div className="font-medium text-[var(--text-secondary)]">部分股票同步失败样例</div>
                  {latestFailed.map((item) => (
                    <div key={item.code} className="mt-1">
                      <span className="finance-number text-[var(--color-primary)]">{item.code}</span>：{item.reason}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-3 text-xs leading-5 text-[var(--color-warning)]">
            <div className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                AKShare 是免费聚合源，全市场同步可能受网络、上游字段变化或限流影响。同步失败的股票会记录在任务结果里，成功的股票会先进入本地 SQLite，后续再由策略扫描。
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>最近后台任务日志</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {jobRuns.length === 0 && <div className="text-sm text-[var(--text-tertiary)]">暂无后台任务记录</div>}
            {jobRuns.slice(0, 8).map((run) => (
              <JobRunRow key={run.id} run={run} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>最近异步任务记录</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {tasks.length === 0 && <div className="text-sm text-[var(--text-tertiary)]">暂无异步任务记录</div>}
            {tasks.slice(0, 8).map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div>
              <CardTitle>失败股票补抓队列</CardTitle>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">3 次重试仍失败的股票会进入这里，下次同步优先补抓。</p>
            </div>
            <Badge tone={retryableFailedRecords.length ? "warning" : "success"}>{retryableFailedRecords.length} 待补抓</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {failedRecords.length === 0 && <div className="text-sm text-[var(--text-tertiary)]">暂无失败记录</div>}
            {failedRecords.slice(0, 8).map((record) => (
              <div key={record.id} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="finance-number font-semibold text-[var(--color-primary)]">{record.code}</span>
                    <span className="ml-2 text-[var(--text-secondary)]">{record.name || "-"}</span>
                  </div>
                  <Badge tone={record.status === "recovered" ? "success" : record.status === "failed" ? "danger" : "warning"}>{failedStatusLabel(record.status)}</Badge>
                </div>
                <div className="mt-2 line-clamp-2 leading-5 text-[var(--text-tertiary)]">{record.error_message || "-"}</div>
                <div className="mt-2 flex flex-wrap gap-3 text-[var(--text-tertiary)]">
                  <span>重试 {record.retry_count}/{record.max_retries}</span>
                  <span>{record.updated_at}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>当前股票池样本</CardTitle>
        </CardHeader>
        <CardContent>
          {stocks.length ? (
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              {stocks.slice(0, 16).map((stock) => (
                <div key={stock.code} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
                  <div className="finance-number text-sm font-semibold text-[var(--color-primary)]">{stock.code}</div>
                  <div className="mt-1 text-sm">{stock.name}</div>
                  <div className="mt-2 text-xs text-[var(--text-tertiary)]">{stock.industry || "未分类"} / {stock.market}</div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              variant="data-missing"
              title="股票池为空"
              description="候选池、一键诊股、回测和策略运行都需要先建立本地股票池。"
              reason="首次推荐同步 500-1000 只验证链路稳定，再扩展到 5000+；日常优先增量同步。"
              primaryAction={{ label: "同步全市场股票池", onClick: startSync, disabled: starting || running }}
              secondaryAction={{ label: "查看使用教程", href: "/guide#data-sync" }}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value, hint, tone = "default" }: { label: string; value: string; hint: string; tone?: "default" | "success" | "warning" | "danger" }) {
  const color = tone === "success" ? "text-[var(--color-success)]" : tone === "warning" ? "text-[var(--color-warning)]" : tone === "danger" ? "text-[var(--color-danger)]" : "text-[var(--color-primary)]";
  return (
    <Card>
      <CardContent>
        <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
        <div className={`finance-number mt-2 text-xl font-semibold ${color}`}>{value}</div>
        <div className="mt-2 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">{hint}</div>
      </CardContent>
    </Card>
  );
}

function jobStatusLabel(status?: FullMarketSyncJob["status"]) {
  if (status === "pending") return "排队中";
  if (status === "running") return "同步中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  return "空闲";
}

function TaskProgress({ task }: { task: TaskRun }) {
  const progress = Math.max(0, Math.min(100, task.progress_percent ?? 0));
  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-sm">
        <div className="font-medium">{taskTypeLabel(task.task_type)}</div>
        <div className="finance-number text-[var(--color-primary)]">{progress.toFixed(0)}%</div>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--bg-card)]">
        <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] sm:grid-cols-2 xl:grid-cols-5">
        <span>阶段：{task.current_stage || "-"}</span>
        <span>处理：{task.processed_count}/{task.total_count}</span>
        <span>成功：{task.success_count}</span>
        <span>失败：{task.failed_count}</span>
        <span>重试：{task.retry_count}</span>
      </div>
      {task.error_message && <div className="mt-3 rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-2 text-xs text-[var(--color-danger)]">{task.error_message}</div>}
    </div>
  );
}

function JobRunRow({ run }: { run: JobRun }) {
  const progress = Math.max(0, Math.min(100, run.progress ?? 0));
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Clock3 className="h-4 w-4 text-[var(--color-primary)]" />
          {scheduledJobName(run.job_name)}
        </div>
        <Badge tone={run.status === "success" ? "success" : run.status === "failed" || run.status === "failed_timeout" ? "danger" : run.status === "partial_success" ? "warning" : "default"}>
          {jobRunStatusLabel(run.status)}
        </Badge>
      </div>
      <div className="mt-2 text-xs text-[var(--text-tertiary)]">{run.current_stage || "-"}</div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-[var(--text-secondary)]">
        <span>进度 {progress.toFixed(0)}%</span>
        <span>失败 {run.failed_count}</span>
        <span>耗时 {formatDuration(run.duration_ms || 0)}</span>
      </div>
      {run.error_message && <div className="mt-3 rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-2 text-xs text-[var(--color-danger)]">{run.error_message}</div>}
    </div>
  );
}

function TaskRow({ task }: { task: TaskRun }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Clock3 className="h-4 w-4 text-[var(--color-primary)]" />
          {taskTypeLabel(task.task_type)}
        </div>
        <Badge tone={task.status === "success" ? "success" : task.status === "failed" ? "danger" : task.status === "partial_success" ? "warning" : "default"}>{taskStatusLabel(task.status)}</Badge>
      </div>
      <div className="mt-2 text-xs text-[var(--text-tertiary)]">{task.current_stage || "-"}</div>
      <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-[var(--text-secondary)]">
        <span>进度 {Number(task.progress_percent || 0).toFixed(0)}%</span>
        <span>失败 {task.failed_count}</span>
        <span>耗时 {formatDuration(task.duration_ms)}</span>
      </div>
    </div>
  );
}

function scheduledJobName(jobName: string) {
  if (jobName === "morning_prewarm_job") return "09:00 开盘前预热";
  if (jobName === "midday_refresh_job") return "11:35 午盘刷新";
  if (jobName === "after_close_refresh_job") return "15:15 收盘后刷新";
  return jobName;
}

function jobRunStatusLabel(status?: JobRun["status"]) {
  if (status === "running") return "运行中";
  if (status === "pending") return "排队中";
  if (status === "success") return "成功";
  if (status === "partial_success") return "部分成功";
  if (status === "failed") return "失败";
  if (status === "failed_timeout") return "超时失败";
  if (status === "skipped_non_trading_day") return "非交易日跳过";
  if (status === "cancelled") return "已取消";
  return "未运行";
}

function dataStatusLabel(status?: string) {
  if (status === "normal") return "正常";
  if (status === "partial") return "部分失败";
  if (status === "stale") return "过期";
  if (status === "no_data") return "无数据";
  return "待检查";
}

function taskTypeLabel(type: string) {
  if (type === "sync_stock_daily") return "增量日线同步";
  if (type === "retry_failed_stocks") return "失败股票补抓";
  if (type === "run_daily_pipeline") return "每日决策流水线";
  if (type.startsWith("run_backtest")) return "异步回测";
  return type;
}

function taskStatusLabel(status: TaskRun["status"]) {
  if (status === "running") return "运行中";
  if (status === "pending") return "排队中";
  if (status === "success") return "成功";
  if (status === "partial_success") return "部分成功";
  if (status === "failed") return "失败";
  return "已取消";
}

function failedStatusLabel(status: FailedSyncRecord["status"]) {
  if (status === "recovered") return "已恢复";
  if (status === "failed") return "失败";
  if (status === "retrying") return "重试中";
  if (status === "ignored") return "忽略";
  return "待补抓";
}

function formatDuration(ms: number) {
  if (!ms) return "-";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}
