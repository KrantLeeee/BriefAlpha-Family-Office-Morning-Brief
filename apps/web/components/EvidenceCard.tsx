"use client";

import type { EvidenceCard as EvidenceCardType } from "@/lib/types";

/**
 * Evidence card — frame uOtTm / ZmOHQ / tnA5G.
 *
 * The whole card is a link to the original source. There is no "selected"
 * or "highlighted" state — per design feedback, the card surface stays
 * plain white in every situation; the only feedback is `:hover` /
 * `:focus-visible` which the global focus ring handles.
 */
export function EvidenceCardItem({ card }: { card: EvidenceCardType }) {
  return (
    <a
      data-evidence-id={card.evidence_id}
      href={card.source_link}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col gap-[7px] rounded-card bg-surface px-[18px] py-4 transition-colors hover:bg-warningWash"
    >
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
      <span className="font-mono text-[11px] text-orange-600">查看原文 ↗</span>
    </a>
  );
}
