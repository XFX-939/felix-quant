export const performanceSeries = [
  { date: "04-22", strategy: 100, benchmark: 100 },
  { date: "04-23", strategy: 101.2, benchmark: 100.5 },
  { date: "04-24", strategy: 102.6, benchmark: 100.2 },
  { date: "04-25", strategy: 101.8, benchmark: 99.8 },
  { date: "04-26", strategy: 103.4, benchmark: 100.9 },
  { date: "04-27", strategy: 104.1, benchmark: 101.3 },
  { date: "04-28", strategy: 103.7, benchmark: 100.7 },
  { date: "04-29", strategy: 105.2, benchmark: 101.5 }
];

export const drawdownSeries = [
  { date: "04-22", drawdown: 0 },
  { date: "04-23", drawdown: -0.6 },
  { date: "04-24", drawdown: -0.3 },
  { date: "04-25", drawdown: -1.8 },
  { date: "04-26", drawdown: -0.9 },
  { date: "04-27", drawdown: -0.4 },
  { date: "04-28", drawdown: -1.1 },
  { date: "04-29", drawdown: -0.7 }
];

export const defaultRiskChecks = [
  { name: "市场风险", level: "medium", detail: "震荡状态，成交活跃度一般" },
  { name: "个股风险", level: "high", detail: "部分候选触发回撤阈值" },
  { name: "行业风险", level: "medium", detail: "银行权重偏高，需防集中度" },
  { name: "策略风险", level: "low", detail: "策略运行正常，信号数量偏少" },
  { name: "数据风险", level: "low", detail: "示例数据完整，更新链路正常" }
] as const;

