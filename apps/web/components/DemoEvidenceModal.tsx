"use client";

import * as React from "react";
import { useEffect, useRef } from "react";
import { useAppStore } from "@/store/use-app-store";

export function DemoEvidenceModal() {
  const state = useAppStore((s) => s.demoEvidenceModal);
  const close = useAppStore((s) => s.closeDemoEvidenceModal);
  const ref = useRef<HTMLDivElement | null>(null);

  // Esc + outside-click close (mirrors DrawerHost convention)
  useEffect(() => {
    if (!state.open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    const onClick = (e: MouseEvent) => {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) close();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [state.open, close]);

  if (!state.open || !state.card) return null;
  const card = state.card;

  const footer =
    state.kind === "internal_research"
      ? "内部研报来源 · 暂未启用浏览器查看（即将上线）"
      : "示例 evidence · 来自 fixture，不连接外网";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="证据详情"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
    >
      <div
        ref={ref}
        className="w-full max-w-[560px] rounded-card bg-canvas p-[28px] shadow-drawer"
      >
        <div className="flex items-start justify-between">
          <span className="font-mono text-[11px] text-ink-700">
            {card.index_label} {card.source_label}
          </span>
          <button
            type="button"
            onClick={close}
            aria-label="关闭"
            className="text-ink-700 hover:text-ink-900"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M18 6L6 18" />
              <path d="M6 6l12 12" />
            </svg>
          </button>
        </div>
        <h3 className="mt-3 font-sans text-[14px] font-medium text-ink-900">{card.title}</h3>
        <p className="mt-3 font-serif text-[16px] leading-[1.45] text-ink-700">{card.quote}</p>
        <p className="mt-6 border-t border-line pt-3 font-mono text-[11px] text-ink-500">
          {footer}
        </p>
      </div>
    </div>
  );
}
