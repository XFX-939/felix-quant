"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Save } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatPercent } from "@/lib/format";
import type { DashboardSummary, Signal } from "@/lib/types";

interface RiskOverview {
  single_position_limit: number;
  total_position_suggestion: number;
  industry_concentration: Array<{ industry: string; count: number; ratio: number }>;
  high_risk_count: number;
  medium_risk_count: number;
  high_risk_pool: Signal[];
  warnings: string[];
  latest_backtest?: {
    strategy_name: string;
    max_drawdown: number;
  } | null;
}

interface RiskRule {
  id: number;
  name: string;
  description: string;
  threshold: number;
  enabled: boolean;
}

export default function RiskPage() {
  const [overview, setOverview] = useState<RiskOverview | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [rules, setRules] = useState<RiskRule[]>([]);
  const [drafts, setDrafts] = useState<Record<number, { threshold: string; enabled: string }>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setError(null);
    const [overviewData, ruleData, dashboardData] = await Promise.all([api.riskOverview(), api.riskRules(), api.dashboard()]);
    const typedRules = ruleData as unknown as RiskRule[];
    setOverview(overviewData as unknown as RiskOverview);
    setSummary(dashboardData);
    setRules(typedRules);
    setDrafts(Object.fromEntries(typedRules.map((rule) => [rule.id, { threshold: String(rule.threshold), enabled: String(rule.enabled) }])));
  }

  useEffect(() => {
    load()
      .catch((err) => setError(err instanceof Error ? err.message : "风控加载失败"))
      .finally(() => setLoading(false));
  }, []);

  async function saveRule(rule: RiskRule) {
    const draft = drafts[rule.id];
    setMessage(null);
    setError(null);
    try {
      await api.updateRiskRule(rule.id, {
        threshold: Number(draft.threshold),
        enabled: draft.enabled === "true"
      });
      await load();
      setMessage(`${rule.name} 已更新`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "规则保存失败");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">风控</h1>
        <p className="mt-1 text-sm text-muted-foreground">统一管理仓位、回撤、波动、行业集中度和高风险候选。</p>
      </div>

      {message && <div className="rounded-md border border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] p-3 text-sm text-[var(--color-success)]">{message}</div>}
      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      {loading && (
        <Card>
          <CardContent className="space-y-3 p-4">
            <div className="h-5 w-36 animate-pulse rounded bg-[var(--bg-elevated)]" />
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-24 animate-pulse rounded-md bg-[var(--bg-elevated)]" />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && !overview && (
        <EmptyState
          variant={error ? "error" : "data-missing"}
          title="风控数据未生成"
          description="当前没有可用的风控快照，无法展示仓位、集中度和风险池。"
          reason={error || "请先完成每日后台任务，或到数据中心检查行情和策略运行状态。"}
          primaryAction={{ label: "进入数据中心", href: "/data-center" }}
          secondaryAction={{ label: "查看使用教程", href: "/guide#risk-center" }}
        />
      )}

      {!loading && overview && (
        <>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Metric label="单票最大仓位" value={formatPercent(overview?.single_position_limit)} />
        <Metric label="基础风控上限" value={formatPercent(overview?.total_position_suggestion)} />
        <Metric label="市场状态上限" value={formatPercent(summary?.position_decision?.marketRegimeLimit)} />
        <Metric label="今日最终仓位" value={`${formatPercent(summary?.position_decision?.finalPositionMin)} ~ ${formatPercent(summary?.position_decision?.finalPositionMax)}`} tone="primary" />
        <Metric label="高风险股票" value={String(overview?.high_risk_count ?? 0)} />
      </div>

      <Card>
        <CardContent className="space-y-2 pt-4 text-sm text-[var(--text-secondary)]">
          <div>基础仓位上限不是今日建议仓位，今日最终建议仓位由市场状态、策略质量、风险候选比例和决策模式共同决定。</div>
          <div className="grid gap-2 md:grid-cols-4">
            <Mini label="基础风控" value={formatPercent(summary?.position_decision?.baseRiskLimit)} />
            <Mini label="市场修正" value={formatPercent(summary?.position_decision?.marketRegimeLimit)} />
            <Mini label="策略质量" value={formatPercent(summary?.position_decision?.strategyQualityLimit)} />
            <Mini label="决策模式" value={`${formatPercent(summary?.position_decision?.decisionModeLimitMin)} ~ ${formatPercent(summary?.position_decision?.decisionModeLimitMax)}`} />
          </div>
          {(summary?.position_decision?.reasons || []).map((reason) => (
            <div key={reason} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2 text-xs">
              {reason}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle>行业集中度</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(overview?.industry_concentration || []).map((item) => (
              <div key={item.industry} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>{item.industry}</span>
                  <span className="font-mono">{formatPercent(item.ratio)}</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, item.ratio * 100)}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>风控预警</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(overview?.warnings || []).map((warning) => (
              <div key={warning} className="rounded-md border border-[var(--border-strong)] bg-[var(--color-warning-soft)] p-3 text-sm text-[var(--color-warning)]">
                {warning}
              </div>
            ))}
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
              Dashboard 与风控仓位：{summary?.position_decision ? "一致" : "等待 Dashboard 口径"}，今日最终仓位 {formatPercent(summary?.position_decision?.finalPositionMin)} ~ {formatPercent(summary?.position_decision?.finalPositionMax)}
            </div>
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
              风险观察池：{summary?.candidate_funnel?.riskPool ?? 0} 只；数据质量：{summary?.data_quality?.integrityLevel || "等待生成"}；回测可信度：{summary?.latest_backtest?.validity?.validityLevel || "等待回测"}
            </div>
            {overview?.latest_backtest && (
              <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
                最近回测：{overview.latest_backtest.strategy_name}，最大回撤 {formatPercent(overview.latest_backtest.max_drawdown)}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>风控规则</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>规则</TableHead>
                  <TableHead>说明</TableHead>
                  <TableHead>阈值</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell>{rule.name}</TableCell>
                    <TableCell className="max-w-xl text-muted-foreground">{rule.description}</TableCell>
                    <TableCell>
                      <Input
                        className="w-32"
                        value={drafts[rule.id]?.threshold || ""}
                        onChange={(event) => setDrafts((current) => ({ ...current, [rule.id]: { ...current[rule.id], threshold: event.target.value } }))}
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        className="w-28"
                        value={drafts[rule.id]?.enabled || "true"}
                        onChange={(event) => setDrafts((current) => ({ ...current, [rule.id]: { ...current[rule.id], enabled: event.target.value } }))}
                      >
                        <option value="true">启用</option>
                        <option value="false">停用</option>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button variant="outline" size="sm" onClick={() => saveRule(rule)}>
                        <Save className="h-4 w-4" />
                        保存
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>高风险股票池</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>行业</TableHead>
                  <TableHead>策略</TableHead>
                  <TableHead>评分</TableHead>
                  <TableHead>风险</TableHead>
                  <TableHead>风险理由</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(overview?.high_risk_pool || []).map((signal) => (
                  <TableRow key={signal.id}>
                    <TableCell className="font-mono">
                      <Link href={`/stocks/${signal.stock_code}`} className="text-[var(--color-primary)] hover:underline">
                        {signal.stock_code}
                      </Link>
                    </TableCell>
                    <TableCell>{signal.stock_name}</TableCell>
                    <TableCell>{signal.industry}</TableCell>
                    <TableCell>{signal.strategy_name}</TableCell>
                    <TableCell>{signal.score.toFixed(1)}</TableCell>
                    <TableCell>
                      <RiskBadge level={signal.risk_level} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{signal.risk_reason}</TableCell>
                  </TableRow>
                ))}
                {!overview?.high_risk_pool?.length && (
                  <TableRow>
                    <TableCell colSpan={7} className="py-4">
                      <EmptyState
                        compact
                        variant="no-result"
                        title="当前没有高风险候选"
                        description="风险池为空通常表示今日快照未发现高风险标的，或风控数据尚未覆盖更多股票。"
                        primaryAction={{ label: "查看候选池", href: "/candidates" }}
                        secondaryAction={{ label: "进入数据中心", href: "/data-center" }}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
        </>
      )}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "primary" }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={`mt-3 text-lg font-semibold ${tone === "primary" ? "text-[var(--color-primary)]" : ""}`}>{value}</div>
      </CardContent>
    </Card>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="text-xs text-[var(--text-tertiary)]">{label}</div>
      <div className="finance-number mt-1 font-semibold text-[var(--color-primary)]">{value}</div>
    </div>
  );
}
