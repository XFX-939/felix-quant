"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { BacktestResult } from "@/lib/types";

export function BacktestChart({ result, height = 320 }: { result: BacktestResult; height?: number }) {
  const drawdowns = result.result_json.drawdown_curve;
  if (!result.result_json.equity_curve.length) {
    return (
      <div className="flex min-h-[320px] items-center justify-center rounded-md border border-dashed border-[var(--border-strong)] bg-[var(--bg-elevated)] text-sm text-[var(--text-tertiary)]">
        暂无净值曲线数据，请先执行回测并生成 strategy_nav_daily。
      </div>
    );
  }
  const initialValue = result.result_json.initial_cash || result.result_json.equity_curve[0]?.value || 1;
  const data = result.result_json.equity_curve.map((point, index) => ({
    date: point.date,
    label: point.date.slice(5),
    nav: Number((point.value / initialValue).toFixed(4)),
    cumulativeReturn: Number(((point.value / initialValue - 1) * 100).toFixed(2)),
    dailyReturn: Number((point.return * 100).toFixed(2)),
    drawdown: Math.round((drawdowns[index]?.value || 0) * 10000) / 100
  }));
  return (
    <div className="space-y-4">
      <div className="text-xs text-[var(--text-tertiary)]">当前回测结果暂未包含正式基准净值，图中展示策略净值、回撤与每日收益。</div>
      <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} />
          <YAxis
            yAxisId="nav"
            tick={{ fill: "var(--text-tertiary)", fontSize: 12 }}
            tickLine={false}
            width={58}
          />
          <YAxis yAxisId="drawdown" orientation="right" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} />
          <Tooltip
            contentStyle={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: 6,
              color: "var(--text-primary)"
            }}
          />
          <Line yAxisId="nav" type="monotone" dataKey="nav" stroke="var(--chart-primary)" strokeWidth={2} dot={false} name="策略净值" />
          <Line yAxisId="drawdown" type="monotone" dataKey="drawdown" stroke="var(--chart-success)" strokeWidth={1.6} dot={false} name="回撤%" />
        </LineChart>
      </ResponsiveContainer>
      </div>
      <div style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} />
            <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} width={48} />
            <Tooltip
              contentStyle={{
                background: "var(--bg-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: 6,
                color: "var(--text-primary)"
              }}
            />
            <Bar dataKey="dailyReturn" name="每日收益%" fill="var(--chart-primary)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
