import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function MetricCard({
  title,
  value,
  hint,
  tone = "default"
}: {
  title: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "up" | "down" | "risk" | "safe";
}) {
  const toneClass =
    tone === "up"
      ? "text-[var(--color-danger)]"
      : tone === "down" || tone === "safe"
        ? "text-[var(--color-success)]"
        : tone === "risk"
          ? "text-[var(--color-warning)]"
          : "text-[var(--text-primary)]";

  return (
    <Card>
      <CardContent className="p-3.5">
        <div className="text-xs text-[var(--text-tertiary)]">{title}</div>
        <div className={cn("finance-number mt-2 min-h-7 text-xl font-semibold", toneClass)}>{value}</div>
        {hint && <div className="mt-1 text-xs text-[var(--text-tertiary)]">{hint}</div>}
      </CardContent>
    </Card>
  );
}

