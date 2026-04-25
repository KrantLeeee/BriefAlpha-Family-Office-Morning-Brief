"use client";

import type { EvidenceCard as EvidenceCardType } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

export function EvidenceCardItem({ card }: { card: EvidenceCardType }) {
  const highlighted = useAppStore((s) => s.drawer.highlightedEvidenceId === card.evidence_id);

  return (
    <article
      data-evidence-id={card.evidence_id}
      className={[
        "flex flex-col gap-[7px] rounded-card border border-line bg-surface px-[18px] py-4",
        highlighted ? "ring-2 ring-orange-600 transition-shadow duration-200" : "",
      ].join(" ")}
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
      <a
        href={card.source_link}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-[11px] text-orange-600 hover:underline"
      >
        查看原文 ↗
      </a>
    </article>
  );
}
