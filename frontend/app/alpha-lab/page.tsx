"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import type { AlphaLabItem } from "@/lib/types";

export default function AlphaLabPage() {
  const [items, setItems] = useState<AlphaLabItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.alphaLab().then(setItems).catch((err) => setError(err instanceof Error ? err.message : "AlphaLab 加载失败"));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">AlphaLab</h1>
        <p className="mt-1 text-sm text-[var(--text-tertiary)]">公式化 Alpha 因子实验室，仅用于研究和复盘，不进入主观察清单</p>
      </div>

      {error && <div className="rounded-md border border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</div>}

      <Card>
        <CardHeader>
          <CardTitle>价量 Alpha 第一版目录</CardTitle>
          <p className="text-xs text-[var(--text-tertiary)]">IC、RankIC、分组收益等指标等待后续因子回测引擎填充。</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto scrollbar-thin">
            <Table className="min-w-[980px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Alpha</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>公式</TableHead>
                  <TableHead>IC</TableHead>
                  <TableHead>RankIC</TableHead>
                  <TableHead>换手率</TableHead>
                  <TableHead>有效性评分</TableHead>
                  <TableHead>状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.alphaId}>
                    <TableCell className="finance-number text-[var(--color-primary)]">{item.alphaId}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell className="font-mono text-xs text-[var(--text-secondary)]">{item.formula}</TableCell>
                    <TableCell>{valueOrDash(item.ic)}</TableCell>
                    <TableCell>{valueOrDash(item.rankIc)}</TableCell>
                    <TableCell>{valueOrDash(item.turnover)}</TableCell>
                    <TableCell>{valueOrDash(item.validityScore)}</TableCell>
                    <TableCell>
                      <Badge tone={item.includedInCandidatePool ? "warning" : "muted"}>
                        {item.includedInCandidatePool ? "进入研究池" : "研究专用"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function valueOrDash(value: number | null) {
  return value === null || value === undefined ? "-" : value.toFixed(4);
}
