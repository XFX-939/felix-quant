"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { BacktestChart } from "@/components/charts/BacktestChart";
import { PriceVolumeChart } from "@/components/charts/PriceVolumeChart";
import { RiskBadge } from "@/components/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatNumber, formatPctPoint, formatPercent } from "@/lib/format";
import type { BacktestResult, PricePoint, Review, Signal, Stock } from "@/lib/types";

export default function StockDetailPage() {
  const params = useParams<{ code: string }>();
  const code = params.code;
  const [stock, setStock] = useState<Stock | null>(null);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    Promise.all([
      api.stock(code),
      api.prices(code, { limit: 180 }),
      api.signals({ search: code, limit: 50 }),
      api.reviews({ stock_code: code }),
      api.backtestResults()
    ])
      .then(([stockData, priceData, signalData, reviewData, backtestData]) => {
        setStock(stockData);
        setPrices(priceData);
        setSignals(signalData.filter((signal) => signal.stock_code === code));
        setReviews(reviewData);
        setBacktests(backtestData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "详情加载失败"));
  }, [code]);

  const latestSignal = signals[0] || stock?.latest_signal;
  const latestBacktest = backtests[0];
  const indicators = stock?.indicators || {};

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-sm text-muted-foreground">股票详情</div>
          <h1 className="mt-1 text-xl font-semibold">
            {stock?.code || code} {stock?.name || ""}
          </h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href={`/stock-inspector/${code}`} className="inline-flex h-9 items-center justify-center rounded-md border border-[var(--color-primary)] bg-[var(--color-primary-soft)] px-3 text-sm text-[var(--color-primary)] hover:bg-[var(--bg-card-hover)]">
            一键诊股
          </Link>
          <Link href={`/reviews?stock=${code}`} className="inline-flex h-9 items-center justify-center rounded-md border border-[var(--border-strong)] px-3 text-sm text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
            写复盘
          </Link>
        </div>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <InfoCard title="当前价格" value={formatNumber(stock?.current_price)} muted={`涨跌幅 ${formatPctPoint(stock?.pct_change)}`} />
        <InfoCard title="所属行业" value={stock?.industry || "-"} muted={stock?.market || ""} />
        <InfoCard title="近60日收益" value={formatPercent(indicators.ret60 as number | null)} muted={`MA20 ${formatNumber(indicators.ma20 as number | null)}`} />
        <InfoCard title="近60日回撤" value={formatPercent(indicators.max_drawdown_60 as number | null)} muted={`波动率 ${formatPercent(indicators.volatility_60 as number | null)}`} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>K线趋势与成交量</CardTitle>
          </CardHeader>
          <CardContent>
            <PriceVolumeChart data={prices} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>入选依据与风险因子</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {latestSignal ? (
              <>
                <div className="flex items-center justify-between rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
                  <span>{latestSignal.strategy_name}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono">{latestSignal.score.toFixed(1)}</span>
                    <RiskBadge level={latestSignal.risk_level} />
                  </div>
                </div>
                <div>
                  <div className="mb-2 text-xs text-muted-foreground">入选原因</div>
                  <p className="leading-6">{latestSignal.reason}</p>
                </div>
                <div>
                  <div className="mb-2 text-xs text-muted-foreground">风险理由</div>
                  <p className="leading-6 text-[var(--color-warning)]">{latestSignal.risk_reason}</p>
                </div>
              </>
            ) : (
              <div className="py-12 text-center text-muted-foreground">暂无入选信号</div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>历史回测表现</CardTitle>
          </CardHeader>
          <CardContent>
            {latestBacktest ? (
              <div className="space-y-3">
                <div className="grid gap-2 md:grid-cols-4">
                  <Metric label="总收益" value={formatPercent(latestBacktest.total_return)} />
                  <Metric label="最大回撤" value={formatPercent(latestBacktest.max_drawdown)} />
                  <Metric label="胜率" value={formatPercent(latestBacktest.win_rate)} />
                  <Metric label="交易次数" value={String(latestBacktest.trade_count)} />
                </div>
                <BacktestChart result={latestBacktest} height={260} />
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-muted-foreground">暂无回测记录</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>策略信号历史</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto scrollbar-thin">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日期</TableHead>
                    <TableHead>策略</TableHead>
                    <TableHead>评分</TableHead>
                    <TableHead>风险</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {signals.map((signal) => (
                    <TableRow key={signal.id}>
                      <TableCell>{signal.date}</TableCell>
                      <TableCell>{signal.strategy_name}</TableCell>
                      <TableCell className="font-mono">{signal.score.toFixed(1)}</TableCell>
                      <TableCell>
                        <RiskBadge level={signal.risk_level} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {!signals.length && (
                    <TableRow>
                      <TableCell colSpan={4} className="py-8 text-center text-muted-foreground">
                        暂无信号历史
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>最近复盘记录</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {reviews.map((review) => (
            <div key={review.id} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <div className="flex items-center justify-between text-sm">
                <span>{review.date}</span>
                <Badge tone={review.action_taken ? "success" : "muted"}>{review.action_taken ? "已执行" : "未执行"}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{review.summary || review.reason}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {review.tags.map((tag) => (
                  <Badge key={tag} tone="muted">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
          {!reviews.length && <div className="py-8 text-sm text-muted-foreground">暂无复盘记录</div>}
        </CardContent>
      </Card>
    </div>
  );
}

function InfoCard({ title, value, muted }: { title: string; value: string; muted: string }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="text-xs text-muted-foreground">{title}</div>
        <div className="mt-3 text-lg font-semibold">{value}</div>
        <div className="mt-1 text-xs text-muted-foreground">{muted}</div>
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 font-mono text-sm">{value}</div>
    </div>
  );
}
