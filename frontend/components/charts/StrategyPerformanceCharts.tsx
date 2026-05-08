"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { formatPercent } from "@/lib/format";
import type { PerformancePeriod, StrategyNavPoint, StrategyNavResponse, StrategyPerformanceRow } from "@/lib/types";

const COLORS = ["#ff6a00", "#e64545", "#8b5cf6", "#2563eb", "#18a058", "#f5a623", "#14b8a6", "#f97316"];

export function StrategyNavLineChart({ data, height = 340 }: { data: StrategyNavResponse | null; height?: number }) {
  const chartData = mergeSeries(data);
  if (!data || !data.series.length || !chartData.length) {
    return <ChartEmpty height={height} text="暂无策略净值数据，请先运行回测或点击更新策略收益。" />;
  }
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} minTickGap={24} />
          <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} width={56} />
          <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatNumber(value)} labelStyle={{ color: "var(--text-primary)" }} />
          <Legend wrapperStyle={{ color: "var(--text-secondary)", fontSize: 12 }} />
          {data.series.slice(0, 8).map((series, index) => (
            <Line key={series.strategyName} type="monotone" dataKey={series.strategyName} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={false} connectNulls name={series.strategyName} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StrategyDrawdownChart({ points, height = 240 }: { points: StrategyNavPoint[]; height?: number }) {
  if (!points.length) return <ChartEmpty height={height} text="暂无回撤曲线。" />;
  const data = points.map((point) => ({ date: point.tradeDate.slice(5), drawdown: Number((point.drawdown * 100).toFixed(2)) }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} minTickGap={24} />
          <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} width={52} />
          <Tooltip contentStyle={tooltipStyle} formatter={(value) => `${Number(value).toFixed(2)}%`} />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Line type="monotone" dataKey="drawdown" stroke="var(--chart-success)" strokeWidth={2} dot={false} name="回撤%" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StrategyReturnBarChart({ points, height = 240 }: { points: StrategyNavPoint[]; height?: number }) {
  if (!points.length) return <ChartEmpty height={height} text="暂无每日收益。" />;
  const data = points.map((point) => ({ date: point.tradeDate.slice(5), dailyReturn: Number((point.dailyReturn * 100).toFixed(2)) }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} minTickGap={24} />
          <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} width={52} />
          <Tooltip contentStyle={tooltipStyle} formatter={(value) => `${Number(value).toFixed(2)}%`} />
          <ReferenceLine y={0} stroke="var(--border-strong)" />
          <Bar dataKey="dailyReturn" fill="var(--color-primary)" opacity={0.82} name="日收益%" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StrategyPerformanceHeatmap({ rows, periods }: { rows: StrategyPerformanceRow[]; periods: PerformancePeriod[] }) {
  if (!rows.length) return <ChartEmpty height={220} text="暂无收益热力图。" />;
  return (
    <div className="overflow-x-auto scrollbar-thin">
      <div className="min-w-[640px] rounded-md border border-[var(--border-subtle)]">
        <div className="grid grid-cols-[220px_repeat(4,1fr)] border-b border-[var(--border-subtle)] text-xs text-[var(--text-tertiary)]">
          <div className="p-2">策略</div>
          {periods.slice(0, 4).map((period) => (
            <div key={period} className="p-2 text-right">{period}</div>
          ))}
        </div>
        {rows.map((row) => (
          <div key={row.strategyName} className="grid grid-cols-[220px_repeat(4,1fr)] border-b border-[var(--border-subtle)] last:border-b-0">
            <div className="truncate p-2 text-sm">{row.strategyName}</div>
            {periods.slice(0, 4).map((period) => {
              const performance = row.periods[period];
              const value = performance?.returnRate;
              const invalidLabel = performance?.validityLevel === "数据不足" || performance?.validityLevel === "样本不足"
                ? performance.validityLevel
                : null;
              const tone = invalidLabel === "数据不足"
                ? "text-[var(--color-danger)]"
                : invalidLabel === "样本不足"
                  ? "text-[var(--color-warning)]"
                  : returnTone(value);
              return (
                <div key={period} className={`p-2 text-right text-sm ${tone}`} title={performance?.warnings.join("；")}>
                  {invalidLabel || (value === null || value === undefined ? "--" : formatPercent(value))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function mergeSeries(data: StrategyNavResponse | null) {
  const byDate = new Map<string, Record<string, string | number | null>>();
  data?.series.forEach((series) => {
    series.points.forEach((point) => {
      const date = point.tradeDate;
      const row = byDate.get(date) || { date: date.slice(5) };
      row[series.strategyName] = Number(point.nav.toFixed(4));
      byDate.set(date, row);
    });
  });
  return Array.from(byDate.entries()).sort(([a], [b]) => a.localeCompare(b)).map(([, row]) => row);
}

function returnTone(value?: number | null) {
  if (value === undefined || value === null) return "text-[var(--text-tertiary)]";
  if (value > 0) return "text-[var(--color-danger)]";
  if (value < 0) return "text-[var(--color-success)]";
  return "text-[var(--text-secondary)]";
}

function formatNumber(value: unknown) {
  const number = Number(value);
  if (Number.isNaN(number)) return "--";
  return number.toFixed(4);
}

function ChartEmpty({ height, text }: { height: number; text: string }) {
  return (
    <div className="flex items-center justify-center rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-sm text-[var(--text-tertiary)]" style={{ height }}>
      {text}
    </div>
  );
}

const tooltipStyle = {
  background: "var(--bg-card)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 6,
  color: "var(--text-primary)"
};
