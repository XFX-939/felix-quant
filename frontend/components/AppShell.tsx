"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Database,
  DatabaseZap,
  FileText,
  FlaskConical,
  Gauge,
  Flame,
  Home,
  LineChart,
  ListChecks,
  Menu,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  TestTube2,
  UserCircle2
} from "lucide-react";

import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { JobRun, JobsLatestStatus, MarketDataSyncStatus, TaskRun } from "@/lib/types";
import { cn } from "@/lib/utils";

const navGroups = [
  {
    title: "每日决策",
    items: [
      { href: "/", label: "Dashboard", icon: Home },
      { href: "/candidates", label: "候选池", icon: ListChecks },
      { href: "/stock-inspector", label: "一键诊股", icon: Search },
      { href: "/limit-up-stats", label: "连板统计", icon: Flame }
    ]
  },
  {
    title: "策略验证",
    items: [
      { href: "/strategies", label: "策略", icon: Gauge },
      { href: "/strategy-performance", label: "策略收益", icon: BarChart3 },
      { href: "/backtest", label: "回测", icon: TestTube2 },
      { href: "/alpha-lab", label: "AlphaLab", icon: FlaskConical }
    ]
  },
  {
    title: "风险复盘",
    items: [
      { href: "/risk", label: "风控", icon: ShieldAlert },
      { href: "/reviews", label: "复盘", icon: ClipboardList },
      { href: "/reports", label: "研究报告", icon: FileText }
    ]
  },
  {
    title: "系统管理",
    items: [
      { href: "/data-center", label: "数据中心", icon: Database },
      { href: "/guide", label: "使用教程", icon: BookOpen },
      { href: "/settings", label: "设置", icon: Settings }
    ]
  }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[var(--bg-page)] text-[var(--text-primary)]">
      <Sidebar pathname={pathname} />
      <div className="lg:pl-64">
        <Header />
        <MobileNav pathname={pathname} />
        <main className="mx-auto w-full max-w-[1540px] px-3 py-4 md:px-5 lg:px-6">{children}</main>
        <footer className="border-t border-[var(--border-subtle)] px-4 py-4 text-xs text-[var(--text-tertiary)] lg:hidden">
          本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。
        </footer>
      </div>
    </div>
  );
}

function Header() {
  const [lastUpdate, setLastUpdate] = useState<string>("-");
  const [startingPipeline, setStartingPipeline] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);
  const [pipelineTask, setPipelineTask] = useState<TaskRun | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [pipelineVisible, setPipelineVisible] = useState(false);
  const [marketSyncStatus, setMarketSyncStatus] = useState<MarketDataSyncStatus | null>(null);
  const [marketSyncVisible, setMarketSyncVisible] = useState(false);
  const [marketSyncStarting, setMarketSyncStarting] = useState(false);
  const [jobsLatest, setJobsLatest] = useState<JobsLatestStatus | null>(null);
  const [manualJobRun, setManualJobRun] = useState<JobRun | null>(null);
  const [manualJobVisible, setManualJobVisible] = useState(false);
  const [manualJobError, setManualJobError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const [summary, jobs] = await Promise.all([api.dashboard(), api.jobsLatest().catch(() => null)]);
      setLastUpdate(summary.snapshot_meta?.generatedAt || jobs?.latestSuccess?.finished_at || summary.last_run_time || summary.last_data_date || "-");
      setJobsLatest(jobs);
    } catch {
      setLastUpdate("后端未连接");
    }
  }, []);

  useEffect(() => {
    loadStatus();
    window.addEventListener("quant:data-updated", loadStatus);
    return () => window.removeEventListener("quant:data-updated", loadStatus);
  }, [loadStatus]);

  const loadMarketSyncStatus = useCallback(async () => {
    const status = await api.marketDataSyncStatus();
    setMarketSyncStatus(status);
    setMarketSyncVisible(status.isRunning || status.status === "failed");
    return status;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function inspectMarketSync() {
      try {
        const status = await loadMarketSyncStatus();
        if (cancelled) return;
        if (status.needsSync) {
          setMarketSyncVisible(true);
        }
      } catch (err) {
        if (!cancelled) {
          setMarketSyncStatus((current) => ({
            tradeDate: current?.tradeDate || "-",
            latestTradeDate: current?.latestTradeDate || null,
            latestUpdatedAt: current?.latestUpdatedAt || null,
            status: "failed",
            progress: current?.progress || 0,
            totalCount: current?.totalCount || 0,
            successCount: current?.successCount || 0,
            failedCount: current?.failedCount || 0,
            errorMessage: err instanceof Error ? err.message : "每日行情同步状态检查失败",
            taskId: current?.taskId || null,
            needsSync: false,
            isRunning: false,
            usingCacheDate: current?.usingCacheDate || null
          }));
          setMarketSyncVisible(true);
        }
      } finally {
        if (!cancelled) setMarketSyncStarting(false);
      }
    }
    inspectMarketSync();
    window.addEventListener("quant:data-updated", loadMarketSyncStatus);
    return () => {
      cancelled = true;
      window.removeEventListener("quant:data-updated", loadMarketSyncStatus);
    };
  }, [loadMarketSyncStatus]);

  useEffect(() => {
    if (!marketSyncStatus?.isRunning && marketSyncStatus?.status !== "running" && marketSyncStatus?.status !== "pending") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await loadMarketSyncStatus();
        if (!next.isRunning && next.status !== "running" && next.status !== "pending") {
          if (next.status === "success") {
            window.dispatchEvent(new Event("quant:data-updated"));
            window.setTimeout(() => setMarketSyncVisible(false), 2500);
          }
        }
      } catch {
        // Keep the last visible status; the next interval can recover.
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [loadMarketSyncStatus, marketSyncStatus?.isRunning, marketSyncStatus?.status]);

  async function retryMarketSync() {
    setMarketSyncStarting(true);
    setMarketSyncVisible(true);
    try {
      const started = await api.startMarketDataSync({ force: true });
      setMarketSyncStatus(applyMarketTaskStatus(started.status, started.task));
    } catch (err) {
      setMarketSyncStatus((current) => ({
        tradeDate: current?.tradeDate || "-",
        latestTradeDate: current?.latestTradeDate || null,
        latestUpdatedAt: current?.latestUpdatedAt || null,
        status: "failed",
        progress: current?.progress || 0,
        totalCount: current?.totalCount || 0,
        successCount: current?.successCount || 0,
        failedCount: current?.failedCount || 0,
        errorMessage: err instanceof Error ? err.message : "重新同步失败",
        taskId: current?.taskId || null,
        needsSync: false,
        isRunning: false,
        usingCacheDate: current?.usingCacheDate || null
      }));
    } finally {
      setMarketSyncStarting(false);
    }
  }

  useEffect(() => {
    const savedTaskId = window.localStorage.getItem("felix-daily-pipeline-task-id");
    if (savedTaskId) {
      api
        .task(Number(savedTaskId))
        .then((task) => {
          if (task.task_type === "run_daily_pipeline" && ["pending", "running"].includes(task.status)) {
            setPipelineTask(task);
            setPipelineVisible(true);
          } else {
            window.localStorage.removeItem("felix-daily-pipeline-task-id");
          }
        })
        .catch(() => window.localStorage.removeItem("felix-daily-pipeline-task-id"));
      return;
    }
    api
      .tasks({ limit: 20 })
      .then((tasks) => {
        const runningDailyTask = tasks.find((task) => task.task_type === "run_daily_pipeline" && ["pending", "running"].includes(task.status));
        if (runningDailyTask) {
          setPipelineTask(runningDailyTask);
          setPipelineVisible(true);
          window.localStorage.setItem("felix-daily-pipeline-task-id", String(runningDailyTask.id));
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const savedJobId = window.localStorage.getItem("felix-scheduled-job-run-id");
    if (!savedJobId) return;
    api
      .jobRun(Number(savedJobId))
      .then((run) => {
        if (["pending", "running"].includes(run.status)) {
          setManualJobRun(run);
          setManualJobVisible(true);
        } else {
          window.localStorage.removeItem("felix-scheduled-job-run-id");
        }
      })
      .catch(() => window.localStorage.removeItem("felix-scheduled-job-run-id"));
  }, []);

  useEffect(() => {
    async function attachStartedJob() {
      const savedJobId = window.localStorage.getItem("felix-scheduled-job-run-id");
      if (!savedJobId) return;
      try {
        const run = await api.jobRun(Number(savedJobId));
        if (["pending", "running"].includes(run.status)) {
          setManualJobRun(run);
          setManualJobVisible(true);
          setManualJobError(null);
          setUpdateMessage(`已接入后台自动任务：${jobDisplayName(run.job_name)} #${run.id}`);
        }
      } catch {
        window.localStorage.removeItem("felix-scheduled-job-run-id");
      }
    }
    window.addEventListener("quant:job-started", attachStartedJob);
    return () => window.removeEventListener("quant:job-started", attachStartedJob);
  }, []);

  useEffect(() => {
    if (!manualJobRun || !["pending", "running"].includes(manualJobRun.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.jobRun(manualJobRun.id);
        setManualJobRun(next);
        setManualJobError(next.error_message || null);
        setUpdateMessage(`${jobDisplayName(next.job_name)} ${getJobProgress(next).toFixed(0)}%：${formatJobStage(next)}`);
        if (!["pending", "running"].includes(next.status)) {
          window.localStorage.removeItem("felix-scheduled-job-run-id");
          await loadStatus();
          if (next.status === "success" || next.status === "partial_success") {
            window.dispatchEvent(new Event("quant:data-updated"));
            setUpdateMessage(next.status === "partial_success" ? "后台任务完成，存在部分数据失败" : "后台任务完成，数据库快照已刷新");
            window.setTimeout(() => setManualJobVisible(false), 3000);
          }
        }
      } catch (err) {
        setManualJobError(err instanceof Error ? err.message : "后台任务状态刷新失败");
        setUpdateMessage("后台任务状态刷新失败");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loadStatus, manualJobRun]);

  useEffect(() => {
    async function attachStartedPipeline() {
      const savedTaskId = window.localStorage.getItem("felix-daily-pipeline-task-id");
      if (!savedTaskId) return;
      try {
        const task = await api.task(Number(savedTaskId));
        if (task.task_type === "run_daily_pipeline" && ["pending", "running"].includes(task.status)) {
          setPipelineTask(task);
          setPipelineVisible(true);
          setPipelineError(null);
          setUpdateMessage(`已接入正在运行的每日流水线：任务 ${task.id}`);
        }
      } catch {
        window.localStorage.removeItem("felix-daily-pipeline-task-id");
      }
    }
    window.addEventListener("quant:pipeline-started", attachStartedPipeline);
    return () => window.removeEventListener("quant:pipeline-started", attachStartedPipeline);
  }, []);

  useEffect(() => {
    if (!pipelineTask || !["pending", "running"].includes(pipelineTask.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.task(pipelineTask.id);
        setPipelineTask(next);
        setPipelineError(next.error_message);
        setUpdateMessage(`每日流水线 ${formatTaskProgress(next)}：${formatPipelineStage(next)}`);
        if (!["pending", "running"].includes(next.status)) {
          window.localStorage.removeItem("felix-daily-pipeline-task-id");
          if (next.status === "success" || next.status === "partial_success") {
            await loadStatus();
            window.dispatchEvent(new Event("quant:data-updated"));
            setUpdateMessage(next.status === "partial_success" ? "策略运行完成，存在部分数据补抓失败" : "策略运行完成，数据已刷新");
            window.setTimeout(() => setPipelineVisible(false), 3000);
          }
        }
      } catch (err) {
        setPipelineError(err instanceof Error ? err.message : "任务状态刷新失败");
        setUpdateMessage("任务状态刷新失败");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loadStatus, pipelineTask]);

  async function handleUpdate() {
    if (startingPipeline || isJobRunning(manualJobRun) || isTaskRunning(pipelineTask)) return;
    setStartingPipeline(true);
    setUpdateMessage(null);
    setManualJobError(null);
    setManualJobVisible(true);
    setManualJobRun(null);
    try {
      const result = await api.runScheduledJob({ jobName: "after_close_refresh_job", force: true });
      setManualJobRun(result.jobRun);
      setManualJobVisible(true);
      window.localStorage.setItem("felix-scheduled-job-run-id", String(result.jobRunId));
      setUpdateMessage(result.jobRun.reused ? `已接入正在运行的后台任务：${result.jobRunId}` : `收盘刷新任务已启动：${result.jobRunId}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "更新失败";
      setManualJobError(message);
      setUpdateMessage(message);
    } finally {
      setStartingPipeline(false);
    }
  }

  const manualJobRunning = startingPipeline || isJobRunning(manualJobRun);
  const pipelineRunning = manualJobRunning || isTaskRunning(pipelineTask);
  const manualJobProgress = manualJobRun ? getJobProgress(manualJobRun) : startingPipeline ? 0 : 0;
  const pipelineButtonText = manualJobRunning ? `刷新中 ${manualJobProgress.toFixed(0)}%` : manualJobRun?.status === "failed" || manualJobError ? "重新运行" : "手动刷新数据与策略";

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--border-subtle)] bg-[var(--bg-header)]/95 backdrop-blur">
      <div className="flex min-h-16 items-center justify-between gap-3 px-3 py-2 md:px-5 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Image
            src="/brand/felix-quant-icon-64.png"
            alt="Felix量化"
            width={36}
            height={36}
            className="h-9 w-9 rounded-md border border-[var(--border-strong)] bg-white object-cover shadow-[0_0_18px_rgba(255,106,0,0.18)] lg:hidden"
          />
          <div className="hidden min-w-0 lg:block">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold tracking-wide">Felix量化</span>
              <span className="rounded-sm border border-[var(--border-subtle)] px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-[var(--text-tertiary)]">
                Quant Research Terminal
              </span>
            </div>
            <div className="mt-1 flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
              <LineChart className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden />
              <span>本地研究环境</span>
            </div>
          </div>
          <div className="min-w-0 lg:hidden">
            <div className="text-sm font-semibold">Felix量化</div>
            <div className="text-xs text-[var(--text-tertiary)]">Quant Research Terminal</div>
          </div>
        </div>

        <div className="flex min-w-0 items-center justify-end gap-2">
          {updateMessage && (
            <div className="hidden max-w-72 truncate rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-secondary)] xl:block">
              {updateMessage}
            </div>
          )}
          <div className="hidden items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-tertiary)] md:flex">
            <RefreshCw className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden />
            <span className="hidden xl:inline">最近自动刷新</span>
            <span className="finance-number max-w-44 truncate text-[var(--text-secondary)]">{lastUpdate}</span>
          </div>
          <div className="hidden items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-tertiary)] xl:flex">
            <DatabaseZap className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden />
            <span>后台任务</span>
            <span className={cn("rounded-sm px-1.5 py-0.5", jobsLatest?.runningRuns?.length ? "bg-[var(--color-warning-soft)] text-[var(--color-warning)]" : jobsLatest?.latestFailure && !jobsLatest.latestSuccess ? "bg-[var(--color-danger-soft)] text-[var(--color-danger)]" : "bg-[var(--color-success-soft)] text-[var(--color-success)]")}>
              {jobsLatest?.runningRuns?.length ? "运行中" : jobsLatest?.latestSuccess ? "已生成快照" : "待初始化"}
            </span>
          </div>
          <div className="hidden items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-tertiary)] lg:flex">
            <Flame className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden />
            <span className="hidden xl:inline">行情</span>
            <span className="finance-number max-w-36 truncate text-[var(--text-secondary)]">{marketSyncStatus?.usingCacheDate || marketSyncStatus?.latestTradeDate || marketSyncStatus?.tradeDate || "-"}</span>
            <span className={cn("rounded-sm px-1.5 py-0.5", marketSyncStatus?.isRunning ? "bg-[var(--color-warning-soft)] text-[var(--color-warning)]" : marketSyncStatus?.status === "success" ? "bg-[var(--color-success-soft)] text-[var(--color-success)]" : marketSyncStatus?.status === "failed" ? "bg-[var(--color-danger-soft)] text-[var(--color-danger)]" : "bg-[var(--bg-elevated)] text-[var(--text-tertiary)]")}>
              {marketStatusLabel(marketSyncStatus, marketSyncStarting)}
            </span>
          </div>
          <Button variant="ghost" size="icon" title="刷新状态" aria-label="刷新状态" onClick={loadStatus}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <ThemeToggle />
          <Button variant="ghost" size="icon" title="提醒" aria-label="提醒">
            <Bell className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" title="用户" aria-label="用户">
            <UserCircle2 className="h-4 w-4" />
          </Button>
          <Button onClick={handleUpdate} disabled={pipelineRunning} className="hidden sm:inline-flex">
            {pipelineRunning ? <RefreshCw className="h-4 w-4 animate-spin" /> : <DatabaseZap className="h-4 w-4" />}
            {pipelineButtonText}
          </Button>
        </div>
      </div>
      {manualJobVisible && (
        <JobRunProgress
          run={manualJobRun}
          starting={startingPipeline}
          error={manualJobError}
          onRetry={handleUpdate}
          onDismiss={() => setManualJobVisible(false)}
        />
      )}
      {pipelineVisible && (
        <DailyPipelineProgress
          task={pipelineTask}
          starting={startingPipeline}
          error={pipelineError}
          onRetry={handleUpdate}
          onDismiss={() => setPipelineVisible(false)}
        />
      )}
      {marketSyncVisible && (
        <MarketDataSyncProgress
          status={marketSyncStatus}
          starting={marketSyncStarting}
          onRetry={retryMarketSync}
          onDismiss={() => setMarketSyncVisible(false)}
        />
      )}
    </header>
  );
}

function JobRunProgress({
  run,
  starting,
  error,
  onRetry,
  onDismiss
}: {
  run: JobRun | null;
  starting: boolean;
  error: string | null;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const progress = run ? getJobProgress(run) : starting ? 0 : 0;
  const running = starting || isJobRunning(run);
  const failed = Boolean(error && !running) || run?.status === "failed" || run?.status === "failed_timeout" || run?.status === "cancelled";
  const completed = run?.status === "success" || run?.status === "partial_success";
  const stageText = failed ? error || run?.error_message || "后台任务执行失败" : run ? formatJobStage(run) : "任务创建";
  const barClassName = failed ? "bg-[var(--color-danger)]" : completed ? "bg-[var(--color-success)]" : "bg-[var(--color-primary)]";

  return (
    <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-header)] px-3 pb-3 md:px-5 lg:px-6">
      <div className="mx-auto w-full max-w-[1540px] rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 shadow-[0_10px_30px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold">
                {failed ? (
                  <AlertTriangle className="h-4 w-4 text-[var(--color-danger)]" />
                ) : completed ? (
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
                ) : (
                  <RefreshCw className={cn("h-4 w-4 text-[var(--color-primary)]", running && "animate-spin")} />
                )}
                {run ? jobDisplayName(run.job_name) : "后台刷新任务"}
              </div>
              <Badge tone={failed ? "danger" : completed ? "success" : "warning"}>{jobStatusLabel(run?.status, starting)}</Badge>
              {run?.id && <span className="finance-number text-xs text-[var(--text-tertiary)]">任务 {run.id}</span>}
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[var(--text-secondary)]">
              <span className="line-clamp-1">{stageText}</span>
              <span className={cn("finance-number shrink-0 font-semibold", failed ? "text-[var(--color-danger)]" : completed ? "text-[var(--color-success)]" : "text-[var(--color-primary)]")}>{progress.toFixed(0)}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
              <div className={cn("h-full rounded-full transition-all duration-500", barClassName)} style={{ width: `${progress}%` }} />
            </div>
            <div className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] sm:grid-cols-2 xl:grid-cols-5">
              <span>数据日：{run?.data_date || "-"}</span>
              <span>成功：{run?.success_count ?? 0}</span>
              <span>失败：{run?.failed_count ?? 0}</span>
              <span>重试：{run?.retry_count ?? 0}</span>
              <span className="flex items-center gap-1">
                <Clock3 className="h-3.5 w-3.5" />
                {run?.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : running ? "运行中" : "-"}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {failed && (
              <Button size="sm" onClick={onRetry}>
                <RefreshCw className="h-4 w-4" />
                手动重跑
              </Button>
            )}
            {!running && (
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                收起
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MarketDataSyncProgress({
  status,
  starting,
  onRetry,
  onDismiss
}: {
  status: MarketDataSyncStatus | null;
  starting: boolean;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const running = starting || Boolean(status?.isRunning || status?.status === "running" || status?.status === "pending");
  const failed = status?.status === "failed";
  const completed = status?.status === "success";
  const progress = completed ? 100 : Math.max(0, Math.min(running ? 99 : 100, Number(status?.progress || 0)));
  const barClassName = failed ? "bg-[var(--color-danger)]" : completed ? "bg-[var(--color-success)]" : "bg-[var(--color-primary)]";
  const message = failed
    ? status?.errorMessage || "全市场行情同步失败"
    : completed
      ? "全市场行情同步完成，本地行情缓存已刷新"
      : `正在同步全市场行情数据 ${progress.toFixed(0)}%`;

  return (
    <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-header)] px-3 pb-3 md:px-5 lg:px-6">
      <div className="mx-auto w-full max-w-[1540px] rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold">
                {failed ? <AlertTriangle className="h-4 w-4 text-[var(--color-danger)]" /> : completed ? <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" /> : <RefreshCw className="h-4 w-4 animate-spin text-[var(--color-primary)]" />}
                每日行情自动入库
              </div>
              <Badge tone={failed ? "danger" : completed ? "success" : "warning"}>{marketStatusLabel(status, starting)}</Badge>
              {status?.taskId && <span className="finance-number text-xs text-[var(--text-tertiary)]">任务 {status.taskId}</span>}
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[var(--text-secondary)]">
              <span className="line-clamp-1">{message}</span>
              <span className={cn("finance-number shrink-0 font-semibold", failed ? "text-[var(--color-danger)]" : completed ? "text-[var(--color-success)]" : "text-[var(--color-primary)]")}>{progress.toFixed(0)}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
              <div className={cn("h-full rounded-full transition-all duration-500", barClassName)} style={{ width: `${progress}%` }} />
            </div>
            <div className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] sm:grid-cols-2 xl:grid-cols-5">
              <span>交易日：{status?.tradeDate || "-"}</span>
              <span>缓存日期：{status?.usingCacheDate || status?.latestTradeDate || "-"}</span>
              <span>完成：{status?.successCount ?? 0}/{status?.totalCount ?? 0}</span>
              <span>失败：{status?.failedCount ?? 0}</span>
              <span>更新：{status?.latestUpdatedAt || "-"}</span>
            </div>
            {running && status?.usingCacheDate && status.usingCacheDate !== status.tradeDate && (
              <div className="mt-3 rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-2 text-xs leading-5 text-[var(--color-warning)]">
                行情数据同步中，当前页面展示为 {status.usingCacheDate} 的缓存数据。同步完成后会自动刷新 Dashboard、候选池和策略状态。
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {failed && (
              <Button size="sm" onClick={onRetry}>
                <RefreshCw className="h-4 w-4" />
                重新同步
              </Button>
            )}
            {!running && (
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                收起
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DailyPipelineProgress({
  task,
  starting,
  error,
  onRetry,
  onDismiss
}: {
  task: TaskRun | null;
  starting: boolean;
  error: string | null;
  onRetry: () => void;
  onDismiss: () => void;
}) {
  const progress = task ? getTaskProgress(task) : starting ? 0 : 0;
  const running = starting || isTaskRunning(task);
  const failed = Boolean(error && !running) || task?.status === "failed" || task?.status === "cancelled";
  const completed = task?.status === "success" || task?.status === "partial_success";
  const stageText = failed ? error || task?.error_message || "任务执行失败" : task ? formatPipelineStage(task) : "任务创建";
  const barClassName = failed ? "bg-[var(--color-danger)]" : completed ? "bg-[var(--color-success)]" : "bg-[var(--color-primary)]";

  return (
    <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-header)] px-3 pb-3 md:px-5 lg:px-6">
      <div className="mx-auto w-full max-w-[1540px] rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 shadow-[0_10px_30px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold">
                {failed ? (
                  <AlertTriangle className="h-4 w-4 text-[var(--color-danger)]" />
                ) : completed ? (
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
                ) : (
                  <RefreshCw className={cn("h-4 w-4 text-[var(--color-primary)]", running && "animate-spin")} />
                )}
                每日决策流水线
              </div>
              <Badge tone={failed ? "danger" : completed ? "success" : "warning"}>{taskStatusLabel(task?.status, starting)}</Badge>
              {task?.id && <span className="finance-number text-xs text-[var(--text-tertiary)]">任务 {task.id}</span>}
            </div>
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[var(--text-secondary)]">
              <span className="line-clamp-1">{stageText}</span>
              <span className={cn("finance-number shrink-0 font-semibold", failed ? "text-[var(--color-danger)]" : completed ? "text-[var(--color-success)]" : "text-[var(--color-primary)]")}>
                {progress.toFixed(0)}%
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
              <div className={cn("h-full rounded-full transition-all duration-500", barClassName)} style={{ width: `${progress}%` }} />
            </div>
            <div className="mt-3 grid gap-2 text-xs text-[var(--text-tertiary)] sm:grid-cols-2 xl:grid-cols-5">
              <span>处理：{task ? `${task.processed_count}/${task.total_count}` : "0/12"}</span>
              <span>成功：{task?.success_count ?? 0}</span>
              <span>失败：{task?.failed_count ?? 0}</span>
              <span>重试：{task?.retry_count ?? 0}</span>
              <span className="flex items-center gap-1">
                <Clock3 className="h-3.5 w-3.5" />
                {task?.duration_ms ? `${(task.duration_ms / 1000).toFixed(1)}s` : running ? "运行中" : "-"}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {failed && (
              <Button size="sm" onClick={onRetry}>
                <RefreshCw className="h-4 w-4" />
                重新运行
              </Button>
            )}
            {!running && (
              <Button variant="ghost" size="sm" onClick={onDismiss}>
                收起
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function isTaskRunning(task: TaskRun | null) {
  return Boolean(task && ["pending", "running"].includes(task.status));
}

function isJobRunning(run: JobRun | null) {
  return Boolean(run && ["pending", "running"].includes(run.status));
}

function getJobProgress(run: JobRun) {
  const rawProgress = Number(run.progress || 0);
  const progress = Number.isFinite(rawProgress) ? rawProgress : 0;
  if (run.status === "success" || run.status === "partial_success") return 100;
  if (run.status === "failed" || run.status === "failed_timeout" || run.status === "cancelled") return Math.max(0, Math.min(100, progress));
  return Math.max(0, Math.min(99, progress));
}

function formatJobStage(run: JobRun) {
  if (run.status === "success") return "后台任务完成，数据库快照已刷新";
  if (run.status === "partial_success") return "后台任务完成，存在部分数据失败";
  if (run.status === "failed") return run.error_message || "后台任务失败";
  if (run.status === "failed_timeout") return run.error_message || "后台任务超时，已自动标记失败";
  if (run.status === "skipped_non_trading_day") return "非交易日，保留最近可用快照";
  const stage = run.current_stage || "任务创建";
  return stage.includes("：") ? stage.split("：").slice(1).join("：") : stage;
}

function jobStatusLabel(status?: JobRun["status"], starting?: boolean) {
  if (starting) return "任务创建";
  if (status === "pending") return "排队中";
  if (status === "running") return "运行中";
  if (status === "success") return "已完成";
  if (status === "partial_success") return "部分完成";
  if (status === "failed") return "失败";
  if (status === "failed_timeout") return "超时失败";
  if (status === "skipped_non_trading_day") return "非交易日跳过";
  if (status === "cancelled") return "已取消";
  return "准备中";
}

function jobDisplayName(jobName: string) {
  if (jobName === "morning_prewarm_job") return "开盘前预热任务";
  if (jobName === "midday_refresh_job") return "午盘刷新任务";
  if (jobName === "after_close_refresh_job") return "收盘后刷新任务";
  return jobName || "后台刷新任务";
}

function getTaskProgress(task: TaskRun) {
  const rawProgress = Number(task.progress_percent || 0);
  const progress = Number.isFinite(rawProgress) ? rawProgress : 0;
  if (task.status === "success" || task.status === "partial_success") return 100;
  if (task.status === "failed" || task.status === "cancelled") return Math.max(0, Math.min(100, progress));
  return Math.max(0, Math.min(99, progress));
}

function formatTaskProgress(task: TaskRun) {
  return `${getTaskProgress(task).toFixed(0)}%`;
}

function formatPipelineStage(task: TaskRun) {
  if (task.status === "success") return "策略运行完成，数据已刷新";
  if (task.status === "partial_success") return "策略运行完成，部分数据补抓失败";
  if (task.status === "failed") return task.error_message || "任务执行失败";
  if (task.status === "cancelled") return "任务已取消";
  const stage = task.current_stage || "任务创建";
  if (stage.includes("sync_market_snapshot")) return "正在同步市场数据";
  if (stage.includes("build_target_symbols")) return "正在生成候选池";
  if (stage.includes("retry_failed_stocks")) return "正在补抓失败股票";
  if (stage.includes("sync_target_stock_daily")) return "正在同步重点股票日线";
  if (stage.includes("compute_target_factors")) return "正在计算因子";
  if (stage.includes("detect_market_regime")) return "正在识别市场状态";
  if (stage.includes("detect_market_theme")) return "正在识别今日主线";
  if (stage.includes("run_enabled_strategies")) return "正在运行策略";
  if (stage.includes("apply_risk_engine")) return "正在计算收益与风险";
  if (stage.includes("generate_daily_decision")) return "正在生成今日决策";
  if (stage.includes("persist_results")) return "正在刷新 Dashboard";
  if (stage.includes("refresh_strategy_performance")) return "正在刷新策略收益";
  if (stage.includes("completed")) return "策略运行完成，数据已刷新";
  return stage.includes("：") ? stage.split("：").slice(1).join("：") : stage;
}

function taskStatusLabel(status?: TaskRun["status"], starting?: boolean) {
  if (starting) return "任务创建";
  if (status === "pending") return "排队中";
  if (status === "running") return "运行中";
  if (status === "success") return "已完成";
  if (status === "partial_success") return "部分完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  return "准备中";
}

function marketStatusLabel(status: MarketDataSyncStatus | null, starting?: boolean) {
  if (starting) return "启动中";
  if (!status) return "检查中";
  if (status.isRunning || status.status === "running" || status.status === "pending") return "同步中";
  if (status.status === "success") return "已同步";
  if (status.status === "failed") return "失败";
  if (status.needsSync) return "待同步";
  return "缓存";
}

function applyMarketTaskStatus(status: MarketDataSyncStatus, task: TaskRun | null) {
  if (!task || task.id === 0) return status;
  return {
    ...status,
    status: task.status,
    progress: task.progress_percent,
    totalCount: task.total_count || status.totalCount,
    successCount: task.success_count,
    failedCount: task.failed_count,
    errorMessage: task.error_message,
    taskId: task.id,
    isRunning: ["pending", "running"].includes(task.status),
    needsSync: false
  };
}

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)] lg:block">
      <div className="flex h-16 items-center gap-3 border-b border-[var(--border-subtle)] px-5">
        <Image
          src="/brand/felix-quant-icon-64.png"
          alt="Felix量化"
          width={40}
          height={40}
          className="h-10 w-10 rounded-md border border-[var(--border-strong)] bg-white object-cover shadow-[0_0_24px_rgba(255,106,0,0.18)]"
        />
        <div>
          <div className="text-sm font-semibold tracking-wide">Felix量化</div>
          <div className="text-xs uppercase tracking-[0.18em] text-[var(--text-tertiary)]">QUANT RESEARCH TERMINAL</div>
        </div>
      </div>
      <nav className="space-y-4 overflow-y-auto p-3 pb-24">
        {navGroups.map((group) => (
          <div key={group.title}>
            <div className="px-3 pb-1 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--text-tertiary)]">{group.title}</div>
            <div className="space-y-1">
              {group.items.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} />
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="absolute bottom-0 left-0 right-0 border-t border-[var(--border-subtle)] p-4 text-[11px] leading-5 text-[var(--text-tertiary)]">
        本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。
      </div>
    </aside>
  );
}

function MobileNav({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);
  const current = navGroups.flatMap((group) => group.items).find((item) => item.href === "/" ? pathname === "/" : pathname.startsWith(item.href));
  return (
    <div className="border-b border-[var(--border-subtle)] bg-[var(--bg-header)] px-3 py-2 lg:hidden">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--border-subtle)] px-3 text-sm text-[var(--text-secondary)]"
          onClick={() => setOpen(true)}
        >
          <Menu className="h-4 w-4" aria-hidden />
          导航
        </button>
        <div className="truncate text-sm font-medium text-[var(--color-primary)]">{current?.label || "Felix量化"}</div>
      </div>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/45" role="dialog" aria-modal="true">
          <button className="absolute inset-0 cursor-default" aria-label="关闭导航" onClick={() => setOpen(false)} type="button" />
          <aside className="relative h-full w-[82vw] max-w-80 overflow-y-auto border-r border-[var(--border-subtle)] bg-[var(--bg-sidebar)] p-3 shadow-[var(--shadow-card)]">
            <div className="mb-3 flex items-center justify-between border-b border-[var(--border-subtle)] pb-3">
              <div>
                <div className="font-semibold">Felix量化</div>
                <div className="text-xs uppercase tracking-[0.16em] text-[var(--text-tertiary)]">Quant Research Terminal</div>
              </div>
              <button className="rounded-md p-2 text-[var(--text-tertiary)] hover:bg-[var(--bg-card-hover)]" onClick={() => setOpen(false)} aria-label="关闭导航" type="button">
                ×
              </button>
            </div>
            <nav className="space-y-4 pb-8">
              {navGroups.map((group) => (
                <div key={group.title}>
                  <div className="px-3 pb-1 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--text-tertiary)]">{group.title}</div>
                  <div className="space-y-1" onClick={() => setOpen(false)}>
                    {group.items.map((item) => (
                      <NavLink key={item.href} item={item} pathname={pathname} />
                    ))}
                  </div>
                </div>
              ))}
            </nav>
          </aside>
        </div>
      )}
    </div>
  );
}

function NavLink({ item, pathname }: { item: (typeof navGroups)[number]["items"][number]; pathname: string }) {
  const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "group relative flex h-10 items-center gap-3 rounded-md px-3 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]",
        active && "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
      )}
    >
      <span
        className={cn(
          "absolute left-0 top-2 h-6 w-0.5 rounded-r bg-transparent transition-colors",
          active && "bg-[var(--color-primary)]"
        )}
      />
      <Icon className="h-4 w-4" aria-hidden />
      <span>{item.label}</span>
    </Link>
  );
}
