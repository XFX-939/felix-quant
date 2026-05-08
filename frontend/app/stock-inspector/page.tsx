"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatNumber, formatPctPoint } from "@/lib/format";
import type { Stock } from "@/lib/types";

export default function StockInspectorIndexPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .stocks({ search, limit: 80 })
      .then((data) => {
        setStocks(data.slice(0, 80));
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "股票列表加载失败"));
  }, [search]);

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return stocks;
    return stocks.filter((stock) => stock.code.toLowerCase().includes(keyword) || stock.name.toLowerCase().includes(keyword) || stock.industry.includes(search.trim()));
  }, [search, stocks]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm text-[var(--text-tertiary)]">Stock Inspector</div>
          <h1 className="mt-1 text-xl font-semibold">一键诊股</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            基于基本面、技术面、情绪面、资金面、风险面和市场状态的个股诊断与研究评级工具。
          </p>
        </div>
        <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          评级仅用于个人量化研究和投资复盘，不构成任何投资建议或交易指令。
        </div>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle>选择诊断标的</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative max-w-xl">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[var(--text-tertiary)]" aria-hidden />
            <Input className="pl-9" placeholder="输入股票代码、名称或行业" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {filtered.map((stock) => (
          <Link key={stock.code} href={`/stock-inspector/${stock.code}`} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--bg-card-hover)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-semibold">{stock.name}</div>
                <div className="finance-number mt-1 text-xs text-[var(--color-primary)]">{stock.code}</div>
              </div>
              <Badge tone="muted">{stock.industry || "未分类"}</Badge>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <MiniMetric label="价格" value={formatNumber(stock.current_price)} />
              <MiniMetric label="涨跌幅" value={formatPctPoint(stock.pct_change)} />
            </div>
            <div className="mt-3 text-xs text-[var(--text-tertiary)]">打开研报式评级摘要、风险因素和评级调整条件</div>
          </Link>
        ))}
        {!filtered.length && <div className="py-10 text-sm text-[var(--text-tertiary)]">暂无匹配股票。</div>}
      </div>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
      <div className="text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 text-[var(--text-primary)]">{value}</div>
    </div>
  );
}
