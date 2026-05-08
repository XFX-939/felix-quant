"use client";

import { useEffect, useState } from "react";
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

      {saved && <div className="rounded-md border border-emerald-500/35 bg-emerald-500/10 p-3 text-sm text-emerald-100">设置已保存到本地浏览器</div>}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>数据与运行</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Select value={settings.dataSource} onChange={(event) => setSettings((current) => ({ ...current, dataSource: event.target.value }))}>
              <option value="示例本地数据">示例本地数据</option>
              <option value="真实行情数据源">真实行情数据源</option>
            </Select>
            <Input
              type="time"
              value={settings.updateTime}
              onChange={(event) => setSettings((current) => ({ ...current, updateTime: event.target.value }))}
            />
            <Select value={settings.stockUniverse} onChange={(event) => setSettings((current) => ({ ...current, stockUniverse: event.target.value }))}>
              <option value="示例A股核心池">示例A股核心池</option>
              <option value="沪深300">沪深300</option>
              <option value="自定义股票池">自定义股票池</option>
            </Select>
            <Input
              value={settings.localDataPath}
              onChange={(event) => setSettings((current) => ({ ...current, localDataPath: event.target.value }))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>默认参数</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={settings.defaultParams}
              onChange={(event) => setSettings((current) => ({ ...current, defaultParams: event.target.value }))}
              className="min-h-44 font-mono text-xs"
              spellCheck={false}
            />
            <Textarea
              value={settings.riskThresholds}
              onChange={(event) => setSettings((current) => ({ ...current, riskThresholds: event.target.value }))}
              className="min-h-44 font-mono text-xs"
              spellCheck={false}
            />
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

