"use client";

import * as React from "react";
import { useMemo, useState } from "react";

import type { Judgement, PlaybookEvent, EvidenceCard } from "@/lib/types";
import { EvidenceCardItem } from "./EvidenceCard";

const ROW_GAP = 24;

/**
 * 今日观察事件 — frame fFOSV / Today Playbook timeline.
 *
 * Vertical stack (top → bottom). The shared rail and the circle markers
 * share the marker column's center axis: rail uses `left-1/2 -translate-x-1/2`
 * inside the same column the circle is `justify-center`-ed in, guaranteeing
 * concentric alignment regardless of column width.
 *
 * Each event is individually expandable; expanding shows the related
 * evidence cards (resolved by `event.related_evidence_ids` from the
 * brief-wide evidence pool built from `judgements`).
 */
export function TodayPlaybook({
  events,
  judgements,
}: {
  events: PlaybookEvent[];
  judgements: Judgement[];
}) {
  const evidencePool = useMemo(() => {
    const m = new Map<string, EvidenceCard>();
    for (const j of judgements) {
      for (const ev of j.evidence) m.set(ev.evidence_id, ev);
    }
    return m;
  }, [judgements]);

  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggle = (idx: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });

  const next = events.find((e) => e.is_next) ?? events[0];

  return (
    <section
      aria-labelledby="playbook-heading"
      className="border-b bg-surface"
      style={{ borderColor: "#dfe3e8" }}
    >
      <div className="mx-auto max-w-[1440px] px-8 py-6">
        <div className="flex items-center justify-between">
          <span id="playbook-heading" className="text-label">
            今日观察事件
          </span>
          {next && (
            <span className="font-mono text-[11px] font-bold text-ink-900">
              下一事件 {next.time_hkt} HKT · {next.relative_time_hkt}
            </span>
          )}
        </div>

        <ol className="mt-3 flex flex-col border-y border-line py-6">
          {events.map((event, idx) => {
            const isLast = idx === events.length - 1;
            const isOpen = expanded.has(idx);
            const relatedIds = event.related_evidence_ids ?? [];
            const related = relatedIds
              .map((eid) => evidencePool.get(eid))
              .filter((c): c is EvidenceCard => Boolean(c));

            return (
              <li
                key={event.time_hkt + idx}
                className="grid grid-cols-[110px_24px_1fr] items-start gap-3"
                style={{ paddingBottom: isLast && !isOpen ? 0 : ROW_GAP }}
              >
                <div className="flex flex-col">
                  <span className="font-mono text-[12px] text-ink-900">
                    {event.time_hkt} HKT
                  </span>
                  <span
                    className={[
                      "font-mono text-[10px]",
                      event.is_next ? "text-orange-600" : "text-ink-500",
                    ].join(" ")}
                  >
                    {event.relative_time_hkt}
                  </span>
                </div>

                {/*
                 * Marker column: circle + rail share `left-1/2 -translate-x-1/2`.
                 * Rail extends from below the circle to the bottom of the
                 * row (incl. paddingBottom = ROW_GAP), so it visually links
                 * to the next item's circle.
                 */}
                <div className="relative flex h-full justify-center">
                  <span
                    aria-hidden
                    className="z-10 mt-[6px] inline-block h-[11px] w-[11px] rounded-full border-[1.5px] border-ink-700 bg-canvas"
                  />
                  {!isLast && (
                    <span
                      aria-hidden
                      className="absolute left-1/2 top-[17px] w-px -translate-x-1/2 bg-line"
                      style={{ bottom: -ROW_GAP }}
                    />
                  )}
                </div>

                <div className="flex flex-col gap-1">
                  <span className="font-sans text-[15px] font-medium text-ink-900">
                    {event.label}
                  </span>
                  <span className="font-sans text-[12px] text-ink-500">{event.detail}</span>

                  {related.length > 0 && (
                    <button
                      type="button"
                      onClick={() => toggle(idx)}
                      aria-expanded={isOpen}
                      className="mt-1 inline-flex w-fit items-center gap-1 font-mono text-[11px] text-orange-600 hover:underline"
                    >
                      <Chevron open={isOpen} />
                      {isOpen ? "收起依据" : `查看 ${related.length} 条依据`}
                    </button>
                  )}

                  {isOpen && related.length > 0 && (
                    <div className="mt-3 flex flex-col gap-2">
                      {related.map((card) => (
                        <EvidenceCardItem key={card.evidence_id} card={card} />
                      ))}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}
    >
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}
