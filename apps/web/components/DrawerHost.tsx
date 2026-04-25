"use client";

import { useEffect, useRef } from "react";

import { EvidenceCardItem } from "./EvidenceCard";
import { LocalQaInput } from "./LocalQaInput";
import { ReasoningChain } from "./ReasoningChain";
import { SupplementarySourcesList } from "./SupplementarySourcesList";

import { useAppStore } from "@/store/use-app-store";

export function DrawerHost() {
  const drawer = useAppStore((s) => s.drawer);
  const close = useAppStore((s) => s.closeDrawer);
  const judgement = useAppStore((s) =>
    drawer.judgementId ? s.brief?.judgements.find((j) => j.id === drawer.judgementId) : undefined
  );
  const briefId = useAppStore((s) => s.brief?.brief_id ?? "");

  const ref = useRef<HTMLDivElement | null>(null);

  // Manage Esc / outside-click close + focus return per Nh2S4 spec.
  useEffect(() => {
    if (!drawer.open) return;

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        close();
      }
    }
    function onClick(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) {
        close();
      }
    }

    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [drawer.open, close]);

  // Return focus to triggering element when drawer closes.
  useEffect(() => {
    if (drawer.open) return;
    if (!drawer.triggerElementId) return;
    const el = document.getElementById(drawer.triggerElementId);
    el?.focus();
  }, [drawer.open, drawer.triggerElementId]);

  if (!drawer.open || !judgement) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`研判 ${judgement.rank} 详情`}
      className="fixed inset-y-0 right-0 z-40 w-full max-w-[640px] bg-canvas shadow-drawer transition-transform duration-200 sm:w-[560px] md:w-[600px] lg:w-[640px]"
      ref={ref}
    >
      <div className="flex h-full flex-col gap-[22px] overflow-y-auto px-[38px] py-[30px]">
        <CloseRow onClose={close} />

        <header className="flex flex-col gap-4">
          <span
            className={[
              "font-mono text-[11px]",
              judgement.requires_review ? "text-orange-600" : "text-ink-500",
            ].join(" ")}
          >
            研判 {String(judgement.rank).padStart(2, "0")} · {judgement.level_label}
          </span>
          <h2 className="font-serif text-[29px] font-medium leading-[1.08] text-ink-900">
            {judgement.title}
          </h2>
        </header>

        <Divider />

        <ReasoningChain chain={judgement.reasoning_chain} />

        <Divider />

        <section aria-labelledby="evidence-heading" className="flex flex-col gap-3">
          <span
            id="evidence-heading"
            className={[
              "text-label",
              judgement.evidence.some((e) => e.conflict) ? "text-orange-600" : "",
            ].join(" ")}
          >
            证据 · {judgement.evidence.length} 来源
            {judgement.evidence.some((e) => e.conflict) && " · ⚠ 结构化冲突"}
          </span>
          {judgement.evidence.map((card) => (
            <EvidenceCardItem key={card.evidence_id} card={card} />
          ))}
        </section>

        {judgement.supplementary_sources.length > 0 && (
          <>
            <Divider />
            <SupplementarySourcesList sources={judgement.supplementary_sources} />
          </>
        )}

        <Divider />

        <LocalQaInput
          briefId={briefId}
          scope="judgement"
          scopeTargetId={judgement.id}
          suggestedQuestions={judgement.suggested_questions}
        />
      </div>
    </div>
  );
}

function CloseRow({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex h-6 items-center justify-end">
      <button
        type="button"
        onClick={onClose}
        aria-label="关闭抽屉"
        className="text-ink-700 hover:text-ink-900"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M18 6L6 18" />
          <path d="M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

function Divider() {
  return <div aria-hidden className="h-px w-full bg-line" />;
}
