"use client";

import * as React from "react";
import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { ReviewMeta } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const REASON_LABELS: Record<ReviewMeta["reason"], string> = {
  source_conflict: "来源对关键数字分歧",
  portfolio_uncertain: "组合关联不确定",
  threshold_breach: "数据穿越人工阈值",
  data_gap: "数据缺口或质量问题",
};

export function ReviewModal() {
  const state = useAppStore((s) => s.reviewModal);
  const close = useAppStore((s) => s.closeReviewModal);
  const judgement = useAppStore((s) =>
    state.judgementId ? s.brief?.judgements.find((j) => j.id === state.judgementId) : undefined
  );
  const briefId = useAppStore((s) => s.brief?.brief_id ?? "");

  const ref = useRef<HTMLDivElement | null>(null);
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

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

  if (!state.open || !judgement) return null;

  const review = judgement.review;
  const isReviewed = review?.status === "reviewed";

  const submit = (nextStatus: "open" | "reviewed") => {
    startTransition(async () => {
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/review/${judgement.id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            brief_id: briefId,
            status: nextStatus,
            note: review?.note ?? "",
          }),
        });
        if (!res.ok) {
          setError(`服务器返回 ${res.status}`);
          return;
        }
        close();
        router.refresh();
      } catch {
        setError("无法连接服务");
      }
    });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`研判 ${judgement.rank} 复核`}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
    >
      <div
        ref={ref}
        className="w-full max-w-[520px] rounded-card bg-canvas p-[28px] shadow-drawer"
      >
        <div className="flex items-start justify-between gap-3">
          <span className="font-mono text-[11px] text-orange-600">
            研判 {String(judgement.rank).padStart(2, "0")} · 复核详情
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

        <h3 className="mt-3 font-sans text-[14px] font-medium text-ink-900">{judgement.title}</h3>

        {review ? (
          <>
            <dl className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
              <div>
                <dt className="text-label">触发原因</dt>
                <dd className="mt-1 font-sans text-[13px] text-ink-700">
                  {REASON_LABELS[review.reason]}
                </dd>
              </div>
              {review.note && (
                <div>
                  <dt className="text-label">说明</dt>
                  <dd className="mt-1 font-serif text-[14px] leading-[1.45] text-ink-700">
                    {review.note}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-label">当前状态</dt>
                <dd className="mt-1 font-mono text-[12px] text-ink-700">
                  {isReviewed ? `已审阅 · ${review.reviewed_at ?? ""}` : "待审阅"}
                </dd>
              </div>
            </dl>

            {error && <p className="mt-3 font-mono text-[11px] text-danger">{error}</p>}

            <div className="mt-6 flex justify-end gap-2">
              {isReviewed ? (
                <button
                  type="button"
                  onClick={() => submit("open")}
                  disabled={pending}
                  className="rounded-chip border border-line bg-canvas px-3 py-[6px] font-mono text-[11px] text-ink-700 hover:bg-warningWash disabled:opacity-50"
                >
                  {pending ? "标记中…" : "标记为待审"}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => submit("reviewed")}
                  disabled={pending}
                  className="rounded-chip bg-orange-600 px-3 py-[6px] font-mono text-[11px] font-medium text-canvas hover:bg-orange-700 disabled:opacity-50"
                >
                  {pending ? "标记中…" : "我已审阅"}
                </button>
              )}
            </div>
          </>
        ) : (
          <p className="mt-4 font-sans text-[13px] text-ink-500">此研判无需人工复核。</p>
        )}
      </div>
    </div>
  );
}
