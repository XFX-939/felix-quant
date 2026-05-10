"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, ExternalLink, FileText, Play, Save, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type { BacktestResult, DashboardSummary, Strategy, StrategyPerformanceSummary, StrategySource } from "@/lib/types";

const emptyStrategy = {
  name: "",
  description: "",
  type: "多因子",
  enabled: true,
  parameters: {
    min_score: 60
  }
};

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [performanceSummary, setPerformanceSummary] = useState<StrategyPerformanceSummary | null>(null);
  const [backtests, setBacktests] = useState<BacktestResult[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [form, setForm] = useState({ ...emptyStrategy, parameters: JSON.stringify(emptyStrategy.parameters, null, 2) });
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedSource, setSelectedSource] = useState<StrategySource | null>(null);

  async function load() {
    const [data, dashboardData, backtestData, performanceData] = await Promise.all([
      api.strategies(),
      api.dashboard(),
      api.backtestResults(),
      api.strategyPerformanceSummary().catch(() => null)
    ]);
    setStrategies(data);
    setSummary(dashboardData);
    setBacktests(backtestData);
    setPerformanceSummary(performanceData);
    setDrafts(Object.fromEntries(data.map((strategy) => [strategy.id, JSON.stringify(strategy.parameters, null, 2)])));
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "策略加载失败"));
  }, []);

  const enabledCount = useMemo(() => strategies.filter((strategy) => strategy.enabled).length, [strategies]);

  async function createStrategy() {
    setMessage(null);
    setError(null);
    try {
      const parameters = JSON.parse(form.parameters);
      await api.createStrategy({
        name: form.name,
        description: form.description,
        type: form.type,
        enabled: form.enabled,
        parameters
      });
      setForm({ ...emptyStrategy, parameters: JSON.stringify(emptyStrategy.parameters, null, 2) });
      await load();
      setMessage("策略已创建");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  async function saveStrategy(strategy: Strategy) {
    setMessage(null);
    setError(null);
    try {
      const parameters = JSON.parse(drafts[strategy.id] || "{}");
      await api.updateStrategy(strategy.id, { ...strategy, parameters });
      await load();
      setMessage(`${strategy.name} 已保存`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function toggleStrategy(strategy: Strategy) {
    await api.updateStrategy(strategy.id, { ...strategy, enabled: !strategy.enabled });
    await load();
  }

  async function runStrategy(strategy: Strategy) {
    setMessage(null);
    setError(null);
    try {
      const result = await api.runStrategy(strategy.id);
      setMessage(`${strategy.name} 已运行，生成 ${result.signals_created} 条候选信号`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行失败");
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-xl font-semibold">策略管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">管理策略启用状态、适用市场环境、参数配置和复盘表现。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-sm text-muted-foreground">启用 {enabledCount} / {strategies.length}</div>
          <Link
            href="/backtest?mode=batch"
            className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--color-primary-soft)] px-3 text-sm text-[var(--color-primary)] hover:border-[var(--border-strong)]"
          >
            <BarChart3 className="h-4 w-4" />
            批量回测选中策略
          </Link>
        </div>
      </div>

      {message && <div className="rounded-md border border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] p-3 text-sm text-[var(--color-success)]">{message}</div>}
      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <div className="grid gap-5 xl:grid-cols-[1fr_0.65fr]">
        <div className="space-y-4">
          {strategies.map((strategy) => (
            <Card key={strategy.id}>
              <CardHeader className="flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <CardTitle>{strategy.name}</CardTitle>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{strategy.description}</p>
                </div>
                <div className="flex gap-2">
                  <Badge tone={strategy.enabled ? "success" : "muted"}>{strategy.enabled ? "启用" : "停用"}</Badge>
                  <Badge tone="muted">{strategy.type}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <StrategySourceStrip source={strategy.source} onOpen={() => strategy.source && setSelectedSource(strategy.source)} />
                <StrategyBusinessSummary strategy={strategy} summary={summary} backtests={backtests} performanceSummary={performanceSummary} />
                <details className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
                  <summary className="cursor-pointer text-sm font-medium text-[var(--color-primary)]">高级配置</summary>
                  <Textarea
                    value={drafts[strategy.id] || ""}
                    onChange={(event) => setDrafts((current) => ({ ...current, [strategy.id]: event.target.value }))}
                    spellCheck={false}
                    className="mt-3 min-h-36 font-mono text-xs"
                  />
                </details>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" onClick={() => toggleStrategy(strategy)}>
                    {strategy.enabled ? "停用" : "启用"}
                  </Button>
                  <Button variant="outline" onClick={() => saveStrategy(strategy)}>
                    <Save className="h-4 w-4" />
                    保存参数
                  </Button>
                  <Button onClick={() => runStrategy(strategy)}>
                    <Play className="h-4 w-4" />
                    运行策略
                  </Button>
                  <Link
                    href={`/strategy-performance?strategy=${encodeURIComponent(strategy.name)}`}
                    className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--border-subtle)] px-3 text-sm text-[var(--text-secondary)] hover:text-[var(--color-primary)]"
                  >
                    <BarChart3 className="h-4 w-4" />
                    查看收益走势
                  </Link>
                  <Button variant="outline" onClick={() => strategy.source && setSelectedSource(strategy.source)} disabled={!strategy.source}>
                    <FileText className="h-4 w-4" />
                    查看来源
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>创建策略</CardTitle>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">仅用于本地研究配置，创建后仍需回测验证和人工复核。</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField label="策略名称" help="建议使用能说明逻辑的中文名称。">
              <Input placeholder="例如：低回撤趋势策略" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
            </FormField>
            <FormField label="策略描述" help="说明信号来源、适用市场和主要风险。">
              <Textarea
                placeholder="描述策略逻辑、适用场景和风控边界"
                value={form.description}
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              />
            </FormField>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField label="策略类型" help="用于策略筛选和收益归类。">
                <Select value={form.type} onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}>
                  <option value="趋势">趋势</option>
                  <option value="均值回归">均值回归</option>
                  <option value="量价">量价</option>
                  <option value="多因子">多因子</option>
                  <option value="短线龙头">短线龙头</option>
                </Select>
              </FormField>
              <FormField label="启用状态" help="新策略建议先仅复盘，通过验证后再参与日常观察。">
                <Select value={form.enabled ? "true" : "false"} onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.value === "true" }))}>
                  <option value="true">启用</option>
                  <option value="false">仅复盘</option>
                </Select>
              </FormField>
            </div>
            <FormField label="参数 JSON" help="必须是合法 JSON；高级参数建议在回测验证后再调整。">
              <Textarea
                value={form.parameters}
                onChange={(event) => setForm((current) => ({ ...current, parameters: event.target.value }))}
                spellCheck={false}
                className="min-h-44 font-mono text-xs"
              />
            </FormField>
            <Button className="w-full" onClick={createStrategy} disabled={!form.name.trim()}>
              创建策略
            </Button>
          </CardContent>
        </Card>
      </div>

      <StrategySourceDrawer source={selectedSource} onClose={() => setSelectedSource(null)} />
    </div>
  );
}

function FormField({ label, help, children }: { label: string; help: string; children: ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium">{label}</span>
      {children}
      <span className="block text-xs leading-5 text-[var(--text-tertiary)]">{help}</span>
    </label>
  );
}

function StrategySourceStrip({ source, onOpen }: { source?: StrategySource | null; onOpen: () => void }) {
  if (!source) {
    return (
      <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--text-tertiary)]">
        来源信息待补齐
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="warning">{sourceLabel(source)}</Badge>
          <Badge tone={source.confidenceLevel === "高" ? "success" : source.confidenceLevel === "低" ? "danger" : "warning"}>
            {source.confidenceLevel}可信
          </Badge>
          <Badge tone={source.isVerifiedByBacktest ? "success" : "muted"}>{source.backtestValidity}</Badge>
        </div>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--text-secondary)]">{source.sourceSummary}</p>
      </div>
      <Button variant="outline" onClick={onOpen}>
        <FileText className="h-4 w-4" />
        来源详情
      </Button>
    </div>
  );
}

function StrategySourceDrawer({ source, onClose }: { source: StrategySource | null; onClose: () => void }) {
  if (!source) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/45" role="dialog" aria-modal="true">
      <button className="absolute inset-0 h-full w-full cursor-default" aria-label="关闭来源详情" onClick={onClose} />
      <aside className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto border-l border-[var(--border-subtle)] bg-[var(--bg-card)] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-primary)]">Strategy Source</p>
            <h2 className="mt-2 text-xl font-semibold">{source.strategyName}</h2>
            <p className="mt-1 text-sm text-[var(--text-tertiary)]">{source.sourceName}</p>
          </div>
          <Button variant="outline" onClick={onClose} aria-label="关闭来源详情">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <Info label="来源类型" value={sourceLabel(source)} />
          <Info label="来源可信度" value={`${source.confidenceLevel}可信`} tone={source.confidenceLevel === "高" ? "success" : source.confidenceLevel === "低" ? "danger" : "warning"} />
          <Info label="回测验证" value={source.backtestValidity} tone={source.isVerifiedByBacktest ? "success" : "warning"} />
        </div>

        <div className="mt-5 space-y-4 text-sm leading-6">
          <SourceSection title="出处">
            <div className="space-y-1 text-[var(--text-secondary)]">
              <p>标题：{source.sourceTitle || "未绑定明确公开标题"}</p>
              <p>机构 / 作者：{source.sourceAuthor || source.sourceName}</p>
              <p>发布时间：{source.publishDate || "未记录"}</p>
              {source.sourceUrl ? (
                <a className="inline-flex items-center gap-1 text-[var(--color-primary)] hover:underline" href={source.sourceUrl} target="_blank" rel="noreferrer">
                  公开链接
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              ) : (
                <p className="text-[var(--text-tertiary)]">暂无公开链接；不展示机构背书。</p>
              )}
            </div>
          </SourceSection>

          <SourceSection title="原始思想">
            <p>{source.originalIdea}</p>
          </SourceSection>
          <SourceSection title="A 股本地化改造">
            <p>{source.localAdaptation}</p>
          </SourceSection>
          <SourceSection title="当前实现差异">
            <p>{source.implementationNotes}</p>
          </SourceSection>
          <SourceList title="数据需求" items={source.requiredData} />
          <SourceList title="当前缺失数据" items={source.missingData} tone="warning" />
          <SourceList title="局限性" items={source.limitations} tone="danger" />
          <SourceList title="标签" items={source.tags} />

          <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs leading-5 text-[var(--text-tertiary)]">
            本系统为个人量化研究和投资复盘工具。若来源为公开研究启发或本地化改造，不等同于原机构原始策略；策略信号和收益表现均需结合数据质量、回测可信度与人工确认。
          </div>
        </div>
      </aside>
    </div>
  );
}

function SourceSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-2 text-[var(--text-secondary)]">{children}</div>
    </section>
  );
}

function SourceList({ title, items, tone }: { title: string; items: string[]; tone?: "warning" | "danger" }) {
  const color = tone === "danger" ? "text-[var(--color-danger)]" : tone === "warning" ? "text-[var(--color-warning)]" : "text-[var(--text-secondary)]";
  return (
    <SourceSection title={title}>
      {items.length ? (
        <ul className={`list-disc space-y-1 pl-5 ${color}`}>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[var(--text-tertiary)]">暂无</p>
      )}
    </SourceSection>
  );
}

function StrategyBusinessSummary({
  strategy,
  summary,
  backtests,
  performanceSummary
}: {
  strategy: Strategy;
  summary: DashboardSummary | null;
  backtests: BacktestResult[];
  performanceSummary: StrategyPerformanceSummary | null;
}) {
  const health = summary?.strategy_health?.find((item) => item.strategyName === strategy.name);
  const latest = backtests.find((item) => item.strategy_name === strategy.name);
  const performance = performanceSummary?.strategies.find((item) => item.strategyName === strategy.name);
  const params = Object.entries(strategy.parameters || {})
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" / ");
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Info label="适用市场状态" value={marketApplicability(strategy.name)} />
      <Info label="今日状态" value={health?.status || (strategy.enabled ? "观察" : "暂停")} tone={health?.status === "有效" ? "success" : health?.status === "暂停" ? "danger" : "warning"} />
      <Info label="状态原因" value={health?.reason || "等待策略运行诊断"} wide />
      <Info label="最近回测可信度" value={latest?.validity?.validityLevel || "暂无"} tone={latest?.validity?.validityLevel === "可信" ? "success" : "warning"} />
      <Info label="近1月收益" value={performanceValue(performance?.periods["1M"]?.returnRate, performance?.periods["1M"]?.validityLevel)} tone={returnTone(performance?.periods["1M"]?.returnRate)} />
      <Info label="近3月收益" value={performanceValue(performance?.periods["3M"]?.returnRate, performance?.periods["3M"]?.validityLevel)} tone={returnTone(performance?.periods["3M"]?.returnRate)} />
      <Info label="近1年最大回撤" value={formatPercent(performance?.periods["1Y"]?.maxDrawdown)} tone="warning" />
      <Info label="主观察候选" value={`${health?.mainCount ?? 0} 只`} />
      <Info label="高风险比例" value={formatPercent(health?.highRiskRatio, 0)} />
      <Info label="核心参数" value={params || "使用默认参数"} wide />
    </div>
  );
}

function performanceValue(value?: number | null, validity?: string) {
  if (validity === "样本不足") return "样本不足";
  return formatPercent(value);
}

function returnTone(value?: number | null): "success" | "warning" | "danger" | undefined {
  if (value === undefined || value === null) return undefined;
  if (value > 0) return "danger";
  if (value < 0) return "success";
  return undefined;
}

function Info({ label, value, tone, wide = false }: { label: string; value: string; tone?: "success" | "warning" | "danger"; wide?: boolean }) {
  const color = tone === "success" ? "text-[var(--color-success)]" : tone === "danger" ? "text-[var(--color-danger)]" : tone === "warning" ? "text-[var(--color-warning)]" : "text-[var(--text-primary)]";
  return (
    <div className={`rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 ${wide ? "md:col-span-2" : ""}`}>
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className={`mt-1 text-sm font-medium ${color}`}>{value}</div>
    </div>
  );
}

function marketApplicability(name: string) {
  if (name.includes("低波")) return "RiskOff / Choppy / Panic";
  if (name.includes("质量")) return "Choppy / Recovery / RiskOff";
  if (name.includes("热点") || name.includes("龙头")) return "RiskOn / Recovery";
  if (name.includes("趋势") || name.includes("均线")) return "RiskOn / Recovery";
  return "Choppy / Recovery";
}

function sourceLabel(source: StrategySource) {
  const labels: Record<StrategySource["sourceType"], string> = {
    academic_paper: "公开论文改造",
    broker_research: "券商研报启发",
    quant_firm_research: "量化机构公开研究启发",
    public_blog: "公开文章启发",
    book: "书籍启发",
    open_source: "开源项目启发",
    self_developed: "自研策略",
    inspired_by: "公开思路改造",
    unknown: "来源待核验"
  };
  return labels[source.sourceType] || source.sourceName;
}
