"use client";

import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatPercent } from "@/lib/format";
import type { DashboardStrategyPerformance, DashboardStrategyPerformanceBrief } from "@/lib/types";

const COLORS = ["#ff6a00", "#e64545", "#f5a623", "#8b5cf6", "#2563eb"];

export function StrategyPerformanceRadar({ data }: { data: DashboardStrategyPerformance | null }) {
  const hasNav = Boolean(data?.navSeries.some((series) => series.points.length));
  const navData = mergeNavSeries(data);
  const barRows = (data?.periodReturns || []).slice(0, 9);
  const drawdownRows = [...(data?.periodReturns || [])]
    .filter((item) => item.maxDrawdown1Y !== null && item.maxDrawdown1Y !== undefined)
    .sort((a, b) => (b.maxDrawdown1Y || 0) - (a.maxDrawdown1Y || 0))
    .slice(0, 6);

  return (
    <Card className="overflow-hidden border-[rgba(255,106,0,0.28)]">
      <CardHeader className="flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle>策略收益雷达</CardTitle>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            近 1 月 / 近 3 月 / 近半年 / 近 1 年策略收益、回撤与可信度对比。
          </p>
        </div>
        <Link href="/strategy-performance">
          <Button variant="outline">进入策略收益看板</Button>
        </Link>
      </CardHeader>
      <CardContent className="space-y-4">
        {data?.warnings?.length ? (
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--color-warning)]">
            {data.warnings[0]}
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <RadarStat title="近 1 月最强策略" item={data?.best1M} />
          <RadarStat title="近 3 月最强策略" item={data?.best3M} />
          <RadarStat title="回撤最大策略" item={data?.worstDrawdown} valueKey="drawdown" />
          <RadarStat title="当前建议启用策略" item={data?.recommendedStrategies?.[0]} />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">多策略净值曲线</h3>
                <p className="text-xs text-[var(--text-tertiary)]">默认展示收益可信度较高或当前建议关注的前 5 个策略。</p>
              </div>
              <Badge tone={hasNav ? "success" : "warning"}>{hasNav ? "NAV 已接入" : "缺少 NAV"}</Badge>
            </div>
            {hasNav ? (
              <div className="h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={navData} margin={{ left: 0, right: 16, top: 8, bottom: 0 }}>
                    <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} minTickGap={24} />
                    <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} width={52} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value) => Number(value).toFixed(4)} />
                    {data?.navSeries.slice(0, 5).map((series, index) => (
                      <Line key={series.strategyName} type="monotone" dataKey={series.strategyName} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={false} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyBox text="暂无策略净值数据，请先运行回测或生成策略每日净值。" />
            )}
          </div>

          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <h3 className="text-sm font-semibold">近 3 月收益柱状图</h3>
            <p className="text-xs text-[var(--text-tertiary)]">样本不足或数据不足的策略显示为灰色，不参与有效性排序。</p>
            {barRows.length ? (
              <div className="mt-3 h-[320px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barRows.map((row) => ({ ...row, label: row.strategyName.slice(0, 8), value: row.return3M }))} margin={{ left: 0, right: 8, top: 12, bottom: 0 }}>
                    <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} />
                    <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} tickFormatter={(value) => `${Number(value * 100).toFixed(0)}%`} width={46} />
                    <Tooltip contentStyle={tooltipStyle} formatter={(value, _name, props) => tooltipReturn(value, props.payload?.validityLevel)} labelFormatter={(_, payload) => payload?.[0]?.payload?.strategyName || ""} />
                    <Bar dataKey="value" name="近3月收益">
                      {barRows.map((row) => (
                        <Cell key={row.strategyName} fill={barColor(row.return3M, row.validityLevel)} opacity={row.validityLevel === "可信" ? 0.92 : 0.62} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyBox text="暂无周期收益汇总。" />
            )}
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <h3 className="text-sm font-semibold">近 1 年回撤对比</h3>
            <div className="mt-3 space-y-3">
              {drawdownRows.length ? drawdownRows.map((row) => (
                <div key={row.strategyName}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                    <span className="truncate text-[var(--text-secondary)]">{row.strategyName}</span>
                    <span className="finance-number text-[var(--color-success)]">{formatPercent(row.maxDrawdown1Y)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--bg-card)]">
                    <div className="h-full rounded-full bg-[var(--color-success)]" style={{ width: `${Math.min(100, Math.max(4, (row.maxDrawdown1Y || 0) * 250))}%` }} />
                  </div>
                </div>
              )) : <EmptyBox text="暂无回撤数据。" compact />}
            </div>
          </div>

          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <h3 className="text-sm font-semibold">收益热力图</h3>
            <div className="mt-3 overflow-x-auto scrollbar-thin">
              <div className="min-w-[620px]">
                <div className="grid grid-cols-[180px_repeat(4,1fr)] text-xs text-[var(--text-tertiary)]">
                  <div className="p-2">策略</div>
                  {["1M", "3M", "6M", "1Y"].map((period) => (
                    <div key={period} className="p-2 text-right">{period}</div>
                  ))}
                </div>
                {buildHeatmapRows(data).map((row) => (
                  <div key={row.strategyName} className="grid grid-cols-[180px_repeat(4,1fr)] border-t border-[var(--border-subtle)]">
                    <Link href={`/strategy-performance?strategy=${encodeURIComponent(row.strategyName)}`} className="truncate p-2 text-sm hover:text-[var(--color-primary)]">
                      {row.strategyName}
                    </Link>
                    {row.periods.map((cell) => (
                      <div key={cell.period} className={`p-2 text-right text-sm ${heatmapClass(cell.returnRate, cell.validityLevel)}`} title={cell.validityLevel}>
                        {cell.validityLevel === "样本不足" || cell.validityLevel === "数据不足" ? cell.validityLevel : formatPercent(cell.returnRate)}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <p className="text-xs text-[var(--text-tertiary)]">
          策略收益用于评估策略近期适配度，不代表未来收益。样本不足或数据不足的策略不参与有效性排序。
        </p>
      </CardContent>
    </Card>
  );
}

function RadarStat({ title, item, valueKey = "return" }: { title: string; item?: DashboardStrategyPerformanceBrief | null; valueKey?: "return" | "drawdown" }) {
  const value = valueKey === "drawdown" ? item?.maxDrawdown : item?.returnRate;
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <p className="text-xs text-[var(--text-tertiary)]">{title}</p>
      <div className="mt-2 truncate text-base font-semibold">{item?.strategyName || "暂无"}</div>
      <div className={`finance-number mt-2 text-2xl font-semibold ${valueKey === "drawdown" ? "text-[var(--color-success)]" : returnTextColor(value)}`}>
        {item ? formatPercent(value) : "--"}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <Badge tone={item?.validityLevel === "可信" ? "success" : "muted"}>{item?.validityLevel || "数据不足"}</Badge>
        {item?.sourceConfidence && <Badge tone={item.sourceConfidence === "低" ? "warning" : "muted"}>{item.sourceConfidence}可信</Badge>}
      </div>
    </div>
  );
}

function mergeNavSeries(data: DashboardStrategyPerformance | null) {
  const byDate = new Map<string, Record<string, string | number | null>>();
  data?.navSeries.forEach((series) => {
    series.points.forEach((point) => {
      const row = byDate.get(point.date) || { date: point.date.slice(5) };
      row[series.strategyName] = Number(point.nav.toFixed(4));
      byDate.set(point.date, row);
    });
  });
  return Array.from(byDate.entries()).sort(([a], [b]) => a.localeCompare(b)).map(([, row]) => row);
}

function buildHeatmapRows(data: DashboardStrategyPerformance | null) {
  const names = Array.from(new Set((data?.heatmap || []).map((cell) => cell.strategyName))).slice(0, 9);
  return names.map((strategyName) => ({
    strategyName,
    periods: ["1M", "3M", "6M", "1Y"].map((period) => data?.heatmap.find((cell) => cell.strategyName === strategyName && cell.period === period) || {
      strategyName,
      period,
      returnRate: null,
      validityLevel: "数据不足"
    })
  }));
}

function tooltipReturn(value: unknown, validity?: string) {
  if (validity === "样本不足" || validity === "数据不足") return validity;
  const number = Number(value);
  if (Number.isNaN(number)) return "--";
  return formatPercent(number);
}

function barColor(value?: number | null, validity?: string) {
  if (validity === "样本不足" || validity === "数据不足") return "var(--text-tertiary)";
  if ((value || 0) >= 0) return "var(--color-danger)";
  return "var(--color-success)";
}

function heatmapClass(value?: number | null, validity?: string) {
  if (validity === "样本不足" || validity === "数据不足") return "bg-[var(--bg-card)] text-[var(--text-tertiary)]";
  if ((value || 0) > 0.05) return "bg-[rgba(230,69,69,0.22)] text-[var(--color-danger)]";
  if ((value || 0) > 0) return "bg-[rgba(230,69,69,0.1)] text-[var(--color-danger)]";
  if ((value || 0) < 0) return "bg-[rgba(24,160,88,0.15)] text-[var(--color-success)]";
  return "bg-[var(--bg-card)] text-[var(--text-secondary)]";
}

function returnTextColor(value?: number | null) {
  if (value === undefined || value === null) return "text-[var(--text-tertiary)]";
  if (value >= 0) return "text-[var(--color-danger)]";
  return "text-[var(--color-success)]";
}

function EmptyBox({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 text-center text-sm text-[var(--text-tertiary)] ${compact ? "min-h-20" : "min-h-[220px]"}`}>
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
