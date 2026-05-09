"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BarChart3, Eye, FileText, LayoutGrid, List, PenLine, Search, X } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatNumber, formatPctPoint } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DashboardSummary, RiskLevel, Signal } from "@/lib/types";

type SortKey = "default" | "finalScore" | "hotspotScore" | "capitalFlowScore" | "pctChg" | "amount" | "riskLevel";
type ViewMode = "table" | "card";

type CandidateView = {
  key: string;
  id: number;
  stockCode: string;
  stockName: string;
  industry: string;
  conceptNames: string[];
  strategies: string[];
  candidateTypes: string[];
  candidateLevel?: string;
  close?: number;
  pctChg?: number;
  return5d?: number;
  amount?: number;
  turnoverRate?: number;
  volumeRatio?: number;
  signalScore: number;
  riskPenalty: number;
  finalScore: number;
  strategyConfidence: number;
  diversityPenalty?: number;
  isNewCandidate?: boolean;
  hotspotScore?: number | null;
  trendScore?: number | null;
  valueScore?: number | null;
  qualityScore?: number | null;
  capitalFlowScore?: number | null;
  sectorHotScore?: number | null;
  leaderScore?: number | null;
  riskLevel: RiskLevel;
  suggestedAction: "观察" | "谨慎观察" | "暂不参与";
  candidateMode?: string;
  hardRisk: string[];
  softRisk: string[];
  triggerReasons: string[];
  riskReasons: string[];
  exitRules: string[];
  recentBacktest: string;
  marketRegime?: string;
  sectorRank?: number | null;
  sectorLimitUpCount?: number | null;
  rawFactors: Record<string, unknown>;
  sourceSignals: Signal[];
};

const STRATEGY_OPTIONS = [
  ["all", "全部策略"],
  ["valueMomentum", "价值动量"],
  ["qualityMomentum", "质量动量"],
  ["trendFollowing", "中期趋势"],
  ["marketHotspot", "短线热点"],
  ["dragon", "龙头候选"],
  ["lowBeta", "低波防御"],
  ["ma", "均线趋势"],
  ["lowDrawdown", "低回撤趋势"],
  ["multiFactor", "多因子评分"],
] as const;

const CANDIDATE_TYPE_OPTIONS = ["全部类型", "蓝筹稳健", "趋势增强", "热点题材", "短线强势", "龙头候选", "价值动量", "质量动量", "低波防御", "风险观察"];

export default function CandidatesPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [search, setSearch] = useState("");
  const [strategyType, setStrategyType] = useState("all");
  const [candidateType, setCandidateType] = useState("全部类型");
  const [riskLevel, setRiskLevel] = useState("all");
  const [suggestedAction, setSuggestedAction] = useState("all");
  const [topic, setTopic] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("default");
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [selected, setSelected] = useState<CandidateView | null>(null);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api
        .signals({ only_today: true, search, limit: 160 })
        .then((data) => {
          setSignals(data);
          setError(null);
        })
        .catch((err) => setError(err instanceof Error ? err.message : "候选池加载失败"));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    api.dashboard().then(setDashboardSummary).catch(() => undefined);
  }, []);

  const mergedCandidates = useMemo(() => mergeSignalsByStock(signals), [signals]);

  const topicOptions = useMemo(() => {
    const values = new Set<string>();
    mergedCandidates.forEach((candidate) => {
      if (candidate.industry) values.add(candidate.industry);
      candidate.conceptNames.forEach((item) => values.add(item));
    });
    return Array.from(values).sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
  }, [mergedCandidates]);

  const filteredCandidates = useMemo(() => {
    const filtered = mergedCandidates.filter((candidate) => {
      const keyword = search.trim().toLowerCase();
      const matchesSearch =
        !keyword ||
        candidate.stockCode.toLowerCase().includes(keyword) ||
        candidate.stockName.toLowerCase().includes(keyword);
      const matchesStrategy = strategyType === "all" || matchesStrategyType(candidate, strategyType);
      const matchesType = candidateType === "全部类型" || candidate.candidateTypes.includes(candidateType);
      const matchesRisk = riskLevel === "all" || candidate.riskLevel === riskLevel;
      const matchesAction = suggestedAction === "all" || candidate.suggestedAction === suggestedAction;
      const matchesTopic = topic === "all" || candidate.industry === topic || candidate.conceptNames.includes(topic);
      return matchesSearch && matchesStrategy && matchesType && matchesRisk && matchesAction && matchesTopic;
    });
    const sorted = sortCandidates(filtered, sortKey, strategyType, candidateType);
    return sorted.slice(0, 80);
  }, [candidateType, mergedCandidates, riskLevel, search, sortKey, strategyType, suggestedAction, topic]);

  const summary = useMemo(() => buildSummary(filteredCandidates, dashboardSummary?.market_theme), [dashboardSummary?.market_theme, filteredCandidates]);
  const layers = useMemo(() => splitCandidateLayers(filteredCandidates), [filteredCandidates]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold">候选股票池</h1>
          <p className="mt-1 text-sm text-muted-foreground">按策略、市场状态、风险等级和候选类型筛选观察标的。</p>
        </div>
        <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] px-3 py-2 text-xs text-[var(--text-secondary)]">
          本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。
        </div>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <SummaryCard label="今日候选" value={`${summary.total}`} hint="合并同股多策略后" />
        <SummaryCard label="热点候选" value={`${summary.hotspotCount}`} hint="热点题材 / 短线强势" tone="orange" />
        <SummaryCard label="高风险" value={`${summary.highRiskCount}`} hint="默认靠后展示" tone="danger" />
        <SummaryCard label="短线强势" value={`${summary.shortStrengthCount}`} hint="资金活跃方向" tone="orange" />
        <SummaryCard label="平均评分" value={summary.averageScore.toFixed(1)} hint="当前筛选范围" />
        <SummaryCard label="今日主线" value={summary.mainTopics} hint={summary.marketHint} wide />
      </section>

      <Card>
        <CardContent className="grid gap-3 pt-4 lg:grid-cols-12">
          <div className="relative lg:col-span-3">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
            <Input className="pl-9" placeholder="搜索代码/名称" value={search} onChange={(event) => setSearch(event.target.value)} />
          </div>
          <Select className="lg:col-span-2" value={strategyType} onChange={(event) => setStrategyType(event.target.value)}>
            {STRATEGY_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <Select className="lg:col-span-2" value={candidateType} onChange={(event) => setCandidateType(event.target.value)}>
            {CANDIDATE_TYPE_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          <Select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value)}>
            <option value="all">全部风险</option>
            <option value="low">低风险</option>
            <option value="medium">中风险</option>
            <option value="high">高风险</option>
          </Select>
          <Select value={suggestedAction} onChange={(event) => setSuggestedAction(event.target.value)}>
            <option value="all">全部动作</option>
            <option value="观察">观察</option>
            <option value="谨慎观察">谨慎观察</option>
            <option value="暂不参与">暂不参与</option>
          </Select>
          <Select value={topic} onChange={(event) => setTopic(event.target.value)}>
            <option value="all">全部行业/题材</option>
            {topicOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          <Select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
            <option value="default">默认排序</option>
            <option value="finalScore">综合评分</option>
            <option value="hotspotScore">热点评分</option>
            <option value="capitalFlowScore">资金评分</option>
            <option value="pctChg">涨幅</option>
            <option value="amount">成交额</option>
            <option value="riskLevel">风险等级</option>
          </Select>
          <div className="flex rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-1 lg:col-span-1">
            <button
              aria-label="精简表格视图"
              className={viewButtonClass(viewMode === "table")}
              onClick={() => setViewMode("table")}
              type="button"
            >
              <List className="h-4 w-4" />
            </button>
            <button
              aria-label="卡片视图"
              className={viewButtonClass(viewMode === "card")}
              onClick={() => setViewMode("card")}
              type="button"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <CandidateSection
          title="主观察清单"
          description="优先展示可观察、风险可控、策略条件满足的候选"
          candidates={layers.main}
          viewMode={viewMode}
          emptyText="暂无主观察候选，当前市场或风控条件偏谨慎。"
          badgeTone="success"
          onOpen={setSelected}
        />
        <CandidateSection
          title="防御观察清单"
          description="RiskOff / Choppy / Panic 下优先跟踪低波防御、质量动量和低回撤候选"
          candidates={layers.defensive}
          viewMode={viewMode}
          emptyText="暂无防御观察候选。"
          badgeTone="default"
          onOpen={setSelected}
        />
        <CandidateSection
          title="热点观察清单"
          description="仅在 RiskOn / Recovery 且热点信号和风险条件匹配时展示"
          candidates={layers.hotspot}
          viewMode={viewMode}
          emptyText="暂无热点观察候选，或热点数据不足以支撑强判断。"
          badgeTone="warning"
          onOpen={setSelected}
        />
        <CandidateSection
          title="风险观察池"
          description="高风险或暂不参与标的，仅用于风险跟踪和复盘，不作为今日行动依据"
          candidates={layers.risk}
          viewMode={viewMode}
          emptyText="暂无风险观察标的。"
          badgeTone="danger"
          onOpen={setSelected}
          muted
          defaultCollapsed
        />
        <CandidateSection
          title="复盘池"
          description="未满足硬条件但有研究价值的历史/相关性样本"
          candidates={layers.review}
          viewMode={viewMode}
          emptyText="暂无复盘池样本。"
          badgeTone="muted"
          onOpen={setSelected}
          muted
        />
      </div>

      <CandidateDrawer candidate={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function CandidateSection({
  title,
  description,
  candidates,
  viewMode,
  emptyText,
  badgeTone,
  muted = false,
  defaultCollapsed = false,
  onOpen,
}: {
  title: string;
  description: string;
  candidates: CandidateView[];
  viewMode: ViewMode;
  emptyText: string;
  badgeTone: "default" | "success" | "warning" | "danger" | "muted";
  muted?: boolean;
  defaultCollapsed?: boolean;
  onOpen: (candidate: CandidateView) => void;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <Card className={muted ? "opacity-95" : ""}>
      <CardHeader className="flex-row items-center justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{description}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={badgeTone}>{candidates.length} 只</Badge>
          {defaultCollapsed && (
            <Button variant="ghost" size="sm" onClick={() => setCollapsed((value) => !value)}>
              {collapsed ? "展开" : "收起"}
            </Button>
          )}
        </div>
      </CardHeader>
      {!collapsed && <CardContent>
        <div className={cn("hidden md:block", viewMode === "table" ? "" : "md:hidden")}>
          <div className="overflow-x-auto scrollbar-thin">
            <Table className="min-w-[1120px]">
              <TableHeader>
                <TableRow>
                  <TableHead>股票</TableHead>
                  <TableHead>行业 / 题材</TableHead>
                  <TableHead>策略</TableHead>
                  <TableHead>价格表现</TableHead>
                  <TableHead>评分拆解</TableHead>
                  <TableHead>市场 / 风险</TableHead>
                  <TableHead>建议动作</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {candidates.map((candidate) => (
                  <CandidateRow key={candidate.key} candidate={candidate} onOpen={() => onOpen(candidate)} />
                ))}
                {!candidates.length && (
                  <TableRow>
                    <TableCell colSpan={8} className="py-4">
                      <EmptyState
                        compact
                        variant={title.includes("风险") ? "no-result" : "strategy-not-run"}
                        title={`${title}暂无结果`}
                        description={emptyText}
                        reason="可能是今日策略尚未运行、当前筛选条件过严、行情数据未同步，或市场状态不适合该类策略。"
                        primaryAction={{ label: "重置筛选", onClick: () => window.location.assign("/candidates") }}
                        secondaryAction={{ label: "手动刷新数据与策略", href: "/" }}
                        helpLink={{ label: "检查数据", href: "/data-center" }}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        <div className={cn("grid gap-3 md:hidden", viewMode === "card" ? "md:grid md:grid-cols-2 xl:grid-cols-3" : "")}>
          {candidates.map((candidate) => (
            <CandidateCard key={candidate.key} candidate={candidate} onOpen={() => onOpen(candidate)} />
          ))}
          {!candidates.length && (
            <EmptyState
              compact
              variant={title.includes("风险") ? "no-result" : "strategy-not-run"}
              title={`${title}暂无结果`}
              description={emptyText}
              reason="可先重置筛选；若仍为空，请检查后台策略快照或数据中心。"
              primaryAction={{ label: "重置筛选", onClick: () => window.location.assign("/candidates") }}
              secondaryAction={{ label: "手动刷新数据与策略", href: "/" }}
            />
          )}
        </div>
      </CardContent>}
    </Card>
  );
}

function CandidateRow({ candidate, onOpen }: { candidate: CandidateView; onOpen: () => void }) {
  return (
    <TableRow>
      <TableCell>
        <div className="min-w-28">
          <Link href={`/stocks/${candidate.stockCode}`} className="font-semibold text-[var(--text-primary)] hover:text-[var(--color-primary)]">
            {candidate.stockName}
          </Link>
          <div className="finance-number mt-1 text-xs text-[var(--color-primary)]">{candidate.stockCode}</div>
        </div>
      </TableCell>
      <TableCell>
        <div className="max-w-48 space-y-1.5">
          <div className="text-sm">{candidate.industry || "未分类"}</div>
          <TagList items={candidate.conceptNames} limit={2} tone="warning" />
        </div>
      </TableCell>
      <TableCell>
        <div className="max-w-48 space-y-1.5">
          <TagList items={candidate.strategies} limit={2} />
          {candidate.candidateLevel && <div className="text-xs text-[var(--color-primary)]">{candidate.candidateLevel}</div>}
          {candidate.isNewCandidate && <Badge tone="success">新进入</Badge>}
        </div>
      </TableCell>
      <TableCell>
        <div className="finance-number text-sm font-semibold">{formatNumber(candidate.close)}</div>
        <div className={cn("finance-number mt-1 text-xs", marketTone(candidate.pctChg))}>{formatPctPoint(candidate.pctChg)}</div>
        {candidate.return5d !== undefined && <div className="mt-1 text-xs text-[var(--text-tertiary)]">5日 {formatPctPoint(candidate.return5d)}</div>}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <span className="finance-number text-base font-semibold text-[var(--color-primary)]">{candidate.finalScore.toFixed(1)}</span>
        </div>
        <div className="mt-1 text-xs text-[var(--text-tertiary)]">
          信号 {candidate.signalScore.toFixed(1)} / 扣分 {candidate.riskPenalty.toFixed(1)}
        </div>
        <div className="mt-1 text-xs text-[var(--color-warning)]">置信度 {candidate.strategyConfidence.toFixed(1)}</div>
        {candidate.hotspotScore ? <div className="mt-1 text-xs text-[var(--color-warning)]">热点 {candidate.hotspotScore.toFixed(1)}</div> : null}
        {candidate.diversityPenalty ? <div className="mt-1 text-xs text-[var(--color-danger)]">重复降权 -{candidate.diversityPenalty.toFixed(0)}</div> : null}
        <div className="mt-1 line-clamp-1 max-w-72 text-xs text-[var(--text-tertiary)]">{candidate.triggerReasons[0] || "-"}</div>
      </TableCell>
      <TableCell>
        <div className="text-xs text-[var(--text-secondary)]">{regimeLabel(candidate.marketRegime)}</div>
        <div className="mt-1">
          <RiskBadge level={candidate.riskLevel} />
        </div>
        <div className="mt-1 text-xs text-[var(--text-tertiary)]">{poolLabel(candidate)}</div>
      </TableCell>
      <TableCell>
        <div className={actionClass(candidate.suggestedAction)}>{candidate.suggestedAction}</div>
        <div className="mt-1 line-clamp-1 max-w-48 text-xs text-[var(--text-tertiary)]">{candidate.riskReasons[0] || "需人工确认"}</div>
      </TableCell>
      <TableCell>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onOpen}>
            <Eye className="h-3.5 w-3.5" />
            详情
          </Button>
          <Link href="/backtest" className="inline-flex h-8 items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]">
            <BarChart3 className="h-3.5 w-3.5" />
            回测
          </Link>
          <Link href={`/stock-inspector/${candidate.stockCode}`} className="inline-flex h-8 items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]">
            <FileText className="h-3.5 w-3.5" />
            诊股
          </Link>
          <Link href={`/reviews?stock=${candidate.stockCode}`} className="inline-flex h-8 items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2 text-xs text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]">
            <PenLine className="h-3.5 w-3.5" />
            复盘
          </Link>
        </div>
      </TableCell>
    </TableRow>
  );
}

function CandidateCard({ candidate, onOpen }: { candidate: CandidateView; onOpen: () => void }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/stocks/${candidate.stockCode}`} className="text-base font-semibold text-[var(--text-primary)] hover:text-[var(--color-primary)]">
            {candidate.stockName}
          </Link>
          <div className="finance-number mt-1 text-xs text-[var(--color-primary)]">{candidate.stockCode}</div>
        </div>
        <RiskBadge level={candidate.riskLevel} />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <TagList items={[candidate.industry, ...candidate.conceptNames]} limit={3} tone="warning" />
        <TagList items={candidate.candidateTypes} limit={2} />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <MiniMetric label="最终" value={candidate.finalScore.toFixed(1)} className="text-[var(--color-primary)]" />
        <MiniMetric label="信号/扣分" value={`${candidate.signalScore.toFixed(0)}/${candidate.riskPenalty.toFixed(0)}`} className="text-[var(--color-warning)]" />
        <MiniMetric label="涨跌幅" value={formatPctPoint(candidate.pctChg)} className={marketTone(candidate.pctChg)} />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-[var(--text-tertiary)]">
        <span>{regimeLabel(candidate.marketRegime)}</span>
        <span>{poolLabel(candidate)}</span>
      </div>
      <div className="mt-3 space-y-1.5 text-xs leading-5 text-[var(--text-secondary)]">
        {candidate.triggerReasons.slice(0, 2).map((item) => (
          <div key={item}>- {item}</div>
        ))}
        <div className="text-[var(--text-tertiary)]">风险：{candidate.riskReasons[0] || "需人工确认"}</div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <span className={actionClass(candidate.suggestedAction)}>{candidate.suggestedAction}</span>
        <div className="flex gap-2">
          <Link href={`/stock-inspector/${candidate.stockCode}`} className="inline-flex h-8 items-center rounded-md border border-[var(--border-strong)] px-2 text-xs text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]">
            诊股
          </Link>
          <Button variant="outline" size="sm" onClick={onOpen}>
            详情
          </Button>
        </div>
      </div>
    </div>
  );
}

function CandidateDrawer({ candidate, onClose }: { candidate: CandidateView | null; onClose: () => void }) {
  if (!candidate) return null;
  const scoreItems = [
    ["信号分", candidate.signalScore],
    ["风险扣分", candidate.riskPenalty],
    ["综合评分", candidate.finalScore],
    ["策略置信度", candidate.strategyConfidence],
    ["热点评分", candidate.hotspotScore],
    ["趋势评分", candidate.trendScore],
    ["估值评分", candidate.valueScore],
    ["质量评分", candidate.qualityScore],
    ["资金评分", candidate.capitalFlowScore],
    ["板块热度", candidate.sectorHotScore],
    ["龙头辨识", candidate.leaderScore],
  ].filter((item): item is [string, number] => typeof item[1] === "number" && !Number.isNaN(item[1]));

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/45" role="dialog" aria-modal="true">
      <button className="hidden flex-1 cursor-default md:block" aria-label="关闭详情抽屉背景" onClick={onClose} type="button" />
      <aside className="h-full w-full overflow-y-auto border-l border-[var(--border-subtle)] bg-[var(--bg-card)] p-4 shadow-[var(--shadow-card)] md:max-w-xl">
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border-subtle)] pb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-semibold">{candidate.stockName}</h2>
              <span className="finance-number text-sm text-[var(--color-primary)]">{candidate.stockCode}</span>
              <RiskBadge level={candidate.riskLevel} />
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <TagList items={[candidate.industry, ...candidate.conceptNames, ...candidate.candidateTypes]} limit={8} tone="warning" />
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="关闭详情抽屉">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-5 py-4">
          <section>
            <h3 className="text-sm font-semibold">策略与候选等级</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <TagList items={candidate.strategies} limit={6} />
              {candidate.candidateLevel && <Badge tone="warning">{candidate.candidateLevel}</Badge>}
              <Badge tone="default">{regimeLabel(candidate.marketRegime)}</Badge>
              <Badge tone={candidate.candidateMode === "main_observation" ? "success" : candidate.candidateMode === "risk_observation" ? "danger" : "muted"}>{poolLabel(candidate)}</Badge>
              <Badge tone={candidate.suggestedAction === "暂不参与" ? "muted" : candidate.suggestedAction === "谨慎观察" ? "warning" : "success"}>
                {candidate.suggestedAction}
              </Badge>
            </div>
          </section>

          <DetailList title="池子归属解释" items={poolExplanation(candidate)} />

          <section>
            <h3 className="text-sm font-semibold">评分拆解</h3>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {scoreItems.map(([label, value]) => (
                <MiniMetric key={label} label={label} value={value.toFixed(1)} className={label.includes("热点") || label.includes("综合") ? "text-[var(--color-primary)]" : ""} />
              ))}
            </div>
          </section>

          <DetailList title="入选原因" items={candidate.triggerReasons} />
          <DetailList title="风险理由" items={candidate.riskReasons} risk />

          <section>
            <h3 className="text-sm font-semibold">回测依据</h3>
            <div className="mt-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm text-[var(--text-secondary)]">
              {candidate.recentBacktest}
            </div>
          </section>

          <DetailList title="退出观察规则" items={candidate.exitRules.length ? candidate.exitRules : ["跌破关键均线或板块热度明显下降时退出观察", "市场状态转弱时降级为风险观察"]} />

          <section>
            <h3 className="text-sm font-semibold">原始因子快照</h3>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
              {rawFactorItems(candidate).map(([key, value]) => (
                <div key={key} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
                  <div className="text-[var(--text-tertiary)]">{key}</div>
                  <div className="finance-number mt-1 break-all text-[var(--text-primary)]">{String(value)}</div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </aside>
    </div>
  );
}

function DetailList({ title, items, risk = false }: { title: string; items: string[]; risk?: boolean }) {
  return (
    <section>
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
        {(items.length ? items : ["暂无详细记录，需人工确认"]).map((item) => (
          <li key={item} className={cn("rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2", risk && "border-[rgba(230,69,69,0.24)] text-[var(--color-danger)]")}>
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SummaryCard({ label, value, hint, tone, wide = false }: { label: string; value: string; hint: string; tone?: "orange" | "danger"; wide?: boolean }) {
  return (
    <Card className={wide ? "xl:col-span-1" : ""}>
      <CardContent className="p-3.5">
        <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
        <div className={cn("mt-2 min-h-7 truncate text-lg font-semibold", tone === "orange" && "text-[var(--color-primary)]", tone === "danger" && "text-[var(--color-danger)]")}>{value}</div>
        <div className="mt-1 truncate text-xs text-[var(--text-tertiary)]">{hint}</div>
      </CardContent>
    </Card>
  );
}

function MiniMetric({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <div className="text-[var(--text-tertiary)]">{label}</div>
      <div className={cn("finance-number mt-1 font-semibold", className)}>{value}</div>
    </div>
  );
}

function TagList({ items, limit, tone = "muted" }: { items: string[]; limit: number; tone?: "muted" | "warning" }) {
  const clean = unique(items.filter(Boolean));
  return (
    <>
      {clean.slice(0, limit).map((item) => (
        <Badge key={item} tone={tone}>
          {item}
        </Badge>
      ))}
      {clean.length > limit && <Badge tone="muted">+{clean.length - limit}</Badge>}
    </>
  );
}

function mergeSignalsByStock(items: Signal[]): CandidateView[] {
  const grouped = new Map<string, Signal[]>();
  items.forEach((signal) => {
    const current = grouped.get(signal.stock_code) || [];
    current.push(signal);
    grouped.set(signal.stock_code, current);
  });

  return Array.from(grouped.entries()).map(([stockCode, group]) => {
    const converted = group.map(signalToCandidate).sort((a, b) => candidatePriority(b) - candidatePriority(a));
    const best = converted[0];
    const riskLevel = worstRisk(converted.map((item) => item.riskLevel));
    const suggestedAction = riskLevel === "high" ? "暂不参与" : best.suggestedAction;
    const allStrategies = unique(converted.flatMap((item) => item.strategies));
    const allTypes = unique(converted.flatMap((item) => item.candidateTypes));
    return {
      ...best,
      key: stockCode,
      riskLevel,
      suggestedAction,
      strategies: allStrategies,
      candidateTypes: allTypes,
      signalScore: best.signalScore,
      riskPenalty: best.riskPenalty,
      finalScore: best.finalScore,
      strategyConfidence: best.strategyConfidence,
      diversityPenalty: maxOptional(converted.map((item) => item.diversityPenalty)) || undefined,
      isNewCandidate: converted.some((item) => item.isNewCandidate),
      hotspotScore: maxOptional(converted.map((item) => item.hotspotScore)),
      trendScore: maxOptional(converted.map((item) => item.trendScore)),
      valueScore: maxOptional(converted.map((item) => item.valueScore)),
      qualityScore: maxOptional(converted.map((item) => item.qualityScore)),
      capitalFlowScore: maxOptional(converted.map((item) => item.capitalFlowScore)),
      sectorHotScore: maxOptional(converted.map((item) => item.sectorHotScore)),
      leaderScore: maxOptional(converted.map((item) => item.leaderScore)),
      hardRisk: unique(converted.flatMap((item) => item.hardRisk)),
      softRisk: unique(converted.flatMap((item) => item.softRisk)),
      triggerReasons: unique(converted.flatMap((item) => item.triggerReasons)),
      riskReasons: unique(converted.flatMap((item) => item.riskReasons)),
      exitRules: unique(converted.flatMap((item) => item.exitRules)),
      sourceSignals: group,
    };
  });
}

function signalToCandidate(signal: Signal): CandidateView {
  const candidate = signal.strategyCandidate;
  const raw: Record<string, unknown> = candidate?.rawFactors || {};
  const subScores: Record<string, number> = candidate?.subScores || signal.subScores || {};
  const candidateTypes = normalizeCandidateTypes(signal);
  const strategies = normalizeStrategies(signal);
  const conceptNames = normalizeStringArray(candidate?.conceptNames || raw.conceptNames);
  const finalScore = Number(candidate?.finalScore ?? signal.score ?? 0);
  const metadata = signal.metadata || {};
  const candidateMode = String(candidate?.candidateMode || signal.candidateMode || metadata.candidateMode || "");
  return {
    key: `${signal.stock_code}-${signal.id}`,
    id: signal.id,
    stockCode: signal.stock_code,
    stockName: signal.stock_name,
    industry: candidate?.industryName || candidate?.sectorName || signal.industry || "未分类",
    conceptNames: conceptNames.length ? conceptNames : [signal.industry].filter(Boolean),
    strategies,
    candidateTypes,
    candidateLevel: signal.candidateLevel || candidate?.candidateLevel,
    close: Number(candidate?.close ?? signal.current_price ?? 0),
    pctChg: Number(candidate?.pctChg ?? signal.pct_change ?? 0),
    return5d: numberOrUndefined(raw.return5d),
    amount: numberOrUndefined(candidate?.amount ?? signal.amount ?? raw.amount),
    turnoverRate: numberOrUndefined(candidate?.turnoverRate ?? signal.turnoverRate ?? raw.turnoverRate),
    volumeRatio: numberOrUndefined(candidate?.volumeRatio ?? signal.volumeRatio ?? raw.volumeRatio),
    signalScore: Number(candidate?.signalScore ?? signal.signalScore ?? metadata.signalScore ?? finalScore),
    riskPenalty: Number(candidate?.riskPenalty ?? signal.riskPenalty ?? metadata.riskPenalty ?? 0),
    finalScore,
    strategyConfidence: Number(candidate?.strategyConfidence ?? signal.strategyConfidence ?? metadata.strategyConfidence ?? finalScore),
    diversityPenalty: numberOrUndefined(signal.diversityPenalty),
    isNewCandidate: Boolean(signal.isNewCandidate),
    hotspotScore: numberOrNull(candidate?.hotspotScore ?? signal.hotspotScore ?? subScores.hotspotScore),
    trendScore: numberOrNull(candidate?.trendScore ?? signal.trend_score ?? subScores.trendScore ?? subScores.momentumScore),
    valueScore: numberOrNull(candidate?.valueScore ?? signal.valuation_score ?? subScores.valueScore),
    qualityScore: numberOrNull(candidate?.qualityScore ?? subScores.qualityScore),
    capitalFlowScore: numberOrNull(candidate?.capitalFlowScore ?? signal.capitalFlowScore ?? signal.capital_score ?? subScores.capitalFlowScore),
    sectorHotScore: numberOrNull(candidate?.sectorHotScore ?? signal.sectorHotScore ?? subScores.sectorHotScore),
    leaderScore: numberOrNull(candidate?.leaderScore ?? signal.leaderScore ?? subScores.leaderScore),
    riskLevel: signal.risk_level,
    suggestedAction: signal.suggestedAction || defaultAction(signal.risk_level),
    candidateMode,
    hardRisk: normalizeStringArray(signal.hardRisk || metadata.hardRisk),
    softRisk: normalizeStringArray(signal.softRisk || metadata.softRisk),
    triggerReasons: normalizeReasons(signal.triggerReasons, signal.reason),
    riskReasons: normalizeReasons(signal.riskReasons, signal.risk_reason),
    exitRules: signal.exitRules || candidate?.exitRules || [],
    recentBacktest: signal.recent_backtest_performance || "暂无回测",
    marketRegime: signal.marketRegime || candidate?.marketRegime,
    sectorRank: numberOrNull(candidate?.sectorRank ?? raw.sectorRank),
    sectorLimitUpCount: numberOrNull(candidate?.sectorLimitUpCount ?? raw.sectorLimitUpCount),
    rawFactors: raw,
    sourceSignals: [signal],
  };
}

function normalizeCandidateTypes(signal: Signal) {
  const candidateTypes = normalizeStringArray(signal.candidateTypes || signal.strategyCandidate?.candidateTypes);
  const mode = String(signal.candidateMode || signal.metadata?.candidateMode || signal.strategyCandidate?.candidateMode || "");
  if (mode === "risk_observation") candidateTypes.push("风险观察");
  if (mode === "review_pool" || mode === "ranked_observation") candidateTypes.push("复盘观察");
  if (candidateTypes.length) return unique(candidateTypes);
  const name = normalizeStrategies(signal).join(" ");
  if (name.includes("市场热点")) return ["热点题材", "短线强势"];
  if (name.includes("短线龙头")) return ["龙头候选", "短线强势"];
  if (name.includes("价值动量")) return ["价值动量", "蓝筹稳健"];
  if (name.includes("质量动量")) return ["质量动量", "蓝筹稳健"];
  if (name.includes("低波")) return ["低波防御"];
  return ["趋势增强"];
}

function normalizeStrategies(signal: Signal) {
  if (signal.dragon) return ["短线龙头候选策略"];
  const fromCandidate = normalizeStringArray(signal.strategyCandidate?.strategies);
  if (fromCandidate.length) return fromCandidate;
  return [signal.strategy_name || signal.strategyCandidate?.strategyName || "未知策略"];
}

function matchesStrategyType(candidate: CandidateView, strategyType: string) {
  const text = `${candidate.strategies.join(" ")} ${candidate.candidateTypes.join(" ")}`;
  const matcher: Record<string, string[]> = {
    valueMomentum: ["价值动量"],
    qualityMomentum: ["质量动量"],
    trendFollowing: ["趋势跟踪", "中期趋势"],
    marketHotspot: ["市场热点", "短线热点", "热点题材"],
    dragon: ["短线龙头", "龙头候选"],
    lowBeta: ["低波"],
    ma: ["均线趋势"],
    lowDrawdown: ["低回撤"],
    multiFactor: ["多因子"],
  };
  return (matcher[strategyType] || []).some((item) => text.includes(item));
}

function sortCandidates(items: CandidateView[], sortKey: SortKey, strategyType: string, candidateType: string) {
  const copy = [...items];
  if (sortKey !== "default") {
    return copy.sort((a, b) => sortValue(b, sortKey) - sortValue(a, sortKey));
  }
  if (strategyType === "marketHotspot" || candidateType === "热点题材" || candidateType === "短线强势") {
    return copy.sort((a, b) => weightedCompare(b, a, ["sectorHotScore", "hotspotScore", "leaderScore", "capitalFlowScore"]) || riskSort(a, b));
  }
  if (strategyType === "valueMomentum" || candidateType === "价值动量") {
    return copy.sort((a, b) => weightedCompare(b, a, ["finalScore", "trendScore", "valueScore"]) || riskSort(a, b));
  }
  return copy.sort((a, b) => candidatePriority(b) - candidatePriority(a));
}

function applyCandidateQuota(candidates: CandidateView[]) {
  const selected: CandidateView[] = [];
  const seen = new Set<string>();
  const buckets = [
    { cap: 8, match: (item: CandidateView) => item.candidateTypes.some((type) => ["热点题材", "短线强势"].includes(type)) },
    { cap: 5, match: (item: CandidateView) => item.candidateTypes.includes("龙头候选") },
    { cap: 5, match: (item: CandidateView) => item.candidateTypes.includes("价值动量") },
    { cap: 5, match: (item: CandidateView) => item.candidateTypes.includes("质量动量") },
    { cap: 3, match: (item: CandidateView) => item.candidateTypes.includes("低波防御") },
  ];
  buckets.forEach((bucket) => {
    candidates.filter(bucket.match).forEach((candidate) => {
      if (selected.filter(bucket.match).length >= bucket.cap || selected.length >= 20 || seen.has(candidate.stockCode)) return;
      selected.push(candidate);
      seen.add(candidate.stockCode);
    });
  });
  candidates.forEach((candidate) => {
    if (selected.length >= 20 || seen.has(candidate.stockCode)) return;
    selected.push(candidate);
    seen.add(candidate.stockCode);
  });
  return selected;
}

function splitCandidateLayers(candidates: CandidateView[]) {
  const risk = candidates
    .filter(isRiskObservation)
    .sort((a, b) => candidatePriority(b) - candidatePriority(a))
    .slice(0, 30);
  const riskCodes = new Set(risk.map((item) => item.stockCode));
  const defensive = candidates
    .filter((item) => !riskCodes.has(item.stockCode) && isDefensiveObservation(item))
    .sort((a, b) => candidatePriority(b) - candidatePriority(a))
    .slice(0, 20);
  const defensiveCodes = new Set(defensive.map((item) => item.stockCode));
  const hotspot = candidates
    .filter((item) => !riskCodes.has(item.stockCode) && !defensiveCodes.has(item.stockCode) && isHotspotObservation(item))
    .sort((a, b) => candidatePriority(b) - candidatePriority(a))
    .slice(0, 20);
  const hotspotCodes = new Set(hotspot.map((item) => item.stockCode));
  const mainRaw = candidates.filter((item) => !riskCodes.has(item.stockCode) && !defensiveCodes.has(item.stockCode) && !hotspotCodes.has(item.stockCode) && isMainObservation(item));
  const main = applyCandidateQuota(sortCandidates(mainRaw, "default", "all", "全部类型"));
  const mainCodes = new Set(main.map((item) => item.stockCode));
  const occupied = new Set([
    ...Array.from(riskCodes),
    ...Array.from(defensiveCodes),
    ...Array.from(hotspotCodes),
    ...Array.from(mainCodes),
  ]);
  const review = candidates
    .filter((item) => !occupied.has(item.stockCode) && isReviewObservation(item))
    .sort((a, b) => candidatePriority(b) - candidatePriority(a))
    .slice(0, 20);
  return { main, defensive, hotspot, risk, review };
}

function isMainObservation(candidate: CandidateView) {
  return (
    candidate.suggestedAction !== "暂不参与" &&
    candidate.riskLevel !== "high" &&
    candidate.finalScore >= 60 &&
    candidate.candidateMode === "main_observation" &&
    isStrategyAllowedByRegime(candidate) &&
    candidate.hardRisk.length === 0
  );
}

function isDefensiveObservation(candidate: CandidateView) {
  const text = `${candidate.strategies.join(" ")} ${candidate.candidateTypes.join(" ")}`;
  return (
    ["RiskOff", "Choppy", "Panic"].includes(candidate.marketRegime || "Choppy") &&
    ["低波防御", "质量动量", "低回撤"].some((item) => text.includes(item)) &&
    candidate.riskLevel !== "high" &&
    candidate.suggestedAction === "观察" &&
    candidate.hardRisk.length === 0
  );
}

function isHotspotObservation(candidate: CandidateView) {
  const text = `${candidate.strategies.join(" ")} ${candidate.candidateTypes.join(" ")}`;
  const score = Number(candidate.hotspotScore || candidate.finalScore || 0);
  return (
    ["RiskOn", "Recovery"].includes(candidate.marketRegime || "") &&
    ["市场热点", "短线龙头", "热点题材", "龙头候选", "短线强势"].some((item) => text.includes(item)) &&
    score >= 60 &&
    candidate.riskLevel !== "high" &&
    candidate.suggestedAction !== "暂不参与" &&
    candidate.hardRisk.length === 0
  );
}

function isRiskObservation(candidate: CandidateView) {
  return candidate.riskLevel === "high" || candidate.suggestedAction === "暂不参与" || candidate.candidateMode === "risk_observation" || candidate.hardRisk.length > 0;
}

function isReviewObservation(candidate: CandidateView) {
  return candidate.candidateMode === "review_pool" || candidate.candidateMode === "ranked_observation" || candidate.candidateTypes.includes("复盘观察") || candidate.finalScore < 60;
}

function isStrategyAllowedByRegime(candidate: CandidateView) {
  const text = candidate.strategies.join(" ");
  const regime = candidate.marketRegime || "Choppy";
  if (regime === "Panic") return ["低波防御", "质量动量"].some((item) => text.includes(item));
  if (regime === "RiskOff") return !["市场热点", "短线龙头", "均线趋势", "趋势跟踪"].some((item) => text.includes(item));
  if (regime === "Choppy") return !text.includes("短线龙头");
  return true;
}

function buildSummary(candidates: CandidateView[], marketTheme?: DashboardSummary["market_theme"]) {
  const total = candidates.length;
  const highRiskCount = candidates.filter((item) => item.riskLevel === "high").length;
  const hotspotCount = candidates.filter((item) => item.candidateTypes.some((type) => ["热点题材", "短线强势"].includes(type))).length;
  const shortStrengthCount = candidates.filter((item) => item.candidateTypes.includes("短线强势")).length;
  const averageScore = total ? candidates.reduce((sum, item) => sum + item.finalScore, 0) / total : 0;
  const topicCounts = new Map<string, number>();
  candidates.forEach((item) => {
    [item.industry, ...item.conceptNames].filter(Boolean).forEach((topicName) => {
      topicCounts.set(topicName, (topicCounts.get(topicName) || 0) + 1);
    });
  });
  const estimatedTopics = Array.from(topicCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name]) => name)
    .join(" / ");
  const themeText = marketTheme?.displayText && marketTheme.displayText !== marketTheme.message ? marketTheme.displayText : "";
  return {
    total,
    highRiskCount,
    hotspotCount,
    shortStrengthCount,
    averageScore,
    mainTopics: themeText || "题材数据不足",
    marketHint: marketTheme?.isComplete
      ? marketTheme.message
      : marketTheme?.message || (estimatedTopics ? `仅按候选分布估算：${estimatedTopics}` : "等待热点数据"),
  };
}

function candidatePriority(candidate: CandidateView) {
  return (
    actionRank(candidate.suggestedAction) * 10000 +
    riskRank(candidate.riskLevel) * 1000 +
    candidateLevelRank(candidate.candidateLevel) * 350 +
    candidate.strategyConfidence * 4 +
    Number(candidate.hotspotScore || 0) * 4 +
    candidate.finalScore * 3 -
    candidate.riskPenalty * 8 +
    Math.min(Number(candidate.amount || 0) / 100000000, 50)
  );
}

function weightedCompare(left: CandidateView, right: CandidateView, keys: Array<keyof CandidateView>) {
  for (const key of keys) {
    const diff = Number(left[key] || 0) - Number(right[key] || 0);
    if (Math.abs(diff) > 0.001) return diff;
  }
  return 0;
}

function sortValue(candidate: CandidateView, key: SortKey) {
  if (key === "riskLevel") return riskRank(candidate.riskLevel);
  if (key === "default") return candidatePriority(candidate);
  const numericKey = key as Exclude<SortKey, "default" | "riskLevel">;
  return Number(candidate[numericKey] || 0);
}

function actionRank(action: CandidateView["suggestedAction"]) {
  return action === "谨慎观察" ? 3 : action === "观察" ? 2 : 1;
}

function riskRank(level: RiskLevel) {
  return level === "low" ? 3 : level === "medium" ? 2 : 1;
}

function riskSeverity(level: RiskLevel) {
  return level === "high" ? 3 : level === "medium" ? 2 : 1;
}

function candidateLevelRank(level?: string) {
  if (!level) return 1;
  if (level.includes("核心")) return 3;
  if (level.includes("强势")) return 2;
  return 1;
}

function riskSort(a: CandidateView, b: CandidateView) {
  return riskRank(b.riskLevel) - riskRank(a.riskLevel);
}

function worstRisk(levels: RiskLevel[]): RiskLevel {
  return levels.sort((a, b) => riskSeverity(b) - riskSeverity(a))[0] || "medium";
}

function defaultAction(level: RiskLevel) {
  return level === "high" ? "暂不参与" : "观察";
}

function actionClass(action?: string) {
  if (action === "暂不参与") return "whitespace-nowrap text-[var(--text-tertiary)]";
  if (action === "谨慎观察") return "whitespace-nowrap text-[var(--color-warning)]";
  return "whitespace-nowrap text-[var(--color-success)]";
}

function poolLabel(candidate: CandidateView) {
  if (isMainObservation(candidate)) return "主观察清单";
  if (isDefensiveObservation(candidate)) return "防御观察清单";
  if (isHotspotObservation(candidate)) return "热点观察清单";
  if (isRiskObservation(candidate)) return "风险观察池";
  return "复盘池";
}

function poolExplanation(candidate: CandidateView) {
  const pool = poolLabel(candidate);
  const reasons: string[] = [];
  if (pool === "主观察清单") {
    reasons.push("进入主观察清单：建议动作可观察、风险等级非高、最终评分不低于 60，且市场状态允许该策略启用。");
  } else if (pool === "防御观察清单") {
    reasons.push(`进入防御观察清单：市场处于 ${candidate.marketRegime || "Choppy"}，候选来自低波防御、质量动量或低回撤策略，风险等级可控。`);
    reasons.push("未进入主观察清单：当前更适合防御观察，不作为趋势进攻或短线热点依据。");
  } else if (pool === "热点观察清单") {
    reasons.push("进入热点观察清单：热点或龙头策略命中，热点评分达到观察阈值，且未触发高风险。");
    reasons.push("未进入主观察清单：短线热点需要结合题材、涨停和炸板数据人工确认。");
  } else if (pool === "风险观察池") {
    reasons.push("进入风险观察池：触发高风险、暂不参与或硬风控条件，仅用于风险跟踪和复盘。");
    reasons.push("未进入主观察清单：风险等级或建议动作不满足今日行动依据要求。");
  } else {
    reasons.push("进入复盘池：策略曾触发或具备研究相关性，但未满足正式观察硬条件。");
    reasons.push("未进入主观察清单：最终评分、策略硬条件或数据完整性不足。");
  }
  reasons.push(upgradeCondition(candidate));
  return reasons;
}

function upgradeCondition(candidate: CandidateView) {
  if (candidate.riskLevel === "high" || candidate.suggestedAction === "暂不参与") {
    return "升级条件：风险等级降至中/低，硬风控解除，最终评分恢复到 60 以上后，才可重新进入观察清单。";
  }
  if (isDefensiveObservation(candidate)) {
    return "升级条件：市场从 RiskOff/Choppy 转为 Recovery/RiskOn，且个股继续保持低回撤与趋势修复。";
  }
  if (isHotspotObservation(candidate)) {
    return "升级条件：补齐涨停、连板、炸板和题材热度数据后，热点延续且风险不升高，可升级为主观察候选。";
  }
  return "升级条件：市场状态匹配该策略，策略评分提升且未触发新的风险项。";
}

function regimeLabel(regime?: string) {
  return {
    RiskOn: "RiskOn 趋势进攻",
    Choppy: "Choppy 震荡",
    RiskOff: "RiskOff 防御",
    Panic: "Panic 恐慌",
    Recovery: "Recovery 修复",
  }[regime || ""] || "Choppy 震荡";
}

function marketTone(value?: number | null) {
  if (Number(value || 0) > 0) return "market-up";
  if (Number(value || 0) < 0) return "market-down";
  return "market-flat";
}

function normalizeReasons(items?: string[], fallback?: string) {
  if (items?.length) return unique(items.filter(Boolean));
  return fallback ? fallback.split(/[；。]/).map((item) => item.trim()).filter(Boolean) : [];
}

function normalizeStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item)).filter(Boolean);
  if (typeof value === "string" && value.trim()) return value.split(/[、/,]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function numberOrNull(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function numberOrUndefined(value: unknown): number | undefined {
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function maxOptional(values: Array<number | null | undefined>) {
  const clean = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  return clean.length ? Math.max(...clean) : null;
}

function rawFactorItems(candidate: CandidateView) {
  const preferred = [
    "pctChg",
    "return5d",
    "amountRatio20d",
    "volumeRatio",
    "turnoverRate",
    "sectorRank",
    "sectorLimitUpCount",
    "sectorStrongStockCount",
    "consecutiveLimitUpDays",
    "marketRegime",
  ];
  const raw: Record<string, unknown> = { ...candidate.rawFactors, marketRegime: candidate.marketRegime };
  return preferred
    .map((key) => [key, raw[key]] as [string, unknown])
    .filter((item) => item[1] !== undefined && item[1] !== null)
    .slice(0, 10);
}

function unique<T>(items: T[]) {
  return Array.from(new Set(items));
}

function viewButtonClass(active: boolean) {
  return cn(
    "inline-flex h-8 flex-1 items-center justify-center rounded text-[var(--text-tertiary)] transition-colors hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]",
    active && "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
  );
}
