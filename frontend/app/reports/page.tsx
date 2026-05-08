import { FileText } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export default function ReportsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">研究报告</h1>
        <p className="mt-1 text-sm text-[var(--text-tertiary)]">策略运行、回测依据与人工复盘的后续汇总入口</p>
      </div>
      <Card>
        <CardContent className="flex min-h-64 flex-col items-center justify-center text-center">
          <FileText className="h-10 w-10 text-[var(--color-primary)]" aria-hidden />
          <div className="mt-4 text-base font-semibold">报告中心待扩展</div>
          <p className="mt-2 max-w-md text-sm leading-6 text-[var(--text-tertiary)]">
            当前 MVP 已保留导航入口，后续可接入每日策略运行摘要、周度复盘报告和组合风险报告。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

