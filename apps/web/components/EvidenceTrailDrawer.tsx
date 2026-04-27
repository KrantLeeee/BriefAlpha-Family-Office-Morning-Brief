"use client";

import * as React from "react";
import { useEffect, useRef, useState } from "react";

import { useAppStore } from "@/store/use-app-store";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface TrailRow {
  timestamp: string;
  label: string;
  source_tier?: string;
  source_link?: string;
  link_kind?: string;
}

interface TrailResponse {
  evidence_trail: TrailRow[];
  evidence_total: number;
}

export function EvidenceTrailDrawer() {
  const open = useAppStore((s) => s.evidenceTrailDrawer.open);
  const close = useAppStore((s) => s.closeEvidenceTrailDrawer);
  const briefId = useAppStore((s) => s.brief?.brief_id ?? "");

  const ref = useRef<HTMLDivElement | null>(null);
  const [filter, setFilter] = useState<string | "all">("all");
  const [data, setData] = useState<TrailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !briefId) return;
    const ctrl = new AbortController();
    fetch(`${API_BASE}/api/evidence/trail?brief_id=${encodeURIComponent(briefId)}`, {
      cache: "no-store",
      signal: ctrl.signal,
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as TrailResponse;
      })
      .then(setData)
      .catch((e) => {
        if ((e as { name?: string }).name === "AbortError") return;
        setError("无法加载证据轨迹");
      });
    return () => ctrl.abort();
  }, [open, briefId]);

  useEffect(() => {
    if (!open) return;
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
  }, [open, close]);

  if (!open) return null;

  const tiers = data
    ? Array.from(
        new Set(
          data.evidence_trail
            .map((r) => r.source_tier)
            .filter((t): t is string => Boolean(t))
        )
      )
    : [];

  const visible = data
    ? data.evidence_trail.filter((r) => filter === "all" || r.source_tier === filter)
    : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="证据轨迹"
      className="fixed inset-y-0 right-0 z-40 w-full max-w-[640px] bg-canvas shadow-drawer sm:w-[560px] md:w-[600px] lg:w-[640px]"
    >
      <div ref={ref} className="flex h-full flex-col gap-4 overflow-y-auto px-[28px] py-[24px]">
        <div className="flex items-center justify-between">
          <span className="font-sans text-[16px] font-medium text-ink-900">
            证据轨迹 {data ? `· ${data.evidence_total} 条` : ""}
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

        {tiers.length > 0 && (
          <div className="flex flex-wrap gap-2 border-y border-line py-3">
            <FilterChip
              label="全部"
              active={filter === "all"}
              onClick={() => setFilter("all")}
            />
            {tiers.map((t) => (
              <FilterChip
                key={t}
                label={t}
                active={filter === t}
                onClick={() => setFilter(t)}
              />
            ))}
          </div>
        )}

        {error && <p className="font-mono text-[11px] text-danger">{error}</p>}

        {!data && !error && (
          <p className="font-mono text-[11px] text-ink-400">加载中…</p>
        )}

        {data && visible.length === 0 && (
          <p className="font-mono text-[11px] text-ink-400">无匹配条目</p>
        )}

        <ul className="flex flex-col divide-y divide-line">
          {visible.map((row, idx) => (
            <li key={idx} className="flex flex-col gap-1 py-3">
              <span className="font-mono text-[11px] text-ink-500">{row.timestamp}</span>
              {row.link_kind === "external" && row.source_link ? (
                <a
                  href={row.source_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-words font-sans text-[13px] text-orange-600 hover:underline"
                >
                  {formatLongDecimals(row.label)} ↗
                </a>
              ) : (
                <span className="break-words font-sans text-[13px] text-ink-700">
                  {formatLongDecimals(row.label)}
                </span>
              )}
              {row.source_tier && (
                <span className="font-mono text-[10px] text-ink-400">{row.source_tier}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function formatLongDecimals(value: string): string {
  return value.replace(/([+-]?\d+\.\d{3,})/g, (match) => {
    const n = Number.parseFloat(match);
    return Number.isFinite(n) ? n.toFixed(2) : match;
  });
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "rounded-chip px-3 py-[4px] font-mono text-[11px] transition-colors",
        active
          ? "border border-orange-600 bg-warningWash text-orange-600"
          : "border border-line bg-canvas text-ink-700 hover:bg-warningWash",
      ].join(" ")}
    >
      {label}
    </button>
  );
}
