export type RiskLevel = "low" | "medium" | "high";

export interface Stock {
  id: number;
  code: string;
  name: string;
  industry: string;
  market: string;
  price_date?: string;
  current_price?: number;
  pct_change?: number;
  indicators?: Record<string, number | null>;
  latest_signal?: Signal | null;
}

export interface PricePoint {
  stock_code: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  pct_change: number;
}

export interface MarketDataSyncStatus {
  tradeDate: string;
  latestTradeDate?: string | null;
  latestUpdatedAt?: string | null;
  status: "idle" | "pending" | "running" | "success" | "failed" | "cancelled" | "partial_success";
  progress: number;
  totalCount: number;
  successCount: number;
  failedCount: number;
  errorMessage?: string | null;
  taskId?: number | null;
  needsSync: boolean;
  isRunning: boolean;
  usingCacheDate?: string | null;
}

export interface LimitUpStatsItem {
  code: string;
  name: string;
  industry: string;
  swL1Name?: string;
  swL2Name?: string;
  swL3Name?: string;
  market: string;
  isST?: boolean;
  open: number;
  high: number;
  low: number;
  close: number;
  pctChange: number;
  amount: number;
  turnoverRate?: number | null;
  floatMarketCap?: number;
  limitUpPrice?: number;
  limitDownPrice?: number;
  isLimitUp: boolean;
  isLimitDown: boolean;
  isBrokenBoard?: boolean;
  boardHeight: number;
  boardLabel: string;
  sealTime?: string | null;
  sealAmount?: number | null;
  sealAmountRatio?: number;
  openBoardCount?: number;
  limitUpType?: string;
  isOneWordBoard?: boolean;
  isNewHigh?: boolean;
  marketSentimentScore?: number;
  industryHeatScore?: number;
  industryHeatRank?: number;
  industryLineType?: string;
  boardHeightScore?: number;
  sealQualityScore?: number;
  liquidityScore?: number;
  riskPenaltyScore?: number;
  totalScore?: number;
  actionLevel?: "A" | "B" | "C" | "D";
  actionLabel?: "可参与" | "观察" | "回避" | "禁止参与";
  triggerCondition?: string;
  positionAdvice?: string;
  stopLossRule?: string;
  takeProfitRule?: string;
  riskReasons?: string[];
}

export interface LimitUpStatsSummary {
  tradeDate: string;
  updatedAt?: string | null;
  limitUpCount: number;
  limitDownCount: number;
  brokenLimitCount: number;
  boardStockCount: number;
  highestBoard: number;
  firstBoardCount: number;
  secondBoardCount: number;
  thirdPlusCount: number;
  heightDistribution: Array<{ height: number; count: number; label: string }>;
  dataWarning?: string | null;
}

export interface LimitUpMarketSentiment {
  tradeDate?: string;
  limitUpCount: number;
  limitDownCount: number;
  brokenBoardCount: number;
  sealRate: number;
  maxBoardHeight: number;
  threeBoardPlusCount: number;
  yesterdayLimitUpPremium: number;
  indexTrendScore: number;
  marketSentimentScore: number;
  marketState: "强情绪" | "可交易" | "弱分歧" | "退潮";
}

export interface LimitUpIndustryHeat {
  industryLevel: string;
  industryCode?: string;
  industryName: string;
  limitUpCount: number;
  chainStockCount: number;
  maxBoardHeight: number;
  avgChangePct: number;
  totalAmount: number;
  amountRatio: number;
  sealRate: number;
  brokenBoardCount: number;
  industryHeatScore: number;
  industryHeatRank: number;
  industryLineType: "主线板块" | "次主线" | "非主线";
}

export interface LimitUpStatsResponse {
  strategyName?: string;
  strategyNameEn?: string;
  strategyCode?: string;
  summary: LimitUpStatsSummary;
  marketSentiment?: LimitUpMarketSentiment;
  industryHeat?: LimitUpIndustryHeat[];
  groups: Array<{ height: number; label: string; stocks: LimitUpStatsItem[] }>;
  items: LimitUpStatsItem[];
  filters: {
    height: string;
    market: string;
    search: string;
    actionLabel?: string;
    minScore?: number | null;
    industry?: string;
    excludeST?: boolean;
    mainlineOnly?: boolean;
  };
  disclaimer?: string;
}

export interface FlumBacktestResult {
  strategyName: string;
  strategyCode: string;
  startDate: string;
  endDate: string;
  totalReturn: number;
  annualReturn: number;
  maxDrawdown: number;
  winRate: number;
  profitLossRatio: number;
  sharpe: number;
  tradeCount: number;
  avgHoldingDays: number;
  maxSingleLoss: number;
  consecutiveLossCount: number;
  heightPerformance: Array<{ name: string; count: number; avgReturn: number; winRate: number }>;
  industryPerformance: Array<{ name: string; count: number; avgReturn: number; winRate: number }>;
  sentimentPerformance: Array<{ name: string; count: number; avgReturn: number; winRate: number }>;
  equityCurve: Array<{ date: string; value: number; return: number }>;
  drawdownCurve: Array<{ date: string; value: number }>;
  trades: Array<Record<string, string | number | null | undefined>>;
  validityLevel: "可信" | "样本不足" | "数据不足" | "需谨慎";
  warnings: string[];
  disclaimer: string;
}

export interface Strategy {
  id: number;
  name: string;
  description: string;
  type: string;
  parameters: Record<string, unknown>;
  enabled: boolean;
  source?: StrategySource | null;
  created_at: string;
  updated_at: string;
}

export type StrategySourceType =
  | "academic_paper"
  | "broker_research"
  | "quant_firm_research"
  | "public_blog"
  | "book"
  | "open_source"
  | "self_developed"
  | "inspired_by"
  | "unknown";

export interface StrategySource {
  strategyName: string;
  sourceType: StrategySourceType;
  sourceName: string;
  sourceTitle?: string | null;
  sourceAuthor?: string | null;
  sourceUrl?: string | null;
  publishDate?: string | null;
  sourceSummary: string;
  originalIdea: string;
  localAdaptation: string;
  implementationNotes: string;
  limitations: string[];
  requiredData: string[];
  missingData: string[];
  confidenceLevel: "高" | "中" | "低";
  evidenceLevel: "强证据" | "中等证据" | "弱证据" | "仅假设";
  isVerifiedByBacktest: boolean;
  backtestValidity: "可信" | "样本不足" | "数据不足" | "未验证";
  tags: string[];
  version: string;
  updatedAt: string;
}

export interface StrategySourceSummary {
  totalCount: number;
  selfDevelopedCount: number;
  publicResearchCount: number;
  brokerResearchCount: number;
  insufficientBacktestCount: number;
  lowConfidenceCount: number;
  unverifiedCount: number;
}

export interface Signal {
  id: number;
  date: string;
  stock_code: string;
  stock_name: string;
  industry: string;
  market?: string;
  strategy_id: number;
  strategy_name: string;
  strategy_type?: string;
  signal_type: string;
  score: number;
  trend_score: number;
  valuation_score: number;
  capital_score: number;
  reason: string;
  risk_reason: string;
  risk_level: RiskLevel;
  current_price?: number;
  pct_change?: number;
  recent_backtest_return?: number;
  recent_backtest_drawdown?: number;
  recent_backtest_performance: string;
  metadata?: Record<string, unknown>;
  signalScore?: number;
  riskPenalty?: number;
  finalScore?: number;
  strategyConfidence?: number;
  diversityPenalty?: number;
  isNewCandidate?: boolean;
  candidateMode?: "main_observation" | "risk_observation" | "review_pool" | "ranked_observation" | string;
  hardRisk?: string[];
  softRisk?: string[];
  dragon?: DragonLeaderCandidate;
  strategyCandidate?: StrategyCandidate;
  dragonScore?: number;
  hotspotScore?: number | null;
  sectorHotScore?: number | null;
  leaderScore?: number | null;
  capitalFlowScore?: number | null;
  volumeRatio?: number | null;
  turnoverRate?: number | null;
  amount?: number | null;
  candidateLevel?: string;
  candidateTypes?: string[];
  suggestedAction?: DragonLeaderCandidate["suggestedAction"];
  suggestedWeight?: number;
  maxPosition?: number;
  marketRegime?: MarketRegime;
  subScores?: Record<string, number>;
  triggerReasons?: string[];
  riskReasons?: string[];
  exitRules?: string[];
  marketSentiment?: DragonLeaderCandidate["marketSentiment"];
  created_at: string;
}

export type MarketRegime = "RiskOn" | "Choppy" | "RiskOff" | "Panic" | "Recovery";
export type DragonRiskLevel = "低" | "中" | "高";
export type ResearchRating = "买入" | "增持" | "持有" | "减持" | "卖出" | "无法评级";
export type DataConfidence = "高" | "中" | "低";

export interface StockInspectionReport {
  code: string;
  name: string;
  tradeDate: string;
  industry: string;
  conceptNames?: string[];
  marketRegime: MarketRegime;
  researchRating: ResearchRating;
  overallScore: number;
  riskLevel: DragonRiskLevel;
  dataConfidence: DataConfidence;
  ratingSummary: string;
  ratingHorizon: string;
  targetPriceRange: {
    low: number | null;
    mid: number | null;
    high: number | null;
    method: string;
    confidence: DataConfidence;
    supportLevels?: number[];
    resistanceLevels?: number[];
  };
  currentPrice?: number | null;
  pctChange?: number | null;
  supportLevels?: number[];
  resistanceLevels?: number[];
  keyBullishReasons: string[];
  keyBearishReasons: string[];
  ratingChangeTriggers: {
    upgradeTriggers: string[];
    downgradeTriggers: string[];
  };
  scores: {
    technicalScore?: number | null;
    fundamentalScore?: number | null;
    sentimentScore?: number | null;
    capitalFlowScore?: number | null;
    riskControlScore?: number | null;
  };
  analysis: Record<string, string[]>;
  ratingReasons?: string[];
  invalidConditions?: string[];
  ratingDisclaimer: string;
  ratingVersion: string;
  updatedAt: string;
  rawFactors: Record<string, number | string | boolean | string[] | null>;
}

export interface StrategyCandidate {
  code: string;
  name: string;
  tradeDate: string;
  industryName?: string;
  sectorName?: string;
  conceptNames?: string[];
  strategies?: string[];
  candidateTypes?: string[];
  close?: number;
  pctChg?: number;
  amount?: number;
  turnoverRate?: number;
  volumeRatio?: number;
  strategyName: string;
  signalScore?: number;
  riskPenalty?: number;
  finalScore: number;
  strategyConfidence?: number;
  candidateMode?: string;
  candidateLevel?: string;
  hotspotScore?: number | null;
  trendScore?: number;
  valueScore?: number;
  qualityScore?: number;
  capitalFlowScore?: number;
  sectorHotScore?: number;
  leaderScore?: number;
  subScores: Record<string, number>;
  marketRegime: MarketRegime;
  riskLevel: DragonRiskLevel;
  suggestedAction: "观察" | "谨慎观察" | "暂不参与";
  suggestedWeight?: number;
  maxPosition?: number;
  triggerReasons: string[];
  riskReasons: string[];
  exitRules: string[];
  rawFactors: Record<string, number | string | boolean | string[] | null>;
  sectorRank?: number;
  sectorLimitUpCount?: number;
  consecutiveLimitUpDays?: number;
}

export interface DragonLeaderCandidate {
  code: string;
  name: string;
  tradeDate: string;
  strategyName: "短线龙头候选策略";
  close: number;
  pctChg: number;
  amount: number;
  turnoverRate: number;
  volumeRatio: number;
  amountRatio?: number;
  isLimitUp: boolean;
  consecutiveLimitUpDays: number;
  isStrongBreakout: boolean;
  sectorName: string;
  sectorLimitUpCount: number;
  sectorAvgPct: number;
  sectorTopPct?: number;
  sectorStrengthRank: number;
  stockExcessMarket: number;
  stockExcessSector: number;
  relativeStrength5d: number;
  relativeStrength20d: number;
  dragonScore: number;
  candidateLevel: "核心龙头候选" | "强势龙头候选" | "观察候选";
  marketSentiment: "Hot" | "Neutral" | "Cold";
  riskLevel: DragonRiskLevel;
  riskPenalty?: number;
  suggestedAction: "观察" | "谨慎观察" | "暂不参与";
  triggerReasons: string[];
  riskReasons: string[];
  exitRules: string[];
  marketLimitUpCount?: number;
  marketLimitDownCount?: number;
  highBoardHeight?: number;
}

export interface BacktestResult {
  id: number;
  strategy_id: number;
  strategy_name: string;
  start_date: string;
  end_date: string;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe: number;
  win_rate: number;
  trade_count: number;
  created_at: string;
  validity?: BacktestValidity;
  result_json: {
    stock_pool: string;
    stock_count: number;
    initial_cash: number;
    fee_rate: number;
    slippage?: number;
    data_coverage_ratio?: number;
    st_suspension_delist_handled?: boolean;
    financial_announcement_lag_handled?: boolean;
    stop_loss: number;
    take_profit?: number;
    position_cap: number;
    max_positions?: number;
    max_holding_days?: number;
    profit_loss_ratio: number;
    avg_holding_days?: number;
    max_single_loss?: number;
    sentiment_performance?: Record<string, { count: number; avg_return: number; win_rate: number }>;
    board_height_performance?: Record<string, { count: number; avg_return: number; win_rate: number }>;
    high_risk_filter_comparison?: {
      after_filter_avg_return: number;
      before_filter_avg_return: number;
      high_risk_observation_count: number;
    };
    equity_curve: Array<{ date: string; value: number; return: number }>;
    drawdown_curve: Array<{ date: string; value: number }>;
    trades: Array<{
      date: string;
      stock_code: string;
      action: string;
      score: number;
      return: number;
      weight: number;
      reason: string;
      risk_level: RiskLevel;
      holding_days?: number;
      exit_reason?: string;
      market_sentiment?: string;
      board_height?: number;
    }>;
  };
}

export interface BacktestValidity {
  validityLevel: "可信" | "需谨慎" | "样本不足" | "区间不足" | "数据不足" | "仅功能验证";
  validityWarnings: string[];
  repairSuggestions?: string[];
  backtestDays: number;
  stockPool?: string;
  stockPoolSize?: number;
  dataCoverageRatio?: number;
  feeIncluded?: boolean;
  slippageIncluded?: boolean;
  stSuspensionDelistHandled?: boolean;
  survivorBiasRisk?: boolean;
  forwardBiasRisk?: boolean;
  sampleSizeLevel?: "样本不足" | "样本充足";
  usableForDecision?: boolean;
  usableForStrategyJudgement: boolean;
  metricsMuted: boolean;
  conclusion: string;
}

export interface BacktestDefaults {
  latestTradeDate: string;
  defaultPeriod: "1M" | "3M" | "6M" | "1Y" | "2Y";
  defaultStockPool: string;
  usesTradingCalendar: boolean;
  periods: Record<"1M" | "3M" | "6M" | "1Y" | "2Y", string>;
}

export interface BatchBacktestValidity {
  validityLevel: "可信" | "需谨慎" | "样本不足" | "数据不足" | "仅功能验证";
  warnings: string[];
  validStrategyCount: number;
  insufficientSampleStrategyCount: number;
  dataInsufficientStrategyCount: number;
}

export interface BatchBacktestResultRow {
  strategyId?: number;
  strategyName: string;
  status: "success" | "failed" | string;
  backtestResultId?: number;
  totalReturn?: number | null;
  annualReturn?: number | null;
  maxDrawdown?: number | null;
  sharpe?: number | null;
  winRate?: number | null;
  profitLossRatio?: number | null;
  tradeCount?: number | null;
  avgHoldingDays?: number | null;
  validityLevel?: BacktestValidity["validityLevel"] | string;
  error?: string;
  equityCurve?: BacktestResult["result_json"]["equity_curve"];
}

export interface BatchBacktestDetail {
  task: TaskRun;
  childTasks: TaskRun[];
  summary: {
    taskType?: string;
    strategyCount?: number;
    successCount?: number;
    failedCount?: number;
    stockPool?: string;
    startDate?: string;
    endDate?: string;
    results?: BatchBacktestResultRow[];
    validity?: BatchBacktestValidity;
  };
  resultTable: BatchBacktestResultRow[];
  navSeries: Array<{
    strategyName: string;
    points: Array<{ date: string; value: number; return?: number; cumulativeReturn?: number | null }>;
  }>;
  validity?: BatchBacktestValidity;
}

export type PerformancePeriod = "1M" | "3M" | "6M" | "1Y" | "ALL";
export type StrategyPerformanceValidity = "可信" | "样本不足" | "数据不足" | "需谨慎";

export interface StrategyPeriodPerformance {
  strategyName: string;
  period: PerformancePeriod;
  startDate: string;
  endDate: string;
  startNav?: number;
  endNav?: number;
  returnRate: number | null;
  annualizedReturn: number | null;
  maxDrawdown: number | null;
  volatility: number | null;
  sharpeRatio: number | null;
  winRate: number | null;
  tradeCount: number;
  avgHoldingDays: number | null;
  benchmarkReturn: number | null;
  excessReturn: number | null;
  dataCoverageRatio: number;
  validityLevel: StrategyPerformanceValidity;
  warnings: string[];
  updatedAt?: string;
}

export interface StrategyPerformanceRow {
  strategyName: string;
  strategyType: string;
  enabled: boolean;
  todayStatus: "保持启用" | "降权观察" | "仅复盘" | "暂停" | string;
  periods: Record<PerformancePeriod, StrategyPeriodPerformance>;
  latestBacktestValidity: StrategyPerformanceValidity;
  performanceStatus: "优秀" | "良好" | "一般" | "偏弱" | "样本不足";
  diagnosisText: string;
  suggestedStrategyAction: "保持启用" | "降权观察" | "仅复盘" | "暂停";
}

export interface StrategyPerformanceSummary {
  periods: PerformancePeriod[];
  benchmarkCode: string;
  updatedAt: string;
  overview: {
    best1M?: { strategyName: string; returnRate: number } | null;
    best3M?: { strategyName: string; returnRate: number } | null;
    best6M?: { strategyName: string; returnRate: number } | null;
    best1Y?: { strategyName: string; returnRate: number } | null;
    enabledStrategyCount: number;
    validBacktestStrategyCount: number;
    insufficientSampleCount: number;
    maxDrawdownStrategy?: { strategyName: string; maxDrawdown: number } | null;
    suggestedPauseCount: number;
  };
  validation?: {
    latestTradeDate?: string | null;
    missingNavStrategies: string[];
    missingSummaryStrategies: string[];
    staleSummaryItems: string[];
    insufficientSampleItems: string[];
    lowCoverageItems: string[];
    invalidZeroReturnItems: string[];
    warnings: string[];
    isHealthy: boolean;
  };
  strategies: StrategyPerformanceRow[];
}

export interface StrategyNavPoint {
  tradeDate: string;
  nav: number;
  dailyReturn: number;
  cumulativeReturn: number;
  drawdown: number;
  benchmarkNav?: number | null;
  benchmarkReturn?: number | null;
}

export interface StrategyNavSeries {
  strategyName: string;
  points: StrategyNavPoint[];
}

export interface StrategyNavResponse {
  period: PerformancePeriod;
  benchmarkCode: string;
  series: StrategyNavSeries[];
}

export interface StrategyPerformanceDetail {
  strategyName: string;
  periods: Record<PerformancePeriod, StrategyPeriodPerformance>;
  nav: StrategyNavPoint[];
  drawdown: Array<{ tradeDate: string; drawdown: number }>;
  dailyReturns: Array<{ tradeDate: string; dailyReturn: number }>;
  trades: Array<Record<string, string | number | null>>;
  diagnosis: {
    performanceStatus: string;
    diagnosisText: string;
    suggestedStrategyAction: string;
  };
}

export interface DashboardStrategyPerformanceBrief {
  strategyName: string;
  strategyType?: string;
  period: PerformancePeriod;
  returnRate: number | null;
  maxDrawdown: number | null;
  validityLevel: StrategyPerformanceValidity;
  strategyStatus?: string;
  sourceName?: string | null;
  sourceType?: StrategySourceType | null;
  sourceConfidence?: "高" | "中" | "低" | null;
  backtestValidity?: string | null;
}

export interface DashboardStrategyPerformance {
  updatedAt: string;
  periods: PerformancePeriod[];
  best1M?: DashboardStrategyPerformanceBrief | null;
  best3M?: DashboardStrategyPerformanceBrief | null;
  worstDrawdown?: DashboardStrategyPerformanceBrief | null;
  recommendedStrategies: DashboardStrategyPerformanceBrief[];
  navSeries: Array<{
    strategyName: string;
    points: Array<{
      date: string;
      nav: number;
      cumulativeReturn: number;
      drawdown: number;
    }>;
  }>;
  periodReturns: Array<{
    strategyName: string;
    strategyType?: string;
    return1M?: number | null;
    return3M?: number | null;
    return6M?: number | null;
    return1Y?: number | null;
    maxDrawdown1Y?: number | null;
    winRate1Y?: number | null;
    tradeCount1Y?: number | null;
    sharpe1Y?: number | null;
    validityLevel: StrategyPerformanceValidity;
    sourceName?: string | null;
    sourceConfidence?: "高" | "中" | "低" | null;
    suggestedStrategyAction?: string;
  }>;
  heatmap: Array<{
    strategyName: string;
    period: PerformancePeriod;
    returnRate?: number | null;
    validityLevel: StrategyPerformanceValidity | string;
  }>;
  warnings: string[];
}

export interface AlphaLabItem {
  alphaId: string;
  name: string;
  formula: string;
  ic: number | null;
  rankIc: number | null;
  groupReturn: number | null;
  turnover: number | null;
  maxDrawdown: number | null;
  longShortReturn: number | null;
  validityScore: number | null;
  researchOnly: boolean;
  includedInCandidatePool: boolean;
}

export interface Review {
  id: number;
  date: string;
  stock_code: string;
  stock_name?: string;
  signal_id?: number | null;
  action_taken: boolean;
  reason: string;
  result: string;
  summary: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  last_data_date: string | null;
  last_run_time: string | null;
  candidate_count: number;
  market_status: {
    avg_change: number;
    up_count: number;
    total_count: number;
    summary: string;
  };
  market_regime?: {
    marketRegime: MarketRegime;
    explanation: string;
    enabledStrategies: string[];
    reducedStrategies: string[];
    disabledStrategies: string[];
    suggestedTotalPosition: number;
    indexReturn20d: number;
    indexReturn60d: number;
    marketVol20d: number;
    upStockRatio: number;
    limitUpCount: number;
    limitDownCount: number;
    amountChange20d: number;
    sectorRotationStrength: number;
    drawdownFromHigh20d: number;
    rawMarketRegime?: MarketRegime;
    intradayRecoveryOverride?: boolean;
    strongRecoverySignal?: boolean;
    superRiskOnSignal?: boolean;
    overrideReason?: string;
    regimeReasons?: string[];
    shIndexPctChg?: number;
    szIndexPctChg?: number;
    cybIndexPctChg?: number;
    kc50PctChg?: number;
    totalAmount?: number;
    totalAmountChange?: number;
    upStockCount?: number;
    downStockCount?: number;
    snapshotUpStockRatio?: number;
    snapshotLimitUpCount?: number;
    snapshotLimitDownCount?: number;
    strongSectorCount?: number;
    topSectorAvgPct?: number;
    growthStyleStrength?: number;
    largeCapStrength?: number;
    smallMidCapStrength?: number;
    snapshotSource?: string;
    marketSnapshot?: {
      tradeDate: string | null;
      provider: string;
      ready: boolean;
      source: string;
      data: Record<string, number | string | boolean | null>;
      message: string;
    };
  };
  daily_decision?: {
    tradeDate: string | null;
    decisionMode: "WAIT" | "DEFENSIVE_OBSERVE" | "WATCH" | "PROBE" | "RISK_OFF";
    decisionText: string;
    marketRegime: MarketRegime;
    suggestedTotalPositionMin: number;
    suggestedTotalPositionMax: number;
    allowedActions: string[];
    forbiddenActions: string[];
    keyReasons: string[];
    nextCheck: string;
    whyCurrentMode?: string[];
    waitingSignals?: string[];
    switchConditions?: {
      toDefensiveObserve: string[];
      toWatch: string[];
      toProbe: string[];
    };
    positionDecision?: PositionDecision;
  };
  position_decision?: PositionDecision;
  candidate_funnel?: {
    rawStockPool: number;
    baseFiltered: number;
    strategyInitialCandidates: number;
    hardRiskFiltered: number;
    riskPool: number;
    defensiveWatchlist: number;
    hotspotWatchlist?: number;
    mainWatchlist: number;
    finalActionableCandidates: number;
    filterBreakdown?: Array<{
      name: string;
      count: number;
      ratio: number;
      warning: boolean;
    }>;
  };
  candidate_layers?: {
    mainWatchlist: Signal[];
    defensiveWatchlist: Signal[];
    hotspotWatchlist: Signal[];
    riskPool: Signal[];
    reviewPool: Signal[];
  };
  strategy_health?: Array<{
    strategyName: string;
    candidateCount: number;
    mainCount: number;
    highRiskCount: number;
    averageScore: number;
    highRiskRatio: number;
    enabled: boolean;
    status: "有效" | "降权" | "暂停" | "仅复盘";
    reason: string;
    backtestValidity?: BacktestValidity;
    latestBacktestTradeCount?: number | null;
  }>;
  strategy_source_summary?: StrategySourceSummary;
  missed_opportunity_risk?: {
    level: "低" | "中" | "高";
    reasons: string[];
    suggestedFixes: string[];
  };
  candidate_diversity?: {
    repeatRate1d: number;
    repeatRate5d: number;
    newCandidateCount: number;
    droppedCandidateCount: number;
    topRepeatedCandidates: Array<{ code: string; name: string; appearances: number }>;
    industryConcentration: number;
    strategyConcentration: number;
    largeCapRatio: number;
    warnings: string[];
  };
  market_theme?: {
    themes: Array<{
      name: string;
      themeScore: number;
      level?: "完整题材" | "行业降级" | "风格估算";
      confidence?: "高" | "中" | "低";
      relatedSectors?: string[];
      evidence?: string[];
      dataBasis?: string[];
      missingData?: string[];
      sectorPctChg: number;
      sectorRank: number;
      sectorLimitUpCount: number;
      sectorStrongStockCount: number;
      sectorAmountChange: number;
      continuationDays: number;
    }>;
    isComplete: boolean;
    confidence?: "高" | "中" | "低";
    message: string;
    displayText: string;
  };
  data_coverage?: DataCoverage;
  data_quality?: {
    priceDataUpdated: boolean;
    limitUpDataReady: boolean;
    brokenLimitDataReady: boolean;
    conceptDataReady: boolean;
    financialAnnouncementReady: boolean;
    feeIncluded: boolean;
    slippageIncluded: boolean;
    futureFunctionRisk: string;
    dataVersion: string;
    strategyParameterVersion: string;
    integrityScore: number;
    integrityLevel: "可信" | "需谨慎" | "不可信";
    integrityWarnings: string[];
    dataCoverage?: DataCoverage;
  };
  strategy_decision_status?: {
    activeStrategies: number;
    observeOnlyStrategies: number;
    reviewOnlyStrategies: number;
    pausedStrategies: number;
  };
  strategy_distribution?: Array<{
    strategyName: string;
    candidateCount: number;
    highRiskCount: number;
    averageScore: number;
    filteredCount: number;
    status?: "有效" | "降权" | "暂停" | "仅复盘";
    reason?: string;
    mainCount?: number;
    highRiskRatio?: number;
    backtestValidity?: BacktestValidity;
    latestBacktestTradeCount?: number | null;
  }>;
  portfolio_risk_budget?: {
    marketRegime: MarketRegime;
    totalSuggestedWeight: number;
    portfolioRiskLevel: DragonRiskLevel;
    sectorExposure: Record<string, number>;
    strategyExposure: Record<string, number>;
    positions: StrategyCandidate[];
  };
  strategy_status: Array<{
    id: number;
    name: string;
    type: string;
    enabled: boolean;
    today_signal_count: number;
  }>;
  latest_backtest: BacktestResult | null;
  current_risk_level: RiskLevel;
  watchlist: Signal[];
  defensive_watchlist?: Signal[];
  hotspot_watchlist?: Signal[];
  risk_pool?: Signal[];
  review_pool?: Signal[];
  risk_alerts: string[];
  recent_backtests: Array<{
    id: number;
    created_at: string;
    strategy_name: string;
    total_return: number;
    max_drawdown: number;
    win_rate: number;
    validity?: BacktestValidity;
  }>;
  recent_reviews: Review[];
  disclaimer: string;
}

export interface PositionDecision {
  baseRiskLimit: number;
  marketRegimeLimit: number;
  strategyQualityLimit: number;
  decisionModeLimitMin: number;
  decisionModeLimitMax: number;
  finalPositionMin: number;
  finalPositionMax: number;
  mainWatchlistCount: number;
  hotspotWatchlistCount?: number;
  effectiveStrategyCount: number;
  highRiskRatio: number;
  averageScore: number;
  reasons: string[];
  explanation: string;
}

export interface DataCoverage {
  items: Array<{ name: string; status: "已接入" | "降级估算" | "缺失" | "过期"; reason: string }>;
  criticalHotspotDataMissing: boolean;
  themeConfidence: "高" | "中" | "低";
  warnings: string[];
}

export interface FullMarketSyncJob {
  jobId: string | null;
  taskId?: number | null;
  status: "idle" | "pending" | "running" | "completed" | "failed";
  progress: number;
  scope: "all";
  limit: number | null;
  message: string;
  createdAt: string | null;
  updatedAt: string | null;
  result: {
    source?: string;
    scope?: string;
    stock_count?: number;
    price_rows?: number;
    skipped_count?: number;
    failed_count?: number;
    retry_count?: number;
    failed?: Array<{ code: string; reason: string }>;
    trade_date?: string;
    start_date?: string;
    end_date?: string;
  } | null;
  error: string | null;
}

export interface TaskRun {
  id: number;
  task_type: string;
  trade_date: string | null;
  status: "pending" | "running" | "success" | "partial_success" | "failed" | "cancelled";
  current_stage: string;
  total_count: number;
  processed_count: number;
  success_count: number;
  failed_count: number;
  retry_count: number;
  progress_percent: number;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number;
  error_message: string | null;
  summary_json: Record<string, unknown>;
  parent_task_id?: number | null;
  child_task_count?: number;
  completed_child_count?: number;
  failed_child_count?: number;
  batch_mode?: number | boolean;
  strategy_name?: string | null;
  task_group_name?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  reused?: boolean;
}

export interface FailedSyncRecord {
  id: number;
  trade_date: string;
  code: string;
  name: string;
  task_type: string;
  data_type: string;
  status: "pending" | "retrying" | "failed" | "recovered" | "ignored";
  retry_count: number;
  max_retries: number;
  error_message: string;
  last_error_at: string | null;
  next_retry_at: string | null;
  created_at: string;
  updated_at: string;
  raw_context_json: Record<string, unknown>;
}
