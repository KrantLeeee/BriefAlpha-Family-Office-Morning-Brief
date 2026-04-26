"use client";

import * as React from "react";
import { useState } from "react";
import type { MacroPulseItem } from "@/lib/types";
import { MacroPulseExpanded } from "./MacroPulseExpanded";

interface Props {
  label: string;
  expandLabel: string;
  items: MacroPulseItem[];
}

export function MacroPulseCollapsed({ label, expandLabel, items }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b" style={{ borderColor: "#d7dce2" }}>
      <button
        type="button"
        className="flex w-full items-center justify-between py-3"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <Chevron open={open} />
          <span
            className="font-sans text-[13px] font-medium text-ink-700"
            style={{ fontFamily: "Montserrat, var(--font-inter)" }}
          >
            {label}
          </span>
        </div>
        <span className="font-mono text-[11px] text-ink-700">
          {open ? "收起" : expandLabel}
        </span>
      </button>
      {open && <MacroPulseExpanded items={items} />}
    </div>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#374151"
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
