"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const defaultSettings = {
  dataSource: "示例本地数据",
  updateTime: "16:10",
  stockUniverse: "示例A股核心池",
  defaultParams: "{\n  \"min_score\": 60,\n  \"ma_short\": 20,\n  \"ma_long\": 60\n}",
  riskThresholds: "{\n  \"single_position_limit\": 0.2,\n  \"max_drawdown_alert\": 0.18,\n  \"loss_streak_alert\": 3\n}",
  localDataPath: "data/quant_research.sqlite3"
};

export default function SettingsPage() {
  const [settings, setSettings] = useState(defaultSettings);
  const [saved, setSaved] = useState(false);

  const formattedDefaultParams = useMemo(() => formatJson(settings.defaultParams), [settings.defaultParams]);
  const formattedRiskThresholds = useMemo(() => formatJson(settings.riskThresholds), [settings.riskThresholds]);

  useEffect(() => {
    const stored = window.localStorage.getItem("quant-settings");
    if (stored) {
      setSettings(JSON.parse(stored));
    }
  }, []);

  function save() {
    window.localStorage.setItem("quant-settings", JSON.stringify(settings));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">系统设置</h1>
        <p className="mt-1 text-sm text-muted-foreground">数据源、更新时间、股票池、策略默认参数和本地数据路径</p>
      </div>

      {saved && <div className="rounded-md border border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] p-3 text-sm text-[var(--color-success)]">设置已保存到本地浏览器</div>}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>数据与运行</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SettingField label="数据源" help="生产环境优先使用后端数据库快照，前端只展示同步结果。">
              <Select value={settings.dataSource} onChange={(event) => setSettings((current) => ({ ...current, dataSource: event.target.value }))}>
                <option value="示例本地数据">示例本地数据</option>
                <option value="真实行情数据源">真实行情数据源</option>
              </Select>
            </SettingField>
            <SettingField label="每日自动刷新时间" help="用于本地提示；服务器定时任务以后台配置为准。">
              <Input
                type="time"
                value={settings.updateTime}
                onChange={(event) => setSettings((current) => ({ ...current, updateTime: event.target.value }))}
              />
            </SettingField>
            <SettingField label="默认股票池" help="决定候选池和回测的默认研究范围。">
              <Select value={settings.stockUniverse} onChange={(event) => setSettings((current) => ({ ...current, stockUniverse: event.target.value }))}>
                <option value="示例A股核心池">示例A股核心池</option>
                <option value="沪深300">沪深300</option>
                <option value="自定义股票池">自定义股票池</option>
              </Select>
            </SettingField>
            <SettingField label="本地数据库路径" help="仅用于本地运行时说明，不会在前端暴露密钥。">
              <Input
                value={settings.localDataPath}
                onChange={(event) => setSettings((current) => ({ ...current, localDataPath: event.target.value }))}
              />
            </SettingField>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>策略参数</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <SettingField label="最低入选评分" help="默认 min_score，低于该分数的候选通常进入观察或复盘。">
              <Input value={readJsonValue(settings.defaultParams, "min_score")} onChange={(event) => setSettings((current) => ({ ...current, defaultParams: writeJsonValue(current.defaultParams, "min_score", Number(event.target.value)) }))} />
            </SettingField>
            <div className="grid gap-3 sm:grid-cols-2">
              <SettingField label="短期均线" help="ma_short">
                <Input value={readJsonValue(settings.defaultParams, "ma_short")} onChange={(event) => setSettings((current) => ({ ...current, defaultParams: writeJsonValue(current.defaultParams, "ma_short", Number(event.target.value)) }))} />
              </SettingField>
              <SettingField label="长期均线" help="ma_long">
                <Input value={readJsonValue(settings.defaultParams, "ma_long")} onChange={(event) => setSettings((current) => ({ ...current, defaultParams: writeJsonValue(current.defaultParams, "ma_long", Number(event.target.value)) }))} />
              </SettingField>
            </div>
            <details className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <summary className="cursor-pointer text-sm font-medium text-[var(--color-primary)]">高级参数 JSON</summary>
              <Textarea
                value={formattedDefaultParams}
                onChange={(event) => setSettings((current) => ({ ...current, defaultParams: event.target.value }))}
                className="mt-3 min-h-44 font-mono text-xs"
                spellCheck={false}
              />
            </details>
          </CardContent>
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>风控参数</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-3">
            <SettingField label="单票仓位上限" help="single_position_limit，例如 0.2 表示 20%。">
              <Input value={readJsonValue(settings.riskThresholds, "single_position_limit")} onChange={(event) => setSettings((current) => ({ ...current, riskThresholds: writeJsonValue(current.riskThresholds, "single_position_limit", Number(event.target.value)) }))} />
            </SettingField>
            <SettingField label="回撤预警阈值" help="max_drawdown_alert，例如 0.18 表示 18%。">
              <Input value={readJsonValue(settings.riskThresholds, "max_drawdown_alert")} onChange={(event) => setSettings((current) => ({ ...current, riskThresholds: writeJsonValue(current.riskThresholds, "max_drawdown_alert", Number(event.target.value)) }))} />
            </SettingField>
            <SettingField label="连续亏损预警" help="loss_streak_alert。">
              <Input value={readJsonValue(settings.riskThresholds, "loss_streak_alert")} onChange={(event) => setSettings((current) => ({ ...current, riskThresholds: writeJsonValue(current.riskThresholds, "loss_streak_alert", Number(event.target.value)) }))} />
            </SettingField>
            <details className="md:col-span-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
              <summary className="cursor-pointer text-sm font-medium text-[var(--color-primary)]">高级风控 JSON</summary>
              <Textarea
                value={formattedRiskThresholds}
                onChange={(event) => setSettings((current) => ({ ...current, riskThresholds: event.target.value }))}
                className="mt-3 min-h-40 font-mono text-xs"
                spellCheck={false}
              />
            </details>
          </CardContent>
        </Card>
      </div>

      <Button onClick={save}>
        <Save className="h-4 w-4" />
        保存设置
      </Button>
    </div>
  );
}

function SettingField({ label, help, children }: { label: string; help: string; children: ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-medium">{label}</span>
      {children}
      <span className="block text-xs leading-5 text-[var(--text-tertiary)]">{help}</span>
    </label>
  );
}

function parseJsonObject(value: string) {
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function formatJson(value: string) {
  const parsed = parseJsonObject(value);
  if (!Object.keys(parsed).length) return value;
  return JSON.stringify(parsed, null, 2);
}

function readJsonValue(source: string, key: string) {
  const value = parseJsonObject(source)[key];
  return value === undefined || value === null ? "" : String(value);
}

function writeJsonValue(source: string, key: string, value: number) {
  const parsed = parseJsonObject(source);
  parsed[key] = Number.isFinite(value) ? value : "";
  return JSON.stringify(parsed, null, 2);
}
