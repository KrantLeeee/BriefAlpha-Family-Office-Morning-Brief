"use client";

import { useAppStore } from "@/store/use-app-store";
import type { BaseCase, Judgement } from "@/lib/types";
import { TrendIcon } from "./TrendIcon";

interface Props {
  baseCase: BaseCase;
  judgements: Judgement[];
}

/**
 * Right column of the Summary Strip — frame fFOSV / Mvgyb.
 *
 * Canonical order (top → bottom):
 *   1. Estimate module (隔夜估算 + -1.09% + ▼ explainer)
 *   2. Base case headline module:
 *      - "今日核心判断" label
 *      - headlineRow: 3px orange rect (h=fill_container) + faint Fraunces "
 *        decoration (color #A8A8A3, opacity 0.32) + Fraunces 30 headline
 *      - summaryFrame: "AI 详细研判" label + summary with [n] citations
 *      - evChip: 证据 (N) → link in orange
 *
 * The container has a single thin gray left border (per canvas Mvgyb stroke
 * left=1 #E8E7E1) — NOT a 3px orange container border.
 */
export function BaseCaseHeadline({ baseCase, judgements }: Props) {
  return (
    <div className="flex flex-1 flex-col gap-7 border-l border-line pl-6">
      <Estimate baseCase={baseCase} />
      <BaseCaseBody baseCase={baseCase} judgements={judgements} />
    </div>
  );
}

function Estimate({ baseCase }: { baseCase: BaseCase }) {
  const valueColor = baseCase.estimate_direction === "down" ? "#DB2627" : "#15803D";
  return (
    <div className="flex flex-col gap-2">
      <span className="text-label">{baseCase.estimate_label}</span>
      <div className="flex flex-wrap items-baseline gap-3">
        <span
          className="font-mono text-[32px] font-bold leading-none"
          style={{ color: valueColor }}
        >
          {baseCase.estimate_value}
        </span>
        <span className="inline-flex items-baseline gap-2 font-sans text-[13px] leading-[1.45] text-ink-500">
          <TrendIcon trend={baseCase.estimate_direction} className="text-[12px]" />
          <span>{baseCase.estimate_explainer}</span>
        </span>
      </div>
    </div>
  );
}

function BaseCaseBody({ baseCase, judgements }: Props) {
  const openDrawer = useAppStore((s) => s.openDrawer);
  const elevatedCount = judgements.filter((j) => j.level === "elevated").length;

  return (
    <div className="flex flex-col gap-[18px]">
      <span className="text-label">{baseCase.headline_label}</span>

      {/* headlineRow — 3px orange rect (fills row height) + decoration + headline */}
      <div className="flex items-stretch gap-4">
        <span aria-hidden className="w-[3px] flex-none self-stretch bg-orange-600" />
        <div className="flex flex-col gap-3">
          <span
            aria-hidden
            className="block font-serif text-[40px] font-black leading-none text-ink-300 select-none"
            style={{ opacity: 0.32, height: 16 }}
          >
            “
          </span>
          <h1 className="font-serif text-[30px] font-medium leading-[1.1] text-ink-900">
            {baseCase.headline}
          </h1>
        </div>
      </div>

      <SummaryWithCitations summary={baseCase.summary} judgements={judgements} onCitation={openDrawer} />

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-meta-mono">
          证据锚点 <span className="text-ink-900">{baseCase.evidence_count}</span> 条
        </span>
        {elevatedCount > 0 && (
          <span className="rounded-chip bg-warningWash px-2 py-[2px] font-mono text-[10px] font-medium text-orange-600">
            {elevatedCount} 项 elevated
          </span>
        )}
      </div>
    </div>
  );
}

function SummaryWithCitations({
  summary,
  judgements,
  onCitation,
}: {
  summary: string;
  judgements: Judgement[];
  onCitation: (
    judgementId: string,
    options?: { triggerElementId?: string; highlightEvidenceId?: string }
  ) => void;
}) {
  const parts = summary.split(/(\[\d+\])/g);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-label">AI 详细研判</span>
      <p className="font-sans text-[14px] leading-[1.55] text-ink-700">
        {parts.map((part, idx) => {
          const m = /^\[(\d+)\]$/.exec(part);
          if (!m) return <span key={idx}>{part}</span>;

          const refIndex = Number(m[1]) - 1;
          const j = judgements[refIndex];
          const triggerId = `cite-${j?.id ?? refIndex}`;

          if (!j) return <span key={idx}>{part}</span>;
          return (
            <button
              key={idx}
              id={triggerId}
              type="button"
              onClick={() =>
                onCitation(j.id, {
                  triggerElementId: triggerId,
                })
              }
              className="mx-[1px] inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-chip border border-orange-600 px-[3px] font-mono text-[10px] text-orange-600 hover:bg-warningWash"
              aria-label={`查看研判 ${j.rank} 的证据`}
            >
              {part}
            </button>
          );
        })}
      </p>
    </div>
  );
}
