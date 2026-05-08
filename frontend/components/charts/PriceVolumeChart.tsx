"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { PricePoint } from "@/lib/types";

function withMovingAverage(data: PricePoint[]) {
  return data.map((point, index) => {
    const ma20Slice = data.slice(Math.max(0, index - 19), index + 1);
    const ma60Slice = data.slice(Math.max(0, index - 59), index + 1);
    const ma20 = ma20Slice.reduce((sum, item) => sum + item.close, 0) / ma20Slice.length;
    const ma60 = ma60Slice.reduce((sum, item) => sum + item.close, 0) / ma60Slice.length;
    return {
      ...point,
      date: point.date.slice(5),
      ma20: Number(ma20.toFixed(2)),
      ma60: Number(ma60.toFixed(2)),
      volumeBar: Math.round(point.volume / 10000)
    };
  });
}

export function PriceVolumeChart({ data, height = 320 }: { data: PricePoint[]; height?: number }) {
  const chartData = withMovingAverage(data);
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 12 }} tickLine={false} />
          <YAxis
            yAxisId="price"
            tick={{ fill: "var(--text-tertiary)", fontSize: 12 }}
            tickLine={false}
            width={48}
          />
          <YAxis yAxisId="volume" orientation="right" hide />
          <Tooltip
            contentStyle={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: 6,
              color: "var(--text-primary)"
            }}
          />
          <Bar yAxisId="volume" dataKey="volumeBar" fill="var(--chart-muted)" opacity={0.35} />
          <Line yAxisId="price" type="monotone" dataKey="close" stroke="var(--chart-primary)" strokeWidth={2} dot={false} name="收盘" />
          <Line yAxisId="price" type="monotone" dataKey="ma20" stroke="var(--chart-warning)" strokeWidth={1.5} dot={false} name="MA20" />
          <Line yAxisId="price" type="monotone" dataKey="ma60" stroke="var(--chart-secondary)" strokeWidth={1.5} dot={false} name="MA60" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
