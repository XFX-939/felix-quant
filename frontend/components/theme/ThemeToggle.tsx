"use client";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/components/theme/ThemeProvider";

export function ThemeToggle() {
  const { resolvedTheme, toggleTheme } = useTheme();
  const nextLabel = resolvedTheme === "dark" ? "切换为浅色模式" : "切换为深色模式";

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      title={nextLabel}
      aria-label={nextLabel}
      onClick={toggleTheme}
      className="border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]"
    >
      {resolvedTheme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </Button>
  );
}

