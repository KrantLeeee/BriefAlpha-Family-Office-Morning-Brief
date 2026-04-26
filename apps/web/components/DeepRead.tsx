"use client";

import * as React from "react";

import type { Brief, SourceHealth } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

interface Props {
  deepRead: Brief["deep_read"];
  sourceHealth: SourceHealth;
}

const STATUS_LABEL: Record<string, string> = {
  ok: "OK",
  active: "已激活",
  degraded: "Degraded",
  failed: "Failed",
};

const STATUS_COLOR: Record<string, string> = {
  ok: "text-ink-500",
  active: "text-orange-600",
  degraded: "text-warning",
  failed: "text-danger",
};

export function DeepRead({ deepRead, sourceHealth }: Props) {
  const openTrail = useAppStore((s) => s.openEvidenceTrailDrawer);

  return (
    <section aria-labelledby="deepread-heading" className="border-b border-line bg-canvas">
      <div className="mx-auto max-w-[1440px] px-8 py-6">
        <span id="deepread-heading" className="text-label">
          深度阅读
        </span>

        <div className="mt-3 grid h-[172px] grid-cols-2 border-y border-line">
          <div className="flex flex-col gap-2 border-r border-line py-[14px] pr-[18px]">
            <div className="flex items-center justify-between">
              <span className="font-sans text-[15px] font-medium text-ink-900">
                证据轨迹 · 前 3 / {deepRead.evidence_total}
              </span>
            </div>
            {deepRead.evidence_trail.map((row, idx) => (
              <div key={idx} className="flex gap-3 font-mono text-[11px] text-ink-500">
                <span className="w-[120px] shrink-0">{row.timestamp}</span>
                <span>{row.label} ↗</span>
              </div>
            ))}
            <button
              type="button"
              onClick={openTrail}
              className="mt-1 self-start font-mono text-[11px] text-orange-600 hover:underline"
            >
              查看全部 {deepRead.evidence_total} 条原文
            </button>
          </div>

          <div className="flex flex-col gap-[6px] py-[14px] pl-[18px]">
            <div className="flex items-center justify-between">
              <span className="font-sans text-[15px] font-medium text-ink-900">数据源健康</span>
              <span className="font-mono text-[10px] text-ink-300">更新 {sourceHealth.as_of_hkt}</span>
            </div>
            {sourceHealth.rows.map((row) => (
              <div
                key={row.name}
                className="grid grid-cols-[110px_90px_1fr] items-baseline gap-2 font-mono text-[11px]"
              >
                <span className="text-ink-700">{row.name}</span>
                <span className={STATUS_COLOR[row.status] ?? "text-ink-500"}>{STATUS_LABEL[row.status] ?? row.status}</span>
                <span className="text-ink-500">{row.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
