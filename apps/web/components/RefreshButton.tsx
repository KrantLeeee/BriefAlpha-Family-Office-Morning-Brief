"use client";

import * as React from "react";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function RefreshButton() {
  const [pending, startTransition] = useTransition();
  const [lastLabel, setLastLabel] = useState<string | null>(null);
  const router = useRouter();

  const handleClick = () => {
    startTransition(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/data/refresh`, {
          method: "POST",
          cache: "no-store",
        });
        if (!res.ok) {
          setLastLabel("刷新失败");
          return;
        }
        const json = (await res.json()) as { refreshed_at_hkt?: string; status?: string };
        if (json.refreshed_at_hkt) {
          setLastLabel(`已刷新 ${json.refreshed_at_hkt}`);
        } else if (json.status === "queued") {
          setLastLabel("已排队，请稍候");
        } else {
          setLastLabel("已刷新");
        }
        router.refresh();
      } catch {
        setLastLabel("刷新失败");
      }
    });
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      className="inline-flex h-[28px] items-center gap-[6px] rounded-chip border border-line bg-canvas px-[10px] font-mono text-[11px] font-medium text-ink-700 hover:bg-warningWash transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      aria-label="刷新数据"
    >
      <RefreshIcon />
      {pending ? "刷新中..." : lastLabel ?? "刷新数据"}
    </button>
  );
}

function RefreshIcon() {
  return (
    <svg
      aria-hidden
      width="11"
      height="11"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 8a6 6 0 1 1-1.76-4.24" />
      <path d="M14 2v4h-4" />
    </svg>
  );
}
