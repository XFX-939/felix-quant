"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ClipboardCopy, Download, FileText, Printer, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatNumber, formatPctPoint } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ResearchRating, StockInspectionReport } from "@/lib/types";

export default function StockInspectorReportPage() {
  const params = useParams<{ code: string }>();
  const code = params.code;
  const [report, setReport] = useState<StockInspectionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const markdown = useMemo(() => (report ? buildMarkdown(report) : ""), [report]);

  const loadReport = useCallback(async (force: boolean) => {
    if (!code) return;
    setLoading(true);
    setMessage(null);
    try {
      const data = await api.inspectStock(code, { force });
      setReport(data);
      setError(null);
      if (force) setMessage("诊股报告已重新生成");
    } catch (err) {
      setError(err instanceof Error ? err.message : "诊股报告加载失败");
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    loadReport(false);
  }, [loadReport]);

  async function copySummary() {
    if (!report) return;
    const text = [
      `${report.name}（${report.code}）给予${report.researchRating}评级`,
      report.ratingSummary,
      `主要看多理由：${report.keyBullishReasons.slice(0, 3).join("；")}`,
      `主要风险：${report.keyBearishReasons.slice(0, 3).join("；")}`,
      report.ratingDisclaimer,
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setMessage("研报摘要已复制");
  }

  function exportMarkdown() {
    if (!report) return;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${report.code}-${report.tradeDate}-Stock-Inspector.md`;
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("Markdown 报告已导出");
  }

  if (loading && !report) {
    return <div className="py-20 text-center text-sm text-[var(--text-tertiary)]">正在生成一键诊股报告...</div>;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm text-[var(--text-tertiary)]">Stock Inspector</div>
          <h1 className="mt-1 text-xl font-semibold">一键诊股</h1>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">研报式研究评级、目标区间、风险因素和评级调整条件。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => loadReport(true)} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            重新生成
          </Button>
          <Button variant="outline" onClick={copySummary} disabled={!report}>
            <ClipboardCopy className="h-4 w-4" />
            复制摘要
          </Button>
          <Button variant="outline" onClick={exportMarkdown} disabled={!report}>
            <Download className="h-4 w-4" />
            导出 Markdown
          </Button>
          <Button variant="outline" onClick={() => window.print()} disabled={!report}>
            <Printer className="h-4 w-4" />
            导出 PDF/打印
          </Button>
        </div>
      </div>

      {message && <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-sm text-[var(--text-secondary)]">{message}</div>}
      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}
      {!report ? null : (
        <>
          <RatingHero report={report} />

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <SectionCard title="核心观点">
              <p className="text-sm leading-7 text-[var(--text-secondary)]">{report.ratingSummary}</p>
              {report.researchRating === "买入" && <SpecialRatingExplanation report={report} mode="buy" />}
              {report.researchRating === "卖出" && <SpecialRatingExplanation report={report} mode="sell" />}
            </SectionCard>

            <SectionCard title="目标价区间与技术位置">
              <TargetRange report={report} />
            </SectionCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <ReasonList title="看多理由" items={report.keyBullishReasons} tone="success" />
            <ReasonList title="看空风险" items={report.keyBearishReasons} tone="danger" />
          </div>

          <SectionCard title="分项评分">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <ScoreCard label="基本面" value={report.scores.fundamentalScore} description="估值、盈利、成长、现金流和财务安全" />
              <ScoreCard label="技术面" value={report.scores.technicalScore} description="均线结构、趋势强度、相对强度、回撤和波动" />
              <ScoreCard label="情绪面" value={report.scores.sentimentScore} description="市场状态、板块热度、题材匹配和短线强度" />
              <ScoreCard label="资金面" value={report.scores.capitalFlowScore} description="成交额、量能放大和换手活跃度" />
              <ScoreCard label="风险面" value={report.scores.riskControlScore} description="硬风险、软风险、数据风险和流动性风险" />
            </div>
          </SectionCard>

          <div className="grid gap-4 xl:grid-cols-2">
            <AnalysisList title="基本面分析" items={report.analysis.fundamental} />
            <AnalysisList title="技术面分析" items={report.analysis.technical} />
            <AnalysisList title="情绪面分析" items={report.analysis.sentiment} />
            <AnalysisList title="资金面分析" items={report.analysis.capitalFlow} />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <AnalysisList title="风险提示" items={report.analysis.risk} danger />
            <SectionCard title="评级上调 / 下调条件">
              <div className="grid gap-3 md:grid-cols-2">
                <TriggerList title="评级上调条件" items={report.ratingChangeTriggers.upgradeTriggers} />
                <TriggerList title="评级下调条件" items={report.ratingChangeTriggers.downgradeTriggers} danger />
              </div>
            </SectionCard>
          </div>

          <SectionCard title="数据完整性说明">
            <div className="grid gap-2 text-xs md:grid-cols-2 xl:grid-cols-4">
              {Object.entries(report.rawFactors).map(([key, value]) => (
                <div key={key} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2">
                  <div className="text-[var(--text-tertiary)]">{key}</div>
                  <div className="finance-number mt-1 break-all text-[var(--text-primary)]">{String(value ?? "-")}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          <div className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-xs leading-6 text-[var(--text-secondary)]">
            {report.ratingDisclaimer}
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-[var(--text-tertiary)]">
            <Link className="text-[var(--color-primary)] hover:underline" href={`/stocks/${report.code}`}>
              返回股票详情
            </Link>
            <span>评级版本：{report.ratingVersion}</span>
            <span>更新时间：{report.updatedAt}</span>
          </div>
        </>
      )}
    </div>
  );
}

function RatingHero({ report }: { report: StockInspectionReport }) {
  return (
    <Card>
      <CardContent className="grid gap-4 p-4 xl:grid-cols-[1fr_1fr_1fr]">
        <div className="space-y-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-semibold">{report.name}</h2>
              <span className="finance-number text-sm text-[var(--color-primary)]">{report.code}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="muted">{report.industry || "未分类"}</Badge>
              {(report.conceptNames || []).slice(0, 4).map((item) => (
                <Badge key={item} tone="warning">
                  {item}
                </Badge>
              ))}
              <Badge tone="default">{report.marketRegime}</Badge>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MiniMetric label="当前价格" value={formatNumber(report.currentPrice)} />
            <MiniMetric label="涨跌幅" value={formatPctPoint(report.pctChange)} />
          </div>
        </div>

        <div className="rounded-md border border-[var(--border-strong)] bg-[var(--bg-elevated)] p-4">
          <div className="text-xs text-[var(--text-tertiary)]">投资评级</div>
          <div className={cn("mt-2 text-4xl font-semibold", ratingTone(report.researchRating))}>{report.researchRating}</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <MiniMetric label="综合评分" value={report.overallScore.toFixed(1)} emphasize />
            <MiniMetric label="风险等级" value={report.riskLevel} />
            <MiniMetric label="数据可信度" value={report.dataConfidence} />
          </div>
          <div className="mt-3 text-xs text-[var(--text-tertiary)]">评级周期：{report.ratingHorizon}</div>
        </div>

        <div className="space-y-3">
          <TargetRange report={report} compact />
          <div className="grid grid-cols-2 gap-2">
            <MiniMetric label="支撑位" value={(report.supportLevels || report.targetPriceRange.supportLevels || []).slice(-2).join(" / ") || "-"} />
            <MiniMetric label="压力位" value={(report.resistanceLevels || report.targetPriceRange.resistanceLevels || []).slice(0, 2).join(" / ") || "-"} />
          </div>
          <div className="text-xs text-[var(--text-tertiary)]">评级更新时间：{report.updatedAt}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function TargetRange({ report, compact = false }: { report: StockInspectionReport; compact?: boolean }) {
  const target = report.targetPriceRange;
  const hasRange = target.low !== null && target.mid !== null && target.high !== null;
  return (
    <div className={compact ? "rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3" : "space-y-3"}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold">目标价区间</div>
        <Badge tone={target.confidence === "高" ? "success" : target.confidence === "中" ? "warning" : "muted"}>可信度 {target.confidence}</Badge>
      </div>
      {hasRange ? (
        <div className="mt-3 grid grid-cols-3 gap-2">
          <MiniMetric label="低位" value={formatNumber(target.low)} />
          <MiniMetric label="中枢" value={formatNumber(target.mid)} emphasize />
          <MiniMetric label="高位" value={formatNumber(target.high)} />
        </div>
      ) : (
        <div className="mt-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 text-sm text-[var(--text-tertiary)]">
          目标价区间数据不足，暂不输出。
        </div>
      )}
      <p className="mt-3 text-xs leading-5 text-[var(--text-tertiary)]">{target.method}</p>
    </div>
  );
}

function SpecialRatingExplanation({ report, mode }: { report: StockInspectionReport; mode: "buy" | "sell" }) {
  const isBuy = mode === "buy";
  return (
    <div className="mt-4 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-sm font-semibold">{isBuy ? "买入评级说明" : "卖出评级说明"}</div>
      <div className="mt-2 grid gap-3 text-sm leading-6 text-[var(--text-secondary)] md:grid-cols-2">
        <ReasonBlock title={isBuy ? "评级依据" : "卖出评级依据"} items={isBuy ? report.keyBullishReasons : report.keyBearishReasons} />
        <ReasonBlock title={isBuy ? "适用前提 / 失效条件" : "风险触发项 / 上调条件"} items={isBuy ? report.invalidConditions || [] : report.ratingChangeTriggers.upgradeTriggers} />
      </div>
      <div className="mt-3 text-xs text-[var(--text-tertiary)]">数据可信度：{report.dataConfidence}。该评级为研究表达，不是交易指令。</div>
    </div>
  );
}

function ReasonBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
      <ul className="mt-2 space-y-1.5">
        {(items.length ? items : ["暂无记录，需人工确认。"]).slice(0, 4).map((item) => (
          <li key={item}>- {item}</li>
        ))}
      </ul>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function ReasonList({ title, items, tone }: { title: string; items: string[]; tone: "success" | "danger" }) {
  return (
    <SectionCard title={title}>
      <ul className="space-y-2 text-sm leading-6">
        {(items.length ? items : ["暂无详细记录，需人工确认。"]).map((item) => (
          <li key={item} className={cn("rounded-md border bg-[var(--bg-elevated)] px-3 py-2", tone === "success" ? "border-[rgba(24,160,88,0.3)] text-[var(--text-secondary)]" : "border-[rgba(230,69,69,0.28)] text-[var(--color-danger)]")}>
            {item}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function AnalysisList({ title, items, danger = false }: { title: string; items?: string[]; danger?: boolean }) {
  return (
    <SectionCard title={title}>
      <ul className="space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
        {(items?.length ? items : ["暂无分析记录。"]).map((item) => (
          <li key={item} className={cn("rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2", danger && "border-[rgba(230,69,69,0.24)] text-[var(--color-danger)]")}>
            {item}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function TriggerList({ title, items, danger = false }: { title: string; items: string[]; danger?: boolean }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-sm font-semibold">{title}</div>
      <ul className="mt-2 space-y-1.5 text-sm leading-6 text-[var(--text-secondary)]">
        {items.map((item) => (
          <li key={item} className={danger ? "text-[var(--color-danger)]" : ""}>
            - {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ScoreCard({ label, value, description }: { label: string; value?: number | null; description: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-2 text-lg font-semibold text-[var(--color-primary)]">{value === null || value === undefined ? "数据不足" : value.toFixed(1)}</div>
      <div className="mt-2 text-xs leading-5 text-[var(--text-tertiary)]">{description}</div>
    </div>
  );
}

function MiniMetric({ label, value, emphasize = false }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2">
      <div className="text-[var(--text-tertiary)]">{label}</div>
      <div className={cn("finance-number mt-1 break-all text-sm font-semibold", emphasize && "text-[var(--color-primary)]")}>{value || "-"}</div>
    </div>
  );
}

function ratingTone(rating: ResearchRating) {
  if (rating === "买入" || rating === "增持") return "text-[var(--color-danger)]";
  if (rating === "持有") return "text-[var(--color-primary)]";
  if (rating === "减持" || rating === "卖出") return "text-[var(--color-success)]";
  return "text-[var(--text-tertiary)]";
}

function buildMarkdown(report: StockInspectionReport) {
  const target = report.targetPriceRange;
  const targetText = target.low !== null && target.mid !== null && target.high !== null ? `${target.low} - ${target.mid} - ${target.high}` : "目标价区间数据不足，暂不输出。";
  return [
    `# ${report.name}（${report.code}）Stock Inspector 研究评级`,
    "",
    `- 研究评级：${report.researchRating}`,
    `- 综合评分：${report.overallScore.toFixed(1)}`,
    `- 风险等级：${report.riskLevel}`,
    `- 数据可信度：${report.dataConfidence}`,
    `- 市场状态：${report.marketRegime}`,
    `- 评级周期：${report.ratingHorizon}`,
    `- 目标价区间：${targetText}`,
    "",
    "## 核心观点",
    report.ratingSummary,
    "",
    "## 看多理由",
    ...report.keyBullishReasons.map((item) => `- ${item}`),
    "",
    "## 看空风险",
    ...report.keyBearishReasons.map((item) => `- ${item}`),
    "",
    "## 评级上调条件",
    ...report.ratingChangeTriggers.upgradeTriggers.map((item) => `- ${item}`),
    "",
    "## 评级下调条件",
    ...report.ratingChangeTriggers.downgradeTriggers.map((item) => `- ${item}`),
    "",
    "## 免责声明",
    report.ratingDisclaimer,
  ].join("\n");
}
