"use client";

import * as React from "react";
import type { MacroPulseItem } from "@/lib/types";

const STATUS_DOT: Record<MacroPulseItem["status"], string> = {
  ok: "#10B981",
  watch: "#F59E0B",
  alert: "#EF4444",
};

export function MacroPulseExpanded({ items }: { items: MacroPulseItem[] }) {
  if (items.length === 0) {
    return (
      <p className="px-3 py-3 font-mono text-[11px] text-ink-400">
        暂无宏观脉搏数据
      </p>
    );
  }
  return (
    <ul className="grid grid-cols-1 divide-y divide-line border-t border-line sm:grid-cols-2 sm:divide-y-0">
      {items.map((item, idx) => {
        const isLeftCol = idx % 2 === 0;
        return (
          <li
            key={item.name}
            className={[
              "grid grid-cols-[110px_1fr_auto] items-center gap-3 px-3 py-[10px] sm:py-[8px]",
              !isLeftCol ? "sm:border-l sm:border-line" : "",
              idx >= 2 ? "sm:border-t sm:border-line" : "",
            ].join(" ")}
          >
            <span className="font-mono text-[11px] text-ink-700">{item.name}</span>
            <span className="flex flex-col gap-[2px]">
              <span className="font-mono text-[12px] text-ink-900">{item.value}</span>
              <span className="font-mono text-[10px] text-ink-500">{item.delta}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-ink-500">{item.threshold}</span>
              <span
                aria-label={`status ${item.status}`}
                className="inline-block h-[6px] w-[6px] rounded-full"
                style={{ backgroundColor: STATUS_DOT[item.status] }}
              />
            </span>
          </li>
        );
      })}
    </ul>
  );
}
