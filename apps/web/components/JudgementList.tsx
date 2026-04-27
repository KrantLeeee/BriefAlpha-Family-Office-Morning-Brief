"use client";

import * as React from "react";
import { useState } from "react";

import type { Judgement } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

const VISIBLE_BY_DEFAULT = 3;

function renderLevelLabel(j: Judgement, openReviewModal: (id: string) => void) {
  if (!j.review) {
    return (
      <span
        className={[
          "font-sans text-[11px] font-medium",
          j.level === "elevated" ? "text-orange-600" : "text-ink-500",
        ].join(" ")}
      >
        {j.level_label}
      </span>
    );
  }
  const isReviewed = j.review.status === "reviewed";
  const cleaned = j.level_label.replace(" · ⚠ 待复核", "");
  const label = isReviewed ? `${cleaned} · ✓ 已审` : j.level_label;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        openReviewModal(j.id);
      }}
      // Permanent dotted underline + cursor-pointer so the chip reads as
      // an interactive control at first glance — without it users can't
      // tell that "关注 · ⚠ 待复核" is the click target for the review
      // modal (the entire judgement row also opens the evidence drawer,
      // so a flat label collapses into the row's affordance).
      className={[
        "cursor-pointer font-sans text-[11px] font-medium underline decoration-dotted underline-offset-2 hover:decoration-solid focus:outline-none focus-visible:ring-1 focus-visible:ring-orange-600",
        isReviewed ? "text-ink-500" : "text-orange-600",
      ].join(" ")}
      title="点击查看复核详情"
      aria-label={`复核详情 ${j.title}`}
    >
      {label}
    </button>
  );
}

export function JudgementList({ judgements }: { judgements: Judgement[] }) {
  const openDrawer = useAppStore((s) => s.openDrawer);
  const openReviewModal = useAppStore((s) => s.openReviewModal);
  const [showAll, setShowAll] = useState(false);

  const sorted = [...judgements].sort((a, b) => a.rank - b.rank);
  const visible = showAll ? sorted : sorted.slice(0, VISIBLE_BY_DEFAULT);

  return (
    <section
      aria-labelledby="ai-priority-heading"
      className="flex flex-col border-y border-line bg-canvas"
    >
      <div className="flex items-center justify-between px-3 py-[14px]">
        <span id="ai-priority-heading" className="text-label">
          AI 组合研判
        </span>
        <button
          type="button"
          aria-label="关于研判排序的说明"
          className="font-mono text-[10px] text-ink-300 hover:text-ink-500"
        >
          ?
        </button>
      </div>

      <ul className="flex flex-col">
        {visible.map((j, idx) => (
          <li
            key={j.id}
            className={[
              "flex items-start gap-4 px-3 py-[14px]",
              idx === 0 ? "" : "border-t border-line",
              j.level === "elevated" ? "bg-warningWash border-l-[3px] border-l-orange-600" : "",
            ].join(" ")}
          >
            <div
              id={`judgement-row-${j.id}`}
              role="button"
              tabIndex={0}
              onClick={() =>
                openDrawer(j.id, {
                  triggerElementId: `judgement-row-${j.id}`,
                })
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openDrawer(j.id, {
                    triggerElementId: `judgement-row-${j.id}`,
                  });
                }
              }}
              className="grid w-full grid-cols-[18px_60px_1fr_118px] items-start gap-4 text-left cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-600"
            >
              <span
                className={[
                  "font-mono text-[12px]",
                  j.level === "elevated" ? "text-orange-600" : "text-ink-500",
                ].join(" ")}
              >
                {String(j.rank).padStart(2, "0")}
              </span>
              {renderLevelLabel(j, openReviewModal)}
              <span className="flex flex-col gap-[5px]">
                <span
                  className={[
                    "font-sans text-[16px] font-medium",
                    j.level === "elevated" ? "text-orange-600" : "text-ink-700",
                  ].join(" ")}
                >
                  {j.title}
                </span>
                <span className="font-mono text-[11px] leading-[1.35] text-ink-500">{j.metadata}</span>
              </span>
              <span className="text-right font-mono text-[11px] text-ink-700">
                证据 ({j.evidence_count}) →
              </span>
            </div>
          </li>
        ))}
      </ul>

      {sorted.length > VISIBLE_BY_DEFAULT && (
        <div className="border-t border-line px-3 py-[10px]">
          <button
            type="button"
            onClick={() => setShowAll((v) => !v)}
            className="font-mono text-[11px] text-orange-600 hover:underline"
          >
            {showAll ? "收起" : `查看全部 (${sorted.length})`}
          </button>
        </div>
      )}
    </section>
  );
}
