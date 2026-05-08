"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function BacktestBars({
  data,
  height = 220
}: {
  data: Array<{ strategy_name: string; total_return: number; max_drawdown: number; win_rate: number }>;
  height?: number;
}) {
  const chartData = data.map((item) => ({
    name: item.strategy_name,
    total_return: Number((item.total_return * 100).toFixed(2)),
    max_drawdown: Number((item.max_drawdown * 100).toFixed(2)),
    win_rate: Number((item.win_rate * 100).toFixed(2))
  }));
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} />
          <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: 6,
              color: "var(--text-primary)"
            }}
          />
          <Bar dataKey="total_return" name="收益%" fill="var(--chart-primary)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="max_drawdown" name="回撤%" fill="var(--chart-success)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
