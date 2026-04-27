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
  const title = cleanDisplayText(card.title);
  const quote = cleanEvidenceQuote(card.quote, title);

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
      <span className="break-words font-sans text-[13px] text-ink-500">{title}</span>
      {quote && (
        <p className="break-words font-serif text-[16px] font-medium leading-[1.35] text-ink-700">
          {quote}
        </p>
      )}
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

function cleanDisplayText(value: string): string {
  return formatLongDecimals(
    decodeEntities(value)
      .replace(/<a\b[^>]*(?:>|$)/gi, " ")
      .replace(/<\/a>|<font\b[^>]*(?:>|$)|<\/font>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/https?:\/\/\S+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
  );
}

function cleanEvidenceQuote(value: string, title: string): string {
  const cleaned = cleanDisplayText(value);
  const rawLooksLikeHtmlLeak = /<a\b|href=|news\.google\.com\/rss\/articles/i.test(value);
  const cleanedLooksLikeUrlDebris = /href=|target=|_blank|oc=5|CBMi/i.test(cleaned);
  if (rawLooksLikeHtmlLeak || cleanedLooksLikeUrlDebris) {
    return title;
  }
  return cleaned;
}

function decodeEntities(value: string): string {
  return value
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/g, "'");
}

function formatLongDecimals(value: string): string {
  return value.replace(/([+-]?\d+\.\d{3,})/g, (match) => {
    const n = Number.parseFloat(match);
    return Number.isFinite(n) ? n.toFixed(2) : match;
  });
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
