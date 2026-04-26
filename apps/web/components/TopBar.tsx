"use client";

import { useAppStore } from "@/store/use-app-store";
import { RefreshButton } from "./RefreshButton";

interface Props {
  delivery: string;
  freezeWindow: string;
  anonymized: boolean;
  auditMode: "demo" | "compliance";
  stale: boolean;
  degraded: boolean;
}

export function TopBar({ delivery, freezeWindow, anonymized, auditMode, stale, degraded }: Props) {
  const openUpload = useAppStore((s) => s.openUpload);

  return (
    <header className="border-b border-line bg-canvas">
      <div className="mx-auto flex h-[62px] max-w-[1440px] items-center justify-between px-8">
        <div className="flex items-center gap-3">
          <span className="font-serif text-[17px] font-medium text-ink-900">BriefAlpha</span>
          <span aria-hidden className="h-4 w-px bg-line" />
          <span className="text-[11px] text-ink-400">组合感知晨报</span>
          {(stale || degraded) && (
            <span className="ml-3 inline-flex items-center gap-1 rounded-chip border border-orange-200 bg-warningWash px-2 py-[2px] font-mono text-[10px] font-medium uppercase tracking-wide text-orange-600">
              {stale ? "stale brief · 上一日数据" : "数据源 degraded"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-[10px]">
          {anonymized && (
            <span className="font-mono text-[11px] text-ink-700" aria-label="数据已脱敏">
              已脱敏
            </span>
          )}
          <span className="font-mono text-[11px] text-ink-700" aria-label={`审计模式 ${auditMode}`}>
            已审计
          </span>
          <span className="font-mono text-[11px] text-ink-500" aria-label="brief 时间窗口">
            更新 {delivery} HKT · {freezeWindow}
          </span>

          <RefreshButton />

          <button
            type="button"
            onClick={() => openUpload()}
            className="inline-flex h-[28px] items-center gap-[6px] rounded-chip bg-ink-900 px-[10px] font-mono text-[11px] font-medium text-canvas hover:bg-ink-700 transition-colors"
          >
            <UploadIcon />
            上传研报
          </button>
        </div>
      </div>
    </header>
  );
}

function UploadIcon() {
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
      <path d="M8 12V3" />
      <path d="M4 7l4-4 4 4" />
      <path d="M2.5 13.5h11" />
    </svg>
  );
}
