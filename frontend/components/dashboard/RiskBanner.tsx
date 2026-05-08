import { AlertTriangle } from "lucide-react";

export function RiskBanner({ text }: { text: string }) {
  return (
    <div className="flex gap-3 rounded-md border border-[var(--border-strong)] bg-[var(--color-primary-soft)] px-3.5 py-3 text-sm text-[var(--text-primary)]">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning)]" aria-hidden />
      <div>
        <span className="font-semibold text-[var(--color-primary)]">风险提示：</span>
        {text}
      </div>
    </div>
  );
}

