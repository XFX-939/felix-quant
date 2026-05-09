import Link from "next/link";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  BarChart3,
  Database,
  FileSearch,
  Loader2,
  PlayCircle,
  RefreshCw,
  SearchX
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type EmptyStateVariant =
  | "data-missing"
  | "strategy-not-run"
  | "backtest-missing"
  | "no-result"
  | "loading"
  | "error";

type EmptyAction = {
  label: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
};

const variantMeta: Record<EmptyStateVariant, { icon: ReactNode; tone: string; border: string }> = {
  "data-missing": {
    icon: <Database className="h-5 w-5" />,
    tone: "text-[var(--color-primary)]",
    border: "border-[var(--border-strong)]"
  },
  "strategy-not-run": {
    icon: <PlayCircle className="h-5 w-5" />,
    tone: "text-[var(--color-warning)]",
    border: "border-[rgba(245,166,35,0.45)]"
  },
  "backtest-missing": {
    icon: <BarChart3 className="h-5 w-5" />,
    tone: "text-[var(--color-primary)]",
    border: "border-[var(--border-strong)]"
  },
  "no-result": {
    icon: <SearchX className="h-5 w-5" />,
    tone: "text-[var(--text-tertiary)]",
    border: "border-[var(--border-subtle)]"
  },
  loading: {
    icon: <Loader2 className="h-5 w-5 animate-spin" />,
    tone: "text-[var(--color-primary)]",
    border: "border-[var(--border-subtle)]"
  },
  error: {
    icon: <AlertTriangle className="h-5 w-5" />,
    tone: "text-[var(--color-danger)]",
    border: "border-[rgba(230,69,69,0.45)]"
  }
};

export function EmptyState({
  title,
  description,
  reason,
  primaryAction,
  secondaryAction,
  helpLink,
  variant = "no-result",
  compact = false,
  className
}: {
  title: string;
  description: string;
  reason?: string;
  primaryAction?: EmptyAction;
  secondaryAction?: EmptyAction;
  helpLink?: EmptyAction;
  variant?: EmptyStateVariant;
  compact?: boolean;
  className?: string;
}) {
  const meta = variantMeta[variant];
  return (
    <div
      className={cn(
        "rounded-md border border-dashed bg-[var(--bg-elevated)] text-center",
        meta.border,
        compact ? "p-4" : "p-8",
        className
      )}
    >
      <div className={cn("mx-auto flex h-10 w-10 items-center justify-center rounded-md bg-[var(--bg-card)]", meta.tone)}>
        {meta.icon}
      </div>
      <div className="mt-3 text-sm font-semibold text-[var(--text-primary)]">{title}</div>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
      {reason && (
        <div className="mx-auto mt-3 max-w-2xl rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] px-3 py-2 text-xs leading-5 text-[var(--text-tertiary)]">
          {reason}
        </div>
      )}
      {(primaryAction || secondaryAction || helpLink) && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {primaryAction && <ActionButton action={primaryAction} primary />}
          {secondaryAction && <ActionButton action={secondaryAction} />}
          {helpLink && <ActionButton action={helpLink} subtle />}
        </div>
      )}
    </div>
  );
}

function ActionButton({ action, primary = false, subtle = false }: { action: EmptyAction; primary?: boolean; subtle?: boolean }) {
  if (action.href) {
    return (
      <Link
        href={action.href}
        className={cn(
          "inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors",
          primary
            ? "border-[var(--color-primary)] bg-[var(--color-primary)] text-white hover:brightness-110"
            : subtle
              ? "border-transparent text-[var(--text-tertiary)] hover:bg-[var(--bg-card-hover)] hover:text-[var(--color-primary)]"
              : "border-[var(--border-strong)] bg-[var(--bg-card)] text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]"
        )}
      >
        {subtle ? <FileSearch className="h-4 w-4" /> : primary ? <PlayCircle className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
        {action.label}
      </Link>
    );
  }
  return (
    <Button type="button" variant={primary ? "default" : subtle ? "ghost" : "outline"} onClick={action.onClick} disabled={action.disabled}>
      {primary ? <PlayCircle className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
      {action.label}
    </Button>
  );
}
