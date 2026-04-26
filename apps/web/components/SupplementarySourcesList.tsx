"use client";

import * as React from "react";
import type { EvidenceCard as EvidenceCardType, SupplementarySource } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

export function SupplementarySourcesList({ sources }: { sources: SupplementarySource[] }) {
  const open = useAppStore((s) => s.openDemoEvidenceModal);
  if (sources.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <span className="text-label">补充来源</span>
      <ul className="flex flex-col gap-1">
        {sources.map((s) => (
          <li key={s.evidence_id} className="font-mono text-[11px] text-ink-500">
            {renderSource(s, open)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function renderSource(
  src: SupplementarySource,
  open: (card: EvidenceCardType, kind: "internal_demo" | "internal_research") => void
) {
  if (src.link_kind === "external" && src.source_link) {
    return (
      <a
        href={src.source_link}
        target="_blank"
        rel="noopener noreferrer"
        className="hover:text-orange-600 hover:underline"
      >
        {src.label} ↗
      </a>
    );
  }

  if (src.link_kind === "internal_demo" || src.link_kind === "internal_research") {
    const synthesizedCard: EvidenceCardType = {
      evidence_id: src.evidence_id,
      index_label: "",
      source_label: src.label,
      title: src.label,
      quote: "(辅助来源 — 完整内容请参考主 evidence)",
      source_link: src.source_link,
      link_kind: src.link_kind,
    };
    return (
      <button
        type="button"
        onClick={() => open(synthesizedCard, src.link_kind as "internal_demo" | "internal_research")}
        className="text-left hover:text-orange-600 hover:underline"
      >
        {src.label}
      </button>
    );
  }

  // unavailable
  return (
    <span title="原文链接不可用" className="cursor-not-allowed opacity-70">
      {src.label}
    </span>
  );
}
