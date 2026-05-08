"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  HelpCircle,
  ImageOff,
  Info,
  Lightbulb,
  Search,
  ShieldAlert,
  X
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { GuideCallout as GuideCalloutData, GuideImageAsset, GuideSection as GuideSectionData, GuideStep, GuideTerm } from "@/lib/guideContent";
import { cn } from "@/lib/utils";

export function GuideLayout({ sections }: { sections: GuideSectionData[] }) {
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState(sections[0]?.id || "");

  const filteredSections = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return sections;
    return sections.filter((section) => {
      const haystack = [
        section.title,
        section.description,
        section.scenario,
        ...section.steps.flatMap((step) => [step.title, step.text, ...(step.bullets || [])]),
        ...section.results,
        ...section.pitfalls,
        ...(section.faq || []).flatMap((item) => [item.question, item.answer]),
        ...(section.terms || []).flatMap((item) => [item.term, item.definition])
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(keyword);
    });
  }, [query, sections]);

  useEffect(() => {
    const observers = sections.map((section) => {
      const element = document.getElementById(section.id);
      if (!element) return null;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) setActiveId(section.id);
        },
        { rootMargin: "-16% 0px -70% 0px", threshold: 0.01 }
      );
      observer.observe(element);
      return observer;
    });
    return () => observers.forEach((observer) => observer?.disconnect());
  }, [sections]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="text-sm text-[var(--text-tertiary)]">User Guide</div>
          <h1 className="mt-1 text-xl font-semibold">使用教程</h1>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--text-tertiary)]">
            从数据同步、策略运行、候选分析、回测验证到风险复盘，帮助用户快速上手 Felix量化。
          </p>
        </div>
        <Link href="/" className="inline-flex">
          <Button variant="outline">
            <ChevronRight className="h-4 w-4 rotate-180" />
            返回 Dashboard
          </Button>
        </Link>
      </div>

      <GuideCallout
        callout={{
          type: "warning",
          title: "使用边界",
          text: "本教程面向个人量化研究和投资复盘操作，不包含任何收益承诺，也不构成投资建议。"
        }}
      />

      <GuideSearch query={query} onQueryChange={setQuery} resultCount={filteredSections.length} />

      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <GuideSidebar sections={sections} filteredSections={filteredSections} activeId={activeId} />
        <div className="min-w-0 space-y-5">
          <GuideProgressNav sections={sections} activeId={activeId} />
          {filteredSections.map((section) => (
            <GuideSection key={section.id} section={section} />
          ))}
          {!filteredSections.length && (
            <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-10 text-center text-sm text-[var(--text-tertiary)]">
              没有找到匹配内容。可以尝试搜索“回测”“数据不足”“候选池”或“策略收益”。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function GuideSidebar({
  sections,
  filteredSections,
  activeId
}: {
  sections: GuideSectionData[];
  filteredSections: GuideSectionData[];
  activeId: string;
}) {
  const visibleIds = new Set(filteredSections.map((section) => section.id));

  return (
    <aside className="xl:sticky xl:top-24 xl:self-start">
      <details className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 xl:hidden">
        <summary className="cursor-pointer text-sm font-semibold">教程目录</summary>
        <GuideNavList sections={sections.filter((section) => visibleIds.has(section.id))} activeId={activeId} />
      </details>
      <div className="hidden rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 xl:block">
        <div className="flex items-center gap-2 px-2 pb-2 text-sm font-semibold">
          <BookOpen className="h-4 w-4 text-[var(--color-primary)]" />
          教程目录
        </div>
        <GuideNavList sections={sections.filter((section) => visibleIds.has(section.id))} activeId={activeId} />
      </div>
    </aside>
  );
}

function GuideNavList({ sections, activeId }: { sections: GuideSectionData[]; activeId: string }) {
  return (
    <nav className="mt-2 space-y-1">
      {sections.map((section, index) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          className={cn(
            "flex items-center gap-2 rounded-md px-2 py-2 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--color-primary-soft)] hover:text-[var(--color-primary)]",
            activeId === section.id && "bg-[var(--color-primary-soft)] text-[var(--color-primary)]"
          )}
        >
          <span className="finance-number w-5 text-[var(--text-tertiary)]">{index + 1}</span>
          <span className="min-w-0 flex-1 truncate">{section.title}</span>
        </a>
      ))}
    </nav>
  );
}

export function GuideSearch({
  query,
  onQueryChange,
  resultCount
}: {
  query: string;
  onQueryChange: (value: string) => void;
  resultCount: number;
}) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[var(--text-tertiary)]" aria-hidden />
        <Input
          className="pl-9"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="搜索教程内容，例如：数据不足、批量回测、候选池、风险中枢"
        />
      </div>
      <div className="mt-2 text-xs text-[var(--text-tertiary)]">匹配章节：{resultCount} 个</div>
    </div>
  );
}

export function GuideProgressNav({ sections, activeId }: { sections: GuideSectionData[]; activeId: string }) {
  const activeIndex = Math.max(0, sections.findIndex((section) => section.id === activeId));
  const activeSection = sections[activeIndex];

  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-3 md:flex-row md:items-center md:justify-between">
      <div className="text-sm">
        <span className="text-[var(--text-tertiary)]">当前章节：</span>
        <span className="font-semibold">{activeSection?.title || sections[0]?.title || "-"}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="h-2 w-40 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
          <div className="h-full rounded-full bg-[var(--color-primary)]" style={{ width: `${((activeIndex + 1) / Math.max(1, sections.length)) * 100}%` }} />
        </div>
        <span className="finance-number text-xs text-[var(--text-tertiary)]">
          {activeIndex + 1}/{sections.length}
        </span>
      </div>
    </div>
  );
}

export function GuideSection({ section }: { section: GuideSectionData }) {
  return (
    <section id={section.id} className="scroll-mt-24 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)]">
      <div className="border-b border-[var(--border-subtle)] p-5">
        <div className="text-xs uppercase tracking-[0.16em] text-[var(--text-tertiary)]">Guide Section</div>
        <h2 className="mt-2 text-xl font-semibold">{section.title}</h2>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--text-secondary)]">{section.description}</p>
      </div>
      <div className="space-y-5 p-5">
        <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
          <div className="text-xs font-semibold text-[var(--text-tertiary)]">适用场景</div>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{section.scenario}</p>
        </div>

        {section.image && <GuideImage image={section.image} />}

        {section.callouts?.map((callout) => <GuideCallout key={`${section.id}-${callout.title}`} callout={callout} />)}

        <div>
          <h3 className="text-sm font-semibold">操作步骤</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {section.steps.map((step, index) => (
              <GuideStepCard key={`${section.id}-${step.title}`} step={step} index={index} />
            ))}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <ResultList title="看什么结果" items={section.results} tone="success" />
          <ResultList title="常见坑" items={section.pitfalls} tone="warning" />
        </div>

        {section.faq && <GuideFAQ items={section.faq} />}
        {section.terms && <GuideTermList terms={section.terms} />}
      </div>
    </section>
  );
}

export function GuideStepCard({ step, index }: { step: GuideStep; index: number }) {
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-start gap-3">
        <div className="finance-number flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--color-primary-soft)] text-xs font-semibold text-[var(--color-primary)]">
          {index + 1}
        </div>
        <div className="min-w-0">
          <h4 className="text-sm font-semibold">{step.title}</h4>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{step.text}</p>
          {step.bullets && (
            <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--text-tertiary)]">
              {step.bullets.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-[var(--color-primary)]">-</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export function GuideImage({ image }: { image: GuideImageAsset }) {
  const [open, setOpen] = useState(false);
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div className="rounded-md border border-dashed border-[var(--border-strong)] bg-[var(--bg-elevated)] p-6 text-center text-sm text-[var(--text-tertiary)]">
        <ImageOff className="mx-auto h-8 w-8 text-[var(--text-tertiary)]" />
        <div className="mt-2 font-medium">{image.title}</div>
        <div className="mt-1">截图暂未生成，请启动本地页面后重新生成教程截图。</div>
      </div>
    );
  }

  return (
    <>
      <figure className="overflow-hidden rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
        <button className="block w-full cursor-zoom-in text-left" onClick={() => setOpen(true)} type="button">
          <Image
            src={image.src}
            alt={image.title}
            width={1440}
            height={900}
            className="h-auto w-full object-cover"
            onError={() => setFailed(true)}
          />
        </button>
        <figcaption className="border-t border-[var(--border-subtle)] px-3 py-2 text-xs leading-5 text-[var(--text-tertiary)]">
          <span className="font-semibold text-[var(--text-secondary)]">{image.title}：</span>
          {image.caption}
        </figcaption>
      </figure>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setOpen(false)}>
          <div className="relative max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-md bg-[var(--bg-card)]" onClick={(event) => event.stopPropagation()}>
            <button
              type="button"
              className="absolute right-3 top-3 z-10 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-card)] p-2 text-[var(--text-secondary)] shadow"
              onClick={() => setOpen(false)}
              aria-label="关闭截图预览"
            >
              <X className="h-4 w-4" />
            </button>
            <Image src={image.src} alt={image.title} width={1440} height={900} className="max-h-[92vh] w-full object-contain" />
          </div>
        </div>
      )}
    </>
  );
}

export function GuideCallout({ callout }: { callout: GuideCalloutData }) {
  const style = calloutStyles[callout.type];
  const Icon = style.icon;

  return (
    <div className={cn("rounded-md border p-3 text-sm leading-6", style.className)}>
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <div className="font-semibold">{callout.title}</div>
          <div className="mt-1">{callout.text}</div>
        </div>
      </div>
    </div>
  );
}

export function GuideFAQ({ items }: { items: Array<{ question: string; answer: string }> }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">常见问题</h3>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <details key={item.question} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <summary className="cursor-pointer text-sm font-semibold">{item.question}</summary>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{item.answer}</p>
          </details>
        ))}
      </div>
    </div>
  );
}

export function GuideTermList({ terms }: { terms: GuideTerm[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">术语解释</h3>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {terms.map((item) => (
          <div key={item.term} className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
            <div className="text-sm font-semibold text-[var(--color-primary)]">{item.term}</div>
            <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{item.definition}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResultList({ title, items, tone }: { title: string; items: string[]; tone: "success" | "warning" }) {
  const Icon = tone === "success" ? CheckCircle2 : AlertTriangle;
  return (
    <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Icon className={cn("h-4 w-4", tone === "success" ? "text-[var(--color-success)]" : "text-[var(--color-warning)]")} />
        {title}
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--text-secondary)]">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className={tone === "success" ? "text-[var(--color-success)]" : "text-[var(--color-warning)]"}>-</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const calloutStyles = {
  info: {
    icon: Info,
    className: "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-secondary)]"
  },
  warning: {
    icon: AlertTriangle,
    className: "border-[var(--border-strong)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]"
  },
  danger: {
    icon: ShieldAlert,
    className: "border-[rgba(230,69,69,0.45)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]"
  },
  success: {
    icon: CheckCircle2,
    className: "border-[rgba(24,160,88,0.45)] bg-[var(--color-success-soft)] text-[var(--color-success)]"
  },
  tip: {
    icon: Lightbulb,
    className: "border-[var(--border-strong)] bg-[var(--color-primary-soft)] text-[var(--text-secondary)]"
  }
} satisfies Record<
  GuideCalloutData["type"],
  {
    icon: typeof HelpCircle;
    className: string;
  }
>;

export function GuideBadge({ children }: { children: string }) {
  return <Badge tone="muted">{children}</Badge>;
}
