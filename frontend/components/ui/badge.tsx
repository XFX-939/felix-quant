import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeTone = "default" | "success" | "warning" | "danger" | "muted";

const tones: Record<BadgeTone, string> = {
  default: "border-[var(--border-strong)] bg-[var(--color-primary-soft)] text-[var(--color-primary)]",
  success: "border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] text-[var(--color-success)]",
  warning: "border-[rgba(245,166,35,0.5)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
  danger: "border-[rgba(230,69,69,0.5)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]",
  muted: "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-tertiary)]"
};

export function Badge({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center whitespace-nowrap rounded-sm border px-2 text-xs font-medium",
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
