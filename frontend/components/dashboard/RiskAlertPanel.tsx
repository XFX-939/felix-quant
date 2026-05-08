import { AlertTriangle } from "lucide-react";

import { RiskBadge } from "@/components/RiskBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { defaultRiskChecks } from "@/lib/dashboardMock";

export function RiskAlertPanel({ alerts }: { alerts: string[] }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-[var(--color-warning)]" aria-hidden />
        <CardTitle>风险预警</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {defaultRiskChecks.map((item) => (
          <div key={item.name} className="flex items-center justify-between gap-3 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-sm">
            <div>
              <div className="font-medium">{item.name}</div>
              <div className="mt-1 text-xs text-[var(--text-tertiary)]">{item.detail}</div>
            </div>
            <RiskBadge level={item.level} />
          </div>
        ))}
        {alerts.map((alert) => (
          <div key={alert} className="rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] p-3 text-xs text-[var(--text-secondary)]">
            {alert}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

