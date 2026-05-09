"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { History, Search, Sparkles } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { formatNumber, formatPctPoint } from "@/lib/format";
import type { MarketDataSyncStatus, Stock } from "@/lib/types";

const EXAMPLES = [
  { label: "贵州茅台", value: "贵州茅台" },
  { label: "600519", value: "600519" },
  { label: "宁德时代", value: "宁德时代" },
  { label: "300750", value: "300750" },
  { label: "AI", value: "AI" },
  { label: "银行", value: "银行" }
];

export default function StockInspectorIndexPage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [syncStatus, setSyncStatus] = useState<MarketDataSyncStatus | null>(null);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);

  useEffect(() => {
    Promise.all([api.stocks({ search, limit: 80 }), api.marketDataSyncStatus().catch(() => null)])
      .then(([data, status]) => {
        setStocks(data.slice(0, 80));
        setSyncStatus(status);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "股票列表加载失败"));
  }, [search]);

  useEffect(() => {
    const saved = window.localStorage.getItem("felix-inspector-searches");
    if (!saved) return;
    try {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed)) setRecentSearches(parsed.filter((item): item is string => typeof item === "string").slice(0, 6));
    } catch {
      window.localStorage.removeItem("felix-inspector-searches");
    }
  }, []);

  function chooseKeyword(value: string) {
    setSearch(value);
    const next = [value, ...recentSearches.filter((item) => item !== value)].slice(0, 6);
    setRecentSearches(next);
    window.localStorage.setItem("felix-inspector-searches", JSON.stringify(next));
  }

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
        <CardContent className="space-y-4">
          <div className="relative max-w-2xl">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[var(--text-tertiary)]" aria-hidden />
            <Input className="pl-9" placeholder="输入 600519 / 贵州茅台 / AI / 银行" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1 text-xs text-[var(--text-tertiary)]"><Sparkles className="h-3.5 w-3.5" /> 热门示例</span>
            {EXAMPLES.map((item) => (
              <button key={item.label} type="button" className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--color-primary)]" onClick={() => chooseKeyword(item.value)}>
                {item.label}
              </button>
            ))}
          </div>
          {!!recentSearches.length && (
            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-1 text-xs text-[var(--text-tertiary)]"><History className="h-3.5 w-3.5" /> 最近搜索</span>
              {recentSearches.map((item) => (
                <button key={item} type="button" className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--color-primary)]" onClick={() => setSearch(item)}>
                  {item}
                </button>
              ))}
            </div>
          )}
          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
            当前行情缓存：{syncStatus?.usingCacheDate || syncStatus?.latestTradeDate || "尚未同步"}。若搜索不到股票，请先去数据中心同步全市场股票池。
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
        {!filtered.length && (
          <div className="md:col-span-2 xl:col-span-4">
            <EmptyState
              variant={stocks.length === 0 ? "data-missing" : "no-result"}
              title={stocks.length === 0 ? "股票池尚未同步" : "暂无匹配股票"}
              description={stocks.length === 0 ? "一键诊股需要先有本地股票池和行情缓存，否则无法生成研报式评级。" : "可能是股票池未覆盖、代码格式不正确、关键词过窄，或当前数据还未同步。"}
              reason={stocks.length === 0 ? "请先进入数据中心扩充全市场股票池，再回到本页输入股票代码、名称或行业关键词。" : "可尝试输入 600519、贵州茅台、300750、宁德时代、AI、银行等关键词。"}
              primaryAction={{ label: "去数据中心同步", href: "/data-center" }}
              secondaryAction={{ label: "查看候选池", href: "/candidates" }}
              helpLink={{ label: "阅读一键诊股教程", href: "/guide#stock-inspector" }}
            />
          </div>
        )}
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
