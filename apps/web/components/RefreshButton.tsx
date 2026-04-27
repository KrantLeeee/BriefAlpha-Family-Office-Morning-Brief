"use client";

import * as React from "react";
import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { getBriefRefreshStatus, updateTodayBrief } from "@/lib/api";

const POLL_MS = 3000;
const POLL_TIMEOUT_MS = 10 * 60_000;

export function RefreshButton() {
  const [pending, startTransition] = useTransition();
  const [lastLabel, setLastLabel] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const startedAt = useRef<number | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!generating) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      const start = startedAt.current ?? Date.now();
      const elapsed = Date.now() - start;
      setProgress(Math.min(92, 12 + Math.floor((elapsed / POLL_TIMEOUT_MS) * 80)));
      try {
        const status = await getBriefRefreshStatus();
        if (cancelled) return;
        if (status.status === "ready") {
          setGenerating(false);
          setProgress(100);
          setLastLabel("已生成");
          router.refresh();
          return;
        }
        if (status.status === "error") {
          setGenerating(false);
          setLastLabel("生成失败");
          return;
        }
      } catch {
        if (!cancelled) setLastLabel("状态读取失败");
      }
      if (elapsed > POLL_TIMEOUT_MS) {
        setGenerating(false);
        setLastLabel("仍在生成");
        return;
      }
      timer = setTimeout(poll, POLL_MS);
    }

    timer = setTimeout(poll, POLL_MS);
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [generating, router]);

  const handleClick = () => {
    startTransition(async () => {
      try {
        const json = await updateTodayBrief();
        if (json.refreshed_at_hkt) {
          setLastLabel(`已更新 ${json.refreshed_at_hkt}`);
        } else if (json.status === "queued") {
          startedAt.current = Date.now();
          setProgress(8);
          setGenerating(true);
          setLastLabel("生成中");
        } else {
          setLastLabel("已更新");
        }
        router.refresh();
      } catch {
        setLastLabel("更新失败");
      }
    });
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending || generating}
      className="relative inline-flex h-[28px] overflow-hidden rounded-chip border border-line bg-canvas px-[10px] font-mono text-[11px] font-medium text-ink-700 transition-colors hover:bg-warningWash disabled:cursor-not-allowed disabled:opacity-80"
      aria-label="更新今日简报"
    >
      {generating && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 bg-warningWash transition-[width]"
          style={{ width: `${progress}%` }}
        />
      )}
      <span className="relative inline-flex items-center gap-[6px]">
        <RefreshIcon />
        {pending ? "更新中..." : generating ? "生成中..." : lastLabel ?? "更新今日简报"}
      </span>
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
