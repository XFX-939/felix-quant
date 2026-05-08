"use client";

import { useEffect, useMemo, useState } from "react";
import { Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { Review, Signal } from "@/lib/types";

const tags = ["成功", "失败", "误判", "纪律问题", "策略问题", "市场问题"];

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReviewsPage() {
  const [presetStock, setPresetStock] = useState("");
  const [reviews, setReviews] = useState<Review[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [filters, setFilters] = useState({ date: "", stock_code: presetStock, tag: "all" });
  const [form, setForm] = useState({
    date: today(),
    stock_code: presetStock,
    signal_id: "",
    action_taken: "false",
    reason: "",
    result: "",
    summary: "",
    tags: [] as string[]
  });
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const stock = new URLSearchParams(window.location.search).get("stock") || "";
    setPresetStock(stock);
    setFilters((current) => ({ ...current, stock_code: stock }));
    setForm((current) => ({ ...current, stock_code: stock }));
  }, []);

  async function load() {
    const [reviewData, signalData, statData] = await Promise.all([
      api.reviews(filters),
      api.todaySignals(),
      api.reviewStats()
    ]);
    setReviews(reviewData);
    setSignals(signalData);
    setStats(statData);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "复盘加载失败"));
  }, [filters.date, filters.stock_code, filters.tag]);

  const selectedSignal = useMemo(
    () => signals.find((signal) => String(signal.id) === form.signal_id),
    [signals, form.signal_id]
  );

  useEffect(() => {
    if (selectedSignal) {
      setForm((current) => ({ ...current, stock_code: selectedSignal.stock_code }));
    }
  }, [selectedSignal]);

  async function submitReview() {
    setError(null);
    setMessage(null);
    try {
      await api.createReview({
        date: form.date,
        stock_code: form.stock_code,
        signal_id: form.signal_id ? Number(form.signal_id) : null,
        action_taken: form.action_taken === "true",
        reason: form.reason,
        result: form.result,
        summary: form.summary,
        tags: form.tags
      });
      setForm({
        date: today(),
        stock_code: presetStock,
        signal_id: "",
        action_taken: "false",
        reason: "",
        result: "",
        summary: "",
        tags: []
      });
      setMessage("复盘记录已保存");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function removeReview(id: number) {
    await api.deleteReview(id);
    await load();
  }

  function toggleTag(tag: string) {
    setForm((current) => ({
      ...current,
      tags: current.tags.includes(tag) ? current.tags.filter((item) => item !== tag) : [...current.tags, tag]
    }));
  }

  const tagCounts = (stats.tag_counts || {}) as Record<string, number>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">复盘</h1>
        <p className="mt-1 text-sm text-muted-foreground">记录每日策略运行、候选变化、风险判断和人工结论。</p>
      </div>

      {message && <div className="rounded-md border border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] p-3 text-sm text-[var(--color-success)]">{message}</div>}
      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="复盘总数" value={String(stats.total ?? 0)} />
        <Metric label="已执行" value={String(stats.executed ?? 0)} />
        <Metric label="未执行" value={String(stats.not_executed ?? 0)} />
        <Metric label="主要标签" value={Object.entries(tagCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || "-"} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>新增复盘</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input type="date" value={form.date} onChange={(event) => setForm((current) => ({ ...current, date: event.target.value }))} />
            <Select value={form.signal_id} onChange={(event) => setForm((current) => ({ ...current, signal_id: event.target.value }))}>
              <option value="">选择当日策略信号</option>
              {signals.map((signal) => (
                <option key={signal.id} value={signal.id}>
                  {signal.stock_code} {signal.stock_name} / {signal.strategy_name}
                </option>
              ))}
            </Select>
            <Input
              placeholder="股票代码"
              value={form.stock_code}
              onChange={(event) => setForm((current) => ({ ...current, stock_code: event.target.value }))}
            />
            <Select value={form.action_taken} onChange={(event) => setForm((current) => ({ ...current, action_taken: event.target.value }))}>
              <option value="false">未执行</option>
              <option value="true">已执行</option>
            </Select>
            <Textarea
              placeholder="执行原因 / 未执行原因"
              value={form.reason}
              onChange={(event) => setForm((current) => ({ ...current, reason: event.target.value }))}
            />
            <Textarea
              placeholder="后续表现"
              value={form.result}
              onChange={(event) => setForm((current) => ({ ...current, result: event.target.value }))}
            />
            <Textarea
              placeholder="经验总结"
              value={form.summary}
              onChange={(event) => setForm((current) => ({ ...current, summary: event.target.value }))}
            />
            <div className="flex flex-wrap gap-2">
              {tags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className={`h-8 rounded-md border px-3 text-xs ${form.tags.includes(tag) ? "border-[var(--border-strong)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]" : "text-[var(--text-tertiary)]"}`}
                  onClick={() => toggleTag(tag)}
                >
                  {tag}
                </button>
              ))}
            </div>
            <Button className="w-full" onClick={submitReview} disabled={!form.stock_code.trim()}>
              保存复盘
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardContent className="grid gap-3 pt-4 md:grid-cols-3">
              <Input type="date" value={filters.date} onChange={(event) => setFilters((current) => ({ ...current, date: event.target.value }))} />
              <Input
                placeholder="按股票筛选"
                value={filters.stock_code}
                onChange={(event) => setFilters((current) => ({ ...current, stock_code: event.target.value }))}
              />
              <Select value={filters.tag} onChange={(event) => setFilters((current) => ({ ...current, tag: event.target.value }))}>
                <option value="all">全部标签</option>
                {tags.map((tag) => (
                  <option key={tag} value={tag}>
                    {tag}
                  </option>
                ))}
              </Select>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>复盘记录</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto scrollbar-thin">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日期</TableHead>
                      <TableHead>股票</TableHead>
                      <TableHead>执行</TableHead>
                      <TableHead>总结</TableHead>
                      <TableHead>标签</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reviews.map((review) => (
                      <TableRow key={review.id}>
                        <TableCell>{review.date}</TableCell>
                        <TableCell>
                          {review.stock_code} {review.stock_name}
                        </TableCell>
                        <TableCell>
                          <Badge tone={review.action_taken ? "success" : "muted"}>{review.action_taken ? "是" : "否"}</Badge>
                        </TableCell>
                        <TableCell className="max-w-md text-muted-foreground">{review.summary || review.reason}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {review.tags.map((tag) => (
                              <Badge key={tag} tone="muted">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Button variant="ghost" size="icon" aria-label="删除复盘" onClick={() => removeReview(review.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {!reviews.length && (
                      <TableRow>
                        <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                          暂无复盘记录
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-3 text-lg font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}
