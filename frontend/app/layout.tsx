import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { ThemeProvider, ThemeScript } from "@/components/theme/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Felix量化 - Quant Research Terminal",
  description: "Felix量化，基于市场状态、策略信号、风险约束和回测验证的个人量化研究终端"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>
        <ThemeScript />
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
