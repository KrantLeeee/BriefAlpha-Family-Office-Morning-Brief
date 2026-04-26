"use client";

import * as React from "react";
import type { EvidenceCard as EvidenceCardType } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

/**
 * Evidence card — frame uOtTm / ZmOHQ / tnA5G.
 *
 * Behavior is dispatched by `link_kind`:
 *   - external          -> <a target=_blank>
 *   - internal_demo     -> <button> opens DemoEvidenceModal
 *   - internal_research -> <button> opens DemoEvidenceModal (different footer)
 *   - unavailable       -> non-interactive <div> with hover tooltip
 */
export function EvidenceCardItem({ card }: { card: EvidenceCardType }) {
  const open = useAppStore((s) => s.openDemoEvidenceModal);
  const baseCls =
    "flex flex-col gap-[7px] rounded-card bg-surface px-[18px] py-4 transition-colors";

  const inner = (
    <>
      <span
        className={[
          "font-mono text-[12px]",
          card.conflict ? "text-orange-600" : "text-ink-900",
        ].join(" ")}
      >
        {card.index_label} {card.source_label}
      </span>
      <span className="font-sans text-[13px] text-ink-500">{card.title}</span>
      <p className="font-serif text-[16px] font-medium leading-[1.35] text-ink-700">{card.quote}</p>
      {renderActionLabel(card)}
    </>
  );

  if (card.link_kind === "external" && card.source_link) {
    return (
      <a
        data-evidence-id={card.evidence_id}
        href={card.source_link}
        target="_blank"
        rel="noopener noreferrer"
        className={`${baseCls} hover:bg-warningWash`}
      >
        {inner}
      </a>
    );
  }

  if (card.link_kind === "internal_demo" || card.link_kind === "internal_research") {
    return (
      <button
        type="button"
        data-evidence-id={card.evidence_id}
        onClick={() => open(card, card.link_kind as "internal_demo" | "internal_research")}
        className={`${baseCls} text-left hover:bg-warningWash`}
      >
        {inner}
      </button>
    );
  }

  // unavailable
  return (
    <div
      data-evidence-id={card.evidence_id}
      title="原文链接不可用"
      className={`${baseCls} cursor-not-allowed opacity-70`}
    >
      {inner}
    </div>
  );
}

function renderActionLabel(card: EvidenceCardType) {
  if (card.link_kind === "external") {
    return <span className="font-mono text-[11px] text-orange-600">查看原文 ↗</span>;
  }
  if (card.link_kind === "internal_demo") {
    return <span className="font-mono text-[11px] text-ink-500">示例 evidence · 点击查看</span>;
  }
  if (card.link_kind === "internal_research") {
    return <span className="font-mono text-[11px] text-ink-500">内部研报 · 点击查看</span>;
  }
  return <span className="font-mono text-[11px] text-ink-400">原文链接不可用</span>;
}
