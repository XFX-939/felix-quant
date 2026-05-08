"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { drawdownSeries, performanceSeries } from "@/lib/dashboardMock";
import type { Signal } from "@/lib/types";

const tooltipStyle = {
  background: "var(--bg-card)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 6,
  color: "var(--text-primary)",
  boxShadow: "var(--shadow-card)"
};

const axisTick = { fill: "var(--text-tertiary)", fontSize: 11 };

export function PerformanceChart() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>策略净值曲线</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={performanceSeries} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={axisTick} tickLine={false} />
              <YAxis tick={axisTick} tickLine={false} width={42} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="strategy" name="策略净值" stroke="var(--chart-primary)" strokeWidth={2.2} dot={false} />
              <Line type="monotone" dataKey="benchmark" name="对比指数" stroke="var(--chart-secondary)" strokeWidth={1.6} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export function DrawdownChart() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>最大回撤曲线</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={drawdownSeries} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={axisTick} tickLine={false} />
              <YAxis tick={axisTick} tickLine={false} width={42} />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="drawdown" name="回撤%" stroke="var(--chart-success)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export function RiskDistributionChart({ signals }: { signals: Signal[] }) {
  const data = [
    { name: "高风险", value: signals.filter((signal) => signal.risk_level === "high").length, color: "var(--chart-danger)" },
    { name: "中风险", value: signals.filter((signal) => signal.risk_level === "medium").length, color: "var(--chart-warning)" },
    { name: "低风险", value: signals.filter((signal) => signal.risk_level === "low").length, color: "var(--chart-success)" }
  ].filter((item) => item.value > 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>风险分布</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={82} paddingAngle={3}>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {data.map((item) => (
            <div key={item.name} className="rounded border border-[var(--border-subtle)] p-2">
              <div className="text-[var(--text-tertiary)]">{item.name}</div>
              <div className="finance-number mt-1 text-base font-semibold">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function IndustryDistributionChart({ signals }: { signals: Signal[] }) {
  const industryCounts = signals.reduce<Record<string, number>>((acc, signal) => {
    acc[signal.industry] = (acc[signal.industry] || 0) + 1;
    return acc;
  }, {});
  const data = Object.entries(industryCounts).map(([industry, count]) => ({ industry, count }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>行业分布</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={axisTick} tickLine={false} allowDecimals={false} />
              <YAxis type="category" dataKey="industry" tick={axisTick} tickLine={false} width={72} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="count" name="候选数" fill="var(--chart-primary)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

