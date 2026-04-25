"use client";

import { useEffect, useRef, useState } from "react";

import { getParseReport, uploadResearch } from "@/lib/api";
import { demoParseReport } from "@/lib/fixtures";
import type { ParseReport } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

const STAGE_LABEL: Record<string, string> = {
  extraction: "Extraction",
  ocr_fallback: "OCR fallback",
  vision_caption: "Vision caption",
  chunking: "Chunking",
  ticker_detection: "Ticker detect",
  fts_dedupe: "FTS dedupe",
  merge_pool: "Merge to pool",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-success",
  partial: "bg-warning",
  failed: "bg-danger",
  consent_required: "bg-orange-600",
};

export function UploadDrawerHost() {
  const ref = useRef<HTMLDivElement | null>(null);
  const drawer = useAppStore((s) => s.uploadDrawer);
  const close = useAppStore((s) => s.closeUpload);
  const [report, setReport] = useState<ParseReport | null>(null);
  const [consent, setConsent] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!drawer.open) return;
    if (!drawer.fileId) {
      // Show the demo parse report so the layout can be reviewed
      // even before a real file is uploaded.
      setReport(demoParseReport);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await getParseReport(drawer.fileId!);
        if (!cancelled) setReport(r);
      } catch {
        if (!cancelled) setReport(demoParseReport);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [drawer.open, drawer.fileId]);

  useEffect(() => {
    if (!drawer.open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    function onClick(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) close();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [drawer.open, close]);

  if (!drawer.open) return null;

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.set("file", f);
      fd.set("consent_state", consent ? "granted" : "not_granted");
      fd.set("policy_version", "2026-04-25");
      const res = await uploadResearch(fd);
      const r = await getParseReport(res.file_id);
      setReport(r);
    } catch {
      // Demo: keep showing the fixture so the layout is testable
      setReport(demoParseReport);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-label="上传研报"
      className="fixed inset-y-0 right-0 z-50 w-full max-w-[580px] bg-canvas shadow-drawer"
    >
      <div className="flex h-full flex-col gap-[22px] overflow-y-auto px-[30px] py-[30px]">
        <header className="flex items-center justify-between">
          <span className="font-mono text-[11px] font-medium text-orange-600">UPLOAD RESEARCH</span>
          <button
            type="button"
            onClick={close}
            aria-label="关闭上传抽屉"
            className="text-ink-700 hover:text-ink-900"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M18 6L6 18" />
              <path d="M6 6l12 12" />
            </svg>
          </button>
        </header>

        {report && (
          <>
            <h2 className="font-serif text-[24px] font-medium leading-[1.15] text-ink-900">
              {report.filename}
            </h2>

            <div className="flex flex-wrap items-center gap-[10px]">
              <span className="rounded-chip bg-success px-2 py-[3px] font-mono text-[10px] text-canvas">
                Parsed
              </span>
              <span className="font-mono text-[11px] text-ink-500">
                {report.size_label} · {report.page_count} pages · uploaded {report.uploaded_at_hkt} HKT · {report.parse_seconds}s parse time
              </span>
            </div>
          </>
        )}

        <ConsentBox consent={consent} setConsent={setConsent} />

        <Divider />

        <UploadField onChange={handleUpload} uploading={uploading} />

        {report && (
          <>
            <Divider />

            <section aria-labelledby="ps-heading" className="flex flex-col gap-[10px]">
              <span id="ps-heading" className="text-label">
                PARSING SUMMARY
              </span>
              <ul className="flex flex-col gap-[6px]">
                {report.stages.map((stage) => (
                  <li
                    key={stage.name}
                    className="grid grid-cols-[140px_18px_1fr] items-center gap-2 font-mono text-[11px] text-ink-500"
                  >
                    <span className="text-ink-700">{STAGE_LABEL[stage.name] ?? stage.name}</span>
                    <span aria-hidden className={`h-2 w-2 rounded-full ${STATUS_DOT[stage.status] ?? "bg-ink-300"}`} />
                    <span>{stage.detail}</span>
                  </li>
                ))}
              </ul>
            </section>

            <Divider />

            <section className="flex flex-col gap-[10px]">
              <span className="text-label">TICKERS DETECTED</span>
              <div className="flex flex-wrap gap-2">
                {report.tickers_in_universe.map((t) => (
                  <span key={t} className="rounded-chip bg-warningWash px-2 py-[2px] font-mono text-[11px] text-orange-600">
                    {t}（在 universe）
                  </span>
                ))}
                {report.tickers_external.map((t) => (
                  <span key={t} className="rounded-chip border border-line bg-surface px-2 py-[2px] font-mono text-[11px] text-ink-500">
                    {t}（external）
                  </span>
                ))}
              </div>
            </section>

            <Divider />

            <section className="flex flex-col gap-[10px]">
              <span className="text-label">LOW-CONFIDENCE CHUNKS</span>
              {report.low_confidence_chunks.length === 0 ? (
                <span className="font-mono text-[11px] text-ink-500">无低置信度片段。</span>
              ) : (
                report.low_confidence_chunks.map((c) => (
                  <article key={c.chunk_id} className="flex flex-col gap-2 rounded-card border border-line bg-surface p-[14px]">
                    <span className="font-mono text-[11px] text-ink-700">
                      第 {c.page} 页 · {c.reason}
                    </span>
                    <span className="font-sans text-[13px] text-ink-500">{c.preview}</span>
                  </article>
                ))
              )}
            </section>

            <Divider />

            <section className="flex flex-col gap-[10px]">
              <span className="text-label">ACTIONS</span>
              <div className="flex flex-wrap gap-[10px]">
                <button
                  type="button"
                  className="rounded-chip border border-orange-600 bg-orange-600 px-3 py-[6px] font-mono text-[11px] text-canvas hover:opacity-90"
                >
                  重新解析（≤ 30s）
                </button>
                <button
                  type="button"
                  className="rounded-chip border border-line bg-surface px-3 py-[6px] font-mono text-[11px] text-ink-700 hover:bg-canvas"
                >
                  删除文件
                </button>
              </div>
              <p className="font-sans text-[11px] leading-[1.5] text-ink-400">
                Re-analyze runs pipeline stage_4 onward only — no re-collection of market / news /
                official feeds. Target ≤ 30s.
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function ConsentBox({ consent, setConsent }: { consent: boolean; setConsent: (v: boolean) => void }) {
  return (
    <div className="flex gap-3 rounded-card border border-orange-200 bg-consentWash p-[14px]">
      <button
        type="button"
        role="checkbox"
        aria-checked={consent}
        onClick={() => setConsent(!consent)}
        className={[
          "mt-[1px] flex h-[14px] w-[14px] items-center justify-center rounded-chip",
          consent ? "bg-orange-600 text-canvas" : "border border-orange-600 bg-canvas",
        ].join(" ")}
      >
        {consent && (
          <svg width="10" height="10" viewBox="0 0 16 16" stroke="currentColor" strokeWidth="2" fill="none" aria-hidden>
            <path d="M3 8l4 4 6-8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
      <div className="flex flex-col gap-1 text-ink-700">
        <span className="font-sans text-[13px] font-medium text-ink-900">允许图像识别用于补充图表说明</span>
        <span className="font-mono text-[11px] text-ink-500">
          仅用于本次研报；vision 调用不携带身份字段。可在右上角更改默认选项。
        </span>
        <a href="#" className="font-mono text-[11px] text-orange-600 hover:underline">
          Change processing preference
        </a>
      </div>
    </div>
  );
}

function UploadField({
  onChange,
  uploading,
}: {
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  uploading: boolean;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-label">UPLOAD FILE</span>
      <span className="flex h-[42px] items-center justify-between rounded-chip border border-dashed border-orange-600 bg-canvas px-3 font-mono text-[11px] text-ink-700">
        <input
          type="file"
          accept="application/pdf"
          onChange={onChange}
          className="font-mono text-[11px] text-ink-700"
          disabled={uploading}
        />
        {uploading && <span className="text-orange-600">解析中…</span>}
      </span>
      <span className="font-mono text-[10px] text-ink-400">PDF · ≤ 20MB · 同时活跃 ≤ 5 份</span>
    </label>
  );
}

function Divider() {
  return <div aria-hidden className="h-px w-full bg-line" />;
}
