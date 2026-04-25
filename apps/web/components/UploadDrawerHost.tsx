"use client";

import { useEffect, useRef, useState } from "react";

import { getParseReport, uploadResearch } from "@/lib/api";
import { demoParseReport } from "@/lib/fixtures";
import type { ParseReport } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

/**
 * Upload research drawer — frame I4Qnp.
 *
 * Layout (top → bottom):
 *   1. Header (UPLOAD RESEARCH + close)
 *   2. Active file's parse_report panel (filename, status, consent, parsing
 *      summary, tickers in / out portfolio, low-confidence chunks)
 *   3. Actions row (重新解析 / 删除文件 / + 添加文件)
 *   4. **Uploaded files list** — sits below the actions row so the file
 *      cards appear right next to the "+ 添加文件" CTA the user just
 *      clicked. Click a file to make it the active report shown above.
 */

const MAX_ACTIVE = 5;

const STAGE_LABEL: Record<string, string> = {
  extraction: "文本抽取",
  ocr_fallback: "OCR 兜底",
  vision_caption: "图像识别",
  chunking: "切片",
  ticker_detection: "标的识别",
  fts_dedupe: "去重",
  merge_pool: "合入证据池",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "OK",
  partial: "部分",
  failed: "失败",
  consent_required: "未授权",
};

const STATUS_DOT: Record<string, string> = {
  ok: "bg-success",
  partial: "bg-warning",
  failed: "bg-danger",
  consent_required: "bg-orange-600",
};

interface ActiveFile {
  file_id: string;
  filename: string;
  report: ParseReport | null;
  loading: boolean;
}

export function UploadDrawerHost() {
  const ref = useRef<HTMLDivElement | null>(null);
  const drawer = useAppStore((s) => s.uploadDrawer);
  const close = useAppStore((s) => s.closeUpload);

  const [files, setFiles] = useState<ActiveFile[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [consent, setConsent] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [bootstrapped, setBootstrapped] = useState(false);

  useEffect(() => {
    if (!drawer.open || bootstrapped) return;
    if (drawer.fileId) {
      setFiles([{ file_id: drawer.fileId, filename: "正在加载…", report: null, loading: true }]);
      setActiveId(drawer.fileId);
      void hydrate(drawer.fileId);
    } else {
      setFiles([
        { file_id: "demo", filename: demoParseReport.filename, report: demoParseReport, loading: false },
      ]);
      setActiveId("demo");
    }
    setBootstrapped(true);
  }, [drawer.open, drawer.fileId, bootstrapped]);

  useEffect(() => {
    if (drawer.open) return;
    setBootstrapped(false);
    setFiles([]);
    setActiveId(null);
    setUploading(false);
  }, [drawer.open]);

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

  async function hydrate(file_id: string): Promise<void> {
    try {
      const r = await getParseReport(file_id);
      setFiles((prev) =>
        prev.map((f) => (f.file_id === file_id ? { ...f, filename: r.filename, report: r, loading: false } : f))
      );
    } catch {
      setFiles((prev) =>
        prev.map((f) =>
          f.file_id === file_id
            ? { ...f, report: demoParseReport, filename: demoParseReport.filename, loading: false }
            : f
        )
      );
    }
  }

  async function handleAddFiles(selected: FileList | null) {
    if (!selected || selected.length === 0) return;
    const realCount = files.filter((f) => !isDemo(f.file_id)).length;
    const remaining = MAX_ACTIVE - realCount;
    if (remaining <= 0) return;
    const arr = Array.from(selected).slice(0, remaining);
    setUploading(true);
    try {
      for (const f of arr) {
        const fd = new FormData();
        fd.set("file", f);
        fd.set("consent_state", consent ? "granted" : "not_granted");
        fd.set("policy_version", "2026-04-25");
        try {
          const res = await uploadResearch(fd);
          const placeholder: ActiveFile = {
            file_id: res.file_id,
            filename: f.name,
            report: null,
            loading: true,
          };
          setFiles((prev) => [...prev.filter((x) => !isDemo(x.file_id)), placeholder]);
          setActiveId(res.file_id);
          await hydrate(res.file_id);
        } catch {
          const demoCopy: ActiveFile = {
            file_id: `demo-${Date.now()}-${f.name}`,
            filename: f.name,
            report: { ...demoParseReport, filename: f.name },
            loading: false,
          };
          setFiles((prev) => [...prev.filter((x) => !isDemo(x.file_id)), demoCopy]);
          setActiveId(demoCopy.file_id);
        }
      }
    } finally {
      setUploading(false);
    }
  }

  const active = files.find((f) => f.file_id === activeId) ?? files[0];
  const realCount = files.filter((f) => !isDemo(f.file_id)).length;
  const remainingSlots = Math.max(0, MAX_ACTIVE - realCount);
  // Only render the file list once the user has more than one file (or has
  // uploaded a real file) — a single demo placeholder doesn't need a list.
  const showFileList = files.length > 1;

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
          <span className="font-mono text-[11px] font-medium text-orange-600">
            UPLOAD RESEARCH
          </span>
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

        {active?.report && (
          <>
            <h2 className="font-serif text-[24px] font-medium leading-[1.15] text-ink-900">
              {active.report.filename}
            </h2>

            <div className="flex flex-wrap items-center gap-[10px]">
              <span className="rounded-chip bg-success px-2 py-[3px] font-mono text-[10px] text-canvas">
                Parsed
              </span>
              <span className="font-mono text-[11px] text-ink-500">
                {active.report.size_label} · {active.report.page_count} pages · uploaded {active.report.uploaded_at_hkt} HKT · {active.report.parse_seconds}s parse time
              </span>
            </div>

            <ConsentBox consent={consent} setConsent={setConsent} />

            <Divider />

            <section aria-labelledby="ps-heading" className="flex flex-col gap-[10px]">
              <span id="ps-heading" className="text-label">
                PARSING SUMMARY
              </span>
              <ul className="flex flex-col gap-[6px]">
                {active.report.stages.map((stage) => (
                  <li
                    key={stage.name}
                    className="grid grid-cols-[120px_18px_60px_1fr] items-center gap-2 font-mono text-[11px]"
                  >
                    <span className="text-ink-700">{STAGE_LABEL[stage.name] ?? stage.name}</span>
                    <span aria-hidden className={`h-2 w-2 rounded-full ${STATUS_DOT[stage.status] ?? "bg-ink-300"}`} />
                    <span className={stage.status === "ok" ? "text-success" : "text-orange-600"}>
                      {STATUS_LABEL[stage.status] ?? stage.status}
                    </span>
                    <span className="text-ink-500">{stage.detail}</span>
                  </li>
                ))}
              </ul>
            </section>

            <Divider />

            <section className="flex flex-col gap-[10px]">
              <span className="text-label">识别到的标的</span>
              <div className="flex flex-wrap gap-2">
                {active.report.tickers_in_universe.map((t) => (
                  <span
                    key={t}
                    className="rounded-chip bg-warningWash px-2 py-[2px] font-mono text-[11px] text-orange-600"
                  >
                    {t} · 组合内
                  </span>
                ))}
                {active.report.tickers_external.map((t) => (
                  <span
                    key={t}
                    className="rounded-chip bg-surface px-2 py-[2px] font-mono text-[11px] text-ink-500"
                  >
                    {t} · 组合外
                  </span>
                ))}
              </div>
              <span className="font-mono text-[10px] text-ink-400">
                组合外标的入证据池但带 warning，不会触发数据采集扩张。
              </span>
            </section>

            <Divider />

            <section className="flex flex-col gap-[10px]">
              <span className="text-label">低置信度片段</span>
              {active.report.low_confidence_chunks.length === 0 ? (
                <span className="font-mono text-[11px] text-ink-500">无低置信度片段。</span>
              ) : (
                active.report.low_confidence_chunks.map((c) => (
                  <article
                    key={c.chunk_id}
                    className="flex flex-col gap-2 rounded-card bg-surface p-[14px]"
                  >
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
              <span className="text-label">操作</span>
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
                <AddMoreFilesButton
                  remainingSlots={remainingSlots}
                  uploading={uploading}
                  onAdd={handleAddFiles}
                />
              </div>

              {showFileList && (
                <FileList
                  files={files}
                  activeId={activeId}
                  onSelect={setActiveId}
                />
              )}

              <p className="font-sans text-[11px] leading-[1.5] text-ink-400">
                重新解析仅运行 pipeline 第 4 阶段及之后，不会重新拉取行情 / 新闻 / 官方公告。目标 ≤ 30 秒。
              </p>
              <p className="font-mono text-[10px] text-ink-400">
                同时可保留 {MAX_ACTIVE} 份；当前已激活 {realCount} 份。
              </p>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function FileList({
  files,
  activeId,
  onSelect,
}: {
  files: ActiveFile[];
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {files.map((f) => {
        const active = f.file_id === activeId;
        return (
          <button
            key={f.file_id}
            type="button"
            onClick={() => onSelect(f.file_id)}
            className={[
              "flex items-center justify-start truncate rounded-chip px-3 py-[6px] text-left font-mono text-[11px] transition-colors",
              active
                ? "bg-ink-900 text-canvas"
                : "bg-surface text-ink-700 hover:text-ink-900",
            ].join(" ")}
            title={f.filename}
          >
            <span className="truncate">
              {truncate(f.filename, 28)}
              {f.loading && " · 解析中"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function AddMoreFilesButton({
  remainingSlots,
  uploading,
  onAdd,
}: {
  remainingSlots: number;
  uploading: boolean;
  onAdd: (files: FileList | null) => void;
}) {
  const disabled = remainingSlots <= 0 || uploading;
  return (
    <label
      className={[
        "inline-flex cursor-pointer items-center gap-2 rounded-chip border border-dashed px-3 py-[6px] font-mono text-[11px]",
        disabled
          ? "cursor-not-allowed border-ink-300 text-ink-300"
          : "border-orange-600 text-orange-600 hover:bg-warningWash",
      ].join(" ")}
    >
      <span aria-hidden>＋</span>
      <span>{uploading ? "解析中…" : `添加文件（剩余 ${remainingSlots}）`}</span>
      <input
        type="file"
        accept="application/pdf"
        multiple
        disabled={disabled}
        onChange={(e) => onAdd(e.target.files)}
        className="sr-only"
      />
    </label>
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
        <span className="font-sans text-[13px] font-medium text-ink-900">
          允许图像识别用于补充图表说明
        </span>
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

function Divider() {
  return <div aria-hidden className="h-px w-full bg-line" />;
}

function isDemo(id: string): boolean {
  return id === "demo" || id.startsWith("demo-");
}

function truncate(s: string, max: number) {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
