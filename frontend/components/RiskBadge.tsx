import { Badge } from "@/components/ui/badge";
import { riskLabel } from "@/lib/format";

export function RiskBadge({ level }: { level?: string | null }) {
  const tone = level === "high" ? "danger" : level === "medium" ? "warning" : level === "low" ? "success" : "muted";
  return <Badge tone={tone}>{riskLabel(level)}风险</Badge>;
}
