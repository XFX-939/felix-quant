import type {
  AlphaLabItem,
  BacktestResult,
  BatchBacktestDetail,
  BacktestDefaults,
  DashboardSummary,
  DashboardStrategyPerformance,
  DataStatusOverview,
  FailedSyncRecord,
  FlumBacktestResult,
  FullMarketSyncJob,
  JobRun,
  JobsLatestStatus,
  LimitUpIndustryHeat,
  LimitUpMarketSentiment,
  LimitUpStatsResponse,
  LimitUpStatsSummary,
  MarketDataSyncStatus,
  PricePoint,
  Review,
  Signal,
  Stock,
  StockInspectionReport,
  Strategy,
  StrategySource,
  StrategySourceSummary,
  StrategyNavResponse,
  StrategyPerformanceDetail,
  StrategyPerformanceSummary,
  TaskRun
} from "@/lib/types";

const CONFIGURED_API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

function isLocalHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "0.0.0.0";
}

function getApiBase() {
  if (!CONFIGURED_API_BASE) {
    if (typeof window === "undefined") return "http://127.0.0.1:8000";
    return isLocalHost(window.location.hostname) ? `${window.location.protocol}//${window.location.hostname}:8000` : "";
  }
  if (typeof window === "undefined") return CONFIGURED_API_BASE;

  try {
    const configured = new URL(CONFIGURED_API_BASE, window.location.origin);
    const current = window.location;
    const configuredIsSameOrigin = configured.origin === current.origin;
    const currentIsLocal = isLocalHost(current.hostname);
    const configuredIsLocal = isLocalHost(configured.hostname);
    const configuredIsRawIp = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(configured.hostname);
    const wouldCrossFromDomainToIp = configuredIsRawIp && configured.hostname !== current.hostname;
    const wouldDowngradeHttps = current.protocol === "https:" && configured.protocol === "http:";

    if (configuredIsSameOrigin) {
      return "";
    }
    if (configuredIsLocal) {
      return currentIsLocal ? configured.origin : "";
    }
    if (wouldCrossFromDomainToIp || wouldDowngradeHttps) {
      return "";
    }

    return configured.origin;
  } catch {
    return "";
  }
}

type QueryValue = string | number | boolean | null | undefined;

function withQuery(path: string, query?: Record<string, QueryValue>) {
  if (!query) return path;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString();
  return suffix ? `${path}?${suffix}` : path;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getApiBase()}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers || {})
      },
      cache: "no-store"
    });
  } catch {
    throw new Error("后端未连接：请确认 FastAPI 服务已启动，或检查 API 地址配置。");
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(readErrorMessage(message, response.status) || `API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function readErrorMessage(message: string, status?: number) {
  if (!message) return "";
  try {
    const parsed = JSON.parse(message) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // Fall through to the original response text.
  }
  if (/<\/?[a-z][\s\S]*>/i.test(message)) {
    const title = message.match(/<title>(.*?)<\/title>/i)?.[1]?.trim();
    return title
      ? `接口返回 HTML 页面（${title}），请检查后端服务或 API 代理配置。`
      : `接口返回 HTML 页面（HTTP ${status ?? "未知"}），请检查后端服务或 API 代理配置。`;
  }
  return message.length > 240 ? `${message.slice(0, 240)}...` : message;
}

export const api = {
  dashboard: () => request<DashboardSummary>("/api/dashboard/latest"),
  dashboardRaw: () => request<DashboardSummary>("/api/dashboard"),
  dashboardStrategyPerformance: () => request<DashboardStrategyPerformance>("/api/dashboard/strategy-performance"),
  jobsLatest: () => request<JobsLatestStatus>("/api/jobs/latest"),
  jobRuns: (query?: Record<string, QueryValue>) => request<{ scheduledJobs: unknown[]; runs: JobRun[] }>(withQuery("/api/jobs", query)),
  jobRun: (runId: number) => request<JobRun>(`/api/jobs/${runId}`),
  runScheduledJob: (payload: { jobName: string; force?: boolean }) =>
    request<{ jobRunId: number; jobRun: JobRun }>("/api/jobs/run", { method: "POST", body: JSON.stringify(payload) }),
  dataStatus: () => request<DataStatusOverview>("/api/data/status"),
  updateData: () => request<{ message: string; data: unknown; strategy: unknown }>("/api/data/update", { method: "POST" }),
  startFullMarketSync: (limit?: number) => request<FullMarketSyncJob>(withQuery("/api/data/sync/full-market", { limit }), { method: "POST" }),
  fullMarketSyncStatus: (jobId?: string | null) => request<FullMarketSyncJob>(withQuery("/api/data/sync/full-market", { job_id: jobId || undefined })),
  tasks: (query?: Record<string, QueryValue>) => request<TaskRun[]>(withQuery("/api/tasks", query)),
  task: (taskId: number) => request<TaskRun>(`/api/tasks/${taskId}`),
  runDailyPipeline: (payload: { tradeDate?: string; force?: boolean; dryRun?: boolean } = {}) => request<{ taskId: number; task: TaskRun }>("/api/tasks/run-daily-pipeline", { method: "POST", body: JSON.stringify(payload) }),
  marketDataSyncStatus: (query?: Record<string, QueryValue>) => request<MarketDataSyncStatus>(withQuery("/api/market-data/sync-status", query)),
  startMarketDataSync: (payload: { tradeDate?: string; force?: boolean; limit?: number } = {}) =>
    request<{ taskId: number | null; task: TaskRun | null; status: MarketDataSyncStatus }>(withQuery("/api/market-data/sync", { tradeDate: payload.tradeDate, force: payload.force, limit: payload.limit }), { method: "POST" }),
  limitUpStats: (query?: Record<string, QueryValue>) => request<LimitUpStatsResponse>(withQuery("/api/limit-up-stats", query)),
  limitUpSummary: (query?: Record<string, QueryValue>) => request<LimitUpStatsSummary>(withQuery("/api/limit-up-stats/summary", query)),
  limitUpMarketSentiment: (query?: Record<string, QueryValue>) => request<LimitUpMarketSentiment>(withQuery("/api/limit-up-stats/market-sentiment", query)),
  limitUpIndustryHeat: (query?: Record<string, QueryValue>) => request<LimitUpIndustryHeat[]>(withQuery("/api/limit-up-stats/industry-heat", query)),
  generateLimitUpSignals: (query?: Record<string, QueryValue>) => request<LimitUpStatsResponse>(withQuery("/api/limit-up-strategy/generate-signals", query), { method: "POST" }),
  limitUpSignals: (query?: Record<string, QueryValue>) => request<LimitUpStatsResponse>(withQuery("/api/limit-up-strategy/signals", query)),
  retryFailedStocks: (payload: { tradeDate?: string; taskType?: string } = {}) => request<{ taskId: number; task: TaskRun }>("/api/tasks/retry-failed-stocks", { method: "POST", body: JSON.stringify(payload) }),
  runBacktestTask: (payload: Record<string, QueryValue>) => request<{ taskId: number; task: TaskRun }>("/api/tasks/run-backtest", { method: "POST", body: JSON.stringify(payload) }),
  runBatchBacktestTask: (payload: Record<string, unknown>) => request<{ taskId: number; task: TaskRun }>("/api/tasks/run-batch-backtest", { method: "POST", body: JSON.stringify(payload) }),
  failedSyncRecords: (query?: Record<string, QueryValue>) => request<FailedSyncRecord[]>(withQuery("/api/sync/failed-records", query)),
  strategyPerformanceSummary: (query?: Record<string, QueryValue>) => request<StrategyPerformanceSummary>(withQuery("/api/strategy-performance/summary", query)),
  strategyPerformanceNav: (query?: Record<string, QueryValue>) => request<StrategyNavResponse>(withQuery("/api/strategy-performance/nav", query)),
  strategyPerformanceDetail: (strategyName: string, query?: Record<string, QueryValue>) => request<StrategyPerformanceDetail>(withQuery(`/api/strategy-performance/detail/${encodeURIComponent(strategyName)}`, query)),
  refreshStrategyPerformance: (payload: { force?: boolean } = {}) => request<{ taskId: number; task: TaskRun }>(withQuery("/api/strategy-performance/refresh", { force: payload.force }), { method: "POST" }),
  generateStrategyNav: (payload: { strategyName?: string; startDate?: string; endDate?: string; force?: boolean } = {}) => request<{ taskId: number; task: TaskRun }>("/api/strategy-performance/generate-nav", { method: "POST", body: JSON.stringify(payload) }),
  refreshStrategySummary: (payload: { strategyName?: string; endDate?: string; force?: boolean } = {}) => request<{ taskId: number; task: TaskRun }>("/api/strategy-performance/refresh-summary", { method: "POST", body: JSON.stringify(payload) }),
  stocks: (query?: Record<string, QueryValue>) => request<Stock[]>(withQuery("/api/stocks", query)),
  stock: (code: string) => request<Stock>(`/api/stocks/${code}`),
  inspectStock: (code: string, query?: Record<string, QueryValue>) => request<StockInspectionReport>(withQuery(`/api/stock-inspector/${code}`, query)),
  prices: (code: string, query?: Record<string, QueryValue>) => request<PricePoint[]>(withQuery(`/api/stocks/${code}/prices`, query)),
  industries: () => request<string[]>("/api/stocks/industries"),
  strategies: () => request<Strategy[]>("/api/strategies"),
  strategySources: () => request<StrategySource[]>("/api/strategies/sources"),
  strategySourceSummary: () => request<StrategySourceSummary>("/api/strategies/sources/summary"),
  createStrategy: (payload: Partial<Strategy>) => request<Strategy>("/api/strategies", { method: "POST", body: JSON.stringify(payload) }),
  updateStrategy: (id: number, payload: Partial<Strategy>) => request<Strategy>(`/api/strategies/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  runStrategy: (id: number) => request<{ signals_created: number; strategies_run: number; trade_date: string }>(`/api/strategies/${id}/run`, { method: "POST" }),
  signals: (query?: Record<string, QueryValue>) => request<Signal[]>(withQuery("/api/signals", query)),
  todaySignals: () => request<Signal[]>("/api/signals/today"),
  runBacktest: (payload: Record<string, QueryValue>) => request<BacktestResult>("/api/backtest/run", { method: "POST", body: JSON.stringify(payload) }),
  runFlumBacktest: (payload: Record<string, QueryValue>) => request<FlumBacktestResult>("/api/backtest/flum", { method: "POST", body: JSON.stringify(payload) }),
  backtestDefaults: () => request<BacktestDefaults>("/api/backtest/defaults"),
  backtestLatest: () => request<BacktestResult>("/api/backtest/latest"),
  backtestHistory: () => request<BacktestResult[]>("/api/backtest/history"),
  backtestDetail: (id: number) => request<BacktestResult>(`/api/backtest/${id}`),
  backtestBatch: (taskId: number) => request<BatchBacktestDetail>(`/api/backtest/batch/${taskId}`),
  deleteBacktest: (id: number) => request<{ deleted: boolean }>(`/api/backtest/${id}`, { method: "DELETE" }),
  backtestResults: () => request<BacktestResult[]>("/api/backtest/results"),
  riskOverview: () => request<Record<string, unknown>>("/api/risk/overview"),
  riskRules: () => request<Array<Record<string, unknown>>>("/api/risk/rules"),
  updateRiskRule: (id: number, payload: Record<string, QueryValue>) => request<Record<string, unknown>>(`/api/risk/rules/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  alphaLab: () => request<AlphaLabItem[]>("/api/research/alpha-lab"),
  researchIntegrity: () => request<Record<string, unknown>>("/api/research/integrity"),
  marketRegime: () => request<Record<string, unknown>>("/api/research/market-regime"),
  portfolioRiskBudget: () => request<Record<string, unknown>>("/api/research/portfolio-risk-budget"),
  reviews: (query?: Record<string, QueryValue>) => request<Review[]>(withQuery("/api/reviews", query)),
  reviewStats: () => request<Record<string, unknown>>("/api/reviews/stats"),
  createReview: (payload: Partial<Review>) => request<Review>("/api/reviews", { method: "POST", body: JSON.stringify(payload) }),
  deleteReview: (id: number) => request<{ deleted: boolean }>(`/api/reviews/${id}`, { method: "DELETE" })
};
